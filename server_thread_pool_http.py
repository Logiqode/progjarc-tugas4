from socket import *
import socket
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from http import HttpServer
import os

httpserver = HttpServer()

def ProcessTheClient(connection, address):
    try:
        connection.settimeout(240.0)
        start_time = time.time()
        print(f"Processing client {address}")
        
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
        
        # Get body data (what we already received after headers)
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
        
        print(f"Received {len(complete_request)} bytes from {address}")
        
        # Process request
        response = httpserver.proses(complete_request)
        if isinstance(response, str):
            response = response.encode()
        
        # Send response
        connection.sendall(response)
        print(f"Sent response to {address}")

    except socket.timeout:
        print(f"Timeout processing {address} after {time.time()-start_time:.2f}s")
        raise
        
    except Exception as e:
        print(f"Error processing client {address}: {str(e)}")
        try:
            error_response = b"HTTP/1.1 500 Internal Server Error\r\n\r\nServer Error"
            connection.sendall(error_response)
        except:
            pass
    finally:
        try:
            connection.shutdown(socket.SHUT_RDWR)
        except:
            pass
        try:
            connection.close()
        except:
            pass

def Server():
    my_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    my_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    my_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 * 1024 * 1024)  # 1MB receive buffer
    my_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    my_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_FASTOPEN, 5)
    my_socket.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)
    
    my_socket.bind(('0.0.0.0', 8885))
    my_socket.listen(5000)  # Increased backlog
    
    print("Thread Pool Server listening on port 8885...")
    
    with ThreadPoolExecutor(max_workers=os.cpu_count() * 50) as executor:
        try:
            while True:
                connection, client_address = my_socket.accept()
                print(f"Accepted connection from {client_address}")
                executor.submit(ProcessTheClient, connection, client_address)
        except KeyboardInterrupt:
            print("Server shutting down...")
        finally:
            my_socket.close()

def main():
    logging.basicConfig(level=logging.WARNING)
    Server()

if __name__ == "__main__":
    main()