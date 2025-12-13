FROM cgr.dev/chainguard/python:latest-dev

USER 65532
WORKDIR /home/nonroot

# Install dependencies
RUN python -m venv /home/nonroot/venv \
 && /home/nonroot/venv/bin/pip install --upgrade pip \
 && /home/nonroot/venv/bin/pip install --no-cache-dir requests packaging click PyYAML pydantic

# Copy application (when ready)
COPY . /home/nonroot/

# Add venv to PATH
ENV PATH="/home/nonroot/venv/bin:${PATH}"

# Default to shell for now (no main.py yet)
CMD ["/bin/sh"]
