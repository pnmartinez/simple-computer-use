# ================================
# Build stage for Python dependencies
# ================================
FROM python:3.12-slim AS builder

# Set environment variables for build
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python dependencies
COPY requirements-py311.txt /tmp/requirements.txt
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt

# ================================
# Runtime stage
# ================================
FROM python:3.12-slim

# Install system dependencies for X11 and graphics
RUN apt-get update && apt-get install -y \
    # X11 dependencies
    xvfb \
    x11-utils \
    xauth \
    x11-apps \
    x11vnc \
    xserver-xorg-video-dummy \
    # Graphics libraries
    libgl1 \
    libglx-mesa0 \
    libegl1 \
    libxrandr2 \
    libxss1 \
    libxxf86vm1 \
    libxi6 \
    libxtst6 \
    libxt6 \
    libxfixes3 \
    libsm6 \
    libxext6 \
    libgl1-mesa-dri \
    # Utilities
    scrot \
    imagemagick \
    wmctrl \
    xdotool \
    fluxbox \
    curl \
    gnupg \
    locales \
    # Fonts and locales
    fonts-liberation \
    && locale-gen en_US.UTF-8 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DISPLAY=:1 \
    XAUTHORITY=/tmp/.Xauthority \
    LANG=en_US.UTF-8 \
    LANGUAGE=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8 \
    TZ=UTC \
    PYTHONPATH=/app \
    PATH="/opt/venv/bin:$PATH"

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Create app user for security
RUN groupadd -r appuser && useradd -r -g appuser -m appuser

# Create application directory
WORKDIR /app

# Copy application code
COPY --chown=appuser:appuser . /app/

# Create necessary directories with proper permissions
RUN mkdir -p /tmp/.X11-unix \
             /tmp/.Xauthority \
             /app/data \
             /app/screenshots \
             /app/logs \
    && chmod 1777 /tmp/.X11-unix \
    && chmod 777 /tmp/.Xauthority \
    && chown -R appuser:appuser /app

# Make entrypoint executable
RUN chmod +x /app/entrypoint.sh

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 5000

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]
