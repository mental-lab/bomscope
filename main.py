#!/usr/bin/env python3
"""
Multi-platform Dependency Analysis Tool

Analyze repositories across GitLab, GitHub, and Azure DevOps to extract
dependency inventory, base-image risk, and end-of-life status.
"""

import click
import time
import os
import json
from typing import Optional

from bomscope.repository_analyzer import RepositoryAnalyzer
from bomscope.database import connect, persist_analysis


@click.command()
@click.version_option("1.0.0")
@click.option('-p', '--platform', type=click.Choice(['gitlab', 'github', 'ado'], case_sensitive=False), help='Platform to analyze (gitlab, github, ado)')
@click.option('-s', '--source', help='Platform instance URL (e.g., https://gitlab.com)')
@click.option('-t', '--token', help='Personal access token')
@click.option('-o', '--org', help='Organization/group name to analyze')
@click.option('-r', '--repo', help='Specific repository to analyze (format: owner/repo for GitHub, group/project for GitLab)')
@click.option('-b', '--branch', help='Specific branch to analyze (default: repository default branch)')
@click.option('-O', '--output', required=True, help='Output JSON file for analysis')
@click.option('-w', '--workers', type=int, default=4, help='Number of parallel workers')
@click.option('-v', '--verbose', is_flag=True, help='Enable verbose output')
@click.option('--database', envvar='DATABASE_URL', help='SQLAlchemy database URL to persist analysis to PostgreSQL')
@click.option('--vulns/--no-vulns', default=False, help='Run grype vulnerability scans per repo (default: off — slow; EOL status via endoflife.date is always on)')
@click.option('--freshness/--no-freshness', default=True, help='Check upstream registries for latest dependency versions (default: on)')
@click.option('--incremental/--no-incremental', default=True, help='Skip repos whose HEAD is unchanged since the last scan (requires --database; default: on)')
@click.option('--trusted-registries', envvar='TRUSTED_REGISTRIES', default=None, help='Comma-separated regex patterns for trusted image sources. Falls back to the dashboard Settings value stored in the database. E.g. "cgr.dev,registry.example.com/secure"')
def cli(platform: str, source: str, token: str, org: str, repo: str, branch: str, output: str, workers: int, verbose: bool, database: Optional[str] = None, vulns: bool = False, freshness: bool = False, incremental: bool = True, trusted_registries: Optional[str] = None):
    """Analyze organization or repository for dependency inventory.

    Analyze an organization or repository for dependency inventory,
    base-image risk, and end-of-life status.

    Defaults: --freshness and --incremental are ON; --vulns (grype) is OFF.
    Disable with --no-freshness / --no-incremental.

    Platforms:
        gitlab  - Fully tested
        github  - Fully tested
        ado     - Azure DevOps support

    Examples:
        # Using environment variables (recommended - see .env.example)
        python3 main.py -O analysis.json -v

        # Using CLI flags
        python3 main.py -p gitlab -s https://gitlab.com -t $TOKEN -o mygroup -O analysis.json -v

        # Fast re-scan, no freshness lookups
        python3 main.py -o myorg -O analysis.json --no-freshness

        # Full scan with vulnerability scanning
        python3 main.py -o myorg -O analysis.json --vulns

        # Analyze specific repository
        python3 main.py -p github -s https://github.com -t $TOKEN -o myorg -r owner/repo -O analysis.json

        # Analyze specific branch
        python3 main.py -p github -s https://github.com -t $TOKEN -o myorg -b develop -O analysis.json
    """
    start_time = time.time()
    
    # Load from environment variables if not provided via CLI
    # Priority: CLI flags > Environment variables > Defaults
    platform = platform or os.getenv('PLATFORM')
    source = source or os.getenv('SOURCE')
    token = token or os.getenv('TOKEN')
    org = org or os.getenv('ORG')
    workers = workers or int(os.getenv('WORKERS', 4))
    
    # Validate required parameters
    if not all([platform, source, token, org]):
        click.echo("Error: -p/--platform, -s/--source, -t/--token, and -o/--org are required", err=True)
        raise click.Abort()

    try:
        # Trusted registries: explicit flag/env wins; otherwise fall back to
        # the dashboard Settings stored in the database (single source of truth).
        if trusted_registries is None and database:
            from bomscope.database import load_setting
            trusted_registries = load_setting(connect(database), "adoption_patterns", "")

        trusted_list = [p.strip() for p in trusted_registries.split(',') if p.strip()] if trusted_registries else None
        cache_dir = os.getenv('REPO_CACHE_DIR') or ('/data/repo-cache' if os.path.isdir('/data') else None)
        analyzer = RepositoryAnalyzer(platform=platform, url=source, token=token, max_workers=workers, enable_vulns=vulns, enable_freshness=freshness, trusted_registries=trusted_list, cache_dir=cache_dir)

        # Incremental: load previous scan results so unchanged repos can be reused
        if incremental and database:
            from bomscope.database import load_latest_projects
            _engine = connect(database)
            analyzer.previous_projects = load_latest_projects(_engine, repo or org)
            if verbose and analyzer.previous_projects:
                click.echo(f"Incremental mode: {len(analyzer.previous_projects)} repos eligible for reuse")

        if repo:
            # Analyze specific repository
            # For GitHub, need to combine org/repo format
            if platform.lower() == 'github' and '/' not in repo:
                repo_spec = f"{org}/{repo}"
            else:
                repo_spec = repo

            if verbose:
                branch_msg = f" (branch: {branch})" if branch else ""
                click.echo(f"Analyzing repository {repo_spec} on {platform}{branch_msg}")
            analysis = analyzer.analyze_repository(repo_spec, branch=branch)
        else:
            # Analyze entire organization
            if verbose:
                branch_msg = f" (branch: {branch})" if branch else ""
                click.echo(f"Analyzing {org} organization on {platform}{branch_msg}")
                click.echo(f"Using {workers} parallel workers")

            analysis = analyzer.analyze_organization(org, branch=branch)

    except Exception as e:
        click.echo(f"Analysis failed: {e}", err=True)
        raise click.Abort()

    # Save results
    from dataclasses import asdict
    output_data = asdict(analysis)
    output_data['trusted_registries'] = trusted_list or []

    # Ensure output directory exists
    output_dir = os.path.dirname(output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(output, 'w') as f:
        json.dump(output_data, f, indent=2, default=str)

    if database:
        if verbose:
            click.echo(f"\nPersisting analysis to database...")
        engine = connect(database)
        scan_id = persist_analysis(engine, output_data)
        if verbose:
            click.echo(f"Persisted to database: scan_id={scan_id}")

    if verbose:
        click.echo("\nAnalysis Complete:")
        if repo:
            click.echo(f"   Repository: {repo}")
            click.echo(f"   Total dependencies: {analysis.total_dependencies}")
        else:
            click.echo(f"   Projects analyzed: {analysis.analyzed_projects}/{analysis.total_projects}")
            click.echo(f"   Total dependencies: {analysis.total_dependencies}")
            
            # Show skipped projects summary
            if hasattr(analysis, 'skipped_projects') and analysis.skipped_projects:
                click.echo(f"\n   Skipped projects: {len(analysis.skipped_projects)}")
                
                # Group by reason
                skip_reasons = {}
                for skipped in analysis.skipped_projects:
                    reason = skipped.reason
                    if reason not in skip_reasons:
                        skip_reasons[reason] = []
                    skip_reasons[reason].append(skipped.name)
                
                for reason, repos in skip_reasons.items():
                    click.echo(f"      {reason}: {len(repos)}")
                    for repo in repos:
                        click.echo(f"         - {repo}")
            
            # Show ecosystem breakdown
            click.echo("")
            for eco, data in analysis.ecosystems_breakdown.items():
                click.echo(f"   {eco.upper()}: {data['total_dependencies']} deps ({data['total_projects']} projects)")
        
        # Show Dockerfile adoption summary
        repos_with_dockerfiles = 0
        repos_with_trusted_images = 0
        total_trusted_images = []

        for project in analysis.projects:
            if hasattr(project, 'dockerfile_adoption') and project.dockerfile_adoption:
                repos_with_dockerfiles += 1
                if project.dockerfile_adoption.get('adoption_detected'):
                    repos_with_trusted_images += 1
                    total_trusted_images.extend(project.dockerfile_adoption.get('trusted_images', []))

        if repos_with_dockerfiles > 0:
            click.echo("\nDockerfile Adoption:")
            click.echo(f"   Repos with Dockerfiles: {repos_with_dockerfiles}/{len(analysis.projects)}")
            click.echo(f"   Repos using trusted images: {repos_with_trusted_images}/{repos_with_dockerfiles}")
            if repos_with_trusted_images > 0:
                click.echo(f"   Total trusted images: {len(total_trusted_images)}")

    click.echo(f"Report saved to: {output}")

    elapsed = time.time() - start_time
    if verbose:
        click.echo(f"Completed in {elapsed:.2f}s")


if __name__ == "__main__":
    cli()