from socket import *
import socket
import logging
from concurrent.futures import ProcessPoolExecutor
from http import HttpServer

httpserver = HttpServer()

def ProcessTheClient(connection, address):
    try:
        connection.settimeout(30.0)  # Increased timeout for file uploads
        print(f"DIAGNOSIS: Connection from {address}")
        
        # Read all data until connection closes or we have complete request
        received_data = b""
        content_length = 0
        headers_complete = False
        
        while True:
            try:
                data = connection.recv(4096)
                if not data:
                    break
                received_data += data
                
                # Check if we've received headers
                if not headers_complete and b"\r\n\r\n" in received_data:
                    headers_part, body_part = received_data.split(b"\r\n\r\n", 1)
                    headers = headers_part.decode('utf-8', errors='replace').split("\r\n")
                    
                    # Find Content-Length if present
                    for header in headers:
                        if header.lower().startswith("content-length:"):
                            content_length = int(header.split(":")[1].strip())
                    
                    headers_complete = True
                    print(f"DIAGNOSIS: Headers complete, Content-Length: {content_length}")
                
                # Stop if we've received all data
                if headers_complete:
                    body_start = received_data.find(b"\r\n\r\n") + 4
                    if len(received_data) >= body_start + content_length:
                        break
            
            except socket.timeout:
                print("DIAGNOSIS: Timeout waiting for request")
                break
        
        if not received_data:
            print("DIAGNOSIS: Empty request, closing")
            return

        try:
            print("DIAGNOSIS: Processing request...")
            hasil = httpserver.proses(received_data)  # Pass raw bytes
            
            if isinstance(hasil, str):
                hasil = hasil.encode('utf-8')
            
            print(f"DIAGNOSIS: Sending response ({len(hasil)} bytes)")
            connection.sendall(hasil)
            
        except Exception as e:
            print(f"DIAGNOSIS: Processing error: {str(e)}")
            error_response = httpserver.response(500, 'Server Error', str(e))
            connection.sendall(error_response.encode())
            
    except Exception as e:
        print(f"DIAGNOSIS: Connection error: {str(e)}")
    finally:
        connection.close()
        print("DIAGNOSIS: Connection closed")

def Server():
    my_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    my_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    my_socket.bind(('0.0.0.0', 8889))
    my_socket.listen(5)
    
    with ProcessPoolExecutor(20) as executor:
        print("SERVER: Process pool server running on port 8889")
        while True:
            connection, client_address = my_socket.accept()
            logging.warning(f"Connection from {client_address}")
            executor.submit(ProcessTheClient, connection, client_address)

def main():
    logging.basicConfig(level=logging.WARNING)
    Server()

if __name__ == "__main__":
    main()