"""
API endpoints for Helm chart version management.
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, and_

from app.core.database import get_db
from app.models.helm_chart import HelmChart, HelmChartVersion, HelmChartTemplate

router = APIRouter()


@router.get("/helm-charts")
async def get_helm_charts(
    db: Session = Depends(get_db),
    include_inactive: bool = Query(False, description="Include inactive charts")
):
    """
    Get all available Helm charts.
    """
    query = db.query(HelmChart).options(
        joinedload(HelmChart.versions)
    )
    
    if not include_inactive:
        query = query.filter(HelmChart.is_active == True)
    
    charts = query.order_by(HelmChart.name).all()
    
    result = []
    for chart in charts:
        # Get active versions only
        active_versions = [v for v in chart.versions if v.is_active]
        
        chart_data = {
            "id": chart.id,
            "name": chart.name,
            "description": chart.description,
            "repository_url": chart.repository_url,
            "home_url": chart.home_url,
            "source_urls": chart.source_urls,
            "maintainers": chart.maintainers,
            "keywords": chart.keywords,
            "last_synced_at": chart.last_synced_at,
            "version_count": len(active_versions),
            "latest_version": None
        }
        
        # Find latest version
        if active_versions:
            latest = next((v for v in active_versions if v.is_latest), None)
            if latest:
                chart_data["latest_version"] = {
                    "version": latest.version,
                    "app_version": latest.app_version,
                    "created_date": latest.created_date
                }
        
        result.append(chart_data)
    
    return result


@router.get("/helm-charts/{chart_name}")
async def get_helm_chart(
    chart_name: str,
    db: Session = Depends(get_db)
):
    """
    Get a specific Helm chart with all its versions.
    """
    chart = db.query(HelmChart).options(
        joinedload(HelmChart.versions)
    ).filter(
        HelmChart.name == chart_name,
        HelmChart.is_active == True
    ).first()
    
    if not chart:
        raise HTTPException(status_code=404, detail="Helm chart not found")
    
    # Sort versions: latest first, then by semantic version
    sorted_versions = sorted(
        [v for v in chart.versions if v.is_active],
        key=lambda v: (
            not v.is_latest,  # Latest first
            v.is_prerelease,  # Stable before prerelease
            v.version  # Then by version string (this could be improved with proper semver parsing)
        ),
        reverse=True
    )
    
    return {
        "id": chart.id,
        "name": chart.name,
        "description": chart.description,
        "repository_url": chart.repository_url,
        "home_url": chart.home_url,
        "source_urls": chart.source_urls,
        "maintainers": chart.maintainers,
        "keywords": chart.keywords,
        "last_synced_at": chart.last_synced_at,
        "versions": [
            {
                "id": version.id,
                "version": version.version,
                "app_version": version.app_version,
                "description": version.description,
                "created_date": version.created_date,
                "digest": version.digest,
                "is_latest": version.is_latest,
                "is_prerelease": version.is_prerelease,
                "is_deprecated": version.is_deprecated,
                "synced_at": version.synced_at
            }
            for version in sorted_versions
        ]
    }


@router.get("/helm-charts/{chart_name}/versions/{version}")
async def get_helm_chart_version(
    chart_name: str,
    version: str,
    db: Session = Depends(get_db),
    include_schema: bool = Query(True, description="Include values schema"),
    include_defaults: bool = Query(True, description="Include default values")
):
    """
    Get a specific version of a Helm chart with its values and schema.
    """
    chart_version = db.query(HelmChartVersion).join(HelmChart).filter(
        HelmChart.name == chart_name,
        HelmChartVersion.version == version,
        HelmChart.is_active == True,
        HelmChartVersion.is_active == True
    ).first()
    
    if not chart_version:
        raise HTTPException(status_code=404, detail="Helm chart version not found")
    
    result = {
        "id": chart_version.id,
        "version": chart_version.version,
        "app_version": chart_version.app_version,
        "description": chart_version.description,
        "created_date": chart_version.created_date,
        "digest": chart_version.digest,
        "is_latest": chart_version.is_latest,
        "is_prerelease": chart_version.is_prerelease,
        "is_deprecated": chart_version.is_deprecated,
        "synced_at": chart_version.synced_at,
        "chart": {
            "id": chart_version.chart.id,
            "name": chart_version.chart.name,
            "description": chart_version.chart.description,
            "repository_url": chart_version.chart.repository_url
        }
    }
    
    if include_schema:
        result["values_schema"] = chart_version.values_schema
    
    if include_defaults:
        result["default_values"] = chart_version.default_values
    
    return result


@router.get("/helm-charts/{chart_name}/versions/{version}/templates")
async def get_chart_version_templates(
    chart_name: str,
    version: str,
    db: Session = Depends(get_db),
    category: Optional[str] = Query(None, description="Filter by template category")
):
    """
    Get configuration templates for a specific chart version.
    """
    chart_version = db.query(HelmChartVersion).join(HelmChart).filter(
        HelmChart.name == chart_name,
        HelmChartVersion.version == version,
        HelmChart.is_active == True,
        HelmChartVersion.is_active == True
    ).first()
    
    if not chart_version:
        raise HTTPException(status_code=404, detail="Helm chart version not found")
    
    query = db.query(HelmChartTemplate).filter(
        HelmChartTemplate.chart_version_id == chart_version.id,
        HelmChartTemplate.is_active == True
    )
    
    if category:
        query = query.filter(HelmChartTemplate.category == category)
    
    templates = query.order_by(
        HelmChartTemplate.sort_order,
        HelmChartTemplate.name
    ).all()
    
    return [
        {
            "id": template.id,
            "name": template.name,
            "description": template.description,
            "category": template.category,
            "template_values": template.template_values,
            "required_fields": template.required_fields,
            "is_default": template.is_default,
            "sort_order": template.sort_order
        }
        for template in templates
    ]


@router.get("/helm-charts/{chart_name}/latest")
async def get_latest_chart_version(
    chart_name: str,
    db: Session = Depends(get_db),
    include_prerelease: bool = Query(False, description="Include prerelease versions"),
    include_schema: bool = Query(True, description="Include values schema"),
    include_defaults: bool = Query(True, description="Include default values")
):
    """
    Get the latest version of a Helm chart.
    """
    query = db.query(HelmChartVersion).join(HelmChart).filter(
        HelmChart.name == chart_name,
        HelmChart.is_active == True,
        HelmChartVersion.is_active == True
    )
    
    if not include_prerelease:
        query = query.filter(HelmChartVersion.is_prerelease == False)
    
    # Try to get the version marked as latest first
    latest_version = query.filter(HelmChartVersion.is_latest == True).first()
    
    # If no version is marked as latest, get the most recent one
    if not latest_version:
        latest_version = query.order_by(desc(HelmChartVersion.created_date)).first()
    
    if not latest_version:
        raise HTTPException(status_code=404, detail="No versions found for this chart")
    
    result = {
        "id": latest_version.id,
        "version": latest_version.version,
        "app_version": latest_version.app_version,
        "description": latest_version.description,
        "created_date": latest_version.created_date,
        "digest": latest_version.digest,
        "is_latest": latest_version.is_latest,
        "is_prerelease": latest_version.is_prerelease,
        "is_deprecated": latest_version.is_deprecated,
        "synced_at": latest_version.synced_at,
        "chart": {
            "id": latest_version.chart.id,
            "name": latest_version.chart.name,
            "description": latest_version.chart.description,
            "repository_url": latest_version.chart.repository_url
        }
    }
    
    if include_schema:
        result["values_schema"] = latest_version.values_schema
    
    if include_defaults:
        result["default_values"] = latest_version.default_values
    
    return result


@router.post("/helm-charts/{chart_name}/validate-values")
async def validate_helm_values(
    chart_name: str,
    values: Dict[str, Any],
    version: Optional[str] = Query(None, description="Chart version to validate against"),
    db: Session = Depends(get_db)
):
    """
    Validate user-provided values against the chart's schema.
    """
    # Get the chart version
    query = db.query(HelmChartVersion).join(HelmChart).filter(
        HelmChart.name == chart_name,
        HelmChart.is_active == True,
        HelmChartVersion.is_active == True
    )
    
    if version:
        chart_version = query.filter(HelmChartVersion.version == version).first()
    else:
        # Use latest version if no version specified
        chart_version = query.filter(HelmChartVersion.is_latest == True).first()
        if not chart_version:
            chart_version = query.order_by(desc(HelmChartVersion.created_date)).first()
    
    if not chart_version:
        raise HTTPException(status_code=404, detail="Chart version not found")
    
    # TODO: Implement actual JSON schema validation
    # For now, return basic validation info
    validation_result = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "chart_version": chart_version.version,
        "validated_at": datetime.utcnow().isoformat()
    }
    
    # Basic validation: check if required fields are present
    schema = chart_version.values_schema
    if schema and "required" in schema:
        for required_field in schema["required"]:
            if required_field not in values:
                validation_result["valid"] = False
                validation_result["errors"].append(f"Required field '{required_field}' is missing")
    
    return validation_result
