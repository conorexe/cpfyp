#pragma once

#include <string>
#include <chrono>

namespace arb {

struct PriceUpdate {
    std::string exchange;
    std::string pair;
    double bid;
    double ask;
    std::chrono::system_clock::time_point timestamp;
    
    // Calculate mid price
    double mid() const {
        return (bid + ask) / 2.0;
    }
    
    // Calculate spread percentage
    double spread_percent() const {
        return ((ask - bid) / mid()) * 100.0;
    }
    
    // Serialize to JSON string for IPC
    std::string to_json() const;
};

} // namespace arb
