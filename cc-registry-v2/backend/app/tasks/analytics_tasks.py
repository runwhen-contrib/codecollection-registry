"""
Analytics computation tasks
"""
import logging
import tempfile
import os
import subprocess
import time
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, Any

from app.tasks.celery_app import celery_app
from app.core.database import SessionLocal
from app.models import CodeCollection, Codebundle, TaskGrowthMetric

logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def compute_task_growth_analytics(self):
    """
    Compute task growth analytics using git history.
    
    This task:
    1. Clones all codecollection repositories
    2. Analyzes git history to find when each codebundle folder first appeared
    3. Calculates monthly cumulative task counts for last 18 months
    4. Stores results in task_growth_metrics table
    
    Runs as background job (scheduled via Celery Beat).
    """
    db = SessionLocal()
    start_time = time.time()
    
    try:
        logger.info(f"Starting task growth analytics computation (task {self.request.id})")
        
        # Calculate date 18 months ago
        eighteen_months_ago = datetime.now() - timedelta(days=18*30)
        
        # Get all active codebundles with their collections
        codebundles = db.query(Codebundle).join(CodeCollection).filter(
            Codebundle.is_active == True,
            CodeCollection.is_active == True
        ).all()
        
        logger.info(f"Analyzing {len(codebundles)} codebundles for first-commit dates")
        
        # Group by collection to minimize git operations
        collections_map = {}
        for cb in codebundles:
            if cb.codecollection_id not in collections_map:
                collections_map[cb.codecollection_id] = {
                    'collection': cb.codecollection,
                    'codebundles': []
                }
            collections_map[cb.codecollection_id]['codebundles'].append(cb)
        
        # Extract FIRST-commit dates from git history
        codebundle_first_dates = []
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            for coll_id, data in collections_map.items():
                collection = data['collection']
                codebundles_list = data['codebundles']
                
                try:
                    # Clone repository
                    repo_path = os.path.join(tmp_dir, collection.slug)
                    logger.info(f"Cloning {collection.git_url} to analyze first-commit dates")
                    
                    subprocess.run(
                        ['git', 'clone', '--quiet', collection.git_url, repo_path],
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    
                    # For each codebundle, get the FIRST commit date
                    for cb in codebundles_list:
                        bundle_path = f"codebundles/{cb.slug}"
                        
                        # Get first commit when directory was added
                        result = subprocess.run(
                            ['git', 'log', '--format=%ct', '--reverse', '--diff-filter=A', '--', bundle_path],
                            cwd=repo_path,
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        
                        if result.returncode == 0 and result.stdout.strip():
                            timestamps = result.stdout.strip().split('\n')
                            if timestamps:
                                first_commit = int(timestamps[0])
                                first_date = datetime.fromtimestamp(first_commit)
                                
                                task_count = (cb.task_count or 0) + (cb.sli_count or 0)
                                
                                codebundle_first_dates.append({
                                    'date': first_date,
                                    'task_count': task_count,
                                    'codebundle': cb.slug,
                                    'collection': collection.slug
                                })
                        else:
                            # Fallback to created_at
                            fallback_date = cb.created_at
                            task_count = (cb.task_count or 0) + (cb.sli_count or 0)
                            codebundle_first_dates.append({
                                'date': fallback_date,
                                'task_count': task_count,
                                'codebundle': cb.slug,
                                'collection': collection.slug
                            })
                
                except Exception as e:
                    logger.error(f"Error analyzing git history for {collection.slug}: {e}")
                    # Fallback: use created_at from database
                    for cb in codebundles_list:
                        fallback_date = cb.created_at
                        task_count = (cb.task_count or 0) + (cb.sli_count or 0)
                        codebundle_first_dates.append({
                            'date': fallback_date,
                            'task_count': task_count,
                            'codebundle': cb.slug,
                            'collection': collection.slug
                        })
        
        # Sort by date
        codebundle_first_dates.sort(key=lambda x: x['date'])
        
        if not codebundle_first_dates:
            logger.warning("No codebundle data found")
            return {"status": "no_data", "message": "No codebundles found"}
        
        # Build MONTHLY aggregates for all time
        monthly_data = defaultdict(int)
        for entry in codebundle_first_dates:
            entry_date = entry['date']
            month_key = entry_date.strftime('%Y-%m-01')
            monthly_data[month_key] += entry['task_count']
        
        # Generate cumulative counts for last 18 months
        months = []
        cumulative = []
        
        start_month = eighteen_months_ago.replace(day=1)
        latest = datetime.now().replace(day=1)
        
        # Calculate total tasks before 18 months ago
        running_total = 0
        earliest_date = codebundle_first_dates[0]['date'].replace(day=1)
        temp_month = earliest_date
        
        while temp_month < start_month:
            month_key = temp_month.strftime('%Y-%m-01')
            running_total += monthly_data.get(month_key, 0)
            # Move to next month
            if temp_month.month == 12:
                temp_month = temp_month.replace(year=temp_month.year + 1, month=1)
            else:
                temp_month = temp_month.replace(month=temp_month.month + 1)
        
        # Generate visible data (last 18 months)
        current_month = start_month
        while current_month <= latest:
            month_key = current_month.strftime('%Y-%m-01')
            running_total += monthly_data.get(month_key, 0)
            
            months.append(month_key)
            cumulative.append(running_total)
            
            # Move to next month
            if current_month.month == 12:
                current_month = current_month.replace(year=current_month.year + 1, month=1)
            else:
                current_month = current_month.replace(month=current_month.month + 1)
        
        # Store results in database
        result_data = {
            "months": months,
            "cumulative": cumulative,
            "total_tasks": running_total
        }
        
        duration = int(time.time() - start_time)
        
        # Delete old metrics for this type
        db.query(TaskGrowthMetric).filter(
            TaskGrowthMetric.metric_type == "monthly_growth",
            TaskGrowthMetric.time_period == "18_months"
        ).delete()
        
        # Create new metric
        metric = TaskGrowthMetric(
            metric_type="monthly_growth",
            time_period="18_months",
            data=result_data,
            computation_duration_seconds=duration,
            codebundles_analyzed=len(codebundles),
            notes=f"Analyzed {len(codebundle_first_dates)} codebundles across {len(collections_map)} collections"
        )
        
        db.add(metric)
        db.commit()
        
        logger.info(f"Task growth analytics computed successfully in {duration}s: {running_total} total tasks")
        
        return {
            "status": "success",
            "duration_seconds": duration,
            "codebundles_analyzed": len(codebundles),
            "total_tasks": running_total,
            "months_generated": len(months)
        }
        
    except Exception as e:
        logger.error(f"Error computing task growth analytics: {e}", exc_info=True)
        db.rollback()
        return {
            "status": "error",
            "message": str(e)
        }
    finally:
        db.close()
