#!/usr/bin/env python3
"""
Ecosystems Evaluate - Multi-platform Dependency Analysis Tool

Analyze repositories across GitLab, GitHub, and Azure DevOps
to extract dependency information for Chainguard package coverage analysis.
"""

import click
import time
import os
import json
from typing import Optional

from repo_analyzer.repository_analyzer import RepositoryAnalyzer
from repo_analyzer.coverage_checker import CoverageChecker


@click.command()
@click.version_option("1.0.0")
@click.option('-i', '--input', 'input_file', help='Input analysis.json file (for coverage-only mode)')
@click.option('-p', '--platform', type=click.Choice(['gitlab', 'github', 'ado'], case_sensitive=False), help='Platform to analyze (gitlab, github, ado)')
@click.option('-s', '--source', help='Platform instance URL (e.g., https://gitlab.com)')
@click.option('-t', '--token', help='Personal access token')
@click.option('-o', '--org', help='Organization/group name to analyze')
@click.option('-r', '--repo', help='Specific repository to analyze (format: owner/repo for GitHub, group/project for GitLab)')
@click.option('-O', '--output', required=True, help='Output JSON file for analysis')
@click.option('-w', '--workers', type=int, default=4, help='Number of parallel workers')
@click.option('-v', '--verbose', is_flag=True, help='Enable verbose output')
@click.option('--coverage', is_flag=True, help='Include Chainguard coverage and adoption analysis')
def cli(input_file: str, platform: str, source: str, token: str, org: str, repo: str, output: str, workers: int, verbose: bool, coverage: bool):
    """Analyze organization or repository for dependency inventory.

    This command can operate in two modes:
    1. Analysis Mode: Analyze repositories and optionally run coverage
    2. Coverage-Only Mode: Run coverage analysis on existing analysis.json

    Platforms:
        gitlab  - Fully tested
        github  - Fully tested
        ado     - Azure DevOps support

    Examples:
        # Using environment variables (recommended - see .env.example)
        python3 main.py -O analysis.json --coverage -v

        # Using CLI flags
        python3 main.py -p gitlab -s https://gitlab.com -t $TOKEN -o mygroup -O analysis.json --coverage -v

        # Run coverage on existing analysis file
        python3 main.py -i analysis.json -O analysis_with_coverage.json --coverage -v

        # Analyze specific repository
        python3 main.py -p github -s https://github.com -t $TOKEN -o myorg -r owner/repo -O analysis.json
    """
    start_time = time.time()
    
    # Load from environment variables if not provided via CLI
    # Priority: CLI flags > Environment variables > Defaults
    platform = platform or os.getenv('PLATFORM')
    source = source or os.getenv('SOURCE')
    token = token or os.getenv('TOKEN')
    org = org or os.getenv('ORG')
    workers = workers or int(os.getenv('WORKERS', 4))
    
    # Check if we're in coverage-only mode (input file provided)
    if input_file:
        # Coverage-only mode: load existing analysis
        if not coverage:
            click.echo("Error: --coverage flag required when using --input", err=True)
            raise click.Abort()
        
        if verbose:
            click.echo(f"Loading analysis from: {input_file}")
        
        try:
            with open(input_file, 'r') as f:
                data = json.load(f)
            
            # Create a simple object to hold the data
            class AnalysisData:
                def __init__(self, data):
                    self.projects = data.get('projects', [])
                    self.organization_name = data.get('organization_name', 'Unknown')
                    self.timestamp = data.get('timestamp', '')
                    self.total_dependencies = data.get('total_dependencies', 0)
                    self.analyzed_projects = data.get('analyzed_projects', 0)
                    self.total_projects = data.get('total_projects', 0)
                    self.ecosystems_breakdown = data.get('ecosystems_breakdown', {})
                    self._raw_data = data
            
            analysis = AnalysisData(data)
            
            if verbose:
                click.echo(f"Loaded {len(analysis.projects)} projects from {analysis.organization_name}")
                click.echo(f"Analysis timestamp: {analysis.timestamp}")
        
        except FileNotFoundError:
            click.echo(f"Error: Input file not found: {input_file}", err=True)
            raise click.Abort()
        except json.JSONDecodeError:
            click.echo(f"Error: Invalid JSON in input file: {input_file}", err=True)
            raise click.Abort()
    
    else:
        # Analysis mode: validate required parameters
        if not all([platform, source, token, org]):
            click.echo("Error: -p/--platform, -s/--source, -t/--token, and -o/--org are required for analysis mode", err=True)
            click.echo("Tip: Use -i/--input to run coverage on existing analysis.json", err=True)
            raise click.Abort()
        
        try:
            # Initialize analyzer with platform credentials
            analyzer = RepositoryAnalyzer(platform=platform, url=source, token=token, max_workers=workers)
            
            if repo:
                # Analyze specific repository
                # For GitHub, need to combine org/repo format
                if platform.lower() == 'github' and '/' not in repo:
                    repo_spec = f"{org}/{repo}"
                else:
                    repo_spec = repo
                
                if verbose:
                    click.echo(f"Analyzing repository {repo_spec} on {platform}")
                analysis = analyzer.analyze_repository(repo_spec)
            else:
                # Analyze entire organization
                if verbose:
                    click.echo(f"Analyzing {org} organization on {platform}")
                    click.echo(f"Using {workers} parallel workers")

                analysis = analyzer.analyze_organization(org)
        
        except Exception as e:
            click.echo(f"Analysis failed: {e}", err=True)
            raise click.Abort()
    
    # Run coverage analysis if requested (works for both input and analysis modes)
    if coverage:
        if verbose:
            click.echo("\nRunning Chainguard coverage analysis...")
            click.echo("Checking for adoption indicators...")
        
        coverage_checker = CoverageChecker()
        coverage_results = coverage_checker.analyze_project_dependencies(analysis.projects, check_adoption=True)
        
        # Add coverage results to analysis
        analysis.coverage_analysis = coverage_results
        
        if verbose:
            click.echo("\nCoverage Analysis Results:")
            for ecosystem, data in coverage_results.items():
                if ecosystem == 'adoption_indicators':
                    continue
                if data['total'] > 0:
                    click.echo(f"   {ecosystem.upper()}: {data['available']}/{data['total']} available ({data['percentage']}%)")
            

    # Save results
    if input_file:
        # In coverage-only mode, merge coverage results with original data
        import os
        output_data = analysis._raw_data.copy()
        if coverage:
            output_data['coverage_analysis'] = coverage_results
        
        # Ensure output directory exists
        output_dir = os.path.dirname(output)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        with open(output, 'w') as f:
            json.dump(output_data, f, indent=2, default=str)
    else:
        # In analysis mode, convert to dict and add coverage if present
        from dataclasses import asdict
        import os
        output_data = asdict(analysis)
        if coverage and hasattr(analysis, 'coverage_analysis') and analysis.coverage_analysis:
            output_data['coverage_analysis'] = analysis.coverage_analysis
        
        # Ensure output directory exists
        output_dir = os.path.dirname(output)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        with open(output, 'w') as f:
            json.dump(output_data, f, indent=2, default=str)

    if verbose:
        click.echo("\nAnalysis Complete:")
        if input_file:
            click.echo(f"   Input file: {input_file}")
        elif repo:
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
        repos_with_chainguard_images = 0
        total_chainguard_images = []
        
        for project in analysis.projects:
            if hasattr(project, 'dockerfile_adoption') and project.dockerfile_adoption:
                repos_with_dockerfiles += 1
                if project.dockerfile_adoption.get('adoption_detected'):
                    repos_with_chainguard_images += 1
                    total_chainguard_images.extend(project.dockerfile_adoption.get('chainguard_images', []))
        
        if repos_with_dockerfiles > 0:
            click.echo("\nDockerfile Adoption:")
            click.echo(f"   Repos with Dockerfiles: {repos_with_dockerfiles}/{len(analysis.projects)}")
            click.echo(f"   Repos using Chainguard: {repos_with_chainguard_images}/{repos_with_dockerfiles}")
            if repos_with_chainguard_images > 0:
                click.echo(f"   Total Chainguard images: {len(total_chainguard_images)}")

    click.echo(f"Report saved to: {output}")

    elapsed = time.time() - start_time
    if verbose:
        click.echo(f"Completed in {elapsed:.2f}s")


if __name__ == "__main__":
    cli()