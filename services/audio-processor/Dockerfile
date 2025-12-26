# Stage 1: Build librespot from source for Spotify Premium streaming
FROM rust:1.83-slim-bookworm AS librespot-builder

RUN apt-get update && apt-get install -y \
    libasound2-dev \
    libssl-dev \
    pkg-config \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install librespot with pulseaudio backend disabled, pipe backend enabled
# Pin to 0.6.0 which supports Rust 1.75+ (0.8.0 requires Rust 1.85+)
RUN cargo install librespot \
    --version 0.6.0 \
    --locked \
    --no-default-features \
    --features "rodio-backend"

# Stage 2: Python runtime with audio processing tools
FROM python:3.11-slim-bookworm

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    rubberband-cli \
    libsndfile1 \
    libffi-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy librespot binary from builder
COPY --from=librespot-builder /usr/local/cargo/bin/librespot /usr/local/bin/librespot

# Install yt-dlp
RUN pip install --no-cache-dir yt-dlp

# Set working directory
WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create temp directory for audio files
RUN mkdir -p /tmp/audio

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
