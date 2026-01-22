#include "websocket_client.hpp"
#include <iostream>
#include <thread>

namespace arb {

WebSocketClient::WebSocketClient(
    asio::io_context& ioc,
    ssl::context& ssl_ctx,
    const std::string& name,
    const std::string& host,
    const std::string& port,
    const std::string& path
)
    : ioc_(ioc)
    , ssl_ctx_(ssl_ctx)
    , resolver_(ioc)
    , ws_(std::make_unique<websocket::stream<beast::ssl_stream<tcp::socket>>>(ioc, ssl_ctx))
    , name_(name)
    , host_(host)
    , port_(port)
    , path_(path)
    , running_(false)
    , reconnect_attempts_(0)
{
}

void WebSocketClient::start() {
    running_ = true;
    reconnect_attempts_ = 0;
    std::cout << "[" << name_ << "] Starting connection..." << std::endl;
    resolve();
}

void WebSocketClient::stop() {
    running_ = false;
    if (ws_) {
        beast::error_code ec;
        ws_->close(websocket::close_code::normal, ec);
    }
    std::cout << "[" << name_ << "] Stopped" << std::endl;
}

void WebSocketClient::resolve() {
    resolver_.async_resolve(
        host_,
        port_,
        [self = shared_from_this()](beast::error_code ec, tcp::resolver::results_type results) {
            if (ec) {
                std::cerr << "[" << self->name_ << "] Resolve error: " << ec.message() << std::endl;
                self->reconnect();
                return;
            }
            self->connect(results);
        }
    );
}

void WebSocketClient::connect(const tcp::resolver::results_type& results) {
    // Use free function async_connect for Boost 1.74 compatibility
    asio::async_connect(
        beast::get_lowest_layer(*ws_),
        results,
        [self = shared_from_this()](beast::error_code ec, const tcp::endpoint&) {
            if (ec) {
                std::cerr << "[" << self->name_ << "] Connect error: " << ec.message() << std::endl;
                self->reconnect();
                return;
            }
            std::cout << "[" << self->name_ << "] TCP connected" << std::endl;
            self->ssl_handshake();
        }
    );
}

void WebSocketClient::ssl_handshake() {
    // Set SNI hostname
    if (!SSL_set_tlsext_host_name(ws_->next_layer().native_handle(), host_.c_str())) {
        beast::error_code ec{static_cast<int>(::ERR_get_error()), asio::error::get_ssl_category()};
        std::cerr << "[" << name_ << "] SNI error: " << ec.message() << std::endl;
        reconnect();
        return;
    }
    
    ws_->next_layer().async_handshake(
        ssl::stream_base::client,
        [self = shared_from_this()](beast::error_code ec) {
            if (ec) {
                std::cerr << "[" << self->name_ << "] SSL handshake error: " << ec.message() << std::endl;
                self->reconnect();
                return;
            }
            std::cout << "[" << self->name_ << "] SSL handshake complete" << std::endl;
            self->ws_handshake();
        }
    );
}

void WebSocketClient::ws_handshake() {
    // Set WebSocket options
    ws_->set_option(websocket::stream_base::decorator(
        [](websocket::request_type& req) {
            req.set(beast::http::field::user_agent, "CryptoArbBot/1.0");
        }
    ));
    
    ws_->async_handshake(
        host_,
        path_,
        [self = shared_from_this()](beast::error_code ec) {
            if (ec) {
                std::cerr << "[" << self->name_ << "] WebSocket handshake error: " << ec.message() << std::endl;
                self->reconnect();
                return;
            }
            std::cout << "[" << self->name_ << "] WebSocket connected!" << std::endl;
            self->reconnect_attempts_ = 0;
            self->subscribe();
        }
    );
}

void WebSocketClient::subscribe() {
    std::string subscribe_msg = get_subscribe_message();
    
    if (subscribe_msg.empty()) {
        // No subscription needed (e.g., Binance URL-based subscription)
        std::cout << "[" << name_ << "] Subscribed via URL" << std::endl;
        read();
        return;
    }
    
    ws_->async_write(
        asio::buffer(subscribe_msg),
        [self = shared_from_this()](beast::error_code ec, std::size_t) {
            if (ec) {
                std::cerr << "[" << self->name_ << "] Subscribe error: " << ec.message() << std::endl;
                self->reconnect();
                return;
            }
            std::cout << "[" << self->name_ << "] Subscribed to feeds" << std::endl;
            self->read();
        }
    );
}

void WebSocketClient::read() {
    ws_->async_read(
        buffer_,
        [self = shared_from_this()](beast::error_code ec, std::size_t bytes_transferred) {
            self->on_read(ec, bytes_transferred);
        }
    );
}

void WebSocketClient::on_read(beast::error_code ec, std::size_t bytes_transferred) {
    if (ec) {
        if (ec != websocket::error::closed) {
            std::cerr << "[" << name_ << "] Read error: " << ec.message() << std::endl;
        }
        reconnect();
        return;
    }
    
    std::string message = beast::buffers_to_string(buffer_.data());
    buffer_.consume(bytes_transferred);
    
    try {
        parse_message(message);
    } catch (const std::exception& e) {
        std::cerr << "[" << name_ << "] Parse error: " << e.what() << std::endl;
    }
    
    // Continue reading
    if (running_) {
        read();
    }
}

void WebSocketClient::reconnect() {
    if (!running_ || reconnect_attempts_ >= MAX_RECONNECT_ATTEMPTS) {
        if (reconnect_attempts_ >= MAX_RECONNECT_ATTEMPTS) {
            std::cerr << "[" << name_ << "] Max reconnection attempts reached" << std::endl;
        }
        return;
    }
    
    reconnect_attempts_++;
    std::cout << "[" << name_ << "] Reconnecting in " << RECONNECT_DELAY_SECONDS 
              << "s (attempt " << reconnect_attempts_ << ")..." << std::endl;
    
    // Close existing connection
    if (ws_) {
        beast::error_code ec;
        beast::get_lowest_layer(*ws_).close(ec);
    }
    
    // Create new websocket stream
    ws_ = std::make_unique<websocket::stream<beast::ssl_stream<tcp::socket>>>(ioc_, ssl_ctx_);
    
    // Schedule reconnection
    auto timer = std::make_shared<asio::steady_timer>(ioc_);
    timer->expires_after(std::chrono::seconds(RECONNECT_DELAY_SECONDS));
    timer->async_wait([self = shared_from_this(), timer](beast::error_code) {
        if (self->running_) {
            self->resolve();
        }
    });
}

void WebSocketClient::notify_price_update(const PriceUpdate& update) {
    if (callback_) {
        callback_(update);
    }
}

} // namespace arb
