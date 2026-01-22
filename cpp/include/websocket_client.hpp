#pragma once

#include <boost/asio.hpp>
#include <boost/asio/ssl.hpp>
#include <boost/beast.hpp>
#include <boost/beast/ssl.hpp>
#include <functional>
#include <memory>
#include <string>
#include <vector>

#include "price_update.hpp"

namespace asio = boost::asio;
namespace beast = boost::beast;
namespace websocket = beast::websocket;
namespace ssl = asio::ssl;
using tcp = asio::ip::tcp;

namespace arb {

class WebSocketClient : public std::enable_shared_from_this<WebSocketClient> {
public:
    using PriceCallback = std::function<void(const PriceUpdate&)>;
    
    WebSocketClient(
        asio::io_context& ioc,
        ssl::context& ssl_ctx,
        const std::string& name,
        const std::string& host,
        const std::string& port,
        const std::string& path
    );
    
    virtual ~WebSocketClient() = default;
    
    void set_callback(PriceCallback callback) { callback_ = std::move(callback); }
    void start();
    void stop();
    
    const std::string& name() const { return name_; }
    
protected:
    // Override in derived classes for exchange-specific behavior
    virtual std::string get_subscribe_message() = 0;
    virtual void parse_message(const std::string& message) = 0;
    
    void notify_price_update(const PriceUpdate& update);
    
    std::string name_;
    std::vector<std::string> pairs_;
    
private:
    void resolve();
    void connect(const tcp::resolver::results_type& results);
    void ssl_handshake();
    void ws_handshake();
    void subscribe();
    void read();
    void on_read(beast::error_code ec, std::size_t bytes_transferred);
    void reconnect();
    
    asio::io_context& ioc_;
    ssl::context& ssl_ctx_;
    tcp::resolver resolver_;
    std::unique_ptr<websocket::stream<beast::ssl_stream<tcp::socket>>> ws_;
    beast::flat_buffer buffer_;
    
    std::string host_;
    std::string port_;
    std::string path_;
    
    PriceCallback callback_;
    bool running_;
    int reconnect_attempts_;
    static constexpr int MAX_RECONNECT_ATTEMPTS = 10;
    static constexpr int RECONNECT_DELAY_SECONDS = 5;
};

} // namespace arb
