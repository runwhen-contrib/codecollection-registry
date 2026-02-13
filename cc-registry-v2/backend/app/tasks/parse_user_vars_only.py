"""
Task to parse ONLY user variables from robot files without using Robot Framework parser
"""
import logging
from typing import Dict, Any
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models import RawRepositoryData, Codebundle
from app.tasks.celery_app import celery_app
from app.tasks.fixed_parser import parse_user_variables

logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def parse_user_variables_task(self):
    """
    Parse user variables from all robot files and update existing codebundles
    This task ONLY extracts user variables using regex - no Robot Framework parser
    """
    db = SessionLocal()
    
    try:
        # Count total files
        total_files = db.query(RawRepositoryData).filter(
            RawRepositoryData.file_type == 'robot',
            RawRepositoryData.file_content.isnot(None)
        ).count()
        
        logger.info(f"Found {total_files} Robot files to parse for user variables")
        
        processed = 0
        updated = 0
        batch_size = 10
        
        # Process files in batches to avoid loading all into memory
        for offset in range(0, total_files, batch_size):
            robot_files = db.query(RawRepositoryData).filter(
                RawRepositoryData.file_type == 'robot',
                RawRepositoryData.file_content.isnot(None)
            ).offset(offset).limit(batch_size).all()
            
            logger.info(f"Processing batch {offset//batch_size + 1}/{(total_files + batch_size - 1)//batch_size} ({len(robot_files)} files)")
        
            for idx, raw_file in enumerate(robot_files, offset + 1):
                try:
                    # Extract user variables from content using regex only
                    user_variables = parse_user_variables(raw_file.file_content)
                    
                    if user_variables:
                        logger.info(f"File {idx}/{total_files}: {raw_file.file_path} - Found {len(user_variables)} user variables")
                        
                        # Find corresponding codebundle by file path
                        # Path format: "codebundles/name/runbook.robot" or "codebundles/name/sli.robot"
                        path_parts = raw_file.file_path.split('/')
                        if len(path_parts) >= 2 and path_parts[0] == 'codebundles':
                            codebundle_slug = path_parts[1].lower().replace(' ', '-').replace('_', '-')
                            
                            # Find codebundle
                            codebundle = db.query(Codebundle).filter(
                                Codebundle.slug == codebundle_slug
                            ).first()
                            
                            if codebundle:
                                # Update user_variables
                                codebundle.user_variables = user_variables
                                updated += 1
                                logger.info(f"Updated codebundle '{codebundle_slug}' with {len(user_variables)} user variables")
                            else:
                                logger.warning(f"Codebundle not found for slug: {codebundle_slug}")
                    
                    processed += 1
                            
                except Exception as e:
                    logger.error(f"Failed to parse user variables from {raw_file.file_path}: {e}")
                    db.rollback()
                    continue
            
            # Commit after each batch
            db.commit()
            logger.info(f"Committed batch {offset//batch_size + 1} - processed {processed} files, updated {updated} codebundles")
        
        # Final commit
        db.commit()
        
        logger.info(f"Parse complete - Processed: {processed}, Updated: {updated}")
        
        return {
            'status': 'success',
            'files_processed': processed,
            'codebundles_updated': updated,
            'message': f'Successfully parsed user variables from {processed} files, updated {updated} codebundles'
        }
        
    except Exception as e:
        logger.error(f"Failed to parse user variables: {e}", exc_info=True)
        db.rollback()
        return {
            'status': 'error',
            'message': str(e)
        }
    finally:
        db.close()
