# Ecosystems Evaluate

Multi-platform dependency analysis tool for GitLab, GitHub, and Azure DevOps repositories.

## Features

**Platform Support**
- GitLab
- GitHub
- Azure DevOps

**Ecosystem Parsing**
- **Python**: requirements.txt, pyproject.toml, Pipfile, setup.py
- **Java**: pom.xml, build.gradle
- **JavaScript**: package.json, package-lock.json, yarn.lock, pnpm-lock.yaml

**Analysis Options**
- Analyze entire organizations/groups
- Analyze individual repositories
- JSON output for integration

## Quick Start

### Prerequisites
- Python 3.9+
- Git
- Personal access token for your platform (GitLab/GitHub/Azure DevOps)

### Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd ecosystems-evaluate

# Create virtual environment and install dependencies
make install

# Activate virtual environment
source venv/bin/activate
```

### Usage

#### Analyze an entire GitLab group
```bash
python3 main.py -p gitlab -s https://gitlab.com -t YOUR_TOKEN -o your-group-name -O analysis.json -v
```

#### Analyze a GitHub organization
```bash
python3 main.py -p github -s https://github.com -t YOUR_TOKEN -o your-org-name -O analysis.json -v
```

#### Analyze an Azure DevOps organization
```bash
python3 main.py -p ado -s https://dev.azure.com/your-org -t YOUR_TOKEN -o your-org-name -O analysis.json -v
```

#### Analyze a specific repository
```bash
python3 main.py -p gitlab -s https://gitlab.com -t YOUR_TOKEN -o group-name -r group-name/project-name -O repo-analysis.json -v
```

### Command Line Options

| Option | Description | Required |
|--------|-------------|----------|
| `-p, --platform` | Platform: gitlab, github, ado | Yes |
| `-s, --source` | Platform URL (e.g., https://gitlab.com) | Yes |
| `-t, --token` | Personal access token | Yes |
| `-o, --org` | Organization/group name to analyze | Yes |
| `-r, --repo` | Specific repository (format: owner/repo) | No |
| `-O, --output` | Output JSON file path | Yes |
| `-w, --workers` | Number of parallel workers (default: 4) | No |
| `-v, --verbose` | Enable verbose output | No |

## Getting Access Tokens

### GitLab Personal Access Token
1. Go to GitLab → User Settings → Access Tokens
2. Create token with `read_api` and `read_repository` scopes
3. Copy the token value

### GitHub Personal Access Token
1. Go to GitHub → Settings → Developer settings → Personal access tokens
2. Generate new token (classic) with `repo` scope for private repos, or no scopes for public repos
3. Copy the token value

### Azure DevOps Personal Access Token
1. Go to Azure DevOps → User settings → Personal access tokens
2. Create new token with `Code (read)` scope
3. Copy the token value

## Output Format

The tool generates a comprehensive JSON report containing:

```json
{
  "organization_name": "your-org",
  "platform": "gitlab",
  "total_projects": 25,
  "analyzed_projects": 23,
  "total_dependencies": 456,
  "ecosystems_breakdown": {
    "python": {"total_dependencies": 200, "total_projects": 15},
    "java": {"total_dependencies": 150, "total_projects": 8},
    "javascript": {"total_dependencies": 106, "total_projects": 12}
  },
  "projects": [
    {
      "name": "my-project",
      "language": "Python",
      "dependencies": [
        {
          "file_path": "requirements.txt",
          "ecosystem": "python",
          "dependencies": [
            {"name": "flask", "version": "2.3.0"},
            {"name": "requests", "version": ">=2.28.0"}
          ]
        }
      ]
    }
  ]
}
```

## Development

### Running Tests
```bash
make test
```

### Project Structure
```
ecosystems-evaluate/
├── main.py                 # CLI entry point
├── repo_analyzer/          # Core analysis modules
│   ├── parsers.py         # Dependency manifest parsers
│   ├── models.py          # Data models
│   ├── platform_analyzers.py  # Base platform analyzer
│   ├── gitlab_analyzer.py     # GitLab-specific logic
│   ├── github_analyzer.py     # GitHub-specific logic
│   ├── azure_devops_analyzer.py # Azure DevOps-specific logic
│   └── repository_analyzer.py # Main orchestration
├── tests/                  # Test suite
└── Makefile               # Development commands
```

## Enterprise Support

**SSL Certificate Control**
For enterprise environments with self-signed certificates, you can disable SSL verification:

```bash
# Add --no-ssl-verify flag for self-signed certificates
python3 main.py -p ado -s https://tfs.company.com -t YOUR_TOKEN -o your-org --no-ssl-verify -O analysis.json -v
```

**Supported Enterprise Platforms**
- GitHub Enterprise Server
- GitLab self-hosted instances  
- Azure DevOps Server (on-premise)

## Troubleshooting

**Authentication Error (401)**
- Verify your token has correct permissions
- Check token hasn't expired
- For Azure DevOps: Ensure token has `Code (read)` scope

**No Dependencies Found**
- Verify repositories contain supported manifest files
- Use `-v` flag for verbose output

**SSL Certificate Issues**
- Use `--no-ssl-verify` flag for self-signed certificates
- Ensure your enterprise certificates are properly configured

**Getting Help**
```bash
python3 main.py --help
```