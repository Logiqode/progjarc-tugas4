import sys
import socket
import json
import logging
import ssl
import os

server_address = ('localhost', 8885)

def make_socket(destination_address='localhost', port=12000):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_address = (destination_address, port)
        logging.warning(f"connecting to {server_address}")
        sock.connect(server_address)
        return sock
    except Exception as ee:
        logging.warning(f"error {str(ee)}")

def send_command(command_str):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10.0)
        sock.connect(server_address)
        
        if not command_str.endswith('\r\n\r\n'):
            command_str = command_str.replace('\n', '\r\n') + '\r\n'
        
        sock.sendall(command_str.encode())
        
        response = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
            if len(chunk) < 4096:
                break
        
        return response.decode('utf-8', errors='replace')
    except socket.timeout:
        return "Error: Connection timed out"
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        sock.close()

def send_command_raw(request_bytes):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10.0)
        sock.connect(server_address)
        sock.sendall(request_bytes)
        
        response = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
            if len(chunk) < 4096:
                break
        
        return response.decode('utf-8', errors='replace')
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        sock.close()

def list_files():
    cmd = """GET /list HTTP/1.1
Host: 172.16.16.101
User-Agent: myclient/1.1
Accept: */*

"""
    hasil = send_command(cmd)
    print("Server response:")
    print(hasil)


def upload_file(filename):
    try:
        with open(filename, 'rb') as f:
            file_content = f.read()
        
        # Build the request
        request = (
            f"POST /upload HTTP/1.1\r\n"
            f"Host: {server_address[0]}\r\n"
            f"User-Agent: PythonUploader/1.0\r\n"
            f"X-Filename: {filename}\r\n"  # <-- FIXED LINE
            f"Content-Length: {len(file_content)}\r\n"
            f"\r\n"
        ).encode() + file_content

        # Send request
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(30.0)
        sock.connect(server_address)
        
        try:
            sock.sendall(request)
            response = sock.recv(4096)
            print(response.decode('utf-8', errors='replace'))
        finally:
            sock.close()
            
    except FileNotFoundError:
        print(f"Error: File {filename} not found")
    except Exception as e:
        print(f"Upload error: {str(e)}")

def delete_file(filename):
    cmd = f"""DELETE /{filename} HTTP/1.1
Host: {server_address[0]}
User-Agent: myclient/1.1
Accept: */*

"""
    hasil = send_command(cmd)
    print(hasil)

if __name__ == '__main__':
    print("1. List files")
    print("2. Upload file")
    print("3. Delete file")
    choice = input("Select operation (1/2/3): ")
    
    if choice == '1':
        list_files()
    elif choice == '2':
        filename = input("Enter filename to upload: ")
        upload_file(filename)
    elif choice == '3':
        filename = input("Enter filename to delete: ")
        delete_file(filename)
    else:
        print("Invalid choice")