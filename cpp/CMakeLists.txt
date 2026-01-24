cmake_minimum_required(VERSION 3.15)
project(CryptoArbBot CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find required packages
# Note: Boost.Beast is header-only, so we only need system and thread
find_package(Boost 1.70 REQUIRED COMPONENTS system thread)
find_package(OpenSSL REQUIRED)
find_package(Threads REQUIRED)

# Include directories
include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${Boost_INCLUDE_DIRS}
    ${OPENSSL_INCLUDE_DIR}
)

# Source files
set(SOURCES
    src/main.cpp
    src/price_update.cpp
    src/websocket_client.cpp
    src/binance_client.cpp
    src/kraken_client.cpp
    src/coinbase_client.cpp
    src/bybit_client.cpp
    src/okx_client.cpp
    src/price_feed_server.cpp
)

# Create executable
add_executable(arb_bot ${SOURCES})

# Link libraries
target_link_libraries(arb_bot
    ${Boost_LIBRARIES}
    OpenSSL::SSL
    OpenSSL::Crypto
    Threads::Threads
)

# Windows-specific libraries
if(WIN32)
    target_link_libraries(arb_bot ws2_32 wsock32)
endif()

# Compiler warnings
if(MSVC)
    target_compile_options(arb_bot PRIVATE /W4)
else()
    target_compile_options(arb_bot PRIVATE -Wall -Wextra -pedantic)
endif()
