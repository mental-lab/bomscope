# Ecosystems Evaluate

Analyze dependencies across GitLab, GitHub, and Azure DevOps organizations.

## Quick Deploy (Fork & Run)

**Want to deploy your own analysis dashboard?**

1. **Fork this repository**
2. **Add GitHub Secrets** (Settings → Secrets and variables → Actions):
   - `PLATFORM_TOKEN` - Your GitLab/GitHub/ADO access token
   - `ORGANIZATION` - Organization name to analyze
   - `PLATFORM` - Platform type (`gitlab`, `github`, or `ado`)
   - `SOURCE` - Platform URL (e.g., `https://gitlab.com`)
   - Optional: `CHAINGUARD_PYTHON_USERNAME`, `CHAINGUARD_PYTHON_PASSWORD`, `CHAINGUARD_JAVA_USERNAME`, `CHAINGUARD_JAVA_PASSWORD`
3. **Enable GitHub Pages** (Settings → Pages → Source: GitHub Actions)
4. **Run the workflow** (Actions → Analyze Dependencies and Deploy Viewer → Run workflow)
5. **View results** at `https://YOUR-USERNAME.github.io/ecosystems-evaluate/`

The dashboard will automatically load your analysis results!

## Quick Start (Local)

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
