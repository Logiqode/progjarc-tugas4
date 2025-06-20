import subprocess
import time
import statistics
import matplotlib.pyplot as plt
import psutil
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
import json
import socket

# Configuration - Adjust these for different test intensities
TEST_CONFIG = {
    'light': {'clients': 100, 'runs': 3, 'file': 'test_small.jpg'},
    'medium': {'clients': 100, 'runs': 3, 'file': 'test_10mb.bin'},
    'heavy': {'clients': 100, 'runs': 3, 'file': 'test_50mb.bin'}
}

def create_test_files():
    """Create test files if they don't exist"""
    files_to_create = [
        ('test_small.jpg', 1024 * 100),  # 100KB
        ('test_10mb.bin', 1024 * 1024 * 10),  # 10MB
        ('test_50mb.bin', 1024 * 1024 * 50)   # 100MB
    ]
    
    for filename, size in files_to_create:
        if not os.path.exists(filename):
            print(f"Creating {filename} ({size/1024/1024:.1f}MB)...")
            with open(filename, 'wb') as f:
                # Write in chunks to avoid memory issues
                chunk_size = min(1024 * 1024, size)  # 1MB chunks
                remaining = size
                while remaining > 0:
                    chunk = os.urandom(min(chunk_size, remaining))
                    f.write(chunk)
                    remaining -= len(chunk)

def run_single_client(client_id, server_ip, port, test_file):
    """Run a single client and return the result"""
    start_time = time.time()
    try:
        # Use direct socket connection instead of subprocess
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.settimeout(180.0)  # Total operation timeout
        
        # Connect with timeout
        sock.connect((server_ip, port))
        
        # Build and send request
        boundary = f"----WebKitFormBoundary{client_id}{int(time.time())}"
        with open(test_file, 'rb') as f:
            file_content = f.read()
        
        body = b"".join([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="file"; filename="{os.path.basename(test_file)}"\r\n'.encode(),
            b"Content-Type: application/octet-stream\r\n\r\n",
            file_content,
            f"\r\n--{boundary}--\r\n".encode()
        ])
        
        headers = (
            f"POST /upload HTTP/1.1\r\n"
            f"Host: {server_ip}:{port}\r\n"
            f"Content-Type: multipart/form-data; boundary={boundary}\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"X-Client-ID: {client_id}\r\n"
            f"Connection: close\r\n\r\n"
        ).encode()
        
        sock.sendall(headers + body)
        
        # Receive response
        response = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
        
        elapsed = time.time() - start_time
        
        # Parse response
        response_str = response.decode('utf-8', errors='replace')
        success = response_str.startswith(('HTTP/1.1 200', 'HTTP/1.1 201'))
        
        return {
            'client_id': str(client_id),
            'success': success,
            'time': elapsed,
            'response': response_str[:200],
            'bytes_sent': len(body)
        }
        
    except socket.timeout as e:
        return {
            'client_id': str(client_id),
            'success': False,
            'error': f"Socket timeout after {time.time()-start_time:.2f}s",
            'time': time.time()-start_time
        }
    except ConnectionRefusedError:
        return {
            'client_id': str(client_id),
            'success': False,
            'error': "Connection refused",
            'time': time.time()-start_time
        }
    except Exception as e:
        return {
            'client_id': str(client_id),
            'success': False,
            'error': str(e),
            'time': time.time()-start_time
        }
    finally:
        try:
            sock.close()
        except:
            pass

def run_clients(num_clients, server_ip, port, test_file):
    """Run multiple clients concurrently"""
    print(f"Starting {num_clients} clients...")
    start_time = time.time()
    results = []
    
    with ThreadPoolExecutor(max_workers=min(200, os.cpu_count() * 4)) as executor:
        # Submit all client tasks
        futures = []
        for i in range(num_clients):
            future = executor.submit(run_single_client, i, server_ip, port, test_file)
            futures.append(future)
            time.sleep(0.01)  # Small delay to stagger starts
        
        # Collect results
        for i, future in enumerate(as_completed(futures)):
            try:
                result = future.result()
                results.append(result)
                if i % 10 == 0:  # Progress update every 10 clients
                    print(f"Completed {i+1}/{num_clients} clients")
            except Exception as e:
                print(f"Client {i} exception: {e}")
                results.append({
                    'client_id': str(i),
                    'success': False,
                    'error': str(e),
                    'time': 0
                })
    
    total_time = time.time() - start_time
    return results, total_time

