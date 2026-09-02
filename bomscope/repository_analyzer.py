"""
Multi-platform dependency analyzer for GitLab, GitHub, and Azure DevOps.

Simple Usage:
    >>> analyzer = RepositoryAnalyzer(platform='gitlab', url='https://gitlab.com', token='your-token')
    >>> results = analyzer.analyze_organization('my-org')
    >>> analyzer.save_results(results, 'output.json')

Supported Platforms: gitlab, github, ado
Supported Ecosystems: Python, Java, JavaScript
"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from .models import OrganizationAnalysis, ProjectAnalysis, RepositoryInfo, DependencyInfo, SkippedRepository
from .platform_analyzers import get_analyzer
from .git_cloner import GitCloner, RepoCache
from .syft_analyzer import SyftAnalyzer
from .dockerfile_analyzer import DockerfileAnalyzer
from .eol_checker import EOLChecker
from .freshness_checker import FreshnessChecker
from .vulnerability_analyzer import VulnerabilityAnalyzer


class RepositoryAnalyzer:
    """Simple, secure analyzer for multi-platform dependency analysis.

    Args:
        platform: Platform name ('gitlab', 'github', 'ado')
        url: Platform URL (e.g., 'https://gitlab.com')
        token: Authentication token
        max_workers: Number of parallel workers (default: 4)

    Example:
        >>> analyzer = RepositoryAnalyzer('gitlab', 'https://gitlab.com', 'token')
        >>> results = analyzer.analyze_organization('my-company')
        >>> print(f"Found {results.total_dependencies} dependencies")
    """

    # Supported platforms and ecosystems (for user reference)
    SUPPORTED_PLATFORMS = ['gitlab', 'github', 'ado']
    SUPPORTED_ECOSYSTEMS = ['python', 'java', 'javascript']

    def __init__(self, platform: str, url: str, token: str, max_workers: int = 4,
                 enable_vulns: bool = False, enable_freshness: bool = False,
                 trusted_registries: Optional[List[str]] = None,
                 cache_dir: Optional[str] = None):
        """Initialize analyzer with platform credentials.

        Args:
            enable_vulns: Run grype vulnerability scans per repo (default: True)
            enable_freshness: Check registry for latest versions (default: False,
                              adds one request per unique package)
            cache_dir: Persistent git mirror cache directory; re-scans fetch
                       deltas instead of full-cloning. None disables caching.
        """
        self.platform = platform.lower()
        self.url = url
        self.token = token
        self.max_workers = max_workers
        self.enable_vulns = enable_vulns
        self.enable_freshness = enable_freshness
        self.previous_projects: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger(__name__)

        # Validate inputs early
        if self.platform not in self.SUPPORTED_PLATFORMS:
            raise ValueError(
                f"Unsupported platform '{platform}'. "
                f"Supported: {', '.join(self.SUPPORTED_PLATFORMS)}"
            )

        # Create platform-specific analyzer (only for listing repos)
        self._analyzer = get_analyzer(self.platform, self.url, self.token)
        
        # Create git cloner, syft analyzer, and dockerfile analyzer
        self.git_cloner = GitCloner(
            token=self.token,
            cache=RepoCache(cache_dir, token=self.token) if cache_dir else None,
        )
        self.syft_analyzer = SyftAnalyzer()
        self.dockerfile_analyzer = DockerfileAnalyzer(trusted_registries=trusted_registries)
        self.freshness_checker = FreshnessChecker() if enable_freshness else None
        self.eol_checker = EOLChecker()
        self.vulnerability_analyzer = VulnerabilityAnalyzer()
        # Check dependencies
        if not self.git_cloner.check_git_available():
            raise RuntimeError("git is not installed or not available in PATH")

        if not self.syft_analyzer.check_syft_available():
            raise RuntimeError("syft is not installed or not available in PATH. Install from: https://github.com/anchore/syft")

        if self.enable_vulns and not self.vulnerability_analyzer.check_grype_available():
            self.logger.warning(
                "grype is not installed; skipping vulnerability scans. "
                "Install from: https://github.com/anchore/grype"
            )
            self.enable_vulns = False

    def analyze_organization(self, organization: str, branch: Optional[str] = None) -> OrganizationAnalysis:
        """Analyze all repositories in an organization for dependencies.

        Args:
            organization: Organization/group name to analyze
            branch: Specific branch to analyze (default: repository default branch)

        Returns:
            OrganizationAnalysis with all discovered dependencies

        Example:
            >>> results = analyzer.analyze_organization('my-company')
            >>> print(f"Analyzed {results.analyzed_projects} projects")
        """
        self.logger.info(f"Analyzing organization '{organization}' on {self.platform}")

        # Get all repositories
        repositories = self._analyzer.get_repositories(organization)
        self.logger.info(f"Found {len(repositories)} repositories")

        # Analyze all repositories
        return self._analyze_repositories(organization, repositories, branch=branch)

    def analyze_repository(self, repository: str, branch: Optional[str] = None) -> OrganizationAnalysis:
        """Analyze a single repository for dependencies.

        Args:
            repository: Repository identifier (e.g., 'group/project' for GitLab)
            branch: Specific branch to analyze (default: repository default branch)

        Returns:
            OrganizationAnalysis with discovered dependencies

        Example:
            >>> results = analyzer.analyze_repository('mygroup/myproject')
            >>> print(f"Found {results.total_dependencies} dependencies")
        """
        self.logger.info(f"Analyzing repository '{repository}' on {self.platform}")

        # Get single repository
        repo_info = self._analyzer.get_single_repository(repository)

        # Analyze it
        return self._analyze_repositories(repository, [repo_info], branch=branch)

    def analyze_scope(self, organization: str, repositories: List[str],
                      branch: Optional[str] = None) -> OrganizationAnalysis:
        """Analyze a specific list of repositories in parallel, reporting them
        under the given organization name.

        Args:
            organization: Organization name to attribute results to
            repositories: Repo identifiers (e.g. 'org/repo')
        """
        self.logger.info(
            "Analyzing %d repositories in '%s' on %s (workers=%d)",
            len(repositories), organization, self.platform, self.max_workers)
        infos = []
        for name in repositories:
            try:
                infos.append(self._analyzer.get_single_repository(name))
            except Exception as e:
                self.logger.error("Could not resolve repository %s: %s", name, e)
        return self._analyze_repositories(organization, infos, branch=branch)

    def _analyze_repositories(
        self, org_name: str, repositories: List[RepositoryInfo], branch: Optional[str] = None
    ) -> OrganizationAnalysis:
        """Analyze a list of repositories for dependencies (internal method)."""
        organization_analysis = OrganizationAnalysis(
            organization_name=org_name,
            platform=self.platform,
            timestamp=self._get_timestamp(),
            total_projects=len(repositories),
            analyzed_projects=0,
            total_dependencies=0,
            projects=[],
            ecosystems_breakdown={},
        )

        # Ensure grype vulnerability DB is ready before parallel workers race on it
        if self.enable_vulns:
            self.vulnerability_analyzer.ensure_db_ready()

        # Analyze repositories in parallel for speed
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_repo = {
                executor.submit(self._analyze_single_repository, repo, branch): repo
                for repo in repositories
            }

            for future in as_completed(future_to_repo):
                repo = future_to_repo[future]
                try:
                    project_analysis = future.result()
                    if project_analysis:
                        organization_analysis.projects.append(project_analysis)
                        organization_analysis.analyzed_projects += 1
                        organization_analysis.total_dependencies += (
                            project_analysis.total_dependencies
                        )

                        self.logger.info(
                            f"{repo.name}: {project_analysis.total_dependencies} dependencies"
                        )
                    else:
                        # Repository was skipped (no dependencies found)
                        skipped = SkippedRepository(
                            name=repo.name,
                            url=repo.url,
                            reason="No dependencies found",
                            error_details="Repository analyzed but no manifest files or dependencies detected"
                        )
                        organization_analysis.skipped_projects.append(skipped)
                        self.logger.info(f"{repo.name}: Skipped - no dependencies found")

                except Exception as e:
                    # Repository analysis failed
                    skipped = SkippedRepository(
                        name=repo.name,
                        url=repo.url,
                        reason="Analysis failed",
                        error_details=str(e)
                    )
                    organization_analysis.skipped_projects.append(skipped)
                    self.logger.error(f"Failed to analyze {repo.name}: {e}")

        # Calculate ecosystems breakdown
        organization_analysis.ecosystems_breakdown = self._calculate_ecosystems_breakdown(
            organization_analysis.projects
        )

        self.logger.info(
            f"Complete: {organization_analysis.analyzed_projects}/"
            f"{organization_analysis.total_projects} projects, "
            f"{organization_analysis.total_dependencies} total dependencies"
        )

        return organization_analysis
    
    def _analyze_single_repository(
        self, repo_info: RepositoryInfo, branch: Optional[str] = None
    ) -> Optional[ProjectAnalysis]:
        """Analyze a single repository using git clone + syft."""
        clone_path = None
        try:
            # Incremental: skip full analysis if remote HEAD unchanged
            target_branch = branch if branch else repo_info.default_branch
            remote_head = self.git_cloner.get_remote_head(repo_info.url, target_branch)
            if remote_head:
                repo_info.head_sha = remote_head
                reused = self._try_reuse_previous(repo_info, remote_head)
                if reused is not None:
                    return reused

            # Clone repository
            # Use specified branch if provided, otherwise use repository's default branch
            self.logger.debug(f"Cloning {repo_info.name} (branch: {target_branch})...")
            clone_path = self.git_cloner.shallow_clone(
                repo_info.url,
                branch=target_branch
            )
            
            if not clone_path:
                self.logger.warning(f"Failed to clone {repo_info.name}")
                return None
            
            # Run syft analysis
            self.logger.debug(f"Running syft on {repo_info.name}...")
            sbom_data = self.syft_analyzer.analyze_repository(clone_path)
            
            if not sbom_data:
                self.logger.warning(f"Syft analysis failed for {repo_info.name}")
                return None
            
            # Analyze Dockerfiles for trusted image adoption
            self.logger.debug(f"Analyzing Dockerfiles in {repo_info.name}...")
            dockerfile_results = self.dockerfile_analyzer.analyze_repository(clone_path)

            # Parse SBOM into our dependency format (with Java enhancement)
            dependencies_by_ecosystem = self.syft_analyzer.parse_sbom_to_dependencies(sbom_data, repo_path=clone_path)

            # License posture from the SBOM
            license_summary = self._extract_license_summary(sbom_data)

            # Vulnerability scan (grype) — opt-in via enable_vulns
            vulnerability_summary = None
            if self.enable_vulns:
                self.logger.debug(f"Running grype on {repo_info.name}...")
                vulnerability_summary = self.vulnerability_analyzer.scan_repository(clone_path)

            # Freshness check against upstream registries — opt-in via enable_freshness
            if self.enable_freshness:
                self.logger.debug(f"Checking dependency freshness for {repo_info.name}...")
                dependencies_by_ecosystem = self.freshness_checker.check_dependencies(
                    dependencies_by_ecosystem
                )

            # EOL status via endoflife.date — cheap API calls, always on
            self.logger.debug(f"Checking EOL status for {repo_info.name}...")
            eol_images = []
            all_images = [
                img
                for df in dockerfile_results.get("dockerfiles", [])
                for img in (df.get("trusted_images", []) + df.get("other_images", []))
            ]
            if all_images:
                eol_images = self.eol_checker.check_base_images(all_images)
            eol_deps = self.eol_checker.check_dependencies(dependencies_by_ecosystem)
            eol_summary = {
                "eol_count": sum(1 for f in eol_images + eol_deps if f["status"] == "eol"),
                "approaching_count": sum(1 for f in eol_images + eol_deps if f["status"] == "approaching"),
                "images": eol_images,
                "dependencies": eol_deps,
            }

            # Check if we found anything useful
            has_dependencies = dependencies_by_ecosystem and any(len(deps) > 0 for deps in dependencies_by_ecosystem.values())
            has_dockerfiles = dockerfile_results['dockerfiles_found'] > 0
            
            if not has_dependencies and not has_dockerfiles:
                self.logger.debug(f"No dependencies or Dockerfiles found in {repo_info.name}")
                return None
            
            # Convert to manifest format
            manifests = []
            total_deps = 0
            
            for ecosystem, deps in dependencies_by_ecosystem.items():
                if deps:
                    # Get unique file paths from dependencies
                    file_paths = set()
                    for dep in deps:
                        for loc in dep.get('locations', []):
                            if loc:
                                file_paths.add(loc)
                    
                    manifest = DependencyInfo(
                        file_path=', '.join(sorted(file_paths)[:3]) if file_paths else f'{ecosystem} dependencies',
                        file_type='sbom',
                        ecosystem=ecosystem,
                        dependencies=[
                            {
                                'name': d['name'],
                                'version': d['version'],
                                **({'latest_version': d['latest_version'],
                                    'versions_behind': d['versions_behind'],
                                    'freshness': d['freshness']}
                                   if 'freshness' in d else {})
                            }
                            for d in deps
                        ],
                        build_tool='syft'
                    )
                    manifests.append(manifest)
                    total_deps += len(deps)

            # Create project analysis with Dockerfile adoption, vuln, and license info
            project = ProjectAnalysis(
                repository=repo_info,
                manifests=manifests,
                total_dependencies=total_deps,
                collection_timestamp=datetime.utcnow().isoformat(),
                dockerfile_adoption=dockerfile_results if dockerfile_results['dockerfiles_found'] > 0 else None,
                vulnerability_summary=vulnerability_summary,
                license_summary=license_summary,
                eol_summary=eol_summary,
            )
            
            return project
            
        except Exception as e:
            self.logger.error(f"Failed to analyze {repo_info.name}: {e}")
            return None
        finally:
            # Always cleanup cloned repository
            if clone_path:
                self.git_cloner.cleanup(clone_path)
    
    def _repo_key(self, url: str) -> str:
        """Normalize a repo URL to host/owner/repo (matches database._repo_full_name)."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        path = parsed.path.rstrip('/')
        if path.endswith('.git'):
            path = path[:-4]
        return f"{parsed.netloc}{path}".lower()

    def _try_reuse_previous(
        self, repo_info: RepositoryInfo, remote_head: str
    ) -> Optional[ProjectAnalysis]:
        """Return the previous scan's ProjectAnalysis if HEAD is unchanged."""
        key = self._repo_key(repo_info.url)
        prev = self.previous_projects.get(key)
        if not prev or prev.get('head_sha') != remote_head:
            return None

        project_dict = prev.get('project')
        if not project_dict:
            return None

        try:
            # Reconstruct ProjectAnalysis from the stored raw dict
            repo_data = dict(project_dict['repository'])
            repo_data['head_sha'] = remote_head
            repo = RepositoryInfo(**{k: v for k, v in repo_data.items()
                                     if k in RepositoryInfo.__dataclass_fields__})
            manifests = [
                DependencyInfo(**{k: v for k, v in m.items()
                                  if k in DependencyInfo.__dataclass_fields__})
                for m in project_dict.get('manifests', [])
            ]
            project = ProjectAnalysis(
                repository=repo,
                manifests=manifests,
                total_dependencies=project_dict.get('total_dependencies', 0),
                collection_timestamp=datetime.utcnow().isoformat(),
                dockerfile_adoption=project_dict.get('dockerfile_adoption'),
                vulnerability_summary=project_dict.get('vulnerability_summary'),
                license_summary=project_dict.get('license_summary'),
                eol_summary=project_dict.get('eol_summary'),
            )
            self.logger.info(f"{repo_info.name}: unchanged ({remote_head[:8]}), reusing previous results")
            return project
        except Exception as e:
            self.logger.debug(f"Could not reuse previous results for {repo_info.name}: {e}")
            return None

    def _extract_license_summary(self, sbom_data: Dict) -> Optional[Dict[str, Any]]:
        """Extract license posture from a syft SBOM.

        Returns counts of copyleft licenses and the full license histogram.
        """
        # Strong copyleft only: real redistribution/compliance risk.
        # Weak copyleft (LGPL/MPL/EPL/CDDL/EUPL) and GPL-with-exception variants
        # are intentionally not flagged — they're fine as dependencies.
        STRONG_COPYLEFT = {'GPL', 'AGPL', 'SSPL', 'CC-BY-SA'}

        def _is_strong_copyleft(value: str) -> bool:
            v = value.upper()
            if 'EXCEPTION' in v:
                return False
            return any(v.startswith(c) for c in STRONG_COPYLEFT)

        artifacts = sbom_data.get('artifacts', [])
        if not artifacts:
            return None

        histogram: Dict[str, int] = {}
        copyleft_packages = []
        seen = set()

        for artifact in artifacts:
            licenses = artifact.get('licenses') or []
            name = artifact.get('name', '')
            version = artifact.get('version', '')
            for lic in licenses:
                value = lic.get('value') or lic.get('spdxExpression') or ''
                if not value:
                    continue
                histogram[value] = histogram.get(value, 0) + 1
                if _is_strong_copyleft(value) and (name, version, value) not in seen:
                    seen.add((name, version, value))
                    copyleft_packages.append({
                        'name': name,
                        'version': version,
                        'license': value,
                    })

        if not histogram:
            return None

        return {
            'histogram': dict(sorted(histogram.items(), key=lambda kv: -kv[1])),
            'copyleft_count': len(copyleft_packages),
            'copyleft_packages': sorted(copyleft_packages, key=lambda p: p['name'])[:20],
            'licensed_packages': sum(histogram.values()),
            'total_packages': len(artifacts),
        }

    def _calculate_ecosystems_breakdown(self, projects: List[ProjectAnalysis]) -> Dict[str, Dict[str, Any]]:
        """Calculate ecosystems breakdown from projects."""
        ecosystems = {}
        
        for project in projects:
            for manifest in project.manifests:
                ecosystem = manifest.ecosystem
                if ecosystem not in ecosystems:
                    ecosystems[ecosystem] = {
                        'total_projects': 0,
                        'total_dependencies': 0
                    }
                
                ecosystems[ecosystem]['total_projects'] += 1
                ecosystems[ecosystem]['total_dependencies'] += len(manifest.dependencies)
        
        # Remove duplicates by counting unique projects per ecosystem
        for ecosystem in ecosystems:
            unique_projects = set()
            total_deps = 0
            
            for project in projects:
                has_ecosystem = any(m.ecosystem == ecosystem for m in project.manifests)
                if has_ecosystem:
                    unique_projects.add(project.repository.name)
                    total_deps += sum(len(m.dependencies) for m in project.manifests if m.ecosystem == ecosystem)
            
            ecosystems[ecosystem]['total_projects'] = len(unique_projects)
            ecosystems[ecosystem]['total_dependencies'] = total_deps
        
        return ecosystems
    
    def save_analysis(self, analysis: OrganizationAnalysis, output_file: str):
        """Save analysis to JSON file."""
        with open(output_file, 'w') as f:
            json.dump(asdict(analysis), f, indent=2, default=str)
        
        self.logger.info(f"Analysis saved to {output_file}")
    
    def load_analysis(self, input_file: str) -> OrganizationAnalysis:
        """Load analysis from JSON file."""
        with open(input_file, 'r') as f:
            data = json.load(f)
        
        # Convert back to dataclass instances
        projects = []
        for project_data in data.get("projects", []):
            repo_data = project_data["repository"]
            repo = RepositoryInfo(**repo_data)
            
            manifests = []
            for manifest_data in project_data.get("manifests", []):
                manifests.append(DependencyInfo(**manifest_data))
            
            projects.append(ProjectAnalysis(
                repository=repo,
                manifests=manifests,
                total_dependencies=project_data["total_dependencies"],
                collection_timestamp=project_data["collection_timestamp"],
                note=project_data.get("note", "")
            ))
        
        return OrganizationAnalysis(
            organization_name=data["organization_name"],
            platform=data["platform"],
            timestamp=data["timestamp"],
            total_projects=data["total_projects"],
            analyzed_projects=data["analyzed_projects"],
            total_dependencies=data["total_dependencies"],
            projects=projects,
            ecosystems_breakdown=data["ecosystems_breakdown"],
        )
    
    def generate_summary_report(self, analysis: OrganizationAnalysis) -> Dict[str, Any]:
        """Generate a summary report from analysis."""
        return {
            "organization": analysis.organization_name,
            "platform": analysis.platform,
            "scan_timestamp": analysis.timestamp,
            "summary": {
                "total_projects": analysis.total_projects,
                "analyzed_projects": analysis.analyzed_projects,
                "total_dependencies": analysis.total_dependencies,
            },
            "ecosystems": analysis.ecosystems_breakdown,
            "top_dependencies": self._get_top_dependencies(analysis),
            "projects_by_ecosystem": self._group_projects_by_ecosystem(analysis)
        }
    
    def _get_top_dependencies(self, analysis: OrganizationAnalysis, limit: int = 20) -> Dict[str, List[Dict[str, Any]]]:
        """Get top dependencies by ecosystem."""
        ecosystem_deps = {}
        
        for project in analysis.projects:
            for manifest in project.manifests:
                ecosystem = manifest.ecosystem
                if ecosystem not in ecosystem_deps:
                    ecosystem_deps[ecosystem] = {}
                
                for dep in manifest.dependencies:
                    dep_name = dep['name']
                    if dep_name not in ecosystem_deps[ecosystem]:
                        ecosystem_deps[ecosystem][dep_name] = 0
                    ecosystem_deps[ecosystem][dep_name] += 1
        
        # Sort and limit
        return {eco: sorted(list(deps)) for eco, deps in ecosystem_deps.items()}
    
    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.utcnow().isoformat()
    
    def _group_projects_by_ecosystem(self, analysis: OrganizationAnalysis) -> Dict[str, List[str]]:
        """Group project names by ecosystem."""
        ecosystem_projects = {}
        
        for project in analysis.projects:
            ecosystems_in_project = set(m.ecosystem for m in project.manifests)
            for ecosystem in ecosystems_in_project:
                if ecosystem not in ecosystem_projects:
                    ecosystem_projects[ecosystem] = []
                ecosystem_projects[ecosystem].append(project.repository.name)
        
        return ecosystem_projects
