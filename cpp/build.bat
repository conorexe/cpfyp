@echo off
REM Build script for Windows

echo ========================================
echo Building C++ Arbitrage Bot Engine
echo ========================================

REM Check if build directory exists
if not exist build mkdir build
cd build

echo.
echo Configuring with CMake...
cmake .. -DCMAKE_BUILD_TYPE=Release

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: CMake configuration failed!
    echo.
    echo Make sure you have:
    echo   1. CMake installed
    echo   2. Visual Studio or MSVC compiler
    echo   3. Boost and OpenSSL installed via vcpkg
    echo.
    echo Install vcpkg and dependencies:
    echo   git clone https://github.com/Microsoft/vcpkg.git
    echo   cd vcpkg
    echo   .\bootstrap-vcpkg.bat
    echo   .\vcpkg install boost:x64-windows openssl:x64-windows
    echo.
    echo Then configure with:
    echo   cmake .. -DCMAKE_TOOLCHAIN_FILE=[path-to-vcpkg]/scripts/buildsystems/vcpkg.cmake
    echo.
    pause
    exit /b 1
)

echo.
echo Building...
cmake --build . --config Release

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Build failed!
    pause
    exit /b 1
)

echo.
echo ========================================
echo Build successful!
echo ========================================
echo.
echo Executable: build\Release\arb_bot.exe
echo.
echo To run:
echo   cd build\Release
echo   arb_bot.exe
echo.
pause
