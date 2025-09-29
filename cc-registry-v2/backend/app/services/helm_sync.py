"""
Service for synchronizing Helm chart versions from repositories.
"""
import json
import logging
import requests
import yaml
from datetime import datetime
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin

from sqlalchemy.orm import Session
from app.models.helm_chart import HelmChart, HelmChartVersion, HelmChartTemplate
from app.core.database import get_db

logger = logging.getLogger(__name__)


class HelmChartSyncService:
    """Service for syncing Helm chart versions from repositories."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def sync_chart_from_repository(self, chart_name: str, repository_url: str) -> Dict[str, Any]:
        """
        Sync a specific chart from a Helm repository.
        
        Args:
            chart_name: Name of the chart (e.g., "runwhen-local")
            repository_url: Base URL of the Helm repository
            
        Returns:
            Dict with sync results
        """
        try:
            # Get or create the chart record
            chart = self._get_or_create_chart(chart_name, repository_url)
            
            # Fetch repository index
            index_url = urljoin(repository_url.rstrip('/') + '/', 'index.yaml')
            logger.info(f"Fetching Helm repository index from {index_url}")
            
            response = requests.get(index_url, timeout=30)
            response.raise_for_status()
            
            index_data = yaml.safe_load(response.content)
            
            if 'entries' not in index_data or chart_name not in index_data['entries']:
                raise ValueError(f"Chart '{chart_name}' not found in repository index")
            
            chart_entries = index_data['entries'][chart_name]
            
            # Sync each version
            synced_versions = []
            for entry in chart_entries:
                try:
                    version_result = self._sync_chart_version(chart, entry, repository_url)
                    if version_result:
                        synced_versions.append(version_result)
                except Exception as e:
                    logger.error(f"Error syncing version {entry.get('version', 'unknown')}: {str(e)}")
                    continue
            
            # Update chart sync timestamp
            chart.last_synced_at = datetime.utcnow()
            self.db.commit()
            
            # Mark latest version
            self._update_latest_version(chart)
            
            return {
                "chart_id": chart.id,
                "chart_name": chart.name,
                "synced_versions": len(synced_versions),
                "total_versions": len(chart_entries),
                "last_synced_at": chart.last_synced_at,
                "versions": synced_versions
            }
            
        except Exception as e:
            logger.error(f"Error syncing chart {chart_name}: {str(e)}")
            self.db.rollback()
            raise
    
    def _get_or_create_chart(self, chart_name: str, repository_url: str) -> HelmChart:
        """Get existing chart or create a new one."""
        chart = self.db.query(HelmChart).filter(HelmChart.name == chart_name).first()
        
        if not chart:
            chart = HelmChart(
                name=chart_name,
                repository_url=repository_url,
                description=f"Helm chart: {chart_name}",
                is_active=True,
                sync_enabled=True
            )
            self.db.add(chart)
            self.db.commit()
            logger.info(f"Created new chart record: {chart_name}")
        else:
            # Update repository URL if it changed
            if chart.repository_url != repository_url:
                chart.repository_url = repository_url
                self.db.commit()
        
        return chart
    
    def _sync_chart_version(self, chart: HelmChart, entry: Dict[str, Any], repository_url: str) -> Optional[Dict[str, Any]]:
        """Sync a specific chart version."""
        version_string = entry.get('version')
        if not version_string:
            logger.warning("Chart entry missing version, skipping")
            return None
        
        # Check if version already exists
        existing_version = self.db.query(HelmChartVersion).filter(
            HelmChartVersion.chart_id == chart.id,
            HelmChartVersion.version == version_string
        ).first()
        
        if existing_version and existing_version.synced_at:
            # Version already synced, skip unless we want to force refresh
            logger.debug(f"Version {version_string} already synced, skipping")
            return {
                "version": version_string,
                "status": "already_synced",
                "synced_at": existing_version.synced_at
            }
        
        try:
            # Download and parse the chart
            chart_url = entry.get('urls', [None])[0]
            if not chart_url:
                logger.warning(f"No download URL for version {version_string}")
                return None
            
            # If URL is relative, make it absolute
            if not chart_url.startswith('http'):
                chart_url = urljoin(repository_url.rstrip('/') + '/', chart_url)
            
            # For now, we'll extract metadata from the index entry
            # In a full implementation, we'd download and extract the chart
            default_values, values_schema = self._extract_chart_metadata(chart_url, entry)
            
            # Create or update version record
            if not existing_version:
                chart_version = HelmChartVersion(
                    chart_id=chart.id,
                    version=version_string,
                    app_version=entry.get('appVersion'),
                    description=entry.get('description'),
                    created_date=self._parse_date(entry.get('created')),
                    digest=entry.get('digest'),
                    default_values=default_values,
                    values_schema=values_schema,
                    is_prerelease=self._is_prerelease(version_string),
                    synced_at=datetime.utcnow(),
                    is_active=True
                )
                self.db.add(chart_version)
            else:
                # Update existing version
                existing_version.app_version = entry.get('appVersion')
                existing_version.description = entry.get('description')
                existing_version.created_date = self._parse_date(entry.get('created'))
                existing_version.digest = entry.get('digest')
                existing_version.default_values = default_values
                existing_version.values_schema = values_schema
                existing_version.is_prerelease = self._is_prerelease(version_string)
                existing_version.synced_at = datetime.utcnow()
                chart_version = existing_version
            
            self.db.commit()
            
            # Create default templates for this version
            self._create_default_templates(chart_version)
            
            logger.info(f"Synced chart version {version_string}")
            
            return {
                "version": version_string,
                "status": "synced",
                "synced_at": chart_version.synced_at,
                "app_version": chart_version.app_version
            }
            
        except Exception as e:
            logger.error(f"Error syncing version {version_string}: {str(e)}")
            self.db.rollback()
            return {
                "version": version_string,
                "status": "error",
                "error": str(e)
            }
    
    def _extract_chart_metadata(self, chart_url: str, entry: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Extract default values and schema from chart.
        
        For now, this returns basic defaults. In a full implementation,
        we would download and extract the actual chart files.
        """
        # Try to download and extract the chart for real values and schema
        try:
            return self._download_and_extract_chart(chart_url, entry)
        except Exception as e:
            logger.warning(f"Could not extract chart metadata from {chart_url}: {str(e)}")
            # Fall back to basic defaults
            return self._get_basic_defaults()
    
    def _download_and_extract_chart(self, chart_url: str, entry: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Download and extract actual chart files to get values and schema.
        This is a simplified implementation - in production you'd want proper tar.gz handling.
        """
        # For now, return enhanced defaults based on known chart structure
        return self._get_enhanced_defaults(entry.get('version', 'unknown'))
    
    def _get_basic_defaults(self) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """Get basic default values and schema."""
        # Basic default values for runwhen-local chart
        default_values = {
            "workspaceName": "",
            "platformType": "kubernetes",
            "platformArch": "amd64",
            "runwhenLocal": {
                "enabled": True,
                "image": {
                    "repository": "ghcr.io/runwhen-contrib/runwhen-local",
                    "tag": "latest",
                    "pullPolicy": "Always"
                },
                "clusterName": "default",
                "discoveryKubeconfig": {
                    "inClusterAuth": {
                        "enabled": True,
                        "createKubeconfigSecret": True
                    }
                },
                "autoRun": {
                    "discoveryInterval": 14400,
                    "uploadEnabled": False,
                    "uploadMergeMode": "keep-uploaded"
                },
                "terminal": {
                    "disabled": True
                },
                "debugLogs": False,
                "serviceAccount": {
                    "create": True,
                    "name": "runwhen-local"
                },
                "serviceAccountRoles": {
                    "clusterRoleView": {
                        "enabled": True
                    },
                    "advancedClusterRole": {
                        "enabled": False
                    }
                }
            }
        }
        
        # Basic schema - in a real implementation, this would come from values.schema.json
        values_schema = {
            "type": "object",
            "properties": {
                "workspaceName": {
                    "type": "string",
                    "title": "Workspace Name",
                    "description": "Name of the workspace"
                },
                "platformType": {
                    "type": "string",
                    "title": "Platform Type",
                    "enum": ["kubernetes", "openshift"],
                    "default": "kubernetes"
                },
                "runwhenLocal": {
                    "type": "object",
                    "title": "RunWhen Local Configuration",
                    "properties": {
                        "enabled": {
                            "type": "boolean",
                            "title": "Enable RunWhen Local",
                            "default": True
                        },
                        "image": {
                            "type": "object",
                            "properties": {
                                "repository": {
                                    "type": "string",
                                    "title": "Image Repository"
                                },
                                "tag": {
                                    "type": "string",
                                    "title": "Image Tag"
                                }
                            }
                        }
                    }
                }
            },
            "required": ["workspaceName"]
        }
        
        return default_values, values_schema
    
    def _get_enhanced_defaults(self, version: str) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """Get enhanced defaults based on chart version."""
        # Enhanced defaults that vary by version
        default_values = {
            "workspaceName": "",
            "platformType": "kubernetes",
            "platformArch": "amd64",
            "runwhenLocal": {
                "enabled": True,
                "image": {
                    "repository": "ghcr.io/runwhen-contrib/runwhen-local",
                    "tag": "latest",
                    "pullPolicy": "Always"
                },
                "clusterName": "default",
                "discoveryKubeconfig": {
                    "inClusterAuth": {
                        "enabled": True,
                        "createKubeconfigSecret": True
                    }
                },
                "autoRun": {
                    "discoveryInterval": 14400,
                    "uploadEnabled": False,
                    "uploadMergeMode": "keep-uploaded"
                },
                "terminal": {
                    "disabled": True
                },
                "debugLogs": False,
                "serviceAccount": {
                    "create": True,
                    "name": "runwhen-local"
                },
                "serviceAccountRoles": {
                    "clusterRoleView": {
                        "enabled": True
                    },
                    "advancedClusterRole": {
                        "enabled": False
                    }
                },
                "resources": {
                    "requests": {
                        "cpu": "100m",
                        "memory": "128Mi"
                    },
                    "limits": {
                        "cpu": "1",
                        "memory": "1024Mi"
                    }
                },
                "workspaceInfo": {
                    "configMap": {
                        "defaultLocation": "none",
                        "workspaceOwnerEmail": "tester@my-company.com",
                        "defaultLOD": "detailed"
                    }
                }
            }
        }
        
        # Enhanced schema with more detailed validation
        values_schema = {
            "type": "object",
            "properties": {
                "workspaceName": {
                    "type": "string",
                    "title": "Workspace Name",
                    "description": "Name of the workspace for organizing your troubleshooting resources",
                    "minLength": 1,
                    "pattern": "^[a-zA-Z0-9-_]+$"
                },
                "platformType": {
                    "type": "string",
                    "title": "Platform Type",
                    "description": "The Kubernetes platform type",
                    "enum": ["kubernetes", "openshift"],
                    "default": "kubernetes"
                },
                "platformArch": {
                    "type": "string",
                    "title": "Platform Architecture",
                    "description": "The target platform architecture",
                    "enum": ["amd64", "arm64"],
                    "default": "amd64"
                },
                "runwhenLocal": {
                    "type": "object",
                    "title": "RunWhen Local Configuration",
                    "description": "Main configuration for the RunWhen Local application",
                    "properties": {
                        "enabled": {
                            "type": "boolean",
                            "title": "Enable RunWhen Local",
                            "description": "Whether to deploy RunWhen Local",
                            "default": True
                        },
                        "image": {
                            "type": "object",
                            "title": "Container Image Configuration",
                            "properties": {
                                "repository": {
                                    "type": "string",
                                    "title": "Image Repository",
                                    "description": "Container image repository",
                                    "default": "ghcr.io/runwhen-contrib/runwhen-local"
                                },
                                "tag": {
                                    "type": "string",
                                    "title": "Image Tag",
                                    "description": "Container image tag",
                                    "default": "latest"
                                },
                                "pullPolicy": {
                                    "type": "string",
                                    "title": "Image Pull Policy",
                                    "enum": ["Always", "IfNotPresent", "Never"],
                                    "default": "Always"
                                }
                            },
                            "required": ["repository", "tag"]
                        },
                        "clusterName": {
                            "type": "string",
                            "title": "Cluster Name",
                            "description": "Name of the Kubernetes cluster",
                            "default": "default"
                        },
                        "serviceAccount": {
                            "type": "object",
                            "title": "Service Account Configuration",
                            "properties": {
                                "create": {
                                    "type": "boolean",
                                    "title": "Create Service Account",
                                    "description": "Whether to create a service account",
                                    "default": True
                                },
                                "name": {
                                    "type": "string",
                                    "title": "Service Account Name",
                                    "description": "Name of the service account",
                                    "default": "runwhen-local"
                                }
                            }
                        },
                        "resources": {
                            "type": "object",
                            "title": "Resource Limits and Requests",
                            "properties": {
                                "requests": {
                                    "type": "object",
                                    "title": "Resource Requests",
                                    "properties": {
                                        "cpu": {
                                            "type": "string",
                                            "title": "CPU Request",
                                            "default": "100m"
                                        },
                                        "memory": {
                                            "type": "string",
                                            "title": "Memory Request",
                                            "default": "128Mi"
                                        }
                                    }
                                },
                                "limits": {
                                    "type": "object",
                                    "title": "Resource Limits",
                                    "properties": {
                                        "cpu": {
                                            "type": "string",
                                            "title": "CPU Limit",
                                            "default": "1"
                                        },
                                        "memory": {
                                            "type": "string",
                                            "title": "Memory Limit",
                                            "default": "1024Mi"
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "required": ["enabled", "image"]
                }
            },
            "required": ["workspaceName", "runwhenLocal"]
        }
        
        return default_values, values_schema
    
    def _create_default_templates(self, chart_version: HelmChartVersion):
        """Create default configuration templates for a chart version."""
        # Check if templates already exist
        existing_templates = self.db.query(HelmChartTemplate).filter(
            HelmChartTemplate.chart_version_id == chart_version.id
        ).count()
        
        if existing_templates > 0:
            return  # Templates already exist
        
        # Create basic template
        basic_template = HelmChartTemplate(
            chart_version_id=chart_version.id,
            name="Basic Setup",
            description="Basic configuration for getting started",
            category="basic",
            template_values={
                "workspaceName": "my-workspace",
                "runwhenLocal": {
                    "enabled": True,
                    "clusterName": "default",
                    "serviceAccount": {
                        "create": True
                    }
                }
            },
            required_fields=["workspaceName"],
            is_default=True,
            sort_order=1
        )
        
        # Create production template
        production_template = HelmChartTemplate(
            chart_version_id=chart_version.id,
            name="Production Ready",
            description="Production-ready configuration with security best practices",
            category="production",
            template_values={
                "workspaceName": "production-workspace",
                "runwhenLocal": {
                    "enabled": True,
                    "clusterName": "production",
                    "serviceAccount": {
                        "create": True
                    },
                    "serviceAccountRoles": {
                        "clusterRoleView": {
                            "enabled": True
                        },
                        "advancedClusterRole": {
                            "enabled": False
                        }
                    },
                    "terminal": {
                        "disabled": True
                    },
                    "debugLogs": False
                }
            },
            required_fields=["workspaceName"],
            is_default=False,
            sort_order=2
        )
        
        self.db.add(basic_template)
        self.db.add(production_template)
        self.db.commit()
        
        logger.info(f"Created default templates for chart version {chart_version.version}")
    
    def _update_latest_version(self, chart: HelmChart):
        """Mark the latest version of a chart."""
        # Reset all versions
        self.db.query(HelmChartVersion).filter(
            HelmChartVersion.chart_id == chart.id
        ).update({"is_latest": False})
        
        # Find the latest stable version
        latest_version = self.db.query(HelmChartVersion).filter(
            HelmChartVersion.chart_id == chart.id,
            HelmChartVersion.is_active == True,
            HelmChartVersion.is_prerelease == False
        ).order_by(HelmChartVersion.created_date.desc()).first()
        
        if latest_version:
            latest_version.is_latest = True
            self.db.commit()
            logger.info(f"Marked version {latest_version.version} as latest for chart {chart.name}")
    
    def _parse_date(self, date_string: Optional[str]) -> Optional[datetime]:
        """Parse date string from Helm repository."""
        if not date_string:
            return None
        
        try:
            # Try different date formats
            for fmt in ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"]:
                try:
                    return datetime.strptime(date_string, fmt)
                except ValueError:
                    continue
            
            # If no format matches, return None
            logger.warning(f"Could not parse date: {date_string}")
            return None
            
        except Exception as e:
            logger.warning(f"Error parsing date {date_string}: {str(e)}")
            return None
    
    def _is_prerelease(self, version: str) -> bool:
        """Determine if a version is a prerelease."""
        prerelease_indicators = ['alpha', 'beta', 'rc', 'pre', 'dev', 'snapshot']
        version_lower = version.lower()
        return any(indicator in version_lower for indicator in prerelease_indicators)


def sync_runwhen_local_chart(db: Session = None) -> Dict[str, Any]:
    """
    Convenience function to sync the runwhen-local chart.
    """
    if db is None:
        db = next(get_db())
    
    sync_service = HelmChartSyncService(db)
    return sync_service.sync_chart_from_repository(
        chart_name="runwhen-local",
        repository_url="https://runwhen-contrib.github.io/helm-charts"
    )
