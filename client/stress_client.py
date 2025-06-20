import socket
import time
import sys
import os
import json

def upload_file(filename, server_address, client_id):
    start_time = time.time()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 8*1024*1024)  # 1MB send buffer
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.settimeout(240.0)
        
        # Connect with verification
        sock.connect(server_address)
        
        # Read file content
        with open(filename, 'rb') as f:
            file_content = f.read()
        
        # Build proper HTTP request
        boundary = f"----WebKitFormBoundary{client_id}{int(time.time())}"
        body_parts = [
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="file"; filename="{os.path.basename(filename)}"\r\n'.encode(),
            f"Content-Type: application/octet-stream\r\n\r\n".encode(),
            file_content,
            f"\r\n--{boundary}--\r\n".encode()
        ]
        body = b"".join(body_parts)
        
        headers = (
            f"POST /upload HTTP/1.1\r\n"
            f"Host: {server_address[0]}:{server_address[1]}\r\n"
            f"Content-Type: multipart/form-data; boundary={boundary}\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"X-Client-ID: {client_id}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        ).encode()
        
        # Send request
        sock.sendall(headers + body)
        
        # Get response
        response = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
        
        end_time = time.time()
        response_time = end_time - start_time
        
        # Parse response
        if not response:
            raise ValueError("Empty response from server")
        
        response_str = response.decode('utf-8', errors='replace')
        success = '200' in response_str or '201' in response_str
        
        return json.dumps({
            'client_id': client_id,
            'success': success,
            'time': response_time,
            'response': response_str[:200],
            'bytes_sent': len(body)
        })
        
    except Exception as e:
        end_time = time.time()
        response_time = end_time - start_time
        return json.dumps({
            'client_id': client_id,
            'error': str(e),
            'success': False,
            'time': response_time
        })
    finally:
        try:
            sock.close()
        except:
            pass

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(json.dumps({
            'error': 'Usage: python stress_client.py <server_ip> <server_port> <client_id> [test_file]',
            'success': False
        }))
        sys.exit(1)
        
    server_ip = sys.argv[1]
    server_port = int(sys.argv[2])
    client_id = sys.argv[3]
    test_file = sys.argv[4] if len(sys.argv) > 4 else 'donalbebek.jpg'
    
    print(upload_file(test_file, (server_ip, server_port), client_id))