"""
Robot Framework Parser for stored repository files
"""
import re
import logging
from typing import List, Dict, Any, Optional
from app.models import RawRepositoryData

logger = logging.getLogger(__name__)

class RobotFrameworkParser:
    """Parser for Robot Framework files stored in database"""
    
    def __init__(self):
        self.current_section = None
        self.current_test = None
        self.current_keyword = None
    
    def parse_robot_file(self, raw_file: RawRepositoryData) -> List[Dict[str, Any]]:
        """Parse a Robot Framework file and extract codebundle data"""
        try:
            content = raw_file.file_content
            lines = content.split('\n')
            
            codebundles = []
            current_codebundle = None
            
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                # Detect sections
                if line.startswith('***') and line.endswith('***'):
                    section = line.replace('*', '').strip().lower()
                    self.current_section = section
                    continue
                
                # Parse test cases
                if self.current_section == 'test cases':
                    if self._is_test_case_name(line):
                        # Save previous test case
                        if current_codebundle:
                            codebundles.append(current_codebundle)
                        
                        # Start new test case
                        current_codebundle = self._create_codebundle_from_test_name(
                            line, raw_file.collection_slug, line_num
                        )
                
                # Parse keywords
                elif self.current_section == 'keywords':
                    if self._is_keyword_name(line):
                        # This is a keyword definition
                        if current_codebundle:
                            keyword = self._parse_keyword_name(line)
                            if keyword:
                                current_codebundle['tasks'].append(keyword)
                
                # Parse documentation
                elif line.startswith('[Documentation]'):
                    if current_codebundle:
                        doc_lines = self._extract_documentation(lines, line_num)
                        current_codebundle['description'] = ' '.join(doc_lines)
                        current_codebundle['doc'] = '\n'.join(doc_lines)
                
                # Parse tags
                elif line.startswith('[Tags]'):
                    if current_codebundle:
                        tags = self._extract_tags(line)
                        current_codebundle['support_tags'].extend(tags)
                
                # Parse test steps
                elif current_codebundle and self.current_section == 'test cases':
                    if line and not line.startswith('['):
                        # This is a test step
                        step = self._parse_test_step(line)
                        if step:
                            current_codebundle['tasks'].append(step)
            
            # Add the last codebundle
            if current_codebundle:
                codebundles.append(current_codebundle)
            
            logger.info(f"Parsed {len(codebundles)} codebundles from {raw_file.file_path}")
            return codebundles
            
        except Exception as e:
            logger.error(f"Error parsing Robot file {raw_file.file_path}: {e}")
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

def parse_all_robot_files(db_session) -> List[Dict[str, Any]]:
    """Parse all Robot Framework files in the database"""
    parser = RobotFrameworkParser()
    all_codebundles = []
    
    # Get all unprocessed Robot files
    robot_files = db_session.query(RawRepositoryData).filter(
        RawRepositoryData.file_type == 'robot',
        RawRepositoryData.is_processed == False
    ).all()
    
    logger.info(f"Found {len(robot_files)} Robot files to parse")
    
    for raw_file in robot_files:
        try:
            codebundles = parser.parse_robot_file(raw_file)
            all_codebundles.extend(codebundles)
            
            # Mark file as processed
            raw_file.is_processed = True
            
        except Exception as e:
            logger.error(f"Failed to parse {raw_file.file_path}: {e}")
            continue
    
    logger.info(f"Parsed {len(all_codebundles)} total codebundles")
    return all_codebundles

