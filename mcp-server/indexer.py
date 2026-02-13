#!/usr/bin/env python3
"""
CodeCollection Indexer

Clones/updates all codecollection repositories, parses codebundles,
generates embeddings, and stores them in the vector database.

Usage:
    python indexer.py                    # Full index
    python indexer.py --local            # Use local embeddings (no API)
    python indexer.py --collection rw-cli-codecollection  # Index specific collection
"""
import os
import sys
import json
import yaml
import shutil
import logging
import argparse
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.robot_parser import RobotParser
from utils.python_parser import PythonParser, PythonModule
from utils.web_crawler import WebCrawler, create_doc_text_from_crawled
from utils.vector_store import VectorStore
from utils.embeddings import get_embedding_generator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class CodeBundle:
    """Parsed codebundle with all metadata"""
    slug: str
    collection_slug: str
    name: str
    display_name: str
    description: str
    platform: str
    author: str
    support_tags: List[str]
    tasks: List[str]
    capabilities: List[str]
    readme: str
    libraries: List[str]
    git_url: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Library:
    """Parsed Python library with documentation"""
    name: str
    module_path: str
    collection_slug: str
    description: str
    functions: List[Dict[str, str]]  # [{name, signature, docstring}]
    classes: List[Dict[str, str]]    # [{name, docstring, methods}]
    keywords: List[str]              # Robot Framework keywords
    category: str                    # cli, k8s, aws, etc.
    import_path: str                 # e.g., RW.CLI
    git_url: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CodeCollectionIndexer:
    """
    Main indexer class that orchestrates the entire indexing pipeline.
    """
    
    def __init__(
        self,
        workspace_dir: str = None,
        collections_file: str = None,
        prefer_local_embeddings: bool = False
    ):
        """
        Initialize the indexer.
        
        Args:
            workspace_dir: Directory to clone repos into
            collections_file: Path to codecollections.yaml
            prefer_local_embeddings: Use local model instead of Azure
        """
        self.base_dir = Path(__file__).parent
        
        # Workspace for cloned repos
        if workspace_dir:
            self.workspace_dir = Path(workspace_dir)
        else:
            self.workspace_dir = self.base_dir / "data" / "repos"
        
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        
        # Load codecollections config
        if collections_file:
            self.collections_file = Path(collections_file)
        else:
            # Look for codecollections.yaml in project root
            self.collections_file = self.base_dir.parent.parent / "codecollections.yaml"
        
        # Initialize components
        self.robot_parser = RobotParser()
        self.python_parser = PythonParser()
        self.vector_store = VectorStore()
        self.embedding_generator = get_embedding_generator(prefer_local=prefer_local_embeddings)
        
        logger.info(f"Indexer initialized")
        logger.info(f"  Workspace: {self.workspace_dir}")
        logger.info(f"  Collections file: {self.collections_file}")
        logger.info(f"  Embedding provider: {self.embedding_generator.provider_name}")
        logger.info(f"  Vector store: local (in-memory + JSON)")
    
    def load_collections_config(self) -> List[Dict[str, Any]]:
        """Load codecollections from YAML config"""
        try:
            with open(self.collections_file, 'r') as f:
                data = yaml.safe_load(f)
            return data.get('codecollections', [])
        except Exception as e:
            logger.error(f"Failed to load collections config: {e}")
            return []
    
    def clone_or_update_repo(self, git_url: str, slug: str) -> Optional[Path]:
        """Clone or update a git repository"""
        repo_dir = self.workspace_dir / slug
        
        try:
            if repo_dir.exists():
                # Pull latest changes
                logger.info(f"Updating {slug}...")
                result = subprocess.run(
                    ["git", "pull", "--ff-only"],
                    cwd=repo_dir,
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                if result.returncode != 0:
                    logger.warning(f"Git pull failed for {slug}, re-cloning...")
                    shutil.rmtree(repo_dir)
                    return self._clone_repo(git_url, repo_dir, slug)
            else:
                return self._clone_repo(git_url, repo_dir, slug)
            
            return repo_dir
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout while updating {slug}")
            return None
        except Exception as e:
            logger.error(f"Error updating {slug}: {e}")
            return None
    
    def _clone_repo(self, git_url: str, repo_dir: Path, slug: str) -> Optional[Path]:
        """Clone a repository"""
        logger.info(f"Cloning {slug}...")
        try:
            result = subprocess.run(
                ["git", "clone", "--depth", "1", git_url, str(repo_dir)],
                capture_output=True,
                text=True,
                timeout=300
            )
            if result.returncode != 0:
                logger.error(f"Git clone failed for {slug}: {result.stderr}")
                return None
            return repo_dir
        except Exception as e:
            logger.error(f"Clone failed for {slug}: {e}")
            return None
    
    def parse_codebundle(
        self,
        bundle_dir: Path,
        collection_slug: str,
        collection_git_url: str
    ) -> Optional[CodeBundle]:
        """Parse a single codebundle directory"""
        # Use collection-prefixed slug to match registry format
        # Registry uses: {collection_slug}-{codebundle_dir}
        codebundle_dir = bundle_dir.name
        slug = f"{collection_slug}-{codebundle_dir}".lower().replace(' ', '-').replace('_', '-')
        
        try:
            # Parse meta.yaml if exists
            meta = {}
            meta_file = bundle_dir / "meta.yaml"
            if meta_file.exists():
                with open(meta_file, 'r') as f:
                    meta = yaml.safe_load(f) or {}
            
            # Parse README.md if exists
            readme = ""
            readme_file = bundle_dir / "README.md"
            if readme_file.exists():
                readme = readme_file.read_text(encoding='utf-8', errors='ignore')
            
            # Parse all robot files
            tasks = []
            capabilities = []
            libraries = set()
            author = meta.get('author', '')
            display_name = meta.get('display_name', codebundle_dir)
            
            for robot_file in bundle_dir.glob("*.robot"):
                parsed = self.robot_parser.parse_file(str(robot_file))
                if parsed:
                    # Extract author from metadata
                    if not author and parsed.metadata.get('Author'):
                        author = parsed.metadata['Author']
                    
                    # Extract display name
                    if parsed.metadata.get('Display Name'):
                        display_name = parsed.metadata['Display Name']
                    
                    # Collect tasks
                    for task in parsed.tasks:
                        tasks.append(task.name)
                        if task.documentation:
                            capabilities.append(f"{task.name}: {task.documentation}")
                    
                    # Collect libraries
                    libraries.update(parsed.libraries)
            
            # Extract tags from meta.yaml or infer from path
            support_tags = meta.get('support_tags', [])
            if not support_tags:
                # Infer from slug
                parts = slug.split('-')
                if parts:
                    support_tags = [parts[0]]  # e.g., 'k8s', 'aws', 'azure'
            
            # Determine platform from slug or tags
            platform = "Unknown"
            slug_lower = slug.lower()
            if 'k8s' in slug_lower or 'kubernetes' in slug_lower:
                platform = "Kubernetes"
            elif 'aws' in slug_lower:
                platform = "AWS"
            elif 'azure' in slug_lower:
                platform = "Azure"
            elif 'gcp' in slug_lower:
                platform = "GCP"
            elif 'linux' in slug_lower:
                platform = "Linux"
            elif 'postgres' in slug_lower or 'redis' in slug_lower or 'mongo' in slug_lower:
                platform = "Database"
            
            # Build description
            description = meta.get('description', '')
            if not description and readme:
                # Extract first paragraph from README
                lines = readme.split('\n')
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('#') and not line.startswith('!'):
                        description = line[:500]
                        break
            
            return CodeBundle(
                slug=slug,  # Collection-prefixed slug to match registry
                collection_slug=collection_slug,
                name=codebundle_dir,  # Simple directory name
                display_name=display_name,
                description=description,
                platform=platform,
                author=author,
                support_tags=support_tags,
                tasks=tasks,
                capabilities=capabilities,
                readme=readme[:5000],  # Limit readme size
                libraries=list(libraries),
                git_url=f"{collection_git_url}/tree/main/codebundles/{codebundle_dir}"  # GitHub uses directory name
            )
        except Exception as e:
            logger.error(f"Error parsing codebundle {slug}: {e}")
            return None
    
    def parse_library(
        self,
        py_file: Path,
        collection_slug: str,
        collection_git_url: str,
        import_base: str
    ) -> Optional[Library]:
        """Parse a single Python library file"""
        try:
            module = self.python_parser.parse_file(str(py_file))
            if not module:
                return None
            
            # Skip __init__ files with minimal content
            if module.name == '__init__' and not module.functions and not module.classes:
                return None
            
            # Build import path (e.g., RW.CLI.CLI)
            rel_path = py_file.relative_to(py_file.parents[len(import_base.split('.')) - 1])
            import_path = str(rel_path.with_suffix('')).replace('/', '.').replace('\\', '.')
            
            # Determine category from path
            category = "general"
            path_lower = str(py_file).lower()
            if '/cli/' in path_lower or 'cli.py' in path_lower:
                category = "cli"
            elif '/k8s/' in path_lower or 'kubectl' in path_lower:
                category = "kubernetes"
            elif '/aws/' in path_lower:
                category = "aws"
            elif '/azure/' in path_lower:
                category = "azure"
            elif '/gcp/' in path_lower:
                category = "gcp"
            elif '/prometheus/' in path_lower:
                category = "prometheus"
            elif '/postgres/' in path_lower or '/redis/' in path_lower:
                category = "database"
            
            # Extract function info
            functions = []
            for func in module.functions:
                if not func.name.startswith('_'):
                    functions.append({
                        'name': func.name,
                        'signature': func.signature,
                        'docstring': func.docstring[:500] if func.docstring else ''
                    })
            
            # Extract class info
            classes = []
            for cls in module.classes:
                methods = [m.name for m in cls.methods if not m.name.startswith('_')]
                classes.append({
                    'name': cls.name,
                    'docstring': cls.docstring[:500] if cls.docstring else '',
                    'methods': ', '.join(methods[:20])
                })
            
            # Get keywords
            keywords = self.python_parser.extract_keywords(module)
            
            # Build description
            description = module.docstring or ''
            if not description and functions:
                # Use first function's docstring
                description = functions[0].get('docstring', '')
            
            return Library(
                name=module.name,
                module_path=str(py_file),
                collection_slug=collection_slug,
                description=description[:1000],
                functions=functions[:50],  # Limit
                classes=classes[:20],
                keywords=keywords[:30],
                category=category,
                import_path=import_path,
                git_url=f"{collection_git_url}/tree/main/libraries/{import_path.replace('.', '/')}.py"
            )
        except Exception as e:
            logger.error(f"Error parsing library {py_file}: {e}")
            return None
    
    def index_collection(self, collection: Dict[str, Any]) -> tuple[List[CodeBundle], List[Library]]:
        """Index a single codecollection (codebundles and libraries)"""
        slug = collection['slug']
        git_url = collection['git_url']
        
        logger.info(f"Indexing collection: {slug}")
        
        # Clone/update repo
        repo_dir = self.clone_or_update_repo(git_url, slug)
        if not repo_dir:
            return [], []
        
        codebundles = []
        libraries = []
        
        # Parse codebundles
        codebundles_dir = repo_dir / "codebundles"
        if codebundles_dir.exists():
            for bundle_dir in codebundles_dir.iterdir():
                if bundle_dir.is_dir() and not bundle_dir.name.startswith('.'):
                    cb = self.parse_codebundle(bundle_dir, slug, git_url)
                    if cb:
                        codebundles.append(cb)
        
        # Parse libraries
        libraries_dir = repo_dir / "libraries"
        if libraries_dir.exists():
            for py_file in libraries_dir.rglob("*.py"):
                if '__pycache__' not in str(py_file) and not py_file.name.startswith('_test'):
                    lib = self.parse_library(py_file, slug, git_url, "RW")
                    if lib:
                        libraries.append(lib)
        
        logger.info(f"  Found {len(codebundles)} codebundles, {len(libraries)} libraries in {slug}")
        return codebundles, libraries
    
    def run(self, collection_filter: str = None):
        """
        Run the full indexing pipeline.
        
        Args:
            collection_filter: Optional slug to index only one collection
        """
        start_time = datetime.now()
        logger.info("=" * 60)
        logger.info("Starting CodeCollection Indexer")
        logger.info("=" * 60)
        
        # Load collections config
        collections = self.load_collections_config()
        if not collections:
            logger.error("No collections found in config")
            return
        
        logger.info(f"Found {len(collections)} codecollections in config")
        
        # Filter if specified
        if collection_filter:
            collections = [c for c in collections if c['slug'] == collection_filter]
            if not collections:
                logger.error(f"Collection not found: {collection_filter}")
                return
        
        # Index all collections
        all_codebundles: List[CodeBundle] = []
        all_libraries: List[Library] = []
        for collection in collections:
            codebundles, libraries = self.index_collection(collection)
            all_codebundles.extend(codebundles)
            all_libraries.extend(libraries)
        
        logger.info(f"Total codebundles parsed: {len(all_codebundles)}")
        logger.info(f"Total libraries parsed: {len(all_libraries)}")
        
        if not all_codebundles and not all_libraries:
            logger.warning("No codebundles or libraries to index")
            return
        
        # Generate embeddings
        logger.info("Generating embeddings...")
        
        # Create document texts for codebundle embedding
        cb_documents = []
        for cb in all_codebundles:
            doc = self._create_embedding_document(cb)
            cb_documents.append(doc)
        
        # Create document texts for library embedding
        lib_documents = []
        for lib in all_libraries:
            doc = self._create_library_document(lib)
            lib_documents.append(doc)
        
        # Generate codebundle embeddings
        cb_embeddings = []
        if cb_documents:
            cb_embeddings = self.embedding_generator.embed_texts(cb_documents)
            if not cb_embeddings or not cb_embeddings[0]:
                logger.error("Failed to generate codebundle embeddings")
                cb_embeddings = []
            else:
                logger.info(f"Generated {len(cb_embeddings)} codebundle embeddings")
        
        # Generate library embeddings
        lib_embeddings = []
        if lib_documents:
            lib_embeddings = self.embedding_generator.embed_texts(lib_documents)
            if not lib_embeddings or not lib_embeddings[0]:
                logger.error("Failed to generate library embeddings")
                lib_embeddings = []
            else:
                logger.info(f"Generated {len(lib_embeddings)} library embeddings")
        
        # Store in vector database
        logger.info("Storing in vector database...")
        
        if cb_embeddings:
            codebundle_dicts = [cb.to_dict() for cb in all_codebundles]
            self.vector_store.add_codebundles(codebundle_dicts, cb_embeddings)
        
        if lib_embeddings:
            library_dicts = [lib.to_dict() for lib in all_libraries]
            self.vector_store.add_libraries(library_dicts, lib_embeddings)
        
        # Also store codecollections
        collection_docs = []
        for cc in collections:
            doc = f"{cc['name']} - {cc.get('description', '')}"
            collection_docs.append(doc)
        
        if collection_docs:
            cc_embeddings = self.embedding_generator.embed_texts(collection_docs)
            self.vector_store.add_codecollections(collections, cc_embeddings)
        
        # Save codebundles JSON for fallback
        output_file = self.base_dir / "data" / "codebundles.json"
        codebundle_dicts = [cb.to_dict() for cb in all_codebundles]
        with open(output_file, 'w') as f:
            json.dump({"codebundles": codebundle_dicts}, f, indent=2)
        
        # Save libraries JSON for fallback
        libraries_file = self.base_dir / "data" / "libraries.json"
        library_dicts = [lib.to_dict() for lib in all_libraries]
        with open(libraries_file, 'w') as f:
            json.dump({"libraries": library_dicts}, f, indent=2)
        
        # Save collections JSON
        collections_file = self.base_dir / "data" / "codecollections.json"
        with open(collections_file, 'w') as f:
            json.dump({"codecollections": collections}, f, indent=2)
        
        # Print summary
        elapsed = datetime.now() - start_time
        stats = self.vector_store.get_stats()
        
        logger.info("=" * 60)
        logger.info("Indexing Complete!")
        logger.info("=" * 60)
        logger.info(f"  Time elapsed: {elapsed}")
        logger.info(f"  Codebundles indexed: {stats.get('codebundles', 0)}")
        logger.info(f"  Codecollections indexed: {stats.get('codecollections', 0)}")
        logger.info(f"  Libraries indexed: {stats.get('libraries', 0)}")
        logger.info(f"  Output: {output_file}")
    
    def _create_embedding_document(self, cb: CodeBundle) -> str:
        """Create a rich document for embedding - includes detailed task info for better search"""
        parts = [
            f"Name: {cb.display_name}",
            f"Slug: {cb.slug}",
        ]
        
        if cb.description:
            parts.append(f"Description: {cb.description}")
        
        if cb.platform:
            parts.append(f"Platform: {cb.platform}")
        
        if cb.support_tags:
            parts.append(f"Tags: {', '.join(cb.support_tags)}")
        
        # Include ALL capabilities (task names with documentation) - critical for search
        # This is what users are actually searching for
        if cb.capabilities:
            parts.append("Tasks and Capabilities:")
            for cap in cb.capabilities[:20]:  # Increased from 5 to 20
                parts.append(f"  - {cap}")
        elif cb.tasks:
            # Fallback to just task names if no capabilities
            parts.append(f"Tasks: {', '.join(cb.tasks[:15])}")
        
        if cb.readme:
            # Include truncated readme for additional context
            parts.append(f"Documentation: {cb.readme[:2000]}")
        
        return "\n".join(parts)
    
    def _create_library_document(self, lib: Library) -> str:
        """Create a rich document for library embedding"""
        parts = [
            f"Library: {lib.name}",
            f"Import: {lib.import_path}",
            f"Category: {lib.category}",
        ]
        
        if lib.description:
            parts.append(f"Description: {lib.description}")
        
        # Add function signatures and docstrings
        if lib.functions:
            parts.append("Functions:")
            for func in lib.functions[:15]:
                func_text = f"  - {func['signature']}"
                if func.get('docstring'):
                    func_text += f"\n    {func['docstring'][:200]}"
                parts.append(func_text)
        
        # Add class info
        if lib.classes:
            parts.append("Classes:")
            for cls in lib.classes[:10]:
                cls_text = f"  - {cls['name']}"
                if cls.get('docstring'):
                    cls_text += f": {cls['docstring'][:150]}"
                if cls.get('methods'):
                    cls_text += f"\n    Methods: {cls['methods']}"
                parts.append(cls_text)
        
        # Add keywords (for Robot Framework)
        if lib.keywords:
            parts.append(f"Robot Keywords: {', '.join(lib.keywords[:20])}")
        
        return "\n".join(parts)


    def load_documentation_sources(self, crawl_content: bool = True) -> List[Dict[str, Any]]:
        """
        Load documentation sources from sources.yaml.
        
        Args:
            crawl_content: If True, fetch actual content from URLs
        """
        sources_file = self.base_dir / "sources.yaml"
        if not sources_file.exists():
            logger.info("No sources.yaml found, skipping documentation indexing")
            return []
        
        try:
            with open(sources_file, 'r') as f:
                data = yaml.safe_load(f)
            
            sources = data.get('sources', {})
            index_config = data.get('index_config', {})
            all_docs = []
            
            # Flatten all source categories
            for category, items in sources.items():
                if isinstance(items, list):
                    for item in items:
                        item['category'] = category
                        all_docs.append(item)
            
            # Optionally crawl URLs to get actual content
            if crawl_content and index_config.get('crawl_linked_pages', True):
                crawler = WebCrawler()
                if crawler.is_available():
                    logger.info(f"Web crawling enabled ({crawler.backend}) - fetching documentation content...")
                    for doc in all_docs:
                        url = doc.get('url')
                        if url and url.startswith('http'):
                            try:
                                crawled = crawler.crawl_url(url)
                                if crawled:
                                    # Store crawled content in the doc
                                    doc['crawled_content'] = crawled.get('content', '')[:15000]
                                    doc['crawled_title'] = crawled.get('title', '')
                                    doc['crawled_code'] = crawled.get('code_blocks', [])[:5]
                                    doc['crawled_headings'] = [h['text'] for h in crawled.get('headings', [])]
                            except Exception as e:
                                logger.warning(f"Failed to crawl {url}: {e}")
                else:
                    logger.info("Web crawling unavailable (install crawl4ai or beautifulsoup4)")
            
            return all_docs
        except Exception as e:
            logger.error(f"Failed to load sources.yaml: {e}")
            return []
    
    def index_documentation(self, crawl_content: bool = True):
        """
        Index documentation sources.
        
        Args:
            crawl_content: If True, fetch actual content from URLs (recommended)
        """
        docs = self.load_documentation_sources(crawl_content=crawl_content)
        if not docs:
            return
        
        logger.info(f"Indexing {len(docs)} documentation sources...")
        
        # Create documents for embedding
        doc_texts = []
        for doc in docs:
            parts = [
                doc.get('name', doc.get('question', '')),
                doc.get('description', doc.get('answer', '')),
            ]
            
            # Use crawled content if available (much richer for semantic search)
            if doc.get('crawled_content'):
                # Crawled content is the primary source
                parts.append(doc['crawled_content'][:8000])
                if doc.get('crawled_headings'):
                    parts.append(f"Sections: {', '.join(doc['crawled_headings'][:15])}")
                if doc.get('crawled_code'):
                    parts.append(f"Code: {' '.join(doc['crawled_code'][:3])[:2000]}")
            else:
                # Fall back to metadata from sources.yaml
                if doc.get('topics'):
                    parts.append(f"Topics: {', '.join(doc['topics'])}")
                if doc.get('key_points'):
                    parts.append(f"Key points: {', '.join(doc['key_points'])}")
                if doc.get('usage_examples'):
                    parts.append(f"Examples: {', '.join(doc['usage_examples'])}")
            
            doc_texts.append(" ".join(parts))
        
        # Generate embeddings
        embeddings = self.embedding_generator.embed_texts(doc_texts)
        if not embeddings:
            logger.error("Failed to generate documentation embeddings")
            return
        
        # Store in vector database
        self.vector_store.add_documentation(docs, embeddings)
        logger.info(f"Indexed {len(docs)} documentation sources")


def main():
    parser = argparse.ArgumentParser(
        description="Index codecollections for semantic search"
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Use local embeddings instead of Azure OpenAI"
    )
    parser.add_argument(
        "--collection",
        type=str,
        help="Index only a specific collection by slug"
    )
    parser.add_argument(
        "--workspace",
        type=str,
        help="Directory to clone repos into"
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to codecollections.yaml"
    )
    parser.add_argument(
        "--docs-only",
        action="store_true",
        help="Only index documentation sources (skip codebundles)"
    )
    
    args = parser.parse_args()
    
    indexer = CodeCollectionIndexer(
        workspace_dir=args.workspace,
        collections_file=args.config,
        prefer_local_embeddings=args.local
    )
    
    if args.docs_only:
        indexer.index_documentation()
    else:
        indexer.run(collection_filter=args.collection)
        # Also index documentation
        indexer.index_documentation()


if __name__ == "__main__":
    main()

