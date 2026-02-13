"""
Robot Framework Parser for stored repository files
Enhanced with access pattern detection and classification
"""
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from app.models import RawRepositoryData

logger = logging.getLogger(__name__)

class RobotFrameworkParser:
    """Parser for Robot Framework files stored in database"""
    
    def __init__(self):
        self.current_section = None
        self.current_test = None
        self.current_keyword = None
        
        # Access pattern keywords for classification
        self.read_only_keywords = {
            'get', 'list', 'describe', 'show', 'check', 'verify', 'validate', 
            'inspect', 'monitor', 'watch', 'query', 'search', 'find', 'fetch',
            'read', 'view', 'display', 'print', 'log', 'status', 'health',
            'ping', 'test', 'probe', 'scan', 'audit', 'analyze', 'report'
        }
        
        self.read_write_keywords = {
            'create', 'update', 'delete', 'modify', 'change', 'set', 'put',
            'post', 'patch', 'remove', 'add', 'insert', 'deploy', 'install',
            'configure', 'setup', 'start', 'stop', 'restart', 'scale', 'resize',
            'migrate', 'backup', 'restore', 'sync', 'apply', 'execute', 'run',
            'trigger', 'launch', 'kill', 'terminate', 'disable', 'enable',
            'attach', 'detach', 'mount', 'unmount', 'copy', 'move', 'transfer'
        }
    
    def parse_robot_file(self, raw_file: RawRepositoryData) -> List[Dict[str, Any]]:
        """Parse a Robot Framework file using the WORKING parser from generate_registry.py"""
        try:
            # Use the fixed parser that actually works
            from app.tasks.fixed_parser import parse_robot_file_content
            
            codebundle_data = parse_robot_file_content(
                raw_file.file_content, 
                raw_file.file_path, 
                raw_file.collection_slug
            )
            
            if codebundle_data:
                return [codebundle_data]
            else:
                return []
                
        except Exception as e:
            logger.error(f"Failed to parse robot file {raw_file.file_path}: {e}")
            return []
    
    def _is_test_case_name(self, line: str) -> bool:
        """Check if line is a test case name"""
        # Test case names are typically at the start of a line and don't start with brackets
        return (line and 
                not line.startswith('[') and 
                not line.startswith(' ') and
                not line.startswith('\t') and
                not line.startswith('***'))
    
    def _is_keyword_name(self, line: str) -> bool:
        """Check if line is a keyword name"""
        return (line and 
                not line.startswith('[') and 
                not line.startswith(' ') and
                not line.startswith('\t') and
                not line.startswith('***'))
    
    def _create_codebundle_from_test_name(self, test_name: str, collection_slug: str, line_num: int) -> Dict[str, Any]:
        """Create a codebundle from test case name"""
        # Clean up test name
        clean_name = test_name.strip()
        slug = self._create_slug(clean_name)
        
        return {
            'name': clean_name,
            'slug': f"{collection_slug}-{slug}",
            'display_name': clean_name,
            'description': '',
            'doc': '',
            'author': '',
            'support_tags': [],
            'tasks': [],
            'slis': [],
            'collection_slug': collection_slug,
            'source_file_line': line_num
        }
    
    def _create_slug(self, name: str) -> str:
        """Create a URL-friendly slug from name"""
        # Convert to lowercase and replace spaces/special chars with hyphens
        slug = re.sub(r'[^\w\s-]', '', name.lower())
        slug = re.sub(r'[-\s]+', '-', slug)
        return slug.strip('-')
    
    def _parse_keyword_name(self, line: str) -> Optional[str]:
        """Parse keyword name from line"""
        # Extract keyword name (everything before any brackets)
        keyword = line.split('[')[0].strip()
        return keyword if keyword else None
    
    def _extract_documentation(self, lines: List[str], start_line: int) -> List[str]:
        """Extract documentation lines"""
        doc_lines = []
        for i in range(start_line, len(lines)):
            line = lines[i].strip()
            if line.startswith('[') and not line.startswith('[Documentation]'):
                break
            if line and not line.startswith('[Documentation]'):
                doc_lines.append(line)
        return doc_lines
    
    def _extract_tags(self, line: str) -> List[str]:
        """Extract tags from [Tags] line"""
        # Remove [Tags] prefix and split by spaces
        tags_line = line.replace('[Tags]', '').strip()
        return [tag.strip() for tag in tags_line.split() if tag.strip()]
    
    def _parse_test_step(self, line: str) -> Optional[str]:
        """Parse a test step into a task"""
        # Clean up the step
        step = line.strip()
        if step and not step.startswith('#'):
            return step
        return None
    
    def _classify_access_level(self, codebundle: Dict[str, Any]) -> str:
        """Classify the access level based on task names and content"""
        read_write_score = 0
        read_only_score = 0
        
        # Analyze task names
        for task in codebundle.get('tasks', []):
            task_lower = task.lower()
            
            # Check for read-write keywords
            for keyword in self.read_write_keywords:
                if keyword in task_lower:
                    read_write_score += 1
            
            # Check for read-only keywords
            for keyword in self.read_only_keywords:
                if keyword in task_lower:
                    read_only_score += 1
        
        # Analyze support tags
        for tag in codebundle.get('support_tags', []):
            tag_lower = tag.lower()
            
            # Check for explicit access tags
            if any(rw_tag in tag_lower for rw_tag in ['write', 'modify', 'create', 'delete', 'update']):
                read_write_score += 2
            elif any(ro_tag in tag_lower for ro_tag in ['read', 'readonly', 'read-only', 'monitor', 'check']):
                read_only_score += 2
        
        # Analyze description and documentation
        text_content = f"{codebundle.get('description', '')} {codebundle.get('doc', '')}".lower()
        
        # Look for action words in descriptions
        for keyword in self.read_write_keywords:
            if keyword in text_content:
                read_write_score += 0.5
        
        for keyword in self.read_only_keywords:
            if keyword in text_content:
                read_only_score += 0.5
        
        # Determine access level
        if read_write_score > read_only_score:
            return "read-write"
        elif read_only_score > read_write_score:
            return "read-only"
        else:
            return "unknown"
    
    def _extract_iam_requirements(self, codebundle: Dict[str, Any]) -> List[str]:
        """Extract potential IAM requirements based on platform and tasks"""
        iam_requirements = []
        
        # Get platform from collection slug or tags
        platform = self._detect_platform(codebundle)
        
        if not platform:
            return iam_requirements
        
        # Platform-specific IAM requirement extraction
        if platform == 'aws':
            iam_requirements.extend(self._extract_aws_iam_requirements(codebundle))
        elif platform == 'kubernetes':
            iam_requirements.extend(self._extract_k8s_rbac_requirements(codebundle))
        elif platform == 'azure':
            iam_requirements.extend(self._extract_azure_iam_requirements(codebundle))
        elif platform == 'gcp':
            iam_requirements.extend(self._extract_gcp_iam_requirements(codebundle))
        
        return list(set(iam_requirements))  # Remove duplicates
    
    def _detect_platform(self, codebundle: Dict[str, Any]) -> Optional[str]:
        """Detect the cloud platform from codebundle content"""
        content = f"{codebundle.get('name', '')} {codebundle.get('collection_slug', '')} {' '.join(codebundle.get('support_tags', []))}".lower()
        
        if any(aws_term in content for aws_term in ['aws', 'ec2', 's3', 'eks', 'rds', 'lambda', 'cloudformation']):
            return 'aws'
        elif any(k8s_term in content for k8s_term in ['kubernetes', 'k8s', 'kubectl', 'pod', 'deployment', 'service']):
            return 'kubernetes'
        elif any(azure_term in content for azure_term in ['azure', 'az', 'resource-group', 'subscription']):
            return 'azure'
        elif any(gcp_term in content for gcp_term in ['gcp', 'gcloud', 'compute', 'storage', 'bigquery']):
            return 'gcp'
        
        return None
    
    def _extract_aws_iam_requirements(self, codebundle: Dict[str, Any]) -> List[str]:
        """Extract AWS IAM requirements"""
        requirements = []
        tasks = [task.lower() for task in codebundle.get('tasks', [])]
        
        # EC2 permissions
        if any('ec2' in task for task in tasks):
            if codebundle.get('access_level') == 'read-only':
                requirements.extend(['ec2:DescribeInstances', 'ec2:DescribeInstanceStatus'])
            else:
                requirements.extend(['ec2:*'])
        
        # S3 permissions
        if any('s3' in task for task in tasks):
            if codebundle.get('access_level') == 'read-only':
                requirements.extend(['s3:GetObject', 's3:ListBucket'])
            else:
                requirements.extend(['s3:*'])
        
        # EKS permissions
        if any('eks' in task for task in tasks):
            requirements.extend(['eks:DescribeCluster', 'eks:ListClusters'])
        
        return requirements
    
    def _extract_k8s_rbac_requirements(self, codebundle: Dict[str, Any]) -> List[str]:
        """Extract Kubernetes RBAC requirements"""
        requirements = []
        tasks = [task.lower() for task in codebundle.get('tasks', [])]
        
        # Pod permissions
        if any('pod' in task for task in tasks):
            if codebundle.get('access_level') == 'read-only':
                requirements.extend(['pods:get', 'pods:list'])
            else:
                requirements.extend(['pods:*'])
        
        # Deployment permissions
        if any('deploy' in task for task in tasks):
            if codebundle.get('access_level') == 'read-only':
                requirements.extend(['deployments:get', 'deployments:list'])
            else:
                requirements.extend(['deployments:*'])
        
        # Service permissions
        if any('service' in task for task in tasks):
            requirements.extend(['services:get', 'services:list'])
        
        return requirements
    
    def _extract_azure_iam_requirements(self, codebundle: Dict[str, Any]) -> List[str]:
        """Extract Azure IAM requirements"""
        requirements = []
        tasks = [task.lower() for task in codebundle.get('tasks', [])]
        
        # Resource Group permissions
        if any('resource' in task for task in tasks):
            if codebundle.get('access_level') == 'read-only':
                requirements.extend(['Microsoft.Resources/subscriptions/resourceGroups/read'])
            else:
                requirements.extend(['Microsoft.Resources/subscriptions/resourceGroups/*'])
        
        # VM permissions
        if any('vm' in task or 'virtual' in task for task in tasks):
            requirements.extend(['Microsoft.Compute/virtualMachines/read'])
        
        return requirements
    
    def _extract_gcp_iam_requirements(self, codebundle: Dict[str, Any]) -> List[str]:
        """Extract GCP IAM requirements"""
        requirements = []
        tasks = [task.lower() for task in codebundle.get('tasks', [])]
        
        # Compute permissions
        if any('compute' in task or 'instance' in task for task in tasks):
            if codebundle.get('access_level') == 'read-only':
                requirements.extend(['compute.instances.get', 'compute.instances.list'])
            else:
                requirements.extend(['compute.instances.*'])
        
        # Storage permissions
        if any('storage' in task or 'bucket' in task for task in tasks):
            requirements.extend(['storage.objects.get', 'storage.buckets.list'])
        
        return requirements

