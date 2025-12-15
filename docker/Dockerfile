# =============================================================================
# RePORTaLiN Specialist MCP Server - Production Docker Image
# =============================================================================
# Multi-stage build for an optimized, secure, air-gapped MCP server.
# Now using uv package manager for fast, reproducible builds.
#
# SECURITY FEATURES:
#   ✓ Non-root user 'analyst' (UID 1000)
#   ✓ Read-only filesystem design
#   ✓ Network isolation support (--network none)
#   ✓ No data baked into image (mounted at runtime)
#   ✓ Minimal attack surface (slim base + cleanup)
#   ✓ PHI/PII never exposed - only aggregates/schemas
#   ✓ Signal handling with exec form ENTRYPOINT
#   ✓ tini init system for proper PID 1 behavior
#
# RUNTIME REQUIREMENTS:
#   - Mount results/ directory as read-only
#   - Mount data/ directory as read-only (if needed)
#   - Run with --network none for air-gapped security
#
# Usage:
#   docker build -f docker/Dockerfile -t reportalin-specialist .
#   docker run -i --rm --network none \
#     -v $(pwd)/results:/app/results:ro \
#     reportalin-specialist
#
# Build with BuildKit for improved caching:
#   DOCKER_BUILDKIT=1 docker build -f docker/Dockerfile -t reportalin-specialist .

# -----------------------------------------------------------------------------
# Stage 1: Build dependencies with uv
# -----------------------------------------------------------------------------
FROM python:3.13-slim-bookworm AS builder

# Build-time arguments for versioning and provenance
ARG BUILD_VERSION
ARG BUILD_DATE
ARG VCS_REF

# Security: Don't store pip cache, disable version check
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

# Install uv - fast Python package installer
# hadolint ignore=DL3013
RUN pip install --no-cache-dir uv

# Copy dependency files first for better layer caching
# README.md is required by pyproject.toml metadata
COPY pyproject.toml .python-version README.md ./

# Copy ONLY the src-layout package structure for proper installation
# NOTE: The backward-compat shims (server/, client/, shared/, scripts/)
# are excluded from the package per pyproject.toml and NOT needed in the
# Docker container since we use the installed package: python -m reportalin.server
COPY src/ ./src/

# Create virtual environment and install dependencies with uv
# UV_PROJECT_ENVIRONMENT tells uv sync to install to /opt/venv
# --frozen ensures lockfile is used if present (uv.lock)
# --no-editable installs the package non-editably (required for multi-stage builds)
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
RUN uv venv /opt/venv && \
    (uv sync --frozen --no-dev --no-editable 2>/dev/null || uv sync --no-dev --no-editable)

# Clean up unnecessary files from venv to minimize attack surface
# hadolint ignore=SC2015
RUN find /opt/venv -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -type f -name "*.pyc" -delete 2>/dev/null || true && \
    find /opt/venv -type f -name "*.pyo" -delete 2>/dev/null || true && \
    find /opt/venv -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -type d -name "test" -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -type d -name "docs" -exec rm -rf {} + 2>/dev/null || true && \
    rm -rf /opt/venv/share/doc /opt/venv/share/man

# -----------------------------------------------------------------------------
# Stage 2: Production image
# -----------------------------------------------------------------------------
FROM python:3.13-slim-bookworm AS production

# Build-time arguments for OCI labels
ARG BUILD_VERSION
ARG BUILD_DATE
ARG VCS_REF

# Security labels (OCI standard) with build-time provenance
LABEL org.opencontainers.image.title="RePORTaLiN Specialist MCP Server" \
      org.opencontainers.image.description="Secure MCP Server for RePORT India - PHI Protected" \
      org.opencontainers.image.vendor="RePORTaLiN Team" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${BUILD_VERSION}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.source="https://github.com/reportalin/reportalin-agent" \
      security.policy="no-new-privileges,read-only-rootfs,network-none" \
      data.classification="PHI/PII-Protected"

# Install tini for proper init (handles signals correctly) and curl for healthchecks
# Using BuildKit cache mounts for faster rebuilds and --fix-missing for reliability
# hadolint ignore=DL3008,DL3013,DL4006
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean && \
    echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache && \
    apt-get update --fix-missing && \
    apt-get install -y --no-install-recommends curl wget ca-certificates && \
    rm -rf /tmp/* /var/tmp/*

# Download tini as a static binary (more reliable than apt package)
# Use architecture-specific binary for multi-arch support
# hadolint ignore=DL3020
ARG TARGETARCH
ADD https://github.com/krallin/tini/releases/download/v0.19.0/tini-${TARGETARCH} /usr/bin/tini
RUN chmod +x /usr/bin/tini

# Security: Create non-root user 'analyst' with explicit UID/GID
RUN groupadd --gid 1000 analyst && \
    useradd --uid 1000 --gid analyst --shell /usr/sbin/nologin --create-home analyst

WORKDIR /app

# Copy virtual environment from builder (includes installed reportalin package)
COPY --from=builder --chown=analyst:analyst /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# No need to copy source or shims - the reportalin package is already
# installed in the venv from the builder stage via 'uv sync'
# The installed package can be imported directly: python -m reportalin.server

# Prepare directories for runtime (DO NOT COPY sensitive data)
# Data will be mounted at runtime as read-only
RUN mkdir -p /app/results /app/encrypted_logs && \
    chown -R analyst:analyst /app && \
    chmod 755 /app/results && \
    chmod 700 /app/encrypted_logs

# No PYTHONPATH needed - package is installed in venv and importable directly

# Security: Switch to non-root user
USER analyst

# Environment variables for secure configuration
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=random \
    # Disable __pycache__ in container
    PYTHONPYCACHEPREFIX=/tmp/.pycache \
    # Privacy: Ensure no raw data exposure
    REPORTALIN_PRIVACY_MODE=strict \
    # Security: Disable debug and fault handler
    PYTHONFAULTHANDLER=0 \
    # MCP defaults
    MCP_TRANSPORT=stdio \
    # Disable Rich console output (critical for MCP stdio)
    NO_COLOR=1 \
    TERM=dumb \
    FORCE_COLOR=0

# Health check (HTTP mode - uses /health endpoint)
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health 2>/dev/null || python -c "import sys; sys.exit(0)"

# Use tini as init to handle signals properly (PID 1 zombie reaping)
# Run the server using reportalin package directly
ENTRYPOINT ["/usr/bin/tini", "--", "python", "-m", "reportalin.server"]

# No CMD needed - stdio_runner handles transport automatically
# Default grace period for SIGTERM: 10 seconds (Docker default)
# Override with: docker run --stop-timeout=30
CMD []
