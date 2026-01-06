"""
Git clone operations for repository analysis.

Handles shallow cloning of repositories with authentication and cleanup.
"""

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse


class GitCloner:
    """Manages git clone operations for dependency analysis."""
    
    def __init__(self, token: Optional[str] = None):
        """
        Initialize git cloner.
        
        Args:
            token: Authentication token for private repositories
        """
        self.token = token
        self.logger = logging.getLogger(__name__)
    
    def shallow_clone(self, repo_url: str, branch: Optional[str] = None) -> Optional[str]:
        """
        Perform a shallow clone of a repository.
        
        Args:
            repo_url: Repository URL (https://github.com/org/repo.git)
            branch: Specific branch to clone (default: repository default branch)
            
        Returns:
            Path to cloned repository, or None if clone failed
        """
        try:
            # Create temporary directory
            temp_dir = tempfile.mkdtemp(prefix='ecosystems-evaluate-')
            
            # Add authentication token to URL if provided
            auth_url = self._add_auth_to_url(repo_url)
            
            # Build git clone command
            cmd = [
                'git', 'clone',
                '--depth=1',           # Only latest commit
                '--single-branch',     # Only default branch
                '--quiet'              # Suppress output
            ]
            
            if branch:
                cmd.extend(['--branch', branch])
            
            cmd.extend([auth_url, temp_dir])
            
            # Execute clone
            self.logger.debug(f"Cloning {repo_url} to {temp_dir}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60  # 60 second timeout
            )
            
            if result.returncode != 0:
                self.logger.error(f"Git clone failed: {result.stderr}")
                self.cleanup(temp_dir)
                return None
            
            self.logger.debug(f"Successfully cloned to {temp_dir}")
            return temp_dir
            
        except subprocess.TimeoutExpired:
            self.logger.error(f"Git clone timed out for {repo_url}")
            if temp_dir:
                self.cleanup(temp_dir)
            return None
        except Exception as e:
            self.logger.error(f"Git clone failed: {e}")
            if temp_dir:
                self.cleanup(temp_dir)
            return None
    
    def _add_auth_to_url(self, repo_url: str) -> str:
        """
        Add authentication token to repository URL.
        
        Args:
            repo_url: Original repository URL
            
        Returns:
            URL with authentication token embedded
        """
        if not self.token:
            return repo_url
        
        # Parse URL
        parsed = urlparse(repo_url)
        
        # Only add token for HTTPS URLs
        if parsed.scheme != 'https':
            return repo_url
        
        # Reconstruct URL with token
        # Format: https://token@github.com/org/repo.git
        auth_url = f"{parsed.scheme}://{self.token}@{parsed.netloc}{parsed.path}"
        
        return auth_url
    
    def cleanup(self, clone_path: str) -> None:
        """
        Remove cloned repository directory.
        
        Args:
            clone_path: Path to cloned repository
        """
        try:
            if clone_path and os.path.exists(clone_path):
                shutil.rmtree(clone_path)
                self.logger.debug(f"Cleaned up {clone_path}")
        except Exception as e:
            self.logger.warning(f"Failed to cleanup {clone_path}: {e}")
    
    def check_git_available(self) -> bool:
        """
        Check if git is installed and available.
        
        Returns:
            True if git is available, False otherwise
        """
        try:
            result = subprocess.run(
                ['git', '--version'],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
