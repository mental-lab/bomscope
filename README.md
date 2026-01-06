# Ecosystems Evaluate

Dependency and container image analysis for GitLab, GitHub, and Azure DevOps.

## Requirements

- Python 3.8+
- Git
- Syft - Install: `brew install syft` or https://github.com/anchore/syft

## Quick Start

```bash
# Install
git clone <repo-url>
cd ecosystems-evaluate
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Analyze organization
python3 main.py -p github -s https://github.com -t TOKEN -o org-name -O analysis.json --coverage -v

# Analyze single repo
python3 main.py -p github -s https://github.com -t TOKEN -o org-name -r repo-name -O analysis.json --coverage -v
```

## Supported Platforms

- **GitLab** - gitlab.com or self-hosted
- **GitHub** - github.com or Enterprise
- **Azure DevOps** - dev.azure.com or Server

## What Gets Detected

- All ecosystems: Python, Java, JavaScript, Go, Rust, Ruby, .NET, Swift, Elixir, PHP, and more
- Dockerfile base images and Chainguard adoption
- GitHub Actions and workflows

## Output

```
Projects analyzed: 14/18
Total dependencies: 9,219

Dockerfile Adoption:
   Repos with Dockerfiles: 10/14
   Repos using Chainguard: 6/10

Coverage Analysis:
   PYTHON: 18/24 available (75.0%)
```

## Chainguard Coverage (Optional)

```bash
export CHAINGUARD_PYTHON_USERNAME=username
export CHAINGUARD_PYTHON_PASSWORD=token
```

Get credentials: https://console.chainguard.dev/

## Options

Run `python3 main.py --help` for all options.
- `-p, --platform` - Platform: gitlab, github, ado
- `-o, --org` - Organization/group name
- `-r, --repo` - Specific repository (optional)
- `-O, --output` - Output file path
- `--coverage` - Include Chainguard coverage analysis
- `-v, --verbose` - Show progress

## Examples

See [examples/README.md](examples/README.md) for more usage examples.

## Getting Tokens

- **GitLab**: Settings → Access Tokens → `read_api` + `read_repository`
- **GitHub**: Settings → Developer settings → PAT → `repo` scope
- **Azure DevOps**: User settings → PAT → `Code (read)` scope