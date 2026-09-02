"""DockerfileAnalyzer: risk assessment + multi-stage alias handling."""
import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from bomscope.dockerfile_analyzer import DockerfileAnalyzer


class TestImageRisk(unittest.TestCase):
    def setUp(self):
        self.a = DockerfileAnalyzer()

    def test_floating_tags_flagged(self):
        self.assertIn("Untagged", self.a._assess_image_risk("alpine"))
        self.assertIn(":latest", self.a._assess_image_risk("alpine:latest"))
        self.assertIn(":latest", self.a._assess_image_risk("ubuntu:latest"))

    def test_pinned_versions_not_flagged(self):
        # Version-level EOL is endoflife.date's job, not this module's.
        for img in (
            "alpine:3.21", "alpine:3.14", "docker.io/library/alpine:3.20",
            "node:20-alpine", "node:9.1", "python:3.12-slim", "python:2.7",
            "postgres:16-alpine", "postgres:9.6", "ubuntu:22.04", "ubuntu:18.04",
            "nginx:1.27", "nginx:1.19.6", "golang:1.17.3",
        ):
            self.assertIsNone(self.a._assess_image_risk(img), img)

    def test_trusted_registry_exempt(self):
        a = DockerfileAnalyzer(trusted_registries=["cgr.dev"])
        self.assertIsNone(a._assess_image_risk("cgr.dev/chainguard/python:latest"))
        self.assertIsNotNone(a._assess_image_risk("ubuntu:latest"))


class TestParseDockerfile(unittest.TestCase):
    def test_multistage_aliases_skipped(self):
        df = textwrap.dedent("""\
            FROM --platform=linux/amd64 node:20-alpine AS base
            FROM base AS builder
            RUN echo hi
            FROM alpine:3.21
            FROM scratch
            FROM ${REGISTRY}/img:latest
            FROM ubuntu:18.04 AS legacy
            FROM legacy
        """)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "Dockerfile"
            p.write_text(df)
            images = DockerfileAnalyzer()._parse_dockerfile(p)
        # External images kept; base/builder/legacy aliases, scratch, and
        # ${REGISTRY} build-arg placeholders are skipped.
        self.assertEqual(
            sorted(images),
            sorted(["node:20-alpine", "alpine:3.21", "ubuntu:18.04"]),
        )


if __name__ == "__main__":
    unittest.main()
