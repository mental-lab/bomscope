#!/usr/bin/env python3
"""
Simple CLI for testing ecosystems-evaluate functionality.

Usage:
    python cli.py analyze-repo gitlab https://gitlab.com TOKEN group/project
    python cli.py analyze-org gitlab https://gitlab.com TOKEN my-org
"""

import argparse
import json
import sys
from repo_analyzer.repository_analyzer import RepositoryAnalyzer


def analyze_repository(platform: str, url: str, token: str, repository: str):
    """Analyze a single repository."""
    print(f"Analyzing repository: {repository}")
    print(f"Platform: {platform}")
    print(f"URL: {url}")
    print()
    
    try:
        analyzer = RepositoryAnalyzer(platform, url, token)
        results = analyzer.analyze_repository(repository)
        
        print(f"Analysis Results:")
        print(f"  Organization: {results.organization_name}")
        print(f"  Platform: {results.platform}")
        print(f"  Total Projects: {results.total_projects}")
        print(f"  Analyzed Projects: {results.analyzed_projects}")
        print(f"  Total Dependencies: {results.total_dependencies}")
        print()
        
        if results.projects:
            project = results.projects[0]
            print(f"Project Details:")
            print(f"  Name: {project.name}")
            print(f"  Language: {project.language}")
            print(f"  Dependencies Found: {len(project.dependencies)}")
            
            if project.dependencies:
                print(f"  Manifest Files:")
                for dep_info in project.dependencies:
                    print(f"    - {dep_info.file_path} ({dep_info.ecosystem}, {len(dep_info.dependencies)} deps)")
        
        return results
        
    except Exception as e:
        print(f"Error: {e}")
        return None


def analyze_organization(platform: str, url: str, token: str, organization: str):
    """Analyze an entire organization."""
    print(f"Analyzing organization: {organization}")
    print(f"Platform: {platform}")
    print(f"URL: {url}")
    print()
    
    try:
        analyzer = RepositoryAnalyzer(platform, url, token)
        results = analyzer.analyze_organization(organization)
        
        print(f"Analysis Results:")
        print(f"  Organization: {results.organization_name}")
        print(f"  Platform: {results.platform}")
        print(f"  Total Projects: {results.total_projects}")
        print(f"  Analyzed Projects: {results.analyzed_projects}")
        print(f"  Total Dependencies: {results.total_dependencies}")
        print()
        
        # Show ecosystem breakdown
        if results.ecosystems_breakdown:
            print("Ecosystem Breakdown:")
            for ecosystem, data in results.ecosystems_breakdown.items():
                print(f"  {ecosystem}: {data.get('unique_dependencies', 0)} unique dependencies")
        
        # Show top projects with dependencies
        projects_with_deps = [p for p in results.projects if p.dependencies]
        if projects_with_deps:
            print(f"\nTop Projects with Dependencies:")
            for project in projects_with_deps[:5]:  # Show top 5
                print(f"  - {project.name}: {len(project.dependencies)} manifest files")
        
        return results
        
    except Exception as e:
        print(f"Error: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description='Ecosystems Evaluate CLI')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Analyze repository command
    repo_parser = subparsers.add_parser('analyze-repo', help='Analyze a single repository')
    repo_parser.add_argument('platform', choices=['gitlab', 'github'], help='Platform name')
    repo_parser.add_argument('url', help='Platform URL (e.g., https://gitlab.com)')
    repo_parser.add_argument('token', help='Authentication token')
    repo_parser.add_argument('repository', help='Repository identifier (e.g., group/project)')
    
    # Analyze organization command
    org_parser = subparsers.add_parser('analyze-org', help='Analyze an organization')
    org_parser.add_argument('platform', choices=['gitlab', 'github'], help='Platform name')
    org_parser.add_argument('url', help='Platform URL (e.g., https://gitlab.com)')
    org_parser.add_argument('token', help='Authentication token')
    org_parser.add_argument('organization', help='Organization/group name')
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Execute command
    if args.command == 'analyze-repo':
        results = analyze_repository(args.platform, args.url, args.token, args.repository)
    elif args.command == 'analyze-org':
        results = analyze_organization(args.platform, args.url, args.token, args.organization)
    
    # Optionally save results to JSON
    if results:
        output_file = f"{results.organization_name}-analysis.json"
        try:
            from dataclasses import asdict
            with open(output_file, 'w') as f:
                json.dump(asdict(results), f, indent=2, default=str)
            print(f"\nResults saved to: {output_file}")
        except Exception as e:
            print(f"Could not save results: {e}")


if __name__ == '__main__':
    main()
