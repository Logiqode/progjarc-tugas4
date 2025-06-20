import sys
import os.path
import uuid
from glob import glob
from datetime import datetime
import os
import re

class HttpServer:
    def __init__(self):
        self.sessions = {}
        self.types = {
            '.pdf': 'application/pdf',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.txt': 'text/plain',
            '.html': 'text/html',
            '.bin': 'application/octet-stream'
        }
        
    def response(self, kode=404, message='Not Found', messagebody=bytes(), headers={}):
        tanggal = datetime.now().strftime('%c')
        resp = [
            f"HTTP/1.1 {kode} {message}\r\n",
            f"Date: {tanggal}\r\n",
            "Connection: close\r\n",
            "Server: myserver/1.0\r\n",
            f"Content-Length: {len(messagebody)}\r\n"
        ]
        
        for kk, vv in headers.items():
            resp.append(f"{kk}: {vv}\r\n")
        
        resp.append("\r\n")
        response_headers = "".join(resp)
        
        if not isinstance(messagebody, bytes):
            messagebody = messagebody.encode()
            
        return response_headers.encode() + messagebody

    def parse_multipart_form_data(self, body, boundary):
        """Parse multipart form data to extract file content and filename"""
        try:
            boundary = boundary.encode() if isinstance(boundary, str) else boundary
            parts = body.split(b'--' + boundary)
            
            for part in parts:
                if b'Content-Disposition' in part and b'filename=' in part:
                    # Extract filename
                    filename_match = re.search(rb'filename="([^"]*)"', part)
                    if not filename_match:
                        continue
                    
                    filename = filename_match.group(1).decode('utf-8')
                    filename = os.path.basename(filename)  # Security: prevent path traversal
                    
                    # Find file content (after double CRLF)
                    content_start = part.find(b'\r\n\r\n')
                    if content_start == -1:
                        continue
                    
                    content = part[content_start + 4:]
                    # Remove trailing CRLF if present
                    if content.endswith(b'\r\n'):
                        content = content[:-2]
                    
                    return filename, content
            
            return None, None
        except Exception as e:
            print(f"Error parsing multipart data: {e}")
            return None, None

    def proses(self, data):
        try:
            # Handle binary data
            if isinstance(data, bytes):
                # Split headers and body
                header_end = data.find(b"\r\n\r\n")
                if header_end < 0:
                    return self.response(400, 'Bad Request', 'Invalid request format')
                
                headers_part = data[:header_end]
                body = data[header_end+4:]
                
                try:
                    # Parse request line and headers
                    headers = headers_part.decode('utf-8').split("\r\n")
                    request_line = headers[0].split(" ")
                    
                    if len(request_line) < 3:
                        return self.response(400, 'Bad Request', 'Invalid request line')
                    
                    method, path, version = request_line[0], request_line[1], request_line[2]
                    method = method.upper()
                    
                    # Parse headers into dict
                    headers_dict = {}
                    for header in headers[1:]:
                        if ':' in header:
                            key, value = header.split(':', 1)
                            headers_dict[key.strip().lower()] = value.strip()
                    
                    print(f"Processing {method} {path}")
                    
                    if method == 'POST' and path == '/upload':
                        return self.http_post(body, headers_dict)
                    elif method == 'GET':
                        return self.http_get(path, headers_dict)
                    elif method == 'DELETE':
                        return self.http_delete(path, headers_dict)
                    else:
                        return self.response(405, 'Method Not Allowed', 'Method not supported')
                        
                except (IndexError, ValueError, UnicodeDecodeError) as e:
                    return self.response(400, 'Bad Request', f'Malformed request: {str(e)}')
            
            return self.response(400, 'Bad Request', 'Expected binary data')
            
        except Exception as e:
            print(f"Error processing request: {e}")
            return self.response(500, 'Internal Server Error', str(e))

    def http_post(self, body, headers_dict):
        """Handle file upload"""
        try:
            content_type = headers_dict.get('content-type', '')
            
            if 'multipart/form-data' in content_type:
                # Extract boundary
                boundary_match = re.search(r'boundary=([^;]+)', content_type)
                if not boundary_match:
                    return self.response(400, 'Bad Request', 'No boundary found in multipart data')
                
                boundary = boundary_match.group(1)
                filename, file_content = self.parse_multipart_form_data(body, boundary)
                
                if not filename or file_content is None:
                    return self.response(400, 'Bad Request', 'No valid file found in upload')
                
            else:
                # Simple binary upload
                filename = headers_dict.get('x-filename') # Try x-filename first
                if not filename:
                    # If not found, try to parse Content-Disposition as a backup
                    content_disposition = headers_dict.get('content-disposition', '')
                    match = re.search(r'filename="([^"]*)"', content_disposition)
                    if match:
                        filename = match.group(1)
                
                if not filename: # If still no filename, use the final fallback
                    filename = 'uploaded_file'
                    
                file_content = body
            
            # Save file
            if not filename:
                return self.response(400, 'Bad Request', 'No filename specified')
            
            # Security: sanitize filename
            filename = os.path.basename(filename)
            if not filename or filename.startswith('.'):
                filename = f"upload_{int(datetime.now().timestamp())}"
            
            with open(filename, 'wb') as f:
                f.write(file_content)
            
            return self.response(201, 'Created', f'File {filename} uploaded successfully ({len(file_content)} bytes)')
            
        except Exception as e:
            return self.response(500, 'Internal Server Error', f'Upload failed: {str(e)}')

    def http_get(self, object_address, headers_dict):
        if object_address == '/':
            return self.response(200, 'OK', 'HTTP Server Test - Upload files to /upload')
        elif object_address == '/video':
            return self.response(302, 'Found', '', {'Location': 'https://youtu.be/katoxpnTf04'})
        elif object_address == '/santai':
            return self.response(200, 'OK', 'santai saja')
        elif object_address == '/list':
            try:
                files = [f for f in os.listdir('.') if os.path.isfile(f)]
                file_list = "\n".join(f"{f} ({os.path.getsize(f)} bytes)" for f in files)
                return self.response(200, 'OK', file_list, {'Content-Type': 'text/plain'})
            except Exception as e:
                return self.response(500, 'Server Error', str(e))
        
        # Serve file
        filepath = object_address[1:]  # Remove leading slash
        if not filepath or not os.path.isfile(filepath):
            return self.response(404, 'Not Found', f'File {filepath} not found')
        
        try:
            with open(filepath, 'rb') as f:
                content = f.read()
            
            ext = os.path.splitext(filepath)[1].lower()
            content_type = self.types.get(ext, 'application/octet-stream')
            
            return self.response(200, 'OK', content, {'Content-Type': content_type})
        except Exception as e:
            return self.response(500, 'Internal Server Error', str(e))

    def http_delete(self, object_address, headers_dict):
        filepath = object_address[1:]  # Remove leading slash
        if not filepath or not os.path.exists(filepath):
            return self.response(404, 'Not Found', f'File {filepath} not found')
        
        try:
            os.remove(filepath)
            return self.response(200, 'OK', f'File {filepath} deleted successfully')
        except Exception as e:
            return self.response(500, 'Internal Server Error', str(e))