#pragma once

#include "websocket_client.hpp"
#include <unordered_map>

namespace arb {

class CoinbaseClient : public WebSocketClient {
public:
    CoinbaseClient(asio::io_context& ioc, ssl::context& ssl_ctx);
    
protected:
    std::string get_subscribe_message() override;
    void parse_message(const std::string& message) override;
    
private:
    std::unordered_map<std::string, std::string> pair_mapping_;
    std::unordered_map<std::string, std::string> reverse_mapping_;
};

} // namespace arb
