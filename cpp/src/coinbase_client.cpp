#include "coinbase_client.hpp"
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

CoinbaseClient::CoinbaseClient(asio::io_context& ioc, ssl::context& ssl_ctx)
    : WebSocketClient(
        ioc,
        ssl_ctx,
        "Coinbase",
        "ws-feed.exchange.coinbase.com",
        "443",
        "/"
    )
{
    // Setup pair mappings
    pair_mapping_["BTC/USDT"] = "BTC-USDT";
    pair_mapping_["ETH/USDT"] = "ETH-USDT";
    pair_mapping_["SOL/USDT"] = "SOL-USDT";
    pair_mapping_["XRP/USDT"] = "XRP-USDT";
    
    // Reverse mapping
    for (const auto& [normalized, coinbase_fmt] : pair_mapping_) {
        reverse_mapping_[coinbase_fmt] = normalized;
    }
}

std::string CoinbaseClient::get_subscribe_message() {
    return R"({
        "type": "subscribe",
        "product_ids": ["BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT"],
        "channels": ["ticker"]
    })";
}

void CoinbaseClient::parse_message(const std::string& message) {
    try {
        // Coinbase ticker format:
        // {"type":"ticker","product_id":"BTC-USD","price":"50000.00","best_bid":"49999.00","best_ask":"50001.00",...}
        std::string type = get_json_string(message, "type");
        if (type != "ticker") {
            return;
        }
        
        if (!has_key(message, "product_id") || !has_key(message, "best_bid") || !has_key(message, "best_ask")) {
            return;
        }
        
        std::string product_id = get_json_string(message, "product_id");
        
        auto it = reverse_mapping_.find(product_id);
        if (it == reverse_mapping_.end()) {
            return;
        }
        
        PriceUpdate update;
        update.exchange = name_;
        update.pair = it->second;
        update.bid = std::stod(get_json_string(message, "best_bid"));
        update.ask = std::stod(get_json_string(message, "best_ask"));
        update.timestamp = std::chrono::system_clock::now();
        
        notify_price_update(update);
        
    } catch (const std::exception& e) {
        // Silent fail for invalid messages
    }
}

} // namespace arb
