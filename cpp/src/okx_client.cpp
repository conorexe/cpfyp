#include "okx_client.hpp"
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

OKXClient::OKXClient(asio::io_context& ioc, ssl::context& ssl_ctx)
    : WebSocketClient(
        ioc,
        ssl_ctx,
        "OKX",
        "ws.okx.com",
        "8443",
        "/ws/v5/public"
    )
{
    // Setup pair mappings
    pair_mapping_["BTC/USDT"] = "BTC-USDT";
    pair_mapping_["ETH/USDT"] = "ETH-USDT";
    pair_mapping_["SOL/USDT"] = "SOL-USDT";
    pair_mapping_["XRP/USDT"] = "XRP-USDT";
    
    // Reverse mapping
    for (const auto& [normalized, okx_fmt] : pair_mapping_) {
        reverse_mapping_[okx_fmt] = normalized;
    }
}

std::string OKXClient::get_subscribe_message() {
    // OKX subscription format
    std::ostringstream oss;
    oss << "{\"op\":\"subscribe\",\"args\":[";
    bool first = true;
    for (const auto& [normalized, okx_fmt] : pair_mapping_) {
        if (!first) oss << ",";
        oss << "{\"channel\":\"tickers\",\"instId\":\"" << okx_fmt << "\"}";
        first = false;
    }
    oss << "]}";
    return oss.str();
}

void OKXClient::parse_message(const std::string& message) {
    try {
        // OKX ticker format:
        // {"arg":{"channel":"tickers","instId":"BTC-USDT"},"data":[{"instId":"BTC-USDT","bidPx":"50000","askPx":"50001",...}]}
        
        if (!has_key(message, "data")) {
            return;
        }
        
        // Extract instId from data array
        std::string inst_id = get_json_string(message, "instId");
        if (inst_id.empty()) {
            return;
        }
        
        auto it = reverse_mapping_.find(inst_id);
        if (it == reverse_mapping_.end()) {
            return;
        }
        
        std::string bid_str = get_json_string(message, "bidPx");
        std::string ask_str = get_json_string(message, "askPx");
        
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
