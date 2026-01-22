#include "binance_client.hpp"
#include <iostream>
#include <sstream>

// Simple JSON parser for compatibility with older Boost versions
namespace {
    std::string get_json_string(const std::string& json, const std::string& key) {
        auto pos = json.find("\"" + key + "\"");
        if (pos == std::string::npos) return "";
        pos = json.find(":", pos);
        pos = json.find("\"", pos);
        auto end = json.find("\"", pos + 1);
        if (pos == std::string::npos || end == std::string::npos) return "";
        return json.substr(pos + 1, end - pos - 1);
    }
    
    bool has_key(const std::string& json, const std::string& key) {
        return json.find("\"" + key + "\"") != std::string::npos;
    }
}

namespace arb {

BinanceClient::BinanceClient(asio::io_context& ioc, ssl::context& ssl_ctx)
    : WebSocketClient(
        ioc,
        ssl_ctx,
        "Binance",
        "stream.binance.com",
        "9443",
        "/ws/btcusdt@bookTicker/ethusdt@bookTicker/solusdt@bookTicker/xrpusdt@bookTicker"
    )
{
    // Setup pair mappings
    pair_mapping_["BTC/USDT"] = "btcusdt";
    pair_mapping_["ETH/USDT"] = "ethusdt";
    pair_mapping_["SOL/USDT"] = "solusdt";
    pair_mapping_["XRP/USDT"] = "xrpusdt";
    
    // Reverse mapping
    for (const auto& [normalized, binance_fmt] : pair_mapping_) {
        reverse_mapping_[binance_fmt] = normalized;
    }
}

std::string BinanceClient::get_subscribe_message() {
    // Binance uses URL-based subscription, no message needed
    return "";
}

void BinanceClient::parse_message(const std::string& message) {
    try {
        // Binance bookTicker format: {"u":12345,"s":"BTCUSDT","b":"50000.00","B":"1.5","a":"50001.00","A":"2.0"}
        if (!has_key(message, "s") || !has_key(message, "b") || !has_key(message, "a")) {
            return;
        }
        
        std::string symbol = get_json_string(message, "s");
        // Convert to lowercase for mapping
        std::transform(symbol.begin(), symbol.end(), symbol.begin(), ::tolower);
        
        auto it = reverse_mapping_.find(symbol);
        if (it == reverse_mapping_.end()) {
            return;
        }
        
        PriceUpdate update;
        update.exchange = name_;
        update.pair = it->second;
        update.bid = std::stod(get_json_string(message, "b"));
        update.ask = std::stod(get_json_string(message, "a"));
        update.timestamp = std::chrono::system_clock::now();
        
        notify_price_update(update);
        
    } catch (const std::exception& e) {
        // Silent fail for invalid messages
    }
}

} // namespace arb