def analyze_results(results, server_type):
    """Analyze and display test results"""
    if not results or all(len(r.get('client_times', [])) == 0 for r in results):
        print(f"\n=== {server_type.upper()} TEST RESULTS ===")
        
        # Calculate metrics from individual runs
        all_runs = []
        for run_data in results:
            if 'client_results' in run_data:
                all_runs.extend(run_data['client_results'])
        
        if not all_runs:
            print("No successful requests recorded")
            return
        
        successful_runs = [r for r in all_runs if r.get('success', False)]
        total_requests = len(all_runs)
        successful_requests = len(successful_runs)
        
        if successful_requests == 0:
            print("No successful requests!")
            return
        
        # Calculate metrics
        response_times = [r['time'] for r in successful_runs if 'time' in r and r['time'] > 0]
        success_rate = successful_requests / total_requests
        
        if response_times:
            avg_response_time = statistics.mean(response_times)
            p50 = statistics.median(response_times)
            p95 = np.percentile(response_times, 95)
            p99 = np.percentile(response_times, 99)
            min_time = min(response_times)
            max_time = max(response_times)
            
            print(f"Total requests: {total_requests}")
            print(f"Successful requests: {successful_requests}")
            print(f"Success rate: {success_rate*100:.1f}%")
            print(f"Average response time: {avg_response_time:.3f}s")
            print(f"Response time percentiles:")
            print(f"  P50 (median): {p50:.3f}s")
            print(f"  P95: {p95:.3f}s")
            print(f"  P99: {p99:.3f}s")
            print(f"  Min: {min_time:.3f}s")
            print(f"  Max: {max_time:.3f}s")
            
            # Calculate throughput for each run
            throughputs = []
            for run_data in results:
                if 'total_time' in run_data and run_data['total_time'] > 0:
                    run_successful = len([r for r in run_data.get('client_results', []) if r.get('success')])
                    throughput = run_successful / run_data['total_time']
                    throughputs.append(throughput)
            
            if throughputs:
                avg_throughput = statistics.mean(throughputs)
                print(f"Average throughput: {avg_throughput:.2f} req/sec")
        
        # Simple plotting
        try:
            if response_times:
                plt.figure(figsize=(10, 6))
                plt.hist(response_times, bins=30, alpha=0.7, edgecolor='black')
                plt.title(f'{server_type.title()} Server - Response Time Distribution')
                plt.xlabel('Response Time (seconds)')
                plt.ylabel('Frequency')
                plt.axvline(avg_response_time, color='red', linestyle='--', label=f'Mean: {avg_response_time:.3f}s')
                plt.axvline(p95, color='orange', linestyle='--', label=f'P95: {p95:.3f}s')
                plt.legend()
                plt.tight_layout()
                plt.savefig(f'{server_type}_response_times.png', dpi=150)
                plt.close()
                print(f"Response time histogram saved as {server_type}_response_times.png")
        except Exception as e:
            print(f"Could not create plot: {e}")

