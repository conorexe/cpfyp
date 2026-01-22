# C++ High-Performance WebSocket Engine

This directory contains the high-performance C++ implementation of the WebSocket clients for the arbitrage bot.

## Why C++?

The C++ engine provides **50-100x lower latency** compared to Python for:
- WebSocket message processing
- JSON parsing
- Price update handling

This is critical for arbitrage trading where opportunities can disappear in milliseconds.

## Prerequisites

### Windows (MSVC)
```powershell
# Install vcpkg for package management
git clone https://github.com/Microsoft/vcpkg.git
cd vcpkg
.\bootstrap-vcpkg.bat

# Install dependencies
.\vcpkg install boost:x64-windows openssl:x64-windows
```

### Linux/Mac
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install build-essential cmake libboost-all-dev libssl-dev

# macOS
brew install cmake boost openssl
```

## Building

```bash
# Create build directory
mkdir build
cd build

# Configure (Windows with vcpkg)
cmake .. -DCMAKE_TOOLCHAIN_FILE=[path-to-vcpkg]/scripts/buildsystems/vcpkg.cmake

# Configure (Linux/Mac)
cmake ..

# Build
cmake --build . --config Release

# Or on Linux/Mac with make
make -j$(nproc)
```

## Running

```bash
# From cpp/build directory
./arb_bot          # Linux/Mac
.\arb_bot.exe      # Windows
```

The C++ engine will:
1. Connect to Binance, Kraken, and Coinbase WebSocket APIs
2. Parse real-time price feeds
3. Stream price updates to Python dashboard via TCP (port 5555)

## Architecture

```
┌─────────────────────────────────────┐
│  C++ Engine (arb_bot)               │
│                                     │
│  ┌─────────────────────────────┐   │
│  │ Binance WebSocket           │   │
│  │ Kraken WebSocket            │   │
│  │ Coinbase WebSocket          │   │
│  └───────────┬─────────────────┘   │
│              │                      │
│  ┌───────────▼─────────────────┐   │
│  │ Price Feed Server (TCP)     │   │
│  │ Port: 5555                  │   │
│  └───────────┬─────────────────┘   │
└──────────────┼─────────────────────┘
               │
               │ TCP Stream (JSON lines)
               │
┌──────────────▼─────────────────────┐
│  Python Dashboard                  │
│  ┌─────────────────────────────┐   │
│  │ CppBridgeClient             │   │
│  │ - Receives price updates    │   │
│  │ - Forwards to engine        │   │
│  └─────────────────────────────┘   │
│                                     │
│  ┌─────────────────────────────┐   │
│  │ ArbitrageEngine             │   │
│  │ Web Dashboard               │   │
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘
```

## Performance Notes

- **Zero-copy parsing**: Boost.Beast provides efficient buffer management
- **Multi-threaded**: Uses thread pool for I/O operations
- **Connection pooling**: Maintains persistent WebSocket connections
- **Efficient JSON**: Boost.JSON is optimized for speed

Expected performance:
- Message processing: <100μs per update
- End-to-end latency: <1ms (network + processing)
- Throughput: >10,000 updates/second

## Troubleshooting

### "Cannot find Boost"
Ensure Boost is installed and CMake can find it. On Windows with vcpkg, use the toolchain file.

### "SSL verification failed"
The C++ engine verifies SSL certificates. Ensure OpenSSL is properly installed with CA certificates.

### "Connection refused on port 5555"
The Python dashboard connects to this port. Make sure the C++ engine starts first.

## Development

To add a new exchange:
1. Create `include/newexchange_client.hpp`
2. Implement `src/newexchange_client.cpp`
3. Add to `CMakeLists.txt`
4. Instantiate in `src/main.cpp`
