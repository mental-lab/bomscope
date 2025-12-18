#!/usr/bin/env python3
"""
Ecosystems Evaluate - Multi-platform Dependency Analysis Tool

Analyze repositories across GitLab, GitHub, Bitbucket, and Azure DevOps
to extract dependency information for Chainguard package coverage analysis.
"""

import click
import time
from typing import Optional

from repo_analyzer.repository_analyzer import RepositoryAnalyzer


@click.command()
@click.version_option("1.0.0")
@click.option('-p', '--platform', required=True, type=click.Choice(['gitlab', 'github'], case_sensitive=False), help='Platform to analyze (gitlab, github)')
@click.option('-s', '--source', required=True, help='Platform instance URL (e.g., https://gitlab.com or https://github.com)')
@click.option('-t', '--token', required=True, help='Personal access token')
@click.option('-o', '--org', required=True, help='Organization/group name to analyze')
@click.option('-r', '--repo', help='Specific repository to analyze (format: owner/repo for GitHub, group/project for GitLab)')
@click.option('-O', '--output', required=True, help='Output JSON file for analysis')
@click.option('-w', '--workers', type=int, default=4, help='Number of parallel workers')
@click.option('-v', '--verbose', is_flag=True, help='Enable verbose output')
def cli(platform: str, source: str, token: str, org: str, repo: str, output: str, workers: int, verbose: bool):
    """Analyze organization or repository for dependency inventory.

    This command analyzes all repositories in an organization/group or a specific repository,
    discovers dependency manifests, and generates a comprehensive coverage report.

    Platforms:
        gitlab  - Fully tested
        github  - Fully tested

    Examples:
        # Analyze GitLab group (tested)
        ecosystems-evaluate -p gitlab -s https://gitlab.com -t $TOKEN -o mygroup -O analysis.json

        # Analyze GitHub organization (tested)
        ecosystems-evaluate -p github -s https://github.com -t $TOKEN -o myorg -O analysis.json

        # Analyze specific repository
        ecosystems-evaluate -p github -s https://github.com -t $TOKEN -o myorg -r owner/repo -O analysis.json
    """
    start_time = time.time()
    
    
    try:
        # Initialize analyzer with platform credentials
        analyzer = RepositoryAnalyzer(platform=platform, url=source, token=token, max_workers=workers)
        
        if repo:
            # Analyze specific repository
            if verbose:
                click.echo(f"Analyzing repository {repo} on {platform}")
            analysis = analyzer.analyze_repository(repo)
        else:
            # Analyze entire organization
            if verbose:
                click.echo(f"Analyzing {org} organization on {platform}")
                click.echo(f"Using {workers} parallel workers")

            analysis = analyzer.analyze_organization(org)

        # Save results
        analyzer.save_analysis(analysis, output)

        if verbose:
            click.echo("\nAnalysis Complete:")
            if repo:
                click.echo(f"   Repository: {repo}")
                click.echo(f"   Total dependencies: {analysis.total_dependencies}")
            else:
                click.echo(f"   Projects analyzed: {analysis.analyzed_projects}/{analysis.total_projects}")
                click.echo(f"   Total dependencies: {analysis.total_dependencies}")
                # Show ecosystem breakdown
                for eco, data in analysis.ecosystems_breakdown.items():
                    click.echo(f"   {eco.upper()}: {data['total_dependencies']} deps ({data['total_projects']} projects)")

        click.echo(f"Report saved to: {output}")

    except Exception as e:
        click.echo(f"Analysis failed: {e}", err=True)
        raise click.Abort()

    elapsed = time.time() - start_time
    if verbose:
        click.echo(f"Completed in {elapsed:.2f}s")


if __name__ == "__main__":
    cli()