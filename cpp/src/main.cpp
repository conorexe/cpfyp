#include <iostream>
#include <memory>
#include <vector>
#include <thread>
#include <csignal>

#include <boost/asio.hpp>
#include <boost/asio/ssl.hpp>

#include "binance_client.hpp"
#include "kraken_client.hpp"
#include "coinbase_client.hpp"
#include "bybit_client.hpp"
#include "okx_client.hpp"
#include "price_feed_server.hpp"

namespace asio = boost::asio;
namespace ssl = asio::ssl;

static std::atomic<bool> running(true);

void signal_handler(int signal) {
    if (signal == SIGINT || signal == SIGTERM) {
        std::cout << "\nShutting down gracefully..." << std::endl;
        running = false;
    }
}

int main() {
    std::cout << R"(
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║     ⚡ CRYPTO ARBITRAGE BOT - C++ ENGINE ⚡              ║
║                                                           ║
║     High-performance WebSocket clients                    ║
║     Exchanges: Binance, Kraken, Coinbase, Bybit, OKX      ║
║     IPC Port: 5555                                        ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
)" << std::endl;

    // Setup signal handlers
    std::signal(SIGINT, signal_handler);
    std::signal(SIGTERM, signal_handler);

    try {
        // IO context for async operations
        asio::io_context ioc;
        
        // SSL context
        ssl::context ssl_ctx(ssl::context::tlsv12_client);
        ssl_ctx.set_default_verify_paths();
        ssl_ctx.set_verify_mode(ssl::verify_peer);
        
        // Create IPC server for sending prices to Python
        auto price_server = std::make_shared<arb::PriceFeedServer>(ioc, 5555);
        price_server->start();
        
        // Price update callback - broadcast to Python clients
        auto price_callback = [price_server](const arb::PriceUpdate& update) {
            price_server->broadcast_price(update);
            
            // Optional: print to console for debugging
            // std::cout << "[" << update.exchange << "] " << update.pair 
            //           << " Bid: " << update.bid << " Ask: " << update.ask << std::endl;
        };
        
        // Create exchange clients
        std::vector<std::shared_ptr<arb::WebSocketClient>> clients;
        
        auto binance = std::make_shared<arb::BinanceClient>(ioc, ssl_ctx);
        binance->set_callback(price_callback);
        clients.push_back(binance);
        
        auto kraken = std::make_shared<arb::KrakenClient>(ioc, ssl_ctx);
        kraken->set_callback(price_callback);
        clients.push_back(kraken);
        
        auto coinbase = std::make_shared<arb::CoinbaseClient>(ioc, ssl_ctx);
        coinbase->set_callback(price_callback);
        clients.push_back(coinbase);
        
        auto bybit = std::make_shared<arb::BybitClient>(ioc, ssl_ctx);
        bybit->set_callback(price_callback);
        clients.push_back(bybit);
        
        auto okx = std::make_shared<arb::OKXClient>(ioc, ssl_ctx);
        okx->set_callback(price_callback);
        clients.push_back(okx);
        
        // Start all clients
        std::cout << "Starting exchange connections..." << std::endl;
        for (auto& client : clients) {
            client->start();
        }
        
        std::cout << "All connections initiated. Running..." << std::endl;
        std::cout << "Press Ctrl+C to stop." << std::endl << std::endl;
        
        // Run IO context in worker threads
        const int num_threads = std::thread::hardware_concurrency();
        std::vector<std::thread> threads;
        threads.reserve(num_threads);
        
        for (int i = 0; i < num_threads - 1; ++i) {
            threads.emplace_back([&ioc]() {
                ioc.run();
            });
        }
        
        // Run in main thread too
        while (running) {
            ioc.run_for(std::chrono::milliseconds(100));
        }
        
        // Cleanup
        std::cout << "Stopping exchange clients..." << std::endl;
        for (auto& client : clients) {
            client->stop();
        }
        
        ioc.stop();
        
        for (auto& thread : threads) {
            if (thread.joinable()) {
                thread.join();
            }
        }
        
        std::cout << "Shutdown complete." << std::endl;
        
    } catch (const std::exception& e) {
        std::cerr << "Fatal error: " << e.what() << std::endl;
        return 1;
    }
    
    return 0;
}
