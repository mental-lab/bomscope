"""
Dockerfile analyzer for detecting trusted base-image adoption.

Scans Dockerfiles to identify base images, detect usage of trusted
registries (user-configured), and flag floating/unpinned base tags.
Version-level EOL status lives in eol_checker (endoflife.date).
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional


class DockerfileAnalyzer:
    """Analyzes Dockerfiles to detect trusted base-image adoption.

    EOL determination is the job of eol_checker (endoflife.date, always on) —
    a static regex list here would silently drift out of date. The risky-image
    heuristics below only cover what the EOL API cannot express: floating
    versions (`:latest`, untagged).
    """

    def __init__(self, trusted_registries: Optional[List[str]] = None):
        """Initialize Dockerfile analyzer.

        Args:
            trusted_registries: Registry/repo patterns treated as trusted
                sources (regex). Images matching these are counted as
                'adopted' and exempt from risky-image heuristics.
                No vendor is trusted by default — configure via
                --trusted-registries or TRUSTED_REGISTRIES.
        """
        self.logger = logging.getLogger(__name__)
        self.trusted_patterns = [
            re.compile(p, re.IGNORECASE)
            for p in (trusted_registries or [])
        ]
    
    def analyze_repository(self, repo_path: str) -> Dict[str, any]:
        """
        Scan repository for Dockerfiles and analyze base images.
        
        Args:
            repo_path: Path to cloned repository
            
        Returns:
            Dictionary with Dockerfile analysis results:
            {
                'dockerfiles_found': 3,
                'trusted_images': ['cgr.dev/example/python:latest'],
                'other_images': ['ubuntu:22.04'],
                'adoption_detected': True
            }
        """
        results = {
            'dockerfiles_found': 0,
            'trusted_images': [],
            'other_images': [],
            'risky_images': [],  # List of {image, file, reason}
            'adoption_detected': False,
            'dockerfiles': []  # List of {path, trusted_images, other_images, risky_images}
        }
        
        # Find all Dockerfiles
        dockerfiles = self._find_dockerfiles(repo_path)
        results['dockerfiles_found'] = len(dockerfiles)
        
        if not dockerfiles:
            return results
        
        repo = Path(repo_path)
        
        # Analyze each Dockerfile
        for dockerfile_path in dockerfiles:
            images = self._parse_dockerfile(dockerfile_path)
            
            dockerfile_info = {
                'path': str(dockerfile_path.relative_to(repo)),
                'trusted_images': [],
                'other_images': [],
                'risky_images': []
            }

            for image in images:
                if self._is_trusted_image(image):
                    results['trusted_images'].append(image)
                    dockerfile_info['trusted_images'].append(image)
                    results['adoption_detected'] = True
                else:
                    results['other_images'].append(image)
                    dockerfile_info['other_images'].append(image)

                risk = self._assess_image_risk(image)
                if risk:
                    entry = {
                        'image': image,
                        'file': dockerfile_info['path'],
                        'reason': risk
                    }
                    results['risky_images'].append(entry)
                    dockerfile_info['risky_images'].append(entry)
            
            results['dockerfiles'].append(dockerfile_info)
        
        # Remove duplicates from summary lists
        results['trusted_images'] = list(set(results['trusted_images']))
        results['other_images'] = list(set(results['other_images']))
        
        return results
    
    def _find_dockerfiles(self, repo_path: str) -> List[Path]:
        """
        Find all Dockerfiles in repository.
        
        Args:
            repo_path: Path to repository
            
        Returns:
            List of Dockerfile paths
        """
        dockerfiles = []
        repo = Path(repo_path)
        
        # Find all files recursively and check if they match Dockerfile patterns
        for file_path in repo.rglob('*'):
            if not file_path.is_file():
                continue
            
            filename = file_path.name.lower()
            
            # Match various Dockerfile patterns (case-insensitive)
            if (filename == 'dockerfile' or 
                filename.startswith('dockerfile.') or 
                filename.endswith('.dockerfile')):
                dockerfiles.append(file_path)
        
        return dockerfiles
    
    def _parse_dockerfile(self, dockerfile_path: Path) -> List[str]:
        """
        Parse Dockerfile and extract base images.
        
        Args:
            dockerfile_path: Path to Dockerfile
            
        Returns:
            List of base image names
        """
        images = []
        
        try:
            content = dockerfile_path.read_text(errors='ignore')
            
            # Match FROM statements
            # FROM image:tag
            # FROM image:tag AS stage
            # FROM --platform=linux/amd64 image:tag
            from_pattern = r'^\s*FROM\s+(?:--platform=[^\s]+\s+)?([^\s]+)'
            
            stage_names = set()
            for line in content.split('\n'):
                match = re.match(from_pattern, line, re.IGNORECASE)
                if match:
                    image = match.group(1)
                    # Skip build stages (they reference previous stages)
                    if (not image.startswith('$') and image.lower() != 'scratch'
                            and image.lower() not in stage_names):
                        images.append(image)
                    # Track stage aliases so multi-stage FROM <stage> refs are skipped
                    alias_match = re.match(r'.*?[ \t]+AS[ \t]+([^\s,;]+)', line, re.IGNORECASE)
                    if alias_match:
                        stage_names.add(alias_match.group(1).lower())
        
        except Exception as e:
            self.logger.debug(f"Failed to parse {dockerfile_path}: {e}")
        
        return images
    
    def _assess_image_risk(self, image: str) -> Optional[str]:
        """
        Assess a base image for reproducibility risk.

        Flags: untagged images and floating :latest tags. Version-level EOL
        is handled separately by eol_checker (endoflife.date).
        Trusted-registry images are exempt (assumed continuously rebuilt).

        Args:
            image: Image reference (e.g., 'python:3.9', 'ubuntu:latest', 'nginx')

        Returns:
            Reason string if risky, None otherwise
        """
        if self._is_trusted_image(image):
            return None

        # Strip registry prefix and digest for pattern matching
        ref = image.split('@')[0]
        # e.g. 'docker.io/library/python:3.9' -> 'python:3.9'
        name = ref.split('/')[-1].lower()

        # Untagged or floating :latest
        if ':' not in name:
            return 'Untagged image — implicitly floats to :latest, builds are not reproducible'
        if name.endswith(':latest'):
            return ':latest tag — version floats, builds are not reproducible'

        return None

    def _is_trusted_image(self, image: str) -> bool:
        """Check if image comes from a configured trusted source."""
        return any(p.search(image) for p in self.trusted_patterns)
    
    def get_adoption_summary(self, results: Dict) -> str:
        """
        Generate human-readable adoption summary.
        
        Args:
            results: Results from analyze_repository
            
        Returns:
            Summary string
        """
        if not results['dockerfiles_found']:
            return "No Dockerfiles found"
        
        if results['adoption_detected']:
            trusted_count = len(results['trusted_images'])
            other_count = len(results['other_images'])
            total = trusted_count + other_count
            percentage = (trusted_count / total * 100) if total > 0 else 0

            return f"{trusted_count}/{total} images from trusted registries ({percentage:.1f}%)"
        else:
            return f"0/{len(results['other_images'])} images from trusted registries"
