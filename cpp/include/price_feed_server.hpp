#pragma once

#include <boost/asio.hpp>
#include <memory>
#include <vector>
#include <queue>
#include <mutex>

#include "price_update.hpp"

namespace asio = boost::asio;
using tcp = asio::ip::tcp;

namespace arb {

// Simple TCP server to send price updates to Python
class PriceFeedServer : public std::enable_shared_from_this<PriceFeedServer> {
public:
    PriceFeedServer(asio::io_context& ioc, unsigned short port);
    
    void start();
    void broadcast_price(const PriceUpdate& update);
    
private:
    void accept();
    void handle_accept(std::shared_ptr<tcp::socket> socket);
    
    asio::io_context& ioc_;
    tcp::acceptor acceptor_;
    std::vector<std::shared_ptr<tcp::socket>> clients_;
    std::mutex clients_mutex_;
};

} // namespace arb
