"""
Analytics endpoints for dashboard charts and metrics
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from datetime import datetime, timedelta
from typing import Dict, List, Any
import logging
import subprocess
import tempfile
import os
from collections import defaultdict

from app.core.database import get_db
from app.models import CodeCollection, Codebundle

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/tasks-by-week")
async def get_tasks_by_week(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Get historical task count by week using git commit history.
    
    This analyzes when codebundles were first introduced (via git history)
    to build a historical chart showing task growth over time.
    
    Returns weekly aggregates starting from the first codebundle commit.
    """
    try:
        logger.info("Generating tasks-by-week analytics from git history")
        
        # Get all active codebundles with their collections
        codebundles = db.query(Codebundle).join(CodeCollection).filter(
            Codebundle.is_active == True,
            CodeCollection.is_active == True
        ).all()
        
        logger.info(f"Analyzing {len(codebundles)} codebundles")
        
        # Group by collection to minimize git operations
        collections_map = {}
        for cb in codebundles:
            if cb.codecollection_id not in collections_map:
                collections_map[cb.codecollection_id] = {
                    'collection': cb.codecollection,
                    'codebundles': []
                }
            collections_map[cb.codecollection_id]['codebundles'].append(cb)
        
        # Extract first-commit dates from git history
        codebundle_dates = []
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            for coll_id, data in collections_map.items():
                collection = data['collection']
                codebundles_list = data['codebundles']
                
                try:
                    # Clone repository (shallow clone for speed)
                    repo_path = os.path.join(tmp_dir, collection.slug)
                    logger.info(f"Cloning {collection.git_url} for git history analysis")
                    
                    # Clone with full history to get accurate first commit dates
                    subprocess.run(
                        ['git', 'clone', collection.git_url, repo_path],
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    
                    # For each codebundle, get the first commit date
                    for cb in codebundles_list:
                        # Find when this codebundle directory was first added
                        bundle_path = f"codebundles/{cb.slug}"
                        
                        result = subprocess.run(
                            ['git', 'log', '--format=%ct', '--diff-filter=A', '--', bundle_path],
                            cwd=repo_path,
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        
                        if result.returncode == 0 and result.stdout.strip():
                            # Get the oldest (last) commit timestamp
                            timestamps = result.stdout.strip().split('\n')
                            if timestamps:
                                # Last timestamp is the first commit (oldest)
                                first_commit = int(timestamps[-1])
                                first_date = datetime.fromtimestamp(first_commit)
                                
                                # Count tasks in this codebundle
                                task_count = (cb.task_count or 0) + (cb.sli_count or 0)
                                
                                codebundle_dates.append({
                                    'date': first_date,
                                    'task_count': task_count,
                                    'codebundle': cb.slug,
                                    'collection': collection.slug
                                })
                        else:
                            # Fallback to git_updated_at or created_at
                            fallback_date = cb.git_updated_at or cb.created_at
                            task_count = (cb.task_count or 0) + (cb.sli_count or 0)
                            codebundle_dates.append({
                                'date': fallback_date,
                                'task_count': task_count,
                                'codebundle': cb.slug,
                                'collection': collection.slug
                            })
                
                except Exception as e:
                    logger.error(f"Error analyzing git history for {collection.slug}: {e}")
                    # Fallback: use existing dates from database
                    for cb in codebundles_list:
                        fallback_date = cb.git_updated_at or cb.created_at
                        task_count = (cb.task_count or 0) + (cb.sli_count or 0)
                        codebundle_dates.append({
                            'date': fallback_date,
                            'task_count': task_count,
                            'codebundle': cb.slug,
                            'collection': collection.slug
                        })
        
        # Sort by date
        codebundle_dates.sort(key=lambda x: x['date'])
        
        if not codebundle_dates:
            return {
                "weeks": [],
                "cumulative": [],
                "total_tasks": 0,
                "message": "No codebundle data available"
            }
        
        # Find the earliest date (start of week)
        earliest = codebundle_dates[0]['date']
        latest = datetime.now()
        
        # Round to start of week (Monday)
        start_week = earliest - timedelta(days=earliest.weekday())
        
        # Build weekly aggregates
        weekly_data = defaultdict(int)
        
        for entry in codebundle_dates:
            # Get the week start date
            entry_date = entry['date']
            week_start = entry_date - timedelta(days=entry_date.weekday())
            week_key = week_start.strftime('%Y-%m-%d')
            weekly_data[week_key] += entry['task_count']
        
        # Generate cumulative counts week by week
        weeks = []
        cumulative = []
        running_total = 0
        
        current_week = start_week
        while current_week <= latest:
            week_key = current_week.strftime('%Y-%m-%d')
            
            # Add tasks introduced this week
            running_total += weekly_data.get(week_key, 0)
            
            weeks.append(week_key)
            cumulative.append(running_total)
            
            current_week += timedelta(days=7)
        
        logger.info(f"Generated {len(weeks)} weeks of data, total tasks: {running_total}")
        
        return {
            "weeks": weeks,
            "cumulative": cumulative,
            "total_tasks": running_total,
            "earliest_date": earliest.isoformat(),
            "latest_date": latest.isoformat(),
            "message": f"Analyzed {len(codebundle_dates)} codebundles from git history"
        }
        
    except Exception as e:
        logger.error(f"Error generating tasks-by-week: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks-by-week-cached")
async def get_tasks_by_week_cached(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Faster version: uses database dates (git_updated_at) without cloning repos.
    Shows last 18 months of data.
    """
    try:
        logger.info("Generating tasks-by-week from database dates (last 18 months)")
        
        # Calculate date 18 months ago
        eighteen_months_ago = datetime.now() - timedelta(days=18*30)  # Approximate 18 months
        
        # Get all active codebundles with dates
        codebundles = db.query(
            Codebundle.git_updated_at,
            Codebundle.created_at,
            Codebundle.task_count,
            Codebundle.sli_count
        ).filter(
            Codebundle.is_active == True
        ).all()
        
        # Build date list - include all codebundles for cumulative count
        codebundle_dates = []
        for cb in codebundles:
            date = cb.git_updated_at or cb.created_at
            task_count = (cb.task_count or 0) + (cb.sli_count or 0)
            codebundle_dates.append({
                'date': date,
                'task_count': task_count
            })
        
        # Sort by date
        codebundle_dates.sort(key=lambda x: x['date'])
        
        if not codebundle_dates:
            return {
                "weeks": [],
                "cumulative": [],
                "total_tasks": 0
            }
        
        # Build weekly aggregates for all time
        weekly_data = defaultdict(int)
        for entry in codebundle_dates:
            entry_date = entry['date']
            week_start = entry_date - timedelta(days=entry_date.weekday())
            week_key = week_start.strftime('%Y-%m-%d')
            weekly_data[week_key] += entry['task_count']
        
        # Generate cumulative counts for last 18 months only
        weeks = []
        cumulative = []
        
        # Start from 18 months ago, but calculate cumulative from beginning
        start_week = eighteen_months_ago - timedelta(days=eighteen_months_ago.weekday())
        latest = datetime.now()
        
        # Calculate total tasks before 18 months ago
        running_total = 0
        temp_week = codebundle_dates[0]['date'] - timedelta(days=codebundle_dates[0]['date'].weekday())
        while temp_week < start_week:
            week_key = temp_week.strftime('%Y-%m-%d')
            running_total += weekly_data.get(week_key, 0)
            temp_week += timedelta(days=7)
        
        # Now generate the visible data (last 18 months)
        current_week = start_week
        while current_week <= latest:
            week_key = current_week.strftime('%Y-%m-%d')
            running_total += weekly_data.get(week_key, 0)
            
            weeks.append(week_key)
            cumulative.append(running_total)
            
            current_week += timedelta(days=7)
        
        return {
            "weeks": weeks,
            "cumulative": cumulative,
            "total_tasks": running_total
        }
        
    except Exception as e:
        logger.error(f"Error generating tasks-by-week-cached: {e}")
        raise HTTPException(status_code=500, detail=str(e))