def parse_all_robot_files(db_session) -> List[Dict[str, Any]]:
    """Parse all Robot Framework files in the database"""
    parser = RobotFrameworkParser()
    all_codebundles = []
    
    # Get all unprocessed Robot files
    robot_files = db_session.query(RawRepositoryData).filter(
        RawRepositoryData.file_type == 'robot',
        RawRepositoryData.is_processed == False
    ).all()
    
    total_files = len(robot_files)
    logger.info(f"Found {total_files} Robot files to parse")
    
    for idx, raw_file in enumerate(robot_files, 1):
        try:
            # Log progress every 50 files or if it's taking a while
            if idx % 50 == 0 or idx == 1:
                logger.info(f"Parsing file {idx}/{total_files}: {raw_file.file_path}")
            
            codebundles = parser.parse_robot_file(raw_file)
            
            # Debug logging (only first 3 files)
            if idx <= 3:
                logger.info(f"DEBUG: File {idx} returned {len(codebundles)} codebundles")
            
            all_codebundles.extend(codebundles)
            
            # Mark file as processed
            raw_file.is_processed = True
            
            # Commit every 50 files to avoid long transactions
            if idx % 50 == 0:
                db_session.commit()
                logger.info(f"Committed batch at file {idx}/{total_files}")
            
        except Exception as e:
            logger.error(f"Failed to parse file {idx}/{total_files} ({raw_file.file_path}): {e}", exc_info=True)
            # Mark as processed even if failed, so we don't retry endlessly
            raw_file.is_processed = True
            # Rollback and continue
            db_session.rollback()
            continue
    
    # Final commit for remaining files
    db_session.commit()
    
    logger.info(f"Parsed {len(all_codebundles)} total codebundles from {total_files} files")
    return all_codebundles

