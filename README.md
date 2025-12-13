# Ecosystems Evaluate

**Multi-platform dependency analysis tool for Chainguard coverage assessment.**

## Status
**Work in Progress** - Initial development phase

## Goal
Analyze repositories across multiple platforms (GitLab, GitHub, Azure DevOps, Bitbucket) to extract dependency information for Chainguard package coverage analysis.

## Planned Features
- Multi-platform repository access
- Dependency manifest parsing (Python, Java, JavaScript)
- Parallel processing for performance
- JSON output for integration with Chainguard tools

## Development Setup

### Prerequisites
- Python 3.9+
- Virtual environment support

### Installation
```bash
# Create virtual environment and install dependencies
make install

# Verify setup
source venv/bin/activate
python --version
```

### Cleanup
```bash
# Remove virtual environment
make clean-all
```