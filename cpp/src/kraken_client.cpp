#include "kraken_client.hpp"
#include <iostream>
#include <sstream>

// Simple JSON parser for compatibility with older Boost versions
namespace {
    bool is_array(const std::string& json) {
        auto first = json.find_first_not_of(" \t\n\r");
        return first != std::string::npos && json[first] == '[';
    }
    
    std::string get_nested_value(const std::string& json, const std::string& key, int index) {
        auto pos = json.find("\"" + key + "\"");
        if (pos == std::string::npos) return "";
        pos = json.find("[", pos);
        if (pos == std::string::npos) return "";
        
        for (int i = 0; i < index; ++i) {
            pos = json.find(",", pos + 1);
            if (pos == std::string::npos) return "";
        }
        
        pos = json.find("\"", pos);
        auto end = json.find("\"", pos + 1);
        if (pos == std::string::npos || end == std::string::npos) return "";
        return json.substr(pos + 1, end - pos - 1);
    }
}

namespace arb {

KrakenClient::KrakenClient(asio::io_context& ioc, ssl::context& ssl_ctx)
    : WebSocketClient(
        ioc,
        ssl_ctx,
        "Kraken",
        "ws.kraken.com",
        "443",
        "/"
    )
{
    // Setup pair mappings
    pair_mapping_["BTC/USDT"] = "XBT/USDT";
    pair_mapping_["ETH/USDT"] = "ETH/USDT";
    pair_mapping_["SOL/USDT"] = "SOL/USDT";
    pair_mapping_["XRP/USDT"] = "XRP/USDT";
    
    // Reverse mapping
    for (const auto& [normalized, kraken_fmt] : pair_mapping_) {
        reverse_mapping_[kraken_fmt] = normalized;
    }
}

std::string KrakenClient::get_subscribe_message() {
    // Subscribe to ticker for all pairs
    return R"({
        "event": "subscribe",
        "pair": ["XBT/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT"],
        "subscription": {"name": "ticker"}
    })";
}

void KrakenClient::parse_message(const std::string& message) {
    try {
        // Skip non-array messages (events, heartbeats)
        if (!is_array(message)) {
            return;
        }
        
        // Check if it's a ticker message - look for "ticker" string
        if (message.find("\"ticker\"") == std::string::npos) {
            return;
        }
        
        // Extract pair name - it's the last string in the array
        auto last_quote = message.rfind("\"");
        auto second_last = message.rfind("\"", last_quote - 1);
        if (second_last == std::string::npos) return;
        std::string kraken_pair = message.substr(second_last + 1, last_quote - second_last - 1);
        
        auto it = reverse_mapping_.find(kraken_pair);
        if (it == reverse_mapping_.end()) {
            return;
        }
        
        // Kraken: "a" = ask [price, whole lot volume, lot volume]
        //         "b" = bid [price, whole lot volume, lot volume]
        double bid = std::stod(get_nested_value(message, "b", 0));
        double ask = std::stod(get_nested_value(message, "a", 0));
        
        PriceUpdate update;
        update.exchange = name_;
        update.pair = it->second;
        update.bid = bid;
        update.ask = ask;
        update.timestamp = std::chrono::system_clock::now();
        
        notify_price_update(update);
        
    } catch (const std::exception& e) {
        // Silent fail for invalid messages
    }
}

} // namespace arb
