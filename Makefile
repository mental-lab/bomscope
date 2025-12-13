# Ecosystems Evaluate - Makefile

.PHONY: help venv install clean clean-all

help:
	@echo "Ecosystems Evaluate - Dependency Analysis Tool"
	@echo ""
	@echo "Commands:"
	@echo "  make venv       Create virtual environment"
	@echo "  make install    Install dependencies"
	@echo "  make clean      Clean up results"
	@echo "  make clean-all  Clean results and venv"

# Create virtual environment
venv:
	@if [ ! -d "venv" ]; then \
		echo "Creating virtual environment..."; \
		python3 -m venv venv; \
		echo "Virtual environment created"; \
	else \
		echo "Virtual environment already exists"; \
	fi

# Install dependencies
install: venv
	@echo "Installing dependencies..."
	@. venv/bin/activate && pip install --upgrade pip
	@. venv/bin/activate && pip install requests packaging click PyYAML pydantic
	@echo ""
	@echo "Installation complete!"

# Clean results
clean:
	@rm -rf results/
	@echo "Results cleaned"

# Clean everything including venv
clean-all: clean
	@rm -rf venv/
	@echo "Complete cleanup done"
