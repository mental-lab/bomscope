"""End-of-life checker via the endoflife.date API.

Flags software that is end-of-life, approaching EOL, or from an
unmaintained release line — for container base images and key
framework/runtime dependencies. No auth required; results are cached
per product cycle for the duration of the process.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

import requests

API_BASE = "https://endoflife.date/api"

# Docker image name -> endoflife.date product
IMAGE_PRODUCTS = {
    "node": "nodejs",
    "nodejs": "nodejs",
    "python": "python",
    "golang": "go",
    "go": "go",
    "ruby": "ruby",
    "php": "php",
    "openjdk": "java",
    "nginx": "nginx",
    "redis": "redis",
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "mysql": "mysql",
    "mariadb": "mariadb",
    "mongo": "mongodb",
    "mongodb": "mongodb",
    "rabbitmq": "rabbitmq",
    "elasticsearch": "elasticsearch",
    "memcached": "memcached",
    "traefik": "traefik",
    "haproxy": "haproxy",
    "alpine": "alpine",
    "debian": "debian",
    "ubuntu": "ubuntu",
    "amazonlinux": "amazon-linux",
    "dotnet": "dotnet",
    "mcr.microsoft.com/dotnet/runtime": "dotnet",
    "mcr.microsoft.com/dotnet/aspnet": "dotnet",
}

# Dependency package names (npm/pypi/maven etc.) -> endoflife.date product.
# Only packages that are themselves tracked products are worth checking.
DEPENDENCY_PRODUCTS = {
    "django": "django",
    "rails": "rails",
    "laravel": "laravel",
    "symfony": "symfony",
    "react": "react",
    "angular": "angular",
    "@angular/core": "angular",
    "vue": "vue",
    "svelte": "svelte",
    "next": "nextjs",
    "nuxt": "nuxt",
    "express": None,  # not tracked
    "spring-boot": "spring-boot",
    "org.springframework.boot": "spring-boot",
    "tensorflow": "tensorflow",
    "pytorch": "pytorch",
    "torch": "pytorch",
    "kubernetes": "kubernetes",
    "terraform": "terraform",
    "ansible": "ansible",
    "jquery": "jquery",
    "bootstrap": "bootstrap",
    "electron": "electron",
    "ionic": "ionic",
    "flutter": "flutter",
    "elixir": "elixir",
    "erlang": "erlang",
    "composer": "composer",
    "nodejs": "nodejs",
    "node": "nodejs",
}

# Days before EOL to flag as "approaching"
APPROACHING_DAYS = 90


class EOLChecker:
    """Checks products against endoflife.date and classifies support status."""

    def __init__(self, timeout: int = 10, max_workers: int = 8):
        self.timeout = timeout
        self.max_workers = max_workers
        self.logger = logging.getLogger(__name__)
        self._cache: Dict[Tuple[str, str], Optional[Dict]] = {}
        self._session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=max_workers, pool_maxsize=max_workers
        )
        self._session.mount("https://", adapter)

    def _cycle_for_version(self, product: str, version: str) -> Optional[str]:
        """Map a concrete version to an endoflife.date release cycle."""
        v = version.strip().lstrip("v")
        # Drop image suffixes: 3.11-slim -> 3.11, 20-alpine3.19 -> 20
        v = v.split("-")[0].split("+")[0]
        if not v or not v[0].isdigit():
            return None
        parts = v.split(".")
        if product in ("ubuntu", "debian", "alpine", "amazon-linux"):
            # OS products cycle on major or major.minor
            return ".".join(parts[:2]) if product != "alpine" else ".".join(parts[:2])
        if len(parts) >= 2:
            return ".".join(parts[:2])
        return parts[0]

    def _fetch_cycle(self, product: str, cycle: str) -> Optional[Dict]:
        """Fetch cycle data from endoflife.date (cached).

        Products vary in cycle granularity (python: '3.9', nodejs: '22').
        If a major.minor cycle 404s, retry with major only.
        """
        key = (product, cycle)
        if key in self._cache:
            return self._cache[key]
        try:
            resp = self._session.get(
                f"{API_BASE}/{product}/{cycle}.json", timeout=self.timeout
            )
            if resp.status_code == 404 and "." in cycle:
                major = cycle.split(".")[0]
                resp = self._session.get(
                    f"{API_BASE}/{product}/{major}.json", timeout=self.timeout
                )
                if resp.status_code == 200:
                    data = resp.json()
                    result = data[0] if isinstance(data, list) else data
                    result["cycle"] = major
                    self._cache[key] = result
                    return result
            if resp.status_code == 404:
                self._cache[key] = None
                return None
            resp.raise_for_status()
            data = resp.json()
            result = data[0] if isinstance(data, list) else data
            self._cache[key] = result
            return result
        except Exception as e:
            self.logger.debug(f"endoflife.date lookup failed for {product} {cycle}: {e}")
            self._cache[key] = None
            return None

    def check(self, product: str, version: str) -> Optional[Dict]:
        """Classify a product version.

        Returns None if unknown, else:
        {product, cycle, status: 'eol'|'approaching'|'supported',
         eol_date, lts, latest}
        """
        cycle = self._cycle_for_version(product, version)
        if not cycle:
            return None
        data = self._fetch_cycle(product, cycle)
        if not data:
            return None

        eol_raw = data.get("eol")
        status = "supported"
        eol_date = None
        if isinstance(eol_raw, str):
            try:
                eol_date = date.fromisoformat(eol_raw)
                days_left = (eol_date - date.today()).days
                if days_left < 0:
                    status = "eol"
                elif days_left <= APPROACHING_DAYS:
                    status = "approaching"
            except ValueError:
                pass
        elif eol_raw is True:
            status = "eol"

        return {
            "product": product,
            "cycle": cycle,
            "status": status,
            "eol_date": eol_date.isoformat() if eol_date else None,
            "lts": bool(data.get("lts")),
            "latest": data.get("latest"),
        }

    def check_base_images(self, images: List[Dict]) -> List[Dict]:
        """Annotate Dockerfile images with EOL status.

        images: [{'image': 'node:18-alpine', ...}, ...]
        Returns list of {image, product, cycle, status, eol_date} for
        images that map to a known product and are EOL or approaching.
        """
        targets = []
        for img in images:
            ref = img.get("image") if isinstance(img, dict) else str(img)
            if not ref or "@" in ref:  # digest-pinned: no version to judge
                continue
            name, _, tag = ref.partition(":")
            name = name.split("/")[-1].lower() if "/" in name else name.lower()
            full = ref.rsplit(":", 1)[0].lower()
            product = IMAGE_PRODUCTS.get(full) or IMAGE_PRODUCTS.get(name)
            if not product:
                continue
            if not tag:
                tag = "latest"
            targets.append((ref, product, tag))

        def work(t):
            ref, product, tag = t
            result = self.check(product, tag)
            return (ref, result)

        findings = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            for ref, result in pool.map(work, targets):
                if result and result["status"] in ("eol", "approaching"):
                    findings.append({"image": ref, **result})
        return findings

    def check_dependencies(
        self, dependencies_by_ecosystem: Dict[str, List[Dict]]
    ) -> List[Dict]:
        """Check tracked framework/runtime dependencies for EOL status.

        Returns list of {name, version, product, cycle, status, eol_date}
        for deps that are EOL or approaching EOL.
        """
        targets = []
        for deps in dependencies_by_ecosystem.values():
            for dep in deps:
                name = (dep.get("name") or "").lower()
                version = dep.get("version") or ""
                if not version:
                    continue
                product = DEPENDENCY_PRODUCTS.get(name)
                if product:
                    targets.append((dep["name"], version, product))

        # Dedupe
        targets = list({(n, v, p) for n, v, p in targets})

        def work(t):
            name, version, product = t
            result = self.check(product, version)
            return (name, version, result)

        findings = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            for name, version, result in pool.map(work, targets):
                if result and result["status"] in ("eol", "approaching"):
                    findings.append({"name": name, "version": version, **result})
        return findings
