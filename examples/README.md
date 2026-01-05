# Examples

See [`sample_output.json`](./sample_output.json) for example output format.

## Basic Usage

### Using .env file (Recommended)

```bash
# 1. Configure .env
PLATFORM=gitlab
SOURCE=https://gitlab.com
TOKEN=glpat-xxx
ORG=my-org

# 2. Run
python3 main.py -O analysis.json -v
```

### Using CLI flags

```bash
# GitLab
python3 main.py -p gitlab -s https://gitlab.com -t $TOKEN -o my-org -O analysis.json -v

# GitHub
python3 main.py -p github -s https://github.com -t $TOKEN -o my-org -O analysis.json -v

# Azure DevOps
python3 main.py -p ado -s https://dev.azure.com/my-org -t $TOKEN -o my-org -O analysis.json -v
```

## With Coverage Analysis

```bash
# Add Chainguard credentials to .env
CHAINGUARD_PYTHON_USERNAME=your_username
CHAINGUARD_PYTHON_PASSWORD=your_token
CHAINGUARD_JAVA_USERNAME=your_username
CHAINGUARD_JAVA_PASSWORD=your_token

# Run with coverage
python3 main.py -O analysis.json --coverage -v
```

## Advanced

```bash
# Specific repository
python3 main.py -p github -t $TOKEN -o my-org -r owner/repo -O analysis.json -v

# More workers for large orgs
python3 main.py -O analysis.json -w 8 -v

# Add coverage to existing analysis
python3 main.py -i analysis.json -O output.json --coverage -v
```
