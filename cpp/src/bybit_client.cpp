#include "bybit_client.hpp"
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

BybitClient::BybitClient(asio::io_context& ioc, ssl::context& ssl_ctx)
    : WebSocketClient(
        ioc,
        ssl_ctx,
        "Bybit",
        "stream.bybit.com",
        "443",
        "/v5/public/spot"
    )
{
    // Setup pair mappings
    pair_mapping_["BTC/USDT"] = "BTCUSDT";
    pair_mapping_["ETH/USDT"] = "ETHUSDT";
    pair_mapping_["SOL/USDT"] = "SOLUSDT";
    pair_mapping_["XRP/USDT"] = "XRPUSDT";
    
    // Reverse mapping
    for (const auto& [normalized, bybit_fmt] : pair_mapping_) {
        reverse_mapping_[bybit_fmt] = normalized;
    }
}

std::string BybitClient::get_subscribe_message() {
    // Bybit v5 subscription format
    std::ostringstream oss;
    oss << "{\"op\":\"subscribe\",\"args\":[";
    bool first = true;
    for (const auto& [normalized, bybit_fmt] : pair_mapping_) {
        if (!first) oss << ",";
        oss << "\"tickers." << bybit_fmt << "\"";
        first = false;
    }
    oss << "]}";
    return oss.str();
}

void BybitClient::parse_message(const std::string& message) {
    try {
        // Bybit v5 ticker format:
        // {"topic":"tickers.BTCUSDT","type":"snapshot","data":{"symbol":"BTCUSDT","bid1Price":"50000","ask1Price":"50001",...}}
        
        if (!has_key(message, "topic") || !has_key(message, "data")) {
            return;
        }
        
        std::string topic = get_json_string(message, "topic");
        if (topic.find("tickers.") != 0) {
            return;
        }
        
        // Extract symbol from data
        std::string symbol = get_json_string(message, "symbol");
        if (symbol.empty()) {
            return;
        }
        
        auto it = reverse_mapping_.find(symbol);
        if (it == reverse_mapping_.end()) {
            return;
        }
        
        std::string bid_str = get_json_string(message, "bid1Price");
        std::string ask_str = get_json_string(message, "ask1Price");
        
        if (bid_str.empty() || ask_str.empty()) {
            return;
        }
        
        PriceUpdate update;
        update.exchange = name_;
        update.pair = it->second;
        update.bid = std::stod(bid_str);
        update.ask = std::stod(ask_str);
        update.timestamp = std::chrono::system_clock::now();
        
        notify_price_update(update);
        
    } catch (const std::exception& e) {
        // Silent fail for invalid messages
    }
}

} // namespace arb
