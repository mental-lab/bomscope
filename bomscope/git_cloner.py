"""
Git clone operations for repository analysis.

Handles shallow cloning of repositories with authentication, an optional
persistent mirror cache (fetch deltas instead of full clones between scans),
and cleanup.
"""

import logging
import os
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse


def _sanitize_git_output(text: str, tokens=()) -> str:
    """Strip credentials from git stderr/stdout before logging."""
    if not text:
        return text
    out = text
    for tok in tokens:
        if tok:
            out = out.replace(tok, '***')
    # Also strip any creds embedded in https URLs
    return re.sub(r'(https://)[^@/\s]+@', r'\1***@', out)


class RepoCache:
    """Persistent mirror cache: keeps bare mirrors on disk so re-scans fetch
    deltas instead of full-cloning every repo.

    Layout: <cache_dir>/<host>/<owner>/<repo>.git (bare mirrors)
    """

    def __init__(self, cache_dir: str, token: Optional[str] = None):
        self.cache_dir = cache_dir
        self.token = token
        self.logger = logging.getLogger(__name__)
        self._locks: Dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def _lock_for(self, mirror: Path):
        with self._locks_guard:
            return self._locks.setdefault(str(mirror), threading.Lock())

    def _mirror_path(self, repo_url: str) -> Path:
        parsed = urlparse(repo_url)
        path = parsed.path.lstrip('/')
        if not path.endswith('.git'):
            path += '.git'
        return Path(self.cache_dir) / parsed.netloc / path

    def _auth_url(self, repo_url: str) -> str:
        if not self.token:
            return repo_url
        parsed = urlparse(repo_url)
        if parsed.scheme != 'https':
            return repo_url
        return f"{parsed.scheme}://{self.token}@{parsed.netloc}{parsed.path}"

    def sync(self, repo_url: str) -> Optional[Path]:
        """Create or update the local mirror. Returns the mirror path, or
        None if unusable (caller should fall back to a remote clone)."""
        mirror = self._mirror_path(repo_url)
        with self._lock_for(mirror):
            return self._sync_locked(repo_url, mirror)

    def _sync_locked(self, repo_url: str, mirror: Path) -> Optional[Path]:
        try:
            if not mirror.exists():
                mirror.parent.mkdir(parents=True, exist_ok=True)
                result = subprocess.run(
                    ['git', 'clone', '--mirror', '--quiet',
                     self._auth_url(repo_url), str(mirror)],
                    capture_output=True, text=True, timeout=300)
                if result.returncode != 0:
                    self.logger.warning(
                        "Mirror clone failed for %s: %s", repo_url,
                        _sanitize_git_output(result.stderr, [self.token]))
                    shutil.rmtree(mirror, ignore_errors=True)
                    return None
            else:
                # Point the existing mirror at the current auth URL, fetch, prune
                subprocess.run(
                    ['git', '-C', str(mirror), 'remote', 'set-url', 'origin',
                     self._auth_url(repo_url)],
                    capture_output=True, text=True, timeout=30)
                result = subprocess.run(
                    ['git', '-C', str(mirror), 'remote', 'update', '--prune'],
                    capture_output=True, text=True, timeout=300)
                if result.returncode != 0:
                    self.logger.warning(
                        "Mirror fetch failed for %s: %s", repo_url,
                        _sanitize_git_output(result.stderr, [self.token]))
                    return None
            return mirror
        except (subprocess.TimeoutExpired, OSError) as e:
            self.logger.warning(
                "Mirror sync failed for %s: %s", repo_url,
                _sanitize_git_output(str(e), [self.token]))
            return None


class GitCloner:
    """Manages git clone operations for dependency analysis."""
    
    def __init__(self, token: Optional[str] = None, cache: Optional['RepoCache'] = None):
        """
        Initialize git cloner.
        
        Args:
            token: Authentication token for private repositories
            cache: Optional persistent RepoCache for mirror-based scanning
        """
        self.token = token
        self.cache = cache
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
        temp_dir = None
        try:
            # Create temporary directory
            temp_dir = tempfile.mkdtemp(prefix='bomscope-')

            # Prefer the local mirror cache when available: network cost is a
            # delta fetch in sync(), and the working copy itself is a local clone.
            source = repo_url
            if self.cache:
                mirror = self.cache.sync(repo_url)
                if mirror:
                    source = mirror.as_uri()

            # Build git clone command
            cmd = [
                'git', 'clone',
                '--depth=1',           # Only latest commit
                '--single-branch',     # Only default branch
                '--quiet'              # Suppress output
            ]

            if branch:
                cmd.extend(['--branch', branch])

            # Add auth only when cloning directly from the remote
            cmd.extend([source if self.cache and source != repo_url
                        else self._add_auth_to_url(repo_url), temp_dir])

            # Execute clone
            self.logger.debug("Cloning %s to %s", repo_url, temp_dir)
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode != 0:
                self.logger.error(
                    "Git clone failed for %s: %s", repo_url,
                    _sanitize_git_output(result.stderr, [self.token]))
                self.cleanup(temp_dir)
                return None

            self.logger.debug("Successfully cloned to %s", temp_dir)
            return temp_dir

        except subprocess.TimeoutExpired:
            self.logger.error("Git clone timed out for %s", repo_url)
            if temp_dir:
                self.cleanup(temp_dir)
            return None
        except Exception as e:
            self.logger.error(
                "Git clone failed for %s: %s", repo_url,
                _sanitize_git_output(str(e), [self.token]))
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
    
    def get_remote_head(self, repo_url: str, branch: Optional[str] = None) -> Optional[str]:
        """Get the remote HEAD SHA for a branch without cloning.

        Args:
            repo_url: Repository URL
            branch: Branch to check (default: remote's default HEAD)

        Returns:
            Commit SHA string, or None if lookup failed
        """
        try:
            auth_url = self._add_auth_to_url(repo_url)
            ref = branch or 'HEAD'
            result = subprocess.run(
                ['git', 'ls-remote', auth_url, ref],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                self.logger.debug(
                    "ls-remote failed for %s: %s", repo_url,
                    _sanitize_git_output(result.stderr, [self.token]))
                return None
            line = result.stdout.strip().split('\n')[0]
            if not line:
                return None
            return line.split('\t')[0]
        except Exception as e:
            self.logger.debug(
                "ls-remote failed for %s: %s", repo_url,
                _sanitize_git_output(str(e), [self.token]))
            return None

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