def analyze_results_simple(results, server_type):
    """Simplified analysis for direct client results"""
    print(f"\n=== {server_type.upper()} TEST RESULTS ===")
    
    if not results:
        print("No results to analyze")
        return
    
    # Properly flatten results structure
    all_results = []
    for run in results:
        if isinstance(run, dict) and 'client_results' in run:
            all_results.extend(run['client_results'])
        elif isinstance(run, list):
            all_results.extend(run)
        else:
            all_results.append(run)
    
    if not all_results:
        print("No client requests recorded")
        return
    
    # Calculate success metrics
    successful = [r for r in all_results if r.get('success', False)]
    failures = [r for r in all_results if not r.get('success', False)]
    
    total = len(all_results)
    success_count = len(successful)
    success_rate = success_count / total if total > 0 else 0
    
    print(f"Total client requests: {total}")
    print(f"Successful requests: {success_count}")
    print(f"Success rate: {success_rate*100:.1f}%")
    
    # Response time analysis
    if successful:
        times = [r['time'] for r in successful if isinstance(r.get('time'), (int, float))]
        if times:
            print("\nResponse Times (successful requests):")
            print(f"Average: {statistics.mean(times):.3f}s")
            print(f"Median: {statistics.median(times):.3f}s")
            print(f"95th percentile: {np.percentile(times, 95):.3f}s")
            print(f"Min: {min(times):.3f}s")
            print(f"Max: {max(times):.3f}s")
            
            # Throughput calculations
            total_time = sum(times)
            avg_throughput = success_count / total_time
            print(f"\nThroughput: {avg_throughput:.2f} req/sec")
            
            total_bytes = sum(r.get('bytes_sent', 0) for r in successful)
            if total_bytes > 0:
                mbps = (total_bytes * 8) / (total_time * 1_000_000)
                print(f"Data throughput: {mbps:.2f} Mbps")
    
    # Error analysis
    if failures:
        print("\nFailure Analysis:")
        error_types = {}
        for f in failures:
            error = f.get('error', 'Unknown error')
            error_types[error] = error_types.get(error, 0) + 1
        
        for error, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True):
            print(f"{count}x {error}")
            
        # Print example failure details
        example_failure = next((f for f in failures if f.get('error')), None)
        if example_failure:
            print("\nExample failure details:")
            for k, v in example_failure.items():
                if k != 'client_id' and v:
                    print(f"{k}: {str(v)[:200]}{'...' if len(str(v)) > 200 else ''}")

def get_system_info():
    """Get system information"""
    cpu_count = psutil.cpu_count()
    memory = psutil.virtual_memory()
    print(f"\n=== SYSTEM INFO ===")
    print(f"CPU cores: {cpu_count}")
    print(f"Memory: {memory.total / (1024**3):.1f} GB total, {memory.available / (1024**3):.1f} GB available")
    return {'cpu_count': cpu_count, 'memory_gb': memory.total / (1024**3)}

def test_server(server_type, server_ip, port, test_intensity='medium', custom_config=None):
    """Test a specific server"""
    print(f"\n{'='*50}")
    print(f"TESTING {server_type.upper()} SERVER")
    print(f"Server: {server_ip}:{port}")
    print(f"Test intensity: {test_intensity}")
    print(f"{'='*50}")
    
    # Use custom config or predefined config
    config = custom_config or TEST_CONFIG.get(test_intensity, TEST_CONFIG['medium'])
    num_clients = config['clients']
    num_runs = config['runs']
    test_file = config['file']
    
    # Check if test file exists
    if not os.path.exists(test_file):
        print(f"Warning: Test file {test_file} not found, using fallback")
        # Try to find any available test file
        for fallback_file in ['test_small.jpg', 'donalbebek.jpg', 'test_10mb.bin']:
            if os.path.exists(fallback_file):
                test_file = fallback_file
                print(f"Using {test_file} instead")
                break
        else:
            print("No test files found. Creating a small test file...")
            test_file = 'temp_test.bin'
            with open(test_file, 'wb') as f:
                f.write(os.urandom(1024 * 100))  # 100KB test file
    
    all_run_results = []
    
    for run_num in range(num_runs):
        print(f"\n--- Run {run_num + 1}/{num_runs} ---")
        client_results, total_time = run_clients(num_clients, server_ip, port, test_file)
        
        run_data = {
            'run': run_num + 1,
            'client_results': client_results,
            'total_time': total_time,
            'num_clients': num_clients
        }
        all_run_results.append(run_data)
        
        # Quick summary for this run
        successful = len([r for r in client_results if r.get('success', False)])
        print(f"Run {run_num + 1} completed: {successful}/{num_clients} successful in {total_time:.2f}s")
        
        # Brief pause between runs
        if run_num < num_runs - 1:
            time.sleep(2)
    
    # Analyze all results
    analyze_results_simple(all_run_results, server_type)
    
    return all_run_results

