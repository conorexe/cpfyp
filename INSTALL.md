# Installation Guide

Complete installation instructions for all modes of the Crypto Arbitrage Bot.

## Table of Contents
- [Python Mode](#python-mode)
- [C++ Mode](#c-mode)
- [Simulation Mode](#simulation-mode)
- [Troubleshooting](#troubleshooting)

---

## Python Mode

### Prerequisites
- Python 3.10 or higher
- pip package manager

### Installation

1. **Clone the repository** (or download the files)
```bash
git clone <your-repo-url>
cd crypto-arb-bot
```

2. **Install Python dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure the bot**
Edit `config.py`:
```python
MODE = "python"
```

4. **Run**
```bash
python main.py
```

5. **Open dashboard**
Navigate to http://localhost:8000

---

## C++ Mode

### Why C++?
- **50-100x faster** than Python
- **Sub-millisecond latency** for price processing
- **Production-ready** for high-frequency trading

### Prerequisites

#### Windows
- Visual Studio 2019 or later (with C++ tools)
- CMake 3.15+
- vcpkg (package manager)

#### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install build-essential cmake libboost-all-dev libssl-dev
```

#### macOS
```bash
brew install cmake boost openssl
```

### Installation

#### Windows

1. **Install vcpkg**
```powershell
git clone https://github.com/Microsoft/vcpkg.git C:\vcpkg
cd C:\vcpkg
.\bootstrap-vcpkg.bat
```

2. **Install dependencies**
```powershell
.\vcpkg install boost:x64-windows openssl:x64-windows
```

3. **Build the C++ engine**
```powershell
cd cpp
.\build.bat
```

Or manually:
```powershell
mkdir build
cd build
cmake .. -DCMAKE_TOOLCHAIN_FILE=C:\vcpkg\scripts\buildsystems\vcpkg.cmake
cmake --build . --config Release
```

4. **Run**
```powershell
# Terminal 1: Start C++ engine
cd cpp\build\Release
.\arb_bot.exe

# Terminal 2: Start Python dashboard
python main.py
```

#### Linux/macOS

1. **Build the C++ engine**
```bash
cd cpp
chmod +x build.sh
./build.sh
```

Or manually:
```bash
mkdir -p build
cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)
```

2. **Run**
```bash
# Terminal 1: Start C++ engine
cd cpp/build
./arb_bot

# Terminal 2: Start Python dashboard (from project root)
python main.py
```

### Configuration for C++ Mode

Edit `config.py`:
```python
MODE = "cpp"
```

The Python dashboard will automatically connect to the C++ engine via TCP (port 5555).

---

## Simulation Mode

Perfect for testing when:
- Network restrictions block exchange WebSockets
- You want to test without real connections
- Development/testing environment

### Installation

1. **Install Python dependencies** (same as Python mode)
```bash
pip install -r requirements.txt
```

2. **Configure**
Edit `config.py`:
```python
MODE = "simulation"
```

3. **Run**
```bash
python main.py
```

The bot will generate realistic price movements and arbitrage opportunities.

---

## Troubleshooting

### Python Issues

**Problem**: `ModuleNotFoundError: No module named 'websockets'`
```bash
pip install -r requirements.txt
```

**Problem**: Port 8000 already in use
```python
# Edit config.py
WEB_PORT = 8001  # Use a different port
```

### C++ Issues

**Problem**: CMake can't find Boost
```bash
# Linux
sudo apt install libboost-all-dev

# macOS
brew install boost
export BOOST_ROOT=/usr/local/opt/boost

# Windows
# Use vcpkg as shown in installation steps
```

**Problem**: CMake can't find OpenSSL
```bash
# Linux
sudo apt install libssl-dev

# macOS
brew install openssl
cmake .. -DOPENSSL_ROOT_DIR=/usr/local/opt/openssl

# Windows
# Use vcpkg - it handles paths automatically
```

**Problem**: "Connection refused on port 5555"
- Make sure the C++ engine (`arb_bot`) is running BEFORE starting Python
- Check if another process is using port 5555: `netstat -an | grep 5555`

**Problem**: SSL certificate errors
```bash
# Update CA certificates
# Linux
sudo apt install ca-certificates
sudo update-ca-certificates

# macOS
# Usually handled automatically by OpenSSL from Homebrew
```

### Network Issues

**Problem**: DNS blocking (Whalebone, corporate firewall)
- Use simulation mode: `MODE = "simulation"`
- Or use a VPN
- Or change DNS servers (8.8.8.8, 1.1.1.1)

**Problem**: Exchange WebSocket timeouts
- Check firewall settings
- Verify internet connection
- Some exchanges may be blocked in your region

### Dashboard Issues

**Problem**: Dashboard loads but no data
- Check console for connection errors
- Verify the bot is running and connected to exchanges
- Check browser console (F12) for WebSocket errors

**Problem**: "Failed to connect to ws://localhost:8000/ws"
- Make sure Python bot is running
- Check if port 8000 is accessible
- Try refreshing the page

---

## Verification

After installation, verify everything works:

1. **Start the bot** (in chosen mode)
2. **Open http://localhost:8000**
3. **Check the dashboard shows:**
   - ✅ Status indicator is green
   - ✅ "Connected" status
   - ✅ Price data in the table
   - ✅ Stats show exchanges connected

If you see arbitrage opportunities detected, congratulations! 🎉

---

## Next Steps

- Read the [README.md](README.md) for usage details
- Check [cpp/README.md](cpp/README.md) for C++ engine specifics
- Modify `config.py` to customize pairs and thresholds
- **Important**: Before trading real money, understand exchange fees, withdrawal times, and market risks!
