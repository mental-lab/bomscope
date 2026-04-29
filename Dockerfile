FROM cgr.dev/chainguard/python:latest-dev

USER 65532
WORKDIR /home/nonroot

# Install dependencies from pinned requirements
COPY requirements.txt /home/nonroot/requirements.txt
RUN python -m venv /home/nonroot/venv \
 && /home/nonroot/venv/bin/pip install --upgrade pip \
 && /home/nonroot/venv/bin/pip install --no-cache-dir -r /home/nonroot/requirements.txt

# Copy application
COPY . /home/nonroot/

# Add venv to PATH
ENV PATH="/home/nonroot/venv/bin:${PATH}"

ENTRYPOINT ["python", "main.py"]
