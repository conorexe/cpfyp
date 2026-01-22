#!/bin/bash

echo "========================================"
echo "Building C++ Arbitrage Bot Engine"
echo "========================================"

# Check dependencies
check_dependency() {
    if ! command -v $1 &> /dev/null; then
        echo "ERROR: $1 not found!"
        echo "Please install $2"
        exit 1
    fi
}

check_dependency cmake "cmake"
check_dependency g++ "g++ or clang++"

# Create build directory
mkdir -p build
cd build

echo ""
echo "Configuring with CMake..."
cmake .. -DCMAKE_BUILD_TYPE=Release

if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: CMake configuration failed!"
    echo ""
    echo "Make sure you have Boost and OpenSSL installed:"
    echo ""
    echo "Ubuntu/Debian:"
    echo "  sudo apt install build-essential cmake libboost-all-dev libssl-dev"
    echo ""
    echo "macOS:"
    echo "  brew install cmake boost openssl"
    echo "  cmake .. -DOPENSSL_ROOT_DIR=/usr/local/opt/openssl"
    echo ""
    exit 1
fi

echo ""
echo "Building..."
make -j$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)

if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Build failed!"
    exit 1
fi

echo ""
echo "========================================"
echo "Build successful!"
echo "========================================"
echo ""
echo "Executable: build/arb_bot"
echo ""
echo "To run:"
echo "  cd build"
echo "  ./arb_bot"
echo ""
