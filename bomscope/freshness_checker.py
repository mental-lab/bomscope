"""Package freshness checker.

Compares pinned dependency versions against the latest available version
in the upstream registry (npm, PyPI, Maven Central, crates.io, Go proxy,
RubyGems) and flags how far behind each dependency is.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

import requests

try:
    from packaging.version import parse as parse_version
except ImportError:
    parse_version = None


class FreshnessChecker:
    """Checks how outdated pinned dependencies are relative to upstream."""

    # Ecosystems we know how to query
    SUPPORTED = {"javascript", "python", "java", "rust", "go", "ruby"}

    def __init__(self, timeout: int = 5, max_workers: int = 16):
        self.timeout = timeout
        self.max_workers = max_workers
        self.logger = logging.getLogger(__name__)
        self._cache: Dict[str, Optional[str]] = {}
        self._session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=max_workers, pool_maxsize=max_workers
        )
        self._session.mount('https://', adapter)
        self._session.mount('http://', adapter)

    def check_dependencies(
        self, dependencies_by_ecosystem: Dict[str, List[Dict]]
    ) -> Dict[str, List[Dict]]:
        """Annotate dependencies with freshness info (in-place on copies).

        Adds to each dep dict:
            latest_version: str or None
            versions_behind: int or None
            freshness: 'current' | 'outdated' | 'stale' | 'unknown'

        Returns a new dict keyed by ecosystem.
        """
        # Pre-fetch latest versions for all unique supported packages in parallel
        unique_pkgs = {
            (eco, dep["name"])
            for eco, deps in dependencies_by_ecosystem.items()
            if eco in self.SUPPORTED
            for dep in deps
            if dep.get("name")
        }
        to_fetch = [k for k in unique_pkgs if f"{k[0]}:{k[1]}" not in self._cache]
        if to_fetch:
            with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
                list(pool.map(lambda k: self._latest_version(*k), to_fetch))

        result: Dict[str, List[Dict]] = {}

        for ecosystem, deps in dependencies_by_ecosystem.items():
            if ecosystem not in self.SUPPORTED:
                result[ecosystem] = deps
                continue

            enriched = []
            for dep in deps:
                latest = self._latest_version(ecosystem, dep["name"])
                entry = dict(dep)
                entry["latest_version"] = latest
                entry["versions_behind"] = None
                entry["freshness"] = "unknown"

                if latest and dep.get("version"):
                    entry["versions_behind"] = self._versions_behind(
                        dep["version"], latest
                    )
                    entry["freshness"] = self._classify(entry["versions_behind"])
                elif latest and dep.get("version") == latest:
                    entry["versions_behind"] = 0
                    entry["freshness"] = "current"

                enriched.append(entry)

            result[ecosystem] = enriched

        return result

    def _latest_version(self, ecosystem: str, package: str) -> Optional[str]:
        """Fetch the latest published version for a package (cached)."""
        key = f"{ecosystem}:{package}"
        if key in self._cache:
            return self._cache[key]

        try:
            if ecosystem == "javascript":
                url = f"https://registry.npmjs.org/{package}/latest"
                data = self._session.get(url, timeout=self.timeout)
                version = data.json().get("version") if data.ok else None
            elif ecosystem == "python":
                url = f"https://pypi.org/pypi/{package}/json"
                data = self._session.get(url, timeout=self.timeout)
                version = data.json()["info"]["version"] if data.ok else None
            elif ecosystem == "java":
                version = self._latest_maven(package)
            elif ecosystem == "rust":
                url = f"https://crates.io/api/v1/crates/{package}"
                data = self._session.get(url, timeout=self.timeout)
                version = (
                    data.json()["crate"]["newest_version"] if data.ok else None
                )
            elif ecosystem == "go":
                url = f"https://proxy.golang.org/{package}/@latest"
                data = self._session.get(url, timeout=self.timeout)
                version = data.json().get("Version") if data.ok else None
            elif ecosystem == "ruby":
                url = f"https://rubygems.org/api/v1/versions/{package}/latest.json"
                data = self._session.get(url, timeout=self.timeout)
                version = data.json().get("version") if data.ok else None
            else:
                version = None
        except Exception as e:
            self.logger.debug(f"Freshness lookup failed for {key}: {e}")
            version = None

        self._cache[key] = version
        return version

    def _latest_maven(self, package: str) -> Optional[str]:
        """Query Maven Central. Package name is 'groupId:artifactId'."""
        if ":" not in package:
            return None
        group, artifact = package.split(":", 1)
        url = (
            "https://search.maven.org/solrsearch/select"
            f"?q=g:%22{group}%22+AND+a:%22{artifact}%22&rows=1&wt=json"
        )
        data = self._session.get(url, timeout=self.timeout)
        if not data.ok:
            return None
        docs = data.json().get("response", {}).get("docs", [])
        return docs[0].get("latestVersion") if docs else None

    def _versions_behind(self, current: str, latest: str) -> Optional[int]:
        """Estimate how many releases behind current is vs latest.

        Uses major/minor/patch difference when versions parse cleanly,
        else None (unknown).
        """
        if current == latest:
            return 0
        if parse_version is None:
            return None
        try:
            cur = parse_version(current.lstrip("v"))
            new = parse_version(latest.lstrip("v"))
        except Exception:
            return None

        if cur >= new:
            return 0

        c, n = cur.release, new.release
        major_diff = (n[0] - c[0]) if len(n) > 0 and len(c) > 0 else 0
        if major_diff > 0:
            # Each major release bundles many minors; weight heavily
            return major_diff * 10 + (n[1] - c[1] if len(n) > 1 and len(c) > 1 else 0)
        if len(n) > 1 and len(c) > 1 and n[1] > c[1]:
            return n[1] - c[1]
        if len(n) > 2 and len(c) > 2 and n[2] > c[2]:
            return max(1, (n[2] - c[2]) // 10)  # patch drift counts as 1 per ~10 patches
        return 1

    def _classify(self, versions_behind: Optional[int]) -> str:
        if versions_behind is None:
            return "unknown"
        if versions_behind == 0:
            return "current"
        if versions_behind <= 2:
            return "outdated"
        return "stale"