def run_test():
    """Main test function - can be called to run all tests"""
    print("HTTP Server Stress Test Suite")
    print("============================")
    
    # Get system info
    get_system_info()
    
    # Create test files
    print("\nPreparing test files...")
    create_test_files()
    
    # Test configuration
    servers_to_test = [
        {'name': 'thread_pool', 'ip': '127.0.0.1', 'port': 8885},
        {'name': 'process_pool', 'ip': '127.0.0.1', 'port': 8889}
    ]
    
    test_intensity = 'medium'  # Can be 'light', 'medium', or 'heavy'
    
    results = {}
    
    for server in servers_to_test:
        try:
            # Test if server is running
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.settimeout(1)
            result = test_socket.connect_ex((server['ip'], server['port']))
            test_socket.close()
            
            if result == 0:
                # Server is running, run the test
                server_results = test_server(
                    server['name'], 
                    server['ip'], 
                    server['port'], 
                    test_intensity
                )
                results[server['name']] = server_results
            else:
                print(f"\n{'='*50}")
                print(f"SKIPPING {server['name'].upper()} SERVER")
                print(f"Server at {server['ip']}:{server['port']} is not running")
                print(f"{'='*50}")
                
        except Exception as e:
            print(f"Error testing {server['name']}: {e}")
    
    # Final comparison
    if len(results) > 1:
        print(f"\n{'='*60}")
        print("COMPARISON SUMMARY")
        print(f"{'='*60}")
        
        for server_name, server_results in results.items():
            # Calculate overall metrics
            all_clients = []
            for run_data in server_results:
                all_clients.extend(run_data['client_results'])
            
            successful = len([r for r in all_clients if r.get('success', False)])
            total = len(all_clients)
            success_rate = (successful / total * 100) if total > 0 else 0
            
            response_times = [r['time'] for r in all_clients if r.get('success') and r.get('time', 0) > 0]
            avg_response = statistics.mean(response_times) if response_times else 0
            
            print(f"{server_name.upper()}:")
            print(f"  Success Rate: {success_rate:.1f}% ({successful}/{total})")
            print(f"  Avg Response Time: {avg_response:.3f}s")
            if response_times:
                print(f"  Median Response Time: {statistics.median(response_times):.3f}s")
            print()
    
    print("Test completed!")
    return results

def run_custom_test(server_ip, server_port, num_clients=50, num_runs=3, test_file='test_small.jpg'):
    """Run a custom test with specified parameters"""
    custom_config = {
        'clients': num_clients,
        'runs': num_runs,
        'file': test_file
    }
    
    return test_server('custom', server_ip, server_port, custom_config=custom_config)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Custom test mode
        if len(sys.argv) >= 3:
            server_ip = sys.argv[1]
            server_port = int(sys.argv[2])
            num_clients = int(sys.argv[3]) if len(sys.argv) > 3 else 50
            num_runs = int(sys.argv[4]) if len(sys.argv) > 4 else 3
            test_file = sys.argv[5] if len(sys.argv) > 5 else 'test_small.jpg'
            
            print(f"Running custom test: {server_ip}:{server_port}")
            print(f"Clients: {num_clients}, Runs: {num_runs}, File: {test_file}")
            
            get_system_info()
            create_test_files()
            run_custom_test(server_ip, server_port, num_clients, num_runs, test_file)
        else:
            print("Usage for custom test:")
            print("python stress_test.py <server_ip> <server_port> [num_clients] [num_runs] [test_file]")
    else:
        # Run full test suite
        run_test()