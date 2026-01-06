"""
Chainguard Coverage Analysis Module

This module provides coverage analysis by checking dependencies against
Chainguard's built package repositories via HTTP scraping.
"""

import requests
import logging
import os
from html.parser import HTMLParser
from typing import Dict, List, Optional, Tuple
from packaging.version import Version
from packaging.utils import parse_wheel_filename, InvalidWheelFilename
from .credential_manager import CredentialManager


class LinksParser(HTMLParser):
    """HTML parser to extract package links from PyPI-style index pages."""
    
    def __init__(self):
        super().__init__()
        self.links = []
        self.current_link = None

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for attr_name, attr_value in attrs:
                if attr_name == 'href':
                    # Extract filename from URL (everything after last /)
                    filename = attr_value.split('/')[-1]
                    # Remove URL fragments (everything after #)
                    filename = filename.split('#')[0]
                    self.current_link = filename

    def handle_data(self, data):
        # The actual filename is in the link text, use that instead
        if self.current_link and data.strip().endswith('.whl'):
            self.links.append(data.strip())

    def handle_endtag(self, tag):
        if tag == 'a':
            self.current_link = None


class CoverageChecker:
    """Checks package coverage against Chainguard repositories."""
    
    def __init__(self, 
                 python_index_url: str = "https://libraries.cgr.dev/python/simple",
                 java_repo_url: str = "https://libraries.cgr.dev/java",
                 credential_manager: Optional[CredentialManager] = None,
                 java_username: Optional[str] = None,
                 java_password: Optional[str] = None):
        """
        Initialize coverage checker.
        
        Args:
            python_index_url: URL for Python PyPI index
            java_repo_url: URL for Java Maven repository
            credential_manager: CredentialManager instance (recommended)
            java_username: Legacy - Java username (use credential_manager instead)
            java_password: Legacy - Java password (use credential_manager instead)
        """
        self.python_index_url = python_index_url
        self.java_repo_url = java_repo_url
        
        # Initialize credential manager
        if credential_manager is None:
            credential_manager = CredentialManager()
        self.credential_manager = credential_manager
        
        # Get credentials from manager or fallback to legacy parameters
        python_creds = self.credential_manager.get_credentials('python')
        java_creds = self.credential_manager.get_credentials('java')
        
        # Python auth (try credential manager first, then .netrc)
        self.python_auth = python_creds if python_creds else None
        
        # Java auth (try credential manager, then legacy params, then env vars)
        if java_creds:
            self.java_auth = java_creds
        elif java_username and java_password:
            self.java_auth = (java_username, java_password)
        else:
            # Fallback to environment variables for backward compatibility
            env_username = os.getenv('CHAINGUARD_JAVA_USERNAME')
            env_password = os.getenv('CHAINGUARD_JAVA_PASSWORD')
            if env_username and env_password:
                self.java_auth = (env_username, env_password)
            else:
                self.java_auth = None
        
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Chainguard coverage checker"
        })
        
        # Log authentication status
        logging.info(f"Coverage checker initialized:")
        logging.info(f"  Python: {'✓ Configured' if self.python_auth else '✗ Using .netrc fallback'}")
        logging.info(f"  Java: {'✓ Configured' if self.java_auth else '✗ Not configured'}")

    def check_python_package(self, package_name: str, version: str) -> bool:
        """
        Check if a Python package version is available in Chainguard's PyPI index.
        
        Args:
            package_name: Name of the Python package
            version: Required version
            
        Returns:
            True if package version is available, False otherwise
        """
        try:
            url = f"{self.python_index_url.rstrip('/')}/{package_name}/"
            # Use explicit auth if available, otherwise fall back to .netrc
            auth = self.python_auth if self.python_auth else None
            response = self.session.get(url, auth=auth, timeout=30, allow_redirects=True)
            response.raise_for_status()
            
            parser = LinksParser()
            parser.feed(response.text)
            
            # Check if any wheel matches the required version
            for link in parser.links:
                if not link.endswith(".whl"):
                    continue
                try:
                    _, wheel_version, _, _ = parse_wheel_filename(link)
                    if str(wheel_version) == version:
                        return True
                except InvalidWheelFilename:
                    continue
                    
            return False
            
        except Exception as e:
            logging.warning(f"Error checking package {package_name}: {e}")
            return False

    def check_java_package(self, package_name: str, version: str) -> bool:
        """
        Check if a Java package version is available in Chainguard's Maven repository.
        
        Args:
            package_name: Maven groupId:artifactId (e.g., 'org.springframework:spring-core')
            version: Required version
            
        Returns:
            True if package version is available, False otherwise
        """
        if not self.java_auth:
            logging.debug(f"Java authentication not configured, skipping {package_name}")
            return False
            
        try:
            # Parse Maven coordinates
            if ':' not in package_name:
                logging.warning(f"Invalid Maven coordinate format: {package_name}")
                return False
                
            group_id, artifact_id = package_name.split(':', 1)
            
            # Convert group ID to path (e.g., org.springframework -> org/springframework)
            group_path = group_id.replace('.', '/')
            
            # Build Maven repository URL
            # Format: /java/{group_path}/{artifact_id}/{version}/
            package_url = f"{self.java_repo_url}/{group_path}/{artifact_id}/{version}/"
            
            response = self.session.get(package_url, auth=self.java_auth, timeout=30)
            
            # If we get 200, the version exists
            if response.status_code == 200:
                return True
            elif response.status_code == 404:
                return False
            else:
                logging.warning(f"Unexpected status {response.status_code} for {package_name}:{version}")
                return False
                
        except Exception as e:
            logging.warning(f"Error checking Java package {package_name}:{version}: {e}")
            return False

    def analyze_dependencies(self, dependencies: List[Dict]) -> Dict:
        """
        Analyze coverage for a list of dependencies.
        
        Args:
            dependencies: List of dependency dicts with 'name', 'version', 'ecosystem'
            
        Returns:
            Coverage analysis results
        """
        results = {
            'python': {
                'total': 0, 
                'available': 0, 
                'missing': [], 
                'percentage': 0.0
            },
            'java': {
                'total': 0, 
                'available': 0, 
                'missing': [], 
                'percentage': 0.0
            },
            'javascript': {
                'total': 0, 
                'available': 0, 
                'missing': [], 
                'percentage': 0.0
            }
        }
        
        for dep in dependencies:
            name = dep.get('name')
            version = dep.get('version')
            ecosystem = dep.get('ecosystem', 'unknown')
            
            if not name or not version or version == 'latest':
                continue
                
            if ecosystem == 'python':
                results['python']['total'] += 1
                # Clean up version format - remove extra = signs
                clean_version = version.lstrip('=')
                if self.check_python_package(name, clean_version):
                    results['python']['available'] += 1
                else:
                    results['python']['missing'].append(f"{name}=={clean_version}")
                    
            elif ecosystem == 'java':
                results['java']['total'] += 1
                if self.check_java_package(name, version):
                    results['java']['available'] += 1
                else:
                    results['java']['missing'].append(f"{name}=={version}")
                    
            elif ecosystem == 'javascript':
                results['javascript']['total'] += 1
                # TODO: Implement JavaScript/NPM checking
                results['javascript']['missing'].append(f"{name}=={version}")
        
        # Calculate percentages
        for ecosystem_data in results.values():
            total = ecosystem_data['total']
            if total > 0:
                ecosystem_data['percentage'] = round((ecosystem_data['available'] / total) * 100, 1)
            else:
                ecosystem_data['percentage'] = 0
                
        return results

    def check_adoption_indicators(self, projects: List) -> Dict[str, List[str]]:
        """
        Check for indicators that projects are already using Chainguard.
        
        This looks for Chainguard-specific configuration patterns in manifest files.
        Note: This is a heuristic check based on available data.
        
        Args:
            projects: List of ProjectAnalysis objects
            
        Returns:
            Dictionary mapping project names to adoption indicators
        """
        adoption_indicators = {}
        
        for project in projects:
            # Handle both ProjectAnalysis objects and dicts
            if hasattr(project, 'repository'):
                repo_name = project.repository.name
                manifests = project.manifests
            else:
                repo_name = project.get('repository', {}).get('name', 'unknown')
                manifests = project.get('manifests', [])
            
            indicators = []
            
            # Check for Chainguard-specific markers in manifests
            for manifest in manifests:
                # Handle both DependencyInfo objects and dicts
                if hasattr(manifest, 'file_path'):
                    file_path = manifest.file_path
                else:
                    file_path = manifest.get('file_path', '')
                
                # Look for configuration files that might indicate Chainguard usage
                if file_path in ['.npmrc', 'pip.conf', 'pip.ini', '.pypirc', 'settings.xml']:
                    indicators.append(f"Found registry config: {file_path}")
            
            if indicators:
                adoption_indicators[repo_name] = indicators
        
        return adoption_indicators
    
    def analyze_project_dependencies(self, projects: List, check_adoption: bool = False) -> Dict[str, Dict]:
        """
        Analyze all projects and check coverage for each ecosystem.
        
        Args:
            projects: List of ProjectAnalysis objects from analysis
            check_adoption: If True, also check for adoption indicators
            
        Returns:
            Dictionary with coverage statistics per ecosystem
        """
        all_dependencies = []
        
        # Check for adoption indicators if requested
        adoption_info = {}
        if check_adoption:
            adoption_info = self.check_adoption_indicators(projects)
        
        # Extract all dependencies from all projects
        for project in projects:
            # Handle both ProjectAnalysis objects and dicts
            if hasattr(project, 'manifests'):
                manifests = project.manifests
            else:
                manifests = project.get('manifests', [])
            
            for manifest in manifests:
                # Handle both DependencyInfo objects and dicts
                if hasattr(manifest, 'ecosystem'):
                    ecosystem = manifest.ecosystem
                    dependencies = manifest.dependencies
                else:
                    ecosystem = manifest.get('ecosystem')
                    dependencies = manifest.get('dependencies', [])
                
                for dep in dependencies:
                    # Ensure dep is a dict
                    if isinstance(dep, dict):
                        dep['ecosystem'] = ecosystem
                        all_dependencies.append(dep)
                    else:
                        # If dep is an object, convert to dict
                        dep_dict = {'name': dep.name, 'version': dep.version, 'ecosystem': ecosystem}
                        all_dependencies.append(dep_dict)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_dependencies = []
        for dep in all_dependencies:
            key = (dep.get('name'), dep.get('version'), dep.get('ecosystem'))
            if key not in seen:
                seen.add(key)
                unique_dependencies.append(dep)
        
        # Analyze coverage
        results = self.analyze_dependencies(unique_dependencies)
        
        # Add adoption information if requested
        if check_adoption:
            results['adoption_indicators'] = adoption_info
            
            # Log adoption summary
            if adoption_info:
                logging.info(f"Found {len(adoption_info)} projects with Chainguard adoption indicators")
        
        return results
