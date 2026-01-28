# MarketScout - C++ Engine Dockerfile
# Multi-stage build for optimized production image

# =============================================================================
# Stage 1: Builder
# =============================================================================
FROM ubuntu:22.04 as builder

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    libboost-all-dev \
    libssl-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy C++ source code
COPY cpp/ ./cpp/

# Build the C++ engine
WORKDIR /app/cpp
RUN mkdir -p build && cd build && \
    cmake -DCMAKE_BUILD_TYPE=Release .. && \
    make -j$(nproc)

# =============================================================================
# Stage 2: Production
# =============================================================================
FROM ubuntu:22.04 as production

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libboost-system1.74.0 \
    libboost-thread1.74.0 \
    libssl3 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Copy the built binary
COPY --from=builder /app/cpp/build/arb_bot /app/arb_bot

# Switch to non-root user
USER appuser

# Health check - check if process is running
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD pgrep arb_bot || exit 1

# Expose IPC port
EXPOSE 5555

# Run the C++ engine
CMD ["./arb_bot"]
