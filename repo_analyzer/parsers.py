"""Dependency manifest parsers for extracting package information."""

import re
from typing import List, Tuple


def parse_python_requirements(file_path: str) -> List[Tuple[str, str]]:
    """Parse Python requirements.txt file.
    
    Returns:
        List of (package_name, version_spec) tuples
    """
    dependencies = []
    
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
                
            # Skip -r includes and other pip options
            if line.startswith('-'):
                continue
                
            # Parse package==version, package>=version, etc.
            match = re.match(r'^([a-zA-Z0-9\-_.]+)([><=~!]+.+)?$', line)
            if match:
                package = match.group(1)
                version = match.group(2) if match.group(2) else ''
                dependencies.append((package, version))
    
    return dependencies


def parse_manifest_file(file_path: str) -> List[Tuple[str, str]]:
    """Auto-detect and parse manifest file based on filename.
    
    Args:
        file_path: Path to the manifest file
        
    Returns:
        List of (package_name, version_spec) tuples
        
    Raises:
        ValueError: If file type is not supported
    """
    if file_path.endswith('requirements.txt'):
        return parse_python_requirements(file_path)
    else:
        raise ValueError(f"Unsupported manifest file type: {file_path}")