#include "price_feed_server.hpp"
#include <iostream>

namespace arb {

PriceFeedServer::PriceFeedServer(asio::io_context& ioc, unsigned short port)
    : ioc_(ioc)
    , acceptor_(ioc, tcp::endpoint(tcp::v4(), port))
{
    std::cout << "[PriceFeedServer] Listening on port " << port << std::endl;
}

void PriceFeedServer::start() {
    accept();
}

void PriceFeedServer::accept() {
    auto socket = std::make_shared<tcp::socket>(ioc_);
    
    acceptor_.async_accept(
        *socket,
        [this, socket](boost::system::error_code ec) {
            if (!ec) {
                std::cout << "[PriceFeedServer] Client connected from " 
                          << socket->remote_endpoint() << std::endl;
                handle_accept(socket);
            } else {
                std::cerr << "[PriceFeedServer] Accept error: " << ec.message() << std::endl;
            }
            
            // Continue accepting connections
            accept();
        }
    );
}

void PriceFeedServer::handle_accept(std::shared_ptr<tcp::socket> socket) {
    std::lock_guard<std::mutex> lock(clients_mutex_);
    clients_.push_back(socket);
}

void PriceFeedServer::broadcast_price(const PriceUpdate& update) {
    std::string json_msg = update.to_json() + "\n";
    
    std::lock_guard<std::mutex> lock(clients_mutex_);
    
    // Remove disconnected clients and send to active ones
    clients_.erase(
        std::remove_if(
            clients_.begin(),
            clients_.end(),
            [&json_msg](std::shared_ptr<tcp::socket>& socket) {
                boost::system::error_code ec;
                asio::write(*socket, asio::buffer(json_msg), ec);
                return ec != boost::system::errc::success;
            }
        ),
        clients_.end()
    );
}

} // namespace arb
