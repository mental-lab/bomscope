# Ecosystems Evaluate

Analyze dependencies across GitLab, GitHub, and Azure DevOps organizations.

## Quick Start

### 1. Install

```bash
git clone <repo-url>
cd ecosystems-evaluate
make install
source venv/bin/activate
```

### 2. Configure

Create `.env` file:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```bash
PLATFORM=gitlab
SOURCE=https://gitlab.com
TOKEN=your_token_here
ORG=your_org_name
```

### 3. Run

```bash
# Basic analysis
python3 main.py -O analysis.json -v

# With Chainguard coverage
python3 main.py -O analysis.json --coverage -v
```

## Supported Platforms

- **GitLab** - gitlab.com or self-hosted
- **GitHub** - github.com or Enterprise
- **Azure DevOps** - dev.azure.com or Server

## Supported Ecosystems

- **Python** - requirements.txt, pyproject.toml, Pipfile, setup.py
- **Java** - pom.xml, build.gradle
- **JavaScript** - package.json, package-lock.json, yarn.lock

## Chainguard Coverage (Optional)

To check which dependencies are available in Chainguard Libraries, add to `.env`:

```bash
CHAINGUARD_PYTHON_USERNAME=your_username
CHAINGUARD_PYTHON_PASSWORD=your_token
CHAINGUARD_JAVA_USERNAME=your_username
CHAINGUARD_JAVA_PASSWORD=your_token
```

Get credentials from: https://console.chainguard.dev/

## CLI Options

Run `python3 main.py --help` for all options.

**Common flags:**
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