"""
Platform-specific analyzers for dependency extraction across GitLab, GitHub, and Azure DevOps.
"""

import os
import re
import requests
import time
import threading
from typing import Dict, List, Optional
import logging
from abc import ABC, abstractmethod
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib3.exceptions import InsecureRequestWarning
from urllib3 import disable_warnings
from .models import RepositoryInfo, DependencyInfo

from .parsers import parse_manifest_file



class PlatformAnalyzer(ABC):
    """Abstract base class for platform-specific analyzers."""
    
    # Class-level rate limit tracking (shared across all instances)
    _rate_limit_lock = threading.Lock()
    _rate_limit_remaining = None
    _rate_limit_reset = None
    _last_request_time = 0
    _request_delay = 0.1  # 100ms delay between requests
    
    def __init__(self, source_url: str, token: str, ssl_verify: bool = True):
        self.source_url = source_url.rstrip('/')
        self.token = token
        
        # Create persistent session with retry logic
        self.session = requests.Session()
        self.session.verify = ssl_verify
        
        # Handle SSL verification warnings
        if not ssl_verify:
            print("Ignoring SSL verification")
            disable_warnings(InsecureRequestWarning)
        
        # Add retry logic for transient failures
        retries = Retry(
            total=2,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504, 429]
        )
        self.session.mount('http://', HTTPAdapter(max_retries=retries))
        self.session.mount('https://', HTTPAdapter(max_retries=retries))
        
        # Set up authentication headers
        self.session.headers.update(self._get_auth_headers())
    
    @abstractmethod
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for the platform."""
        pass
    
    def _throttle_request(self) -> None:
        """Throttle requests to avoid rate limiting."""
        with self._rate_limit_lock:
            current_time = time.time()
            time_since_last = current_time - self._last_request_time
            
            if time_since_last < self._request_delay:
                sleep_time = self._request_delay - time_since_last
                time.sleep(sleep_time)
            
            self._last_request_time = time.time()
    
    def _update_rate_limit_info(self, headers: dict) -> None:
        """Update global rate limit information from response headers."""
        with self._rate_limit_lock:
            # GitHub rate limiting
            if 'X-RateLimit-Remaining' in headers:
                self._rate_limit_remaining = int(headers.get('X-RateLimit-Remaining', 0))
                self._rate_limit_reset = int(headers.get('X-RateLimit-Reset', 0))
            # GitLab rate limiting
            elif 'RateLimit-Remaining' in headers:
                self._rate_limit_remaining = int(headers.get('RateLimit-Remaining', 0))
                reset_time = headers.get('RateLimit-ResetTime')
                if reset_time:
                    self._rate_limit_reset = int(reset_time)
    
    def _handle_rate_limiting(self, headers: dict, platform: str = "generic") -> None:
        """Handle platform rate limiting with intelligent throttling."""
        # Update global rate limit info
        self._update_rate_limit_info(headers)
        
        # GitHub rate limiting
        if 'X-RateLimit-Remaining' in headers:
            remaining = int(headers.get('X-RateLimit-Remaining', 100))
            
            # More aggressive threshold - wait when < 100 requests remaining
            if remaining < 100:
                reset_time = headers.get('X-RateLimit-Reset')
                if reset_time:
                    wait_time = max(1, int(reset_time) - int(time.time()))
                    logging.warning(f"{platform} rate limit low ({remaining} remaining), waiting {wait_time} seconds until reset")
                    time.sleep(wait_time)
            # Warn when getting low
            elif remaining < 500:
                logging.info(f"{platform} rate limit: {remaining} requests remaining")
        
        # GitLab rate limiting (RateLimit-Remaining header)
        elif 'RateLimit-Remaining' in headers:
            remaining = int(headers.get('RateLimit-Remaining', 100))
            if remaining < 100:
                reset_time = headers.get('RateLimit-ResetTime')
                if reset_time:
                    wait_time = max(1, int(reset_time) - int(time.time()))
                    logging.warning(f"{platform} rate limit low ({remaining} remaining), waiting {wait_time} seconds until reset")
                    time.sleep(wait_time)
            elif remaining < 500:
                logging.info(f"{platform} rate limit: {remaining} requests remaining")
    
    def check_rate_limit_status(self) -> Dict[str, any]:
        """Check current rate limit status."""
        with self._rate_limit_lock:
            if self._rate_limit_remaining is not None:
                return {
                    'remaining': self._rate_limit_remaining,
                    'reset': self._rate_limit_reset,
                    'reset_in': max(0, self._rate_limit_reset - int(time.time())) if self._rate_limit_reset else None
                }
        return {}
    
    @abstractmethod
    def get_repositories(self, org_name: str) -> List[RepositoryInfo]:
        """Get all repositories in an organization."""
        pass
    
    @abstractmethod
    def get_single_repository(self, repo_spec: str) -> RepositoryInfo:
        """Get information for a single repository."""
        pass
    
    @abstractmethod
    def get_file_content(self, repo_info: RepositoryInfo, file_path: str) -> Optional[str]:
        """Get file content from repository."""
        pass
    
    def discover_manifests(self, repo_info: RepositoryInfo) -> List[DependencyInfo]:
        """Discover dependency manifests in a repository."""
        manifests = []
        
        # Common manifest files to look for (Java, Python, JavaScript only)
        manifest_files = [
            'requirements.txt', 'pyproject.toml', 'setup.py', 'Pipfile',  # Python
            'pom.xml', 'build.gradle', 'build.gradle.kts',     # Java
            'package.json', 'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml',  # JavaScript
        ]
        
        for manifest_file in manifest_files:
            try:
                file_content = self.get_file_content(repo_info, manifest_file)
                if file_content:
                    dependencies = self._parse_manifest_content(manifest_file, file_content)
                    if dependencies:
                        ecosystem = self._determine_ecosystem_from_file(manifest_file)
                        manifests.append(DependencyInfo(
                            file_path=manifest_file,
                            file_type=self._get_file_type(manifest_file),
                            ecosystem=ecosystem,
                            dependencies=dependencies,
                            build_tool=self._determine_build_tool(manifest_file)
                        ))
            except Exception as e:
                # File doesn't exist or can't be parsed
                logging.debug(f"Could not process {manifest_file} in {repo_info.name}: {e}")
                continue
        
        return manifests
    
    def _parse_manifest_content(self, file_name: str, content: str) -> List[Dict[str, str]]:
        """Parse manifest content to extract dependencies."""
        try:
            # Validate inputs
            if not file_name or not content:
                return []
            
            # Sanitize filename - only allow safe characters
            import re
            safe_filename = re.sub(r'[^a-zA-Z0-9._-]', '_', file_name)
            
            # Limit content size to prevent DoS attacks
            MAX_CONTENT_SIZE = 10 * 1024 * 1024  # 10MB limit
            if len(content) > MAX_CONTENT_SIZE:
                logging.warning(f"Content too large for {safe_filename}: {len(content)} bytes")
                return []
            
            # Use secure temporary file with automatic cleanup
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix=f'_{safe_filename}', delete=True) as tmp:
                tmp.write(content)
                tmp.flush()
                
                # Use existing parser
                dependencies = parse_manifest_file(tmp.name)
                
                # Convert to dict format
                return [{"name": name, "version": version} for name, version in dependencies]
                # File automatically deleted when context exits
                
        except Exception as e:
            logging.debug(f"Failed to parse {safe_filename}: {e}")
            return []
    
    def _determine_ecosystem_from_file(self, file_name: str) -> str:
        """Determine ecosystem from file name."""
        ecosystem_map = {
            'requirements.txt': 'python', 'pyproject.toml': 'python', 'setup.py': 'python', 'Pipfile': 'python',
            'pom.xml': 'java', 'build.gradle': 'java', 'build.gradle.kts': 'java',
            'package.json': 'javascript', 'package-lock.json': 'javascript', 'yarn.lock': 'javascript', 'pnpm-lock.yaml': 'javascript',
        }
        return ecosystem_map.get(file_name, 'unknown')
    
    def _get_file_type(self, file_name: str) -> str:
        """Get file type from file name."""
        if file_name.endswith('.json'):
            return 'json'
        elif file_name.endswith('.xml'):
            return 'xml'
        elif file_name.endswith('.toml'):
            return 'toml'
        elif file_name.endswith(('.yaml', '.yml')):
            return 'yaml'
        elif file_name.endswith('.lock'):
            return 'lock'
        else:
            return 'text'
    
    def _determine_build_tool(self, file_name: str) -> Optional[str]:
        """Determine build tool from file name."""
        build_tools = {
            'requirements.txt': 'pip', 'pyproject.toml': 'poetry', 'setup.py': 'setuptools', 'Pipfile': 'pipenv',
            'pom.xml': 'maven', 'build.gradle': 'gradle', 'build.gradle.kts': 'gradle',
            'package.json': 'npm', 'package-lock.json': 'npm', 'yarn.lock': 'yarn', 'pnpm-lock.yaml': 'pnpm',
        }
        return build_tools.get(file_name)






def get_analyzer(platform: str, source_url: str, token: str) -> PlatformAnalyzer:
    """Factory function to get the appropriate analyzer for a platform."""
    # Import analyzers locally to avoid circular imports
    from .gitlab_analyzer import GitLabAnalyzer
    from .github_analyzer import GitHubAnalyzer
    from .azure_devops_analyzer import AzureDevOpsAnalyzer
    
    analyzers = {
        'gitlab': GitLabAnalyzer,
        'github': GitHubAnalyzer,
        'ado': AzureDevOpsAnalyzer
    }
    
    analyzer_class = analyzers.get(platform.lower())
    if not analyzer_class:
        raise ValueError(f"Unsupported platform: {platform}")
    
    return analyzer_class(source_url, token)
