# ---------- Stage 1: build the Vue viewer ----------
FROM node:22-alpine AS viewer

WORKDIR /build
COPY package.json package-lock.json vite.config.js ./
COPY viewer ./viewer
RUN npm ci && npm run build
# Output lands in /build/docs per vite.config.js

# ---------- Stage 2: Python deps + runtime binaries rootfs ----------
# The -dev image has apk and a shell; the final runtime image has neither.
FROM cgr.dev/chainguard/python:latest-dev AS pybuild

USER root
# Install the analyzer's binary deps into a standalone rootfs we can overlay
# onto the minimal runtime image (all Wolfi packages, same glibc). Keys and
# repo config are resolved relative to /rootfs, so seed them first.
# Note: busybox provides /bin/sh, which git requires to spawn its local
# upload-pack/fetch-pack helpers (mirror cache clones run through the shell).
RUN mkdir -p /rootfs/etc/apk \
 && cp -r /etc/apk/keys /rootfs/etc/apk/keys \
 && cp /etc/apk/repositories /rootfs/etc/apk/repositories \
 && apk add --no-cache --initdb --root /rootfs git syft grype ca-certificates busybox

# /data: embedded SQLite DB + repo mirror cache + credential key.
# Ownership is copied into fresh named volumes by Docker on first mount,
# so it must be nonroot-owned in the image itself.
RUN mkdir -p /data/repo-cache && chown -R 65532:65532 /data

# The Chainguard python base ships its own site-packages (setuptools/msgpack)
# that scanners flag; upgrade past the known CVEs in this (shelled) stage and
# overlay them onto the minimal runtime below.
USER root
RUN pip install --no-cache-dir --upgrade "setuptools>=78.1.1" "msgpack>=1.2.1"

USER 65532
WORKDIR /home/nonroot
COPY requirements.txt /home/nonroot/requirements.txt
RUN python -m venv /home/nonroot/venv \
 && /home/nonroot/venv/bin/pip install --upgrade pip "setuptools>=78.1.1" \
 && /home/nonroot/venv/bin/pip install --no-cache-dir -r /home/nonroot/requirements.txt

# ---------- Stage 3: minimal runtime (no shell, no apk) ----------
FROM cgr.dev/chainguard/python:latest

# Upgraded base site-packages from pybuild (minimal runtime has no pip/shell)
COPY --from=pybuild /usr/lib/python3.14 /usr/lib/python3.14

# Analyzer binaries from the Wolfi rootfs; venv and /data from pybuild
COPY --from=pybuild /rootfs/ /
COPY --from=pybuild /home/nonroot/venv /home/nonroot/venv
COPY --from=pybuild --chown=65532:65532 /data /data

WORKDIR /home/nonroot
COPY main.py /home/nonroot/main.py
COPY bomscope /home/nonroot/bomscope
COPY --from=viewer /build/docs /home/nonroot/docs

VOLUME ["/data"]

ENV PATH="/home/nonroot/venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    GIT_SSL_CAINFO=/etc/ssl/certs/ca-certificates.crt

# Default: run the web service as nonroot (65532). Override with
# `python main.py ...` for CLI scans (see docker-compose.yml).
EXPOSE 8000
ENTRYPOINT ["uvicorn", "bomscope.api:app", "--host", "0.0.0.0", "--port", "8000"]
