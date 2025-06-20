from socket import *
import socket
import logging
import os
import multiprocessing as mp
from http import HttpServer
from concurrent.futures import ProcessPoolExecutor

def worker_process(request_data):
    """Worker function that processes HTTP requests"""
    httpserver = HttpServer()
    try:
        response = httpserver.proses(request_data)
        if isinstance(response, str):
            response = response.encode()
        return response
    except Exception as e:
        error_response = f"HTTP/1.1 500 Internal Server Error\r\n\r\nError: {str(e)}"
        return error_response.encode()

def handle_connection(connection, address):
    """Handle a single client connection"""
    try:
        connection.settimeout(240.0)
        
        # Receive request headers first
        headers_data = b""
        while b"\r\n\r\n" not in headers_data:
            chunk = connection.recv(1024*1024)
            if not chunk:
                raise ConnectionError("Client disconnected during headers")
            headers_data += chunk
        
        # Parse headers to get content length
        headers_str = headers_data[:headers_data.find(b"\r\n\r\n")].decode('utf-8')
        content_length = 0
        
        for line in headers_str.split('\r\n'):
            if line.lower().startswith('content-length:'):
                content_length = int(line.split(':')[1].strip())
                break
        
        # Get body data
        body_start = headers_data.find(b"\r\n\r\n") + 4
        body_data = headers_data[body_start:]
        
        # Receive remaining body if needed
        while len(body_data) < content_length:
            remaining = content_length - len(body_data)
            chunk = connection.recv(min(8192, remaining))
            if not chunk:
                raise ConnectionError("Client disconnected during body")
            body_data += chunk
        
        # Reconstruct complete request
        complete_request = headers_data[:body_start] + body_data
        
        # Process request
        response = worker_process(complete_request)
        
        # Send response
        connection.sendall(response)
        
    except Exception as e:
        print(f"Error processing client {address}: {str(e)}")
        try:
            error_response = b"HTTP/1.1 500 Internal Server Error\r\n\r\nServer Error"
            connection.sendall(error_response)
        except:
            pass
    finally:
        try:
            connection.close()
        except:
            pass

def Server():
    # Create main server socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 * 1024 * 1024)
    server_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    
    server_socket.bind(('0.0.0.0', 8889))
    server_socket.listen(5000)
    
    print("Process Pool Server listening on port 8889...")

    # Create process pool
    num_workers = os.cpu_count() * 4
    print(f"Starting {num_workers} worker processes")
    
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        try:
            while True:
                connection, client_address = server_socket.accept()
                # Handle connection in the main process (for simplicity)
                # In production, you'd need a more sophisticated approach
                handle_connection(connection, client_address)
        except KeyboardInterrupt:
            print("Server shutting down...")
        finally:
            server_socket.close()

def main():
    # Set multiprocessing start method
    mp.set_start_method('fork', force=True)
    logging.basicConfig(level=logging.WARNING)
    Server()

if __name__ == "__main__":
    main()