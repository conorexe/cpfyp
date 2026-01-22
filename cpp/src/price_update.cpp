#include "price_update.hpp"
#include <sstream>
#include <iomanip>

namespace arb {

std::string PriceUpdate::to_json() const {
    auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(
        timestamp.time_since_epoch()
    ).count();
    
    std::ostringstream oss;
    oss << std::fixed << std::setprecision(8);
    oss << "{\"exchange\":\"" << exchange << "\","
        << "\"pair\":\"" << pair << "\","
        << "\"bid\":" << bid << ","
        << "\"ask\":" << ask << ","
        << "\"timestamp\":" << ms << "}";
    
    return oss.str();
}

} // namespace arb
