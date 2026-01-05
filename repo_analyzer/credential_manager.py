"""
Credential Manager for Chainguard Libraries

Manages authentication credentials for multiple ecosystems using environment variables.
"""

import os
import logging
from typing import Optional, Tuple


class CredentialManager:
    """Manages credentials for Chainguard Libraries across multiple ecosystems."""
    
    def __init__(self):
        """Initialize credential manager and load from environment variables."""
        self.credentials = {}
        self._load_credentials()
    
    def _load_credentials(self):
        """Load credentials from environment variables."""
        ecosystems = ['python', 'java', 'javascript']
        
        for ecosystem in ecosystems:
            username_key = f'CHAINGUARD_{ecosystem.upper()}_USERNAME'
            password_key = f'CHAINGUARD_{ecosystem.upper()}_PASSWORD'
            
            username = os.getenv(username_key)
            password = os.getenv(password_key)
            
            if username and password:
                self.credentials[ecosystem] = {
                    'enabled': True,
                    'username': username,
                    'password': password
                }
                logging.info(f"Loaded {ecosystem} credentials from environment variables")
        
        if not self.credentials:
            logging.debug("No Chainguard credentials found in environment variables")
    
    def get_credentials(self, ecosystem: str) -> Optional[Tuple[str, str]]:
        """
        Get credentials for a specific ecosystem.
        
        Args:
            ecosystem: Ecosystem name (python, java, javascript)
            
        Returns:
            Tuple of (username, password) or None if not available
        """
        if ecosystem not in self.credentials:
            return None
        
        creds = self.credentials[ecosystem]
        
        # Check if ecosystem is enabled
        if not creds.get('enabled', False):
            logging.debug(f"{ecosystem} credentials are disabled")
            return None
        
        username = creds.get('username', '').strip()
        password = creds.get('password', '').strip()
        
        if not username or not password:
            logging.debug(f"{ecosystem} credentials are incomplete")
            return None
        
        return (username, password)
    
    def has_credentials(self, ecosystem: str) -> bool:
        """
        Check if credentials are available for an ecosystem.
        
        Args:
            ecosystem: Ecosystem name (python, java, javascript)
            
        Returns:
            True if valid credentials exist
        """
        return self.get_credentials(ecosystem) is not None
    
    def get_all_enabled_ecosystems(self) -> list:
        """
        Get list of all ecosystems with valid credentials.
        
        Returns:
            List of ecosystem names
        """
        return [
            ecosystem for ecosystem in self.credentials.keys()
            if self.has_credentials(ecosystem)
        ]
