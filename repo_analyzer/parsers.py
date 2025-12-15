"""Dependency manifest parsers for extracting package information.

Supports Python manifest formats:
- requirements.txt (pip)
- pyproject.toml (Poetry, PEP 621)
- Pipfile (pipenv)
- setup.py (setuptools)

Supports Java manifest formats:
- pom.xml (Maven)
- build.gradle (Gradle)
"""

import re
import xml.etree.ElementTree as ET
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


def parse_pyproject_toml(file_path: str) -> List[Tuple[str, str]]:
    """Parse pyproject.toml file for dependencies (Poetry format).

    Returns:
        List of (package_name, version_spec) tuples
    """
    dependencies = []
    with open(file_path, 'r') as f:
        content = f.read()

    # Simple TOML parsing for dependencies section
    # Look for [tool.poetry.dependencies] or [project.dependencies]
    in_deps_section = False

    for line in content.split('\n'):
        line = line.strip()

        # Check if entering dependencies section
        if line in ['[tool.poetry.dependencies]', '[project.dependencies]', '[tool.poetry.dev-dependencies]']:
            in_deps_section = True
            continue
        elif line.startswith('[') and in_deps_section:
            # Exiting dependencies section
            in_deps_section = False

        # Parse dependency lines in the section
        if in_deps_section and '=' in line and not line.startswith('#'):
            match = re.match(r'^([a-zA-Z0-9\-_.]+)\s*=\s*["\']([^"\']+)["\']', line)
            if match:
                package = match.group(1)
                version = match.group(2)
                if package.lower() != 'python':  # Skip python version constraint
                    dependencies.append((package, version))

    return dependencies


def parse_pipfile(file_path: str) -> List[Tuple[str, str]]:
    """Parse Pipfile for dependencies (Pipenv format).

    Returns:
        List of (package_name, version_spec) tuples
    """
    dependencies = []
    with open(file_path, 'r') as f:
        content = f.read()

    # Parse [packages] and [dev-packages] sections
    in_packages = False

    for line in content.split('\n'):
        line = line.strip()

        if line in ['[packages]', '[dev-packages]']:
            in_packages = True
            continue
        elif line.startswith('[') and in_packages:
            in_packages = False

        if in_packages and '=' in line and not line.startswith('#'):
            match = re.match(r'^([a-zA-Z0-9\-_.]+)\s*=\s*["\']([^"\']+)["\']', line)
            if match:
                package = match.group(1)
                version = match.group(2)
                dependencies.append((package, version))

    return dependencies


def parse_setup_py(file_path: str) -> List[Tuple[str, str]]:
    """Parse setup.py file for dependencies.

    Returns:
        List of (package_name, version_spec) tuples
    """
    dependencies = []
    with open(file_path, 'r') as f:
        content = f.read()

    # Find install_requires section
    # Patterns: install_requires=['pkg>=1.0', 'pkg2'],
    #           install_requires=["pkg>=1.0"],
    match = re.search(r'install_requires\s*=\s*\[(.*?)\]', content, re.DOTALL)
    if match:
        requires_content = match.group(1)
        # Extract each requirement
        for req in re.findall(r'["\']([^"\']+)["\']', requires_content):
            # Parse package name and version
            pkg_match = re.match(r'^([a-zA-Z0-9\-_.]+)([><=~!]+.+)?$', req.strip())
            if pkg_match:
                package = pkg_match.group(1)
                version = pkg_match.group(2) if pkg_match.group(2) else ''
                dependencies.append((package, version))

    return dependencies


def parse_java_pom(file_path: str) -> List[Tuple[str, str]]:
    """Parse Java pom.xml file for dependencies.

    Returns:
        List of (groupId:artifactId, version_spec) tuples
    """
    dependencies = []
    tree = ET.parse(file_path)
    root = tree.getroot()

    # Find all dependencies
    for dep in root.findall('.//{http://maven.apache.org/POM/4.0.0}dependency'):
        group_id = dep.find('{http://maven.apache.org/POM/4.0.0}groupId')
        artifact_id = dep.find('{http://maven.apache.org/POM/4.0.0}artifactId')
        version_elem = dep.find('{http://maven.apache.org/POM/4.0.0}version')

        if group_id is not None and artifact_id is not None:
            package = f"{group_id.text}:{artifact_id.text}"
            version = version_elem.text if version_elem is not None else ''
            dependencies.append((package, version))

    return dependencies


def parse_gradle_build(file_path: str) -> List[Tuple[str, str]]:
    """Parse Gradle build.gradle or build.gradle.kts file for dependencies.

    Returns:
        List of (package_name, version_spec) tuples
    """
    dependencies = []
    with open(file_path, 'r') as f:
        content = f.read()

    # Pattern to match dependency declarations
    # Examples:
    #   implementation 'group:artifact:version'
    #   implementation "group:artifact:version"
    #   implementation('group:artifact:version')
    patterns = [
        r'(?:implementation|compile|api|testImplementation|runtimeOnly)\s*[("\']([^:"\']+):([^:"\']+):([^"\']+)["\']',
        r'(?:implementation|compile|api|testImplementation|runtimeOnly)\s*\(\s*["\']([^:"\']+):([^:"\']+):([^"\']+)["\']\s*\)',
    ]

    for pattern in patterns:
        matches = re.finditer(pattern, content)
        for match in matches:
            group_id = match.group(1)
            artifact_id = match.group(2)
            version = match.group(3)
            package = f"{group_id}:{artifact_id}"
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
    # Python manifests
    if file_path.endswith('requirements.txt'):
        return parse_python_requirements(file_path)
    elif file_path.endswith('pyproject.toml'):
        return parse_pyproject_toml(file_path)
    elif file_path.endswith('Pipfile'):
        return parse_pipfile(file_path)
    elif file_path.endswith('setup.py'):
        return parse_setup_py(file_path)
    
    # Java manifests
    elif file_path.endswith('pom.xml'):
        return parse_java_pom(file_path)
    elif file_path.endswith('build.gradle') or file_path.endswith('build.gradle.kts'):
        return parse_gradle_build(file_path)
    
    else:
        raise ValueError(f"Unsupported manifest file type: {file_path}")