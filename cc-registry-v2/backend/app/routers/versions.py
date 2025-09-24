"""
API endpoints for CodeCollection versions management.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc

from app.core.database import get_db
from app.models.code_collection import CodeCollection
from app.models.version import CodeCollectionVersion, VersionCodebundle

router = APIRouter()

@router.get("/collections-with-versions")
async def get_collections_with_versions(
    db: Session = Depends(get_db),
    limit: Optional[int] = Query(None, description="Limit number of collections returned"),
    offset: Optional[int] = Query(0, description="Offset for pagination")
):
    """
    Get all CodeCollections with their versions (tags and branches).
    """
    try:
        query = db.query(CodeCollection).options(
            joinedload(CodeCollection.versions)
        ).order_by(CodeCollection.name)
        
        if limit:
            query = query.offset(offset).limit(limit)
        
        collections = query.all()
        
        result = []
        for collection in collections:
            # Sort versions: main first, then latest tags, then other versions
            sorted_versions = sorted(
                collection.versions,
                key=lambda v: (
                    v.version_type != 'main',  # main first
                    not v.is_latest,          # latest next
                    v.is_prerelease,          # stable before prerelease
                    v.version_name            # alphabetical
                )
            )
            
            collection_data = {
                "id": collection.id,
                "name": collection.name,
                "slug": collection.slug,
                "description": collection.description,
                "repository_url": collection.repository_url,
                "created_at": collection.created_at,
                "updated_at": collection.updated_at,
                "versions": [
                    {
                        "id": version.id,
                        "version_name": version.version_name,
                        "display_name": version.display_name,
                        "description": version.description,
                        "version_type": version.version_type,
                        "git_ref": version.git_ref,
                        "is_latest": version.is_latest,
                        "is_prerelease": version.is_prerelease,
                        "version_date": version.version_date,
                        "synced_at": version.synced_at,
                        "is_active": version.is_active
                    }
                    for version in sorted_versions[:10]  # Limit to 10 versions per collection
                ]
            }
            result.append(collection_data)
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching collections with versions: {str(e)}")

@router.get("/collections/{collection_slug}/versions")
async def get_collection_versions(
    collection_slug: str,
    db: Session = Depends(get_db),
    include_inactive: bool = Query(False, description="Include inactive versions")
):
    """
    Get all versions for a specific CodeCollection.
    """
    collection = db.query(CodeCollection).filter(
        CodeCollection.slug == collection_slug
    ).first()
    
    if not collection:
        raise HTTPException(status_code=404, detail="CodeCollection not found")
    
    query = db.query(CodeCollectionVersion).filter(
        CodeCollectionVersion.codecollection_id == collection.id
    )
    
    if not include_inactive:
        query = query.filter(CodeCollectionVersion.is_active == True)
    
    versions = query.order_by(
        CodeCollectionVersion.version_type.asc(),  # main first
        desc(CodeCollectionVersion.is_latest),     # latest next
        CodeCollectionVersion.is_prerelease.asc(), # stable before prerelease
        desc(CodeCollectionVersion.version_date)   # newest first
    ).all()
    
    return [
        {
            "id": version.id,
            "version_name": version.version_name,
            "display_name": version.display_name,
            "description": version.description,
            "version_type": version.version_type,
            "git_ref": version.git_ref,
            "is_latest": version.is_latest,
            "is_prerelease": version.is_prerelease,
            "version_date": version.version_date,
            "synced_at": version.synced_at,
            "is_active": version.is_active,
            "codebundle_count": len(version.codebundles)
        }
        for version in versions
    ]

@router.get("/collections/{collection_slug}/versions/{version_name}")
async def get_version_by_name(
    collection_slug: str,
    version_name: str,
    db: Session = Depends(get_db)
):
    """
    Get a specific version by collection slug and version name.
    """
    collection = db.query(CodeCollection).filter(
        CodeCollection.slug == collection_slug
    ).first()
    
    if not collection:
        raise HTTPException(status_code=404, detail="CodeCollection not found")
    
    version = db.query(CodeCollectionVersion).filter(
        CodeCollectionVersion.codecollection_id == collection.id,
        CodeCollectionVersion.version_name == version_name
    ).first()
    
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    
    return {
        "id": version.id,
        "version_name": version.version_name,
        "display_name": version.display_name,
        "description": version.description,
        "version_type": version.version_type,
        "git_ref": version.git_ref,
        "is_latest": version.is_latest,
        "is_prerelease": version.is_prerelease,
        "version_date": version.version_date,
        "synced_at": version.synced_at,
        "is_active": version.is_active,
        "codecollection": {
            "id": collection.id,
            "name": collection.name,
            "slug": collection.slug,
            "description": collection.description,
            "repository_url": collection.repository_url
        }
    }

@router.get("/collections/{collection_slug}/latest-version")
async def get_latest_version(
    collection_slug: str,
    db: Session = Depends(get_db),
    version_type: Optional[str] = Query(None, description="Filter by version type: tag, branch, main")
):
    """
    Get the latest version for a CodeCollection.
    """
    collection = db.query(CodeCollection).filter(
        CodeCollection.slug == collection_slug
    ).first()
    
    if not collection:
        raise HTTPException(status_code=404, detail="CodeCollection not found")
    
    query = db.query(CodeCollectionVersion).filter(
        CodeCollectionVersion.codecollection_id == collection.id,
        CodeCollectionVersion.is_active == True
    )
    
    if version_type:
        query = query.filter(CodeCollectionVersion.version_type == version_type)
    
    # Prefer main, then latest tagged versions
    version = query.order_by(
        CodeCollectionVersion.version_type == 'main',  # main first
        desc(CodeCollectionVersion.is_latest),         # latest next
        desc(CodeCollectionVersion.version_date)       # newest first
    ).first()
    
    if not version:
        raise HTTPException(status_code=404, detail="No versions found")
    
    return {
        "id": version.id,
        "version_name": version.version_name,
        "display_name": version.display_name,
        "description": version.description,
        "version_type": version.version_type,
        "git_ref": version.git_ref,
        "is_latest": version.is_latest,
        "is_prerelease": version.is_prerelease,
        "version_date": version.version_date,
        "synced_at": version.synced_at,
        "is_active": version.is_active,
        "codebundle_count": len(version.codebundles)
    }

@router.get("/collections/{collection_slug}/versions/{version_name}/codebundles")
async def get_version_codebundles(
    collection_slug: str,
    version_name: str,
    db: Session = Depends(get_db),
    limit: Optional[int] = Query(None, description="Limit number of codebundles returned"),
    offset: Optional[int] = Query(0, description="Offset for pagination")
):
    """
    Get all codebundles for a specific version.
    """
    collection = db.query(CodeCollection).filter(
        CodeCollection.slug == collection_slug
    ).first()
    
    if not collection:
        raise HTTPException(status_code=404, detail="CodeCollection not found")
    
    version = db.query(CodeCollectionVersion).filter(
        CodeCollectionVersion.codecollection_id == collection.id,
        CodeCollectionVersion.version_name == version_name
    ).first()
    
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    
    query = db.query(VersionCodebundle).filter(
        VersionCodebundle.version_id == version.id
    ).order_by(VersionCodebundle.name)
    
    if limit:
        query = query.offset(offset).limit(limit)
    
    codebundles = query.all()
    
    return {
        "version": {
            "id": version.id,
            "version_name": version.version_name,
            "display_name": version.display_name,
            "version_type": version.version_type,
            "is_latest": version.is_latest,
            "is_prerelease": version.is_prerelease,
            "version_date": version.version_date
        },
        "codebundles": [
            {
                "id": cb.id,
                "name": cb.name,
                "slug": cb.slug,
                "display_name": cb.display_name,
                "description": cb.description,
                "doc": cb.doc,
                "author": cb.author,
                "support_tags": cb.support_tags,
                "categories": cb.categories,
                "task_count": cb.task_count,
                "sli_count": cb.sli_count,
                "runbook_path": cb.runbook_path,
                "runbook_source_url": cb.runbook_source_url,
                "added_in_version": cb.added_in_version,
                "modified_in_version": cb.modified_in_version,
                "removed_in_version": cb.removed_in_version,
                "discovery_info": cb.discovery_info
            }
            for cb in codebundles
        ]
    }


