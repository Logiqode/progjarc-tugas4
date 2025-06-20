import sys
import os.path
import uuid
from glob import glob
from datetime import datetime
import os

class HttpServer:
    def __init__(self):
        self.sessions = {}
        self.types = {
            '.pdf': 'application/pdf',
            '.jpg': 'image/jpeg',
            '.txt': 'text/plain',
            '.html': 'text/html'
        }
        
    def response(self, kode=404, message='Not Found', messagebody=bytes(), headers={}):
        tanggal = datetime.now().strftime('%c')
        resp = [
            f"HTTP/1.0 {kode} {message}\r\n",
            f"Date: {tanggal}\r\n",
            "Connection: close\r\n",
            "Server: myserver/1.0\r\n",
            f"Content-Length: {len(messagebody)}\r\n"
        ]
        
        for kk, vv in headers.items():
            resp.append(f"{kk}:{vv}\r\n")
        
        resp.append("\r\n")
        response_headers = "".join(resp)
        
        if not isinstance(messagebody, bytes):
            messagebody = messagebody.encode()
            
        return response_headers.encode() + messagebody + b'\r\n'

    def proses(self, data):
        # Handle binary data directly
        if isinstance(data, bytes):
            try:
                # Split headers and body
                header_end = data.find(b"\r\n\r\n")
                if header_end < 0:
                    return self.response(400, 'Bad Request', 'Invalid request format')
                    
                headers_part = data[:header_end]
                body = data[header_end+4:]  # Skip \r\n\r\n
                
                try:
                    # Parse request line
                    headers = headers_part.decode('utf-8').split("\r\n")
                    method, path, _ = headers[0].split(" ", 2)
                    method = method.upper()
                    
                    if method == 'POST' and path == '/upload':
                        # Find filename in headers
                        filename = None
                        for header in headers[1:]:
                            if 'filename=' in header.lower():
                                try:
                                    filename_start = header.lower().index('filename="') + 10
                                    filename_end = header.lower().index('"', filename_start)
                                    filename = header[filename_start:filename_end]
                                    break
                                except ValueError:
                                    pass
                        
                        if not filename:
                            return self.response(400, 'Bad Request', 'No filename specified')
                        
                        # Save file
                        filename = os.path.basename(filename)
                        with open(filename, 'wb') as f:
                            f.write(body)
                        
                        return self.response(201, 'Created', f'File {filename} uploaded successfully')
                    
                    elif method == 'GET':
                        return self.http_get(path, headers[1:])
                    elif method == 'DELETE':
                        return self.http_delete(path, headers[1:])
                    else:
                        return self.response(400, 'Bad Request', 'Unsupported method')
                        
                except (IndexError, ValueError) as e:
                    return self.response(400, 'Bad Request', 'Malformed request headers')
                    
            except UnicodeDecodeError:
                return self.response(400, 'Bad Request', 'Invalid header encoding')
        
        return self.response(400, 'Bad Request', 'Expected binary data')

    def http_get(self, object_address, headers):
        if object_address == '/':
            return self.response(200, 'OK', 'Ini Adalah web Server percobaan')
        elif object_address == '/video':
            return self.response(302, 'Found', '', {'location': 'https://youtu.be/katoxpnTf04'})
        elif object_address == '/santai':
            return self.response(200, 'OK', 'santai saja')
        elif object_address == '/list':
            try:
                files = [f for f in os.listdir('.') if os.path.isfile(f)]
                return self.response(200, 'OK', "\n".join(files), {'Content-Type': 'text/plain'})
            except Exception as e:
                return self.response(500, 'Server Error', str(e))
        
        filepath = object_address[1:]  # Remove leading slash
        if not os.path.isfile(filepath):
            return self.response(404, 'Not Found')
        
        try:
            with open(filepath, 'rb') as f:
                content = f.read()
            ext = os.path.splitext(filepath)[1]
            return self.response(200, 'OK', content, {'Content-type': self.types.get(ext, 'application/octet-stream')})
        except Exception as e:
            return self.response(500, 'Internal Server Error', str(e))

    def http_post(self, object_address, headers, body):
        if object_address != '/upload':
            return self.response(400, 'Bad Request', 'Uploads must be sent to /upload endpoint')
        
        # Extract filename from headers
        filename = None
        for header in headers:
            if 'filename=' in header.lower():
                try:
                    filename_start = header.lower().index('filename="') + 10
                    filename_end = header.lower().index('"', filename_start)
                    filename = header[filename_start:filename_end]
                    break
                except ValueError:
                    pass
        
        if not filename:
            return self.response(400, 'Bad Request', 'No filename specified')
        
        filename = os.path.basename(filename)  # Sanitize filename
        if not filename:
            return self.response(400, 'Bad Request', 'Invalid filename')
        
        try:
            with open(filename, 'wb') as f:
                f.write(body if isinstance(body, bytes) else body.encode())
            return self.response(201, 'Created', f'File {filename} uploaded successfully')
        except Exception as e:
            return self.response(500, 'Internal Server Error', f'Upload failed: {str(e)}')

    def http_delete(self, object_address, headers):
        filepath = object_address[1:]  # Remove leading slash
        if not os.path.exists(filepath):
            return self.response(404, 'Not Found', f'File {filepath} not found')
        
        try:
            os.remove(filepath)
            return self.response(200, 'OK', f'File {filepath} deleted successfully')
        except Exception as e:
            return self.response(500, 'Internal Server Error', str(e))