# --- Builder stage ---
    FROM rust:1-bookworm AS builder
    WORKDIR /app
    
    # Install build deps (openssl is optional; keep if your deps need it)
    RUN apt-get update && apt-get install -y --no-install-recommends pkg-config libssl-dev ca-certificates && rm -rf /var/lib/apt/lists/*
    
    # Leverage build cache
    COPY Cargo.toml Cargo.lock ./
    COPY src ./src
    COPY migrations ./migrations
    
    RUN cargo build --release
    
    # --- Runtime stage ---
  FROM debian:bookworm-slim AS runtime
  RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates libssl3 curl ffmpeg python3 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 10001 appuser
  
  RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp \
    && chmod a+rx /usr/local/bin/yt-dlp \
    && /usr/local/bin/yt-dlp --version
  COPY --from=builder /app/target/release/backend /usr/local/bin/app
  RUN yt-dlp --rm-cache-dir
  ENV RUST_LOG=info
  EXPOSE 8000
  USER appuser
  CMD ["/usr/local/bin/app"]