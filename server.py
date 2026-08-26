#!/usr/bin/env python3
"""
网络诊断工具 - 本地服务器
启动后用手机访问 http://本机IP:8080
"""
from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context
from flask_cors import CORS
import subprocess
import socket
import re
import platform
import time
import os
import sys
import json
import threading
import queue
from collections import defaultdict
from functools import wraps

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

PORT = 8080

# ========== 安全配置 ==========
# 域名白名单（空列表表示不限制）
DOMAIN_WHITELIST = [
    # 'baidu.com',
    # '*.baidu.com',
    # 'qq.com',
]

# 限流配置
RATE_LIMIT_REQUESTS = 30  # 每个时间窗口内的最大请求数
RATE_LIMIT_WINDOW = 60    # 时间窗口（秒）

# 并发限制配置
MAX_CONCURRENT_TASKS = 5  # 最大并发任务数

# ========== 安全实现 ==========
# 限流记录
rate_limit_data = defaultdict(list)
rate_limit_lock = threading.Lock()

# 并发控制
concurrent_semaphore = threading.Semaphore(MAX_CONCURRENT_TASKS)
current_tasks = 0
tasks_lock = threading.Lock()

def get_client_ip():
    """获取客户端真实IP"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    if request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    return request.remote_addr

def check_rate_limit(ip):
    """检查是否超过限流"""
    with rate_limit_lock:
        now = time.time()
        # 清理过期记录
        if ip in rate_limit_data:
            rate_limit_data[ip] = [t for t in rate_limit_data[ip] if now - t < RATE_LIMIT_WINDOW]
        else:
            rate_limit_data[ip] = []
        
        # 先检查是否超过限制
        if len(rate_limit_data[ip]) >= RATE_LIMIT_REQUESTS:
            return False, RATE_LIMIT_WINDOW - (now - rate_limit_data[ip][0])
        
        # 未超过限制，记录本次请求
        rate_limit_data[ip].append(now)
        return True, 0

def check_domain_whitelist(host):
    """检查域名是否在白名单中"""
    if not DOMAIN_WHITELIST:
        return True, ""  # 白名单为空，不限制
    
    host = host.lower()
    for pattern in DOMAIN_WHITELIST:
        pattern = pattern.lower()
        if pattern.startswith('*.'):
            # 通配符匹配
            domain = pattern[2:]
            if host.endswith(domain) or host == domain:
                return True, ""
        elif host == pattern:
            return True, ""
    
    return False, f"目标域名不在白名单中。允许的域名: {', '.join(DOMAIN_WHITELIST)}"

def rate_limit_decorator(f):
    """限流装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        ip = get_client_ip()
        allowed, retry_after = check_rate_limit(ip)
        
        if not allowed:
            return jsonify({
                'success': False,
                'error': f'请求过于频繁，请 {int(retry_after)} 秒后重试',
                'retry_after': int(retry_after)
            }), 429
        
        return f(*args, **kwargs)
    return decorated_function

def concurrent_limit_decorator(f):
    """并发限制装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        global current_tasks
        
        if not concurrent_semaphore.acquire(blocking=False):
            return jsonify({
                'success': False,
                'error': f'服务器繁忙，当前并发任务已达上限 ({MAX_CONCURRENT_TASKS})，请稍后重试'
            }), 503
        
        with tasks_lock:
            current_tasks += 1
        
        try:
            result = f(*args, **kwargs)
            return result
        finally:
            concurrent_semaphore.release()
            with tasks_lock:
                current_tasks -= 1
    
    return decorated_function

def validate_host(host):
    """验证并检查目标主机"""
    if not host:
        return False, '请提供主机地址'
    
    if not re.match(r'^[a-zA-Z0-9._-]+$', host):
        return False, '主机名格式无效'
    
    allowed, msg = check_domain_whitelist(host)
    if not allowed:
        return False, msg
    
    return True, ""

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def parse_ping_output(output, system):
    """解析ping命令输出"""
    result = {
        'success': False,
        'ip': '',
        'packets_sent': 0,
        'packets_received': 0,
        'packet_loss': 100,
        'min_rtt': 0,
        'avg_rtt': 0,
        'max_rtt': 0,
        'raw_output': output
    }
    
    if system == 'Windows':
        ip_match = re.search(r'Ping (\S+) \[(\d+\.\d+\.\d+\.\d+)\]', output)
        if not ip_match:
            ip_match = re.search(r'Ping (\S+) \((\d+\.\d+\.\d+\.\d+)\)', output)
        if ip_match:
            result['ip'] = ip_match.group(2)
        
        stats_match = re.search(r'Packets: Sent = (\d+), Received = (\d+), Lost = (\d+)', output)
        if stats_match:
            result['packets_sent'] = int(stats_match.group(1))
            result['packets_received'] = int(stats_match.group(2))
            result['packet_loss'] = round(int(stats_match.group(3)) / result['packets_sent'] * 100)
        
        rtt_match = re.search(r'Minimum = (\d+)ms, Maximum = (\d+)ms, Average = (\d+)ms', output)
        if rtt_match:
            result['min_rtt'] = int(rtt_match.group(1))
            result['max_rtt'] = int(rtt_match.group(2))
            result['avg_rtt'] = int(rtt_match.group(3))
        
        result['success'] = result['packets_received'] > 0
    else:
        ip_match = re.search(r'\((\d+\.\d+\.\d+\.\d+)\)', output)
        if ip_match:
            result['ip'] = ip_match.group(1)
        
        stats_match = re.search(r'(\d+) packets transmitted, (\d+) received', output)
        if stats_match:
            result['packets_sent'] = int(stats_match.group(1))
            result['packets_received'] = int(stats_match.group(2))
            result['packet_loss'] = round((result['packets_sent'] - result['packets_received']) / result['packets_sent'] * 100)
        
        rtt_match = re.search(r'rtt min/avg/max/mdev = ([\d.]+)/([\d.]+)/([\d.]+)', output)
        if rtt_match:
            result['min_rtt'] = float(rtt_match.group(1))
            result['avg_rtt'] = float(rtt_match.group(2))
            result['max_rtt'] = float(rtt_match.group(3))
        
        result['success'] = result['packets_received'] > 0
    
    return result

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/ping', methods=['POST'])
@rate_limit_decorator
@concurrent_limit_decorator
def ping():
    """ICMP Ping检测"""
    data = request.get_json()
    host = data.get('host', '')
    count = data.get('count', 4)
    timeout = data.get('timeout', 10)
    
    valid, msg = validate_host(host)
    if not valid:
        return jsonify({'success': False, 'error': msg}), 400
    
    system = platform.system()
    
    try:
        if system == 'Windows':
            cmd = ['ping', '-n', str(count), '-w', str(timeout * 1000), host]
        else:
            cmd = ['ping', '-c', str(count), '-W', str(timeout), host]
        
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
        output = proc.stdout + proc.stderr
        
        result = parse_ping_output(output, system)
        result['source'] = 'server'
        result['source_ip'] = get_local_ip()
        return jsonify(result)
    
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'error': 'ping超时',
            'raw_output': '命令执行超时',
            'source': 'server',
            'source_ip': get_local_ip()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'raw_output': '',
            'source': 'server',
            'source_ip': get_local_ip()
        })

@app.route('/api/dns', methods=['POST'])
@rate_limit_decorator
@concurrent_limit_decorator
def dns_lookup():
    """DNS查询"""
    data = request.get_json()
    domain = data.get('domain', '')
    dns_server = data.get('dns_server', '114.114.114.114')
    record_type = data.get('type', 'A')
    
    valid, msg = validate_host(domain)
    if not valid:
        return jsonify({'success': False, 'error': msg}), 400
    
    if not re.match(r'^\d+\.\d+\.\d+\.\d+$', dns_server):
        return jsonify({'success': False, 'error': 'DNS服务器地址格式无效'}), 400
    
    if record_type not in ['A', 'AAAA', 'NS', 'MX', 'TXT', 'CNAME', 'SOA', 'PTR']:
        return jsonify({'success': False, 'error': '不支持的记录类型'}), 400
    
    try:
        system = platform.system()
        
        if system == 'Windows':
            cmd = ['nslookup', f'-type={record_type}', domain, dns_server]
        else:
            cmd = ['dig', f'@{dns_server}', domain, record_type, '+short', '+time=5', '+tries=2']
        
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        output = proc.stdout
        
        records = []
        if system == 'Windows':
            lines = output.split('\n')
            for line in lines:
                if 'Address:' in line or 'Addresses:' in line:
                    continue
                ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                if ip_match:
                    records.append(ip_match.group(1))
        else:
            for line in output.strip().split('\n'):
                line = line.strip()
                if line and not line.startswith(';'):
                    records.append(line)
        
        return jsonify({
            'success': True,
            'domain': domain,
            'dns_server': dns_server,
            'type': record_type,
            'records': records,
            'raw_output': output,
            'source': 'server',
            'source_ip': get_local_ip()
        })
    
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'error': 'DNS查询超时',
            'raw_output': '',
            'source': 'server',
            'source_ip': get_local_ip()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'raw_output': '',
            'source': 'server',
            'source_ip': get_local_ip()
        })

@app.route('/api/port', methods=['POST'])
@rate_limit_decorator
@concurrent_limit_decorator
def port_check():
    """TCP端口检测"""
    data = request.get_json()
    host = data.get('host', '')
    port = data.get('port', 80)
    timeout = data.get('timeout', 5)
    
    valid, msg = validate_host(host)
    if not valid:
        return jsonify({'success': False, 'error': msg}), 400
    
    if port < 1 or port > 65535:
        return jsonify({'success': False, 'error': '端口号无效'}), 400
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        
        start_time = time.time()
        result = sock.connect_ex((host, port))
        elapsed = round((time.time() - start_time) * 1000, 2)
        
        sock.close()
        
        return jsonify({
            'success': result == 0,
            'host': host,
            'port': port,
            'open': result == 0,
            'latency_ms': elapsed if result == 0 else None,
            'error': None if result == 0 else f'连接被拒绝或超时 (errno: {result})',
            'source': 'server',
            'source_ip': get_local_ip()
        })
    
    except socket.gaierror:
        return jsonify({
            'success': False,
            'host': host,
            'port': port,
            'open': False,
            'error': '域名解析失败',
            'source': 'server',
            'source_ip': get_local_ip()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'host': host,
            'port': port,
            'open': False,
            'error': str(e),
            'source': 'server',
            'source_ip': get_local_ip()
        })

@app.route('/api/http', methods=['POST'])
@rate_limit_decorator
@concurrent_limit_decorator
def http_check():
    """HTTP网站检测"""
    import requests
    from urllib.parse import urlparse
    
    data = request.get_json()
    url = data.get('url', '')
    timeout = data.get('timeout', 10)
    
    if not url:
        return jsonify({'success': False, 'error': '请提供URL'}), 400
    
    if not url.startswith('http'):
        url = 'https://' + url
    
    try:
        parsed = urlparse(url)
        host = parsed.hostname
    except Exception:
        return jsonify({'success': False, 'error': 'URL格式无效'}), 400
    
    valid, msg = validate_host(host)
    if not valid:
        return jsonify({'success': False, 'error': msg}), 400
    
    try:
        start_time = time.time()
        response = requests.get(url, timeout=timeout, allow_redirects=True, verify=False)
        elapsed = round((time.time() - start_time) * 1000, 2)
        
        return jsonify({
            'success': True,
            'url': url,
            'host': host,
            'status_code': response.status_code,
            'latency_ms': elapsed,
            'final_url': response.url,
            'error': None,
            'source': 'server',
            'source_ip': get_local_ip()
        })
    except requests.exceptions.Timeout:
        return jsonify({
            'success': False,
            'url': url,
            'host': host,
            'error': '请求超时',
            'source': 'server',
            'source_ip': get_local_ip()
        })
    except requests.exceptions.ConnectionError:
        return jsonify({
            'success': False,
            'url': url,
            'host': host,
            'error': '连接失败',
            'source': 'server',
            'source_ip': get_local_ip()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'url': url,
            'host': host,
            'error': str(e),
            'source': 'server',
            'source_ip': get_local_ip()
        })

@app.route('/api/batch_ping', methods=['POST'])
@rate_limit_decorator
@concurrent_limit_decorator
def batch_ping():
    """批量Ping检测"""
    data = request.get_json()
    hosts = data.get('hosts', [])
    count = data.get('count', 2)
    timeout = data.get('timeout', 5)
    
    if not hosts:
        return jsonify({'success': False, 'error': '请提供主机列表'}), 400
    
    if len(hosts) > 10:
        return jsonify({'success': False, 'error': '单次检测不能超过10个主机'}), 400
    
    # 验证所有主机
    for host in hosts:
        valid, msg = validate_host(host.strip())
        if not valid:
            return jsonify({'success': False, 'error': msg}), 400
    
    results = []
    
    for host in hosts:
        host = host.strip()
        if not host:
            continue
        
        try:
            try:
                ip = socket.gethostbyname(host)
            except:
                ip = host
            
            system = platform.system()
            if system == 'Windows':
                cmd = ['ping', '-n', str(count), '-w', str(timeout * 1000), host]
            else:
                cmd = ['ping', '-c', str(count), '-W', str(timeout), host]
            
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
            output = proc.stdout + proc.stderr
            
            result = parse_ping_output(output, system)
            result['host'] = host
            result['resolved_ip'] = ip
            results.append(result)
        
        except Exception as e:
            results.append({
                'host': host,
                'success': False,
                'error': str(e)
            })
    
    return jsonify({
        'success': True,
        'results': results,
        'total': len(results),
        'online': sum(1 for r in results if r.get('success', False)),
        'source': 'server',
        'source_ip': get_local_ip()
    })

@app.route('/api/traceroute', methods=['POST'])
@rate_limit_decorator
@concurrent_limit_decorator
def traceroute():
    """路由跟踪 - 实时流式输出"""
    import shutil
    import queue
    
    data = request.get_json()
    host = data.get('host', '')
    max_hops = data.get('max_hops', 30)
    timeout = data.get('timeout', 30)
    
    valid, msg = validate_host(host)
    if not valid:
        return jsonify({'success': False, 'error': msg}), 400
    
    # 解析目标IP
    try:
        target_ip = socket.gethostbyname(host)
    except:
        target_ip = host
    
    def generate():
        """生成器函数，逐跳返回结果"""
        system = platform.system()
        has_traceroute = shutil.which('traceroute') or (system == 'Windows' and shutil.which('tracert'))
        
        # 发送开始事件
        yield f"data: {json.dumps({'type': 'start', 'host': host, 'target_ip': target_ip, 'source': 'server', 'source_ip': get_local_ip()})}\n\n"
        
        if has_traceroute:
            # 使用系统traceroute命令
            if system == 'Windows':
                cmd = ['tracert', '-h', str(max_hops), '-w', str(5000), host]
            else:
                cmd = ['traceroute', '-m', str(max_hops), '-w', '5', host]
            
            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
                
                for line in proc.stdout:
                    hop = None
                    if system == 'Windows':
                        match = re.match(r'\s*(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)', line)
                        if match:
                            hop_num = int(match.group(1))
                            rtt1 = match.group(2)
                            rtt2 = match.group(3)
                            rtt3 = match.group(4)
                            ip_or_host = match.group(5)
                            
                            if rtt1 == '*' and rtt2 == '*' and rtt3 == '*':
                                hop = {
                                    'hop': hop_num,
                                    'ip': '*',
                                    'hostname': '*',
                                    'rtt': ['*', '*', '*']
                                }
                            else:
                                ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', ip_or_host)
                                ip = ip_match.group(1) if ip_match else ip_or_host
                                hostname = ip_or_host if not ip_match else ip_or_host.replace(f'[{ip}]', '').strip()
                                
                                rtt_values = []
                                for rtt in [rtt1, rtt2, rtt3]:
                                    if rtt == '*':
                                        rtt_values.append('*')
                                    else:
                                        try:
                                            rtt_values.append(float(rtt.replace('ms', '')))
                                        except:
                                            rtt_values.append('*')
                                
                                hop = {
                                    'hop': hop_num,
                                    'ip': ip,
                                    'hostname': hostname if hostname else ip,
                                    'rtt': rtt_values
                                }
                    else:
                        match = re.match(r'\s*(\d+)\s+(.+)', line)
                        if match:
                            hop_num = int(match.group(1))
                            rest = match.group(2).strip()
                            
                            if rest.startswith('*'):
                                hop = {
                                    'hop': hop_num,
                                    'ip': '*',
                                    'hostname': '*',
                                    'rtt': ['*', '*', '*']
                                }
                            else:
                                host_ip_match = re.search(r'([a-zA-Z0-9._-]+)\s+\((\d+\.\d+\.\d+\.\d+)\)', rest)
                                if host_ip_match:
                                    hostname = host_ip_match.group(1)
                                    ip = host_ip_match.group(2)
                                else:
                                    ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', rest)
                                    ip = ip_match.group(1) if ip_match else '*'
                                    hostname = ip
                                
                                rtt_values = []
                                rtt_matches = re.findall(r'([\d.]+)\s+ms', rest)
                                for rtt in rtt_matches:
                                    try:
                                        rtt_values.append(float(rtt))
                                    except:
                                        rtt_values.append('*')
                                
                                while len(rtt_values) < 3:
                                    rtt_values.append('*')
                                
                                hop = {
                                    'hop': hop_num,
                                    'ip': ip,
                                    'hostname': hostname,
                                    'rtt': rtt_values[:3]
                                }
                    
                    if hop:
                        yield f"data: {json.dumps({'type': 'hop', 'data': hop})}\n\n"
                
                proc.wait()
                
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
        else:
            # 使用Python实现的traceroute（流式）
            dest_addr = socket.gethostbyname(host)
            
            for ttl in range(1, max_hops + 1):
                rtts = []
                current_addr = None
                hostname = None
                
                # 发送3个探测包并测量RTT
                for probe in range(3):
                    try:
                        recv_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
                        send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
                        send_socket.setsockopt(socket.SOL_IP, socket.IP_TTL, ttl)
                        recv_socket.settimeout(2)
                        recv_socket.bind(("", 33434 + probe))
                        
                        start_time = time.time()
                        send_socket.sendto(b"", (dest_addr, 33434 + probe))
                        
                        try:
                            data_recv, addr = recv_socket.recvfrom(512)
                            elapsed = round((time.time() - start_time) * 1000, 1)
                            current_addr = addr[0]
                            rtts.append(elapsed)
                            
                            if not hostname:
                                try:
                                    hostname = socket.gethostbyaddr(current_addr)[0]
                                except:
                                    hostname = current_addr
                                    
                        except socket.timeout:
                            rtts.append('*')
                        
                        recv_socket.close()
                        send_socket.close()
                        
                    except Exception:
                        rtts.append('*')
                
                # 确保rtt列表有3个元素
                while len(rtts) < 3:
                    rtts.append('*')
                
                if current_addr:
                    hop = {
                        'hop': ttl,
                        'ip': current_addr,
                        'hostname': hostname or current_addr,
                        'rtt': rtts[:3]
                    }
                else:
                    hop = {
                        'hop': ttl,
                        'ip': '*',
                        'hostname': '*',
                        'rtt': ['*', '*', '*']
                    }
                
                yield f"data: {json.dumps({'type': 'hop', 'data': hop})}\n\n"
                
                if current_addr == dest_addr:
                    break
        
        # 发送完成事件
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
    
    return Response(
        stream_with_context(generate()), 
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )

@app.route('/api/mtr', methods=['POST'])
@rate_limit_decorator
@concurrent_limit_decorator
def mtr():
    """MTR (My Traceroute) 检测"""
    data = request.get_json()
    host = data.get('host', '')
    count = data.get('count', 10)
    timeout = data.get('timeout', 60)
    
    valid, msg = validate_host(host)
    if not valid:
        return jsonify({'success': False, 'error': msg}), 400
    
    system = platform.system()
    
    try:
        hops_data = {}
        
        if system == 'Windows':
            for i in range(count):
                cmd = ['tracert', '-h', '30', '-w', '3000', host]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout // count + 5)
                output = proc.stdout
                lines = output.strip().split('\n')
                
                for line in lines:
                    match = re.match(r'\s*(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)', line)
                    if match:
                        hop_num = int(match.group(1))
                        rtt1 = match.group(2)
                        ip_or_host = match.group(5)
                        
                        if hop_num not in hops_data:
                            ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', ip_or_host)
                            ip = ip_match.group(1) if ip_match else ip_or_host
                            hops_data[hop_num] = {
                                'hop': hop_num,
                                'ip': ip,
                                'hostname': ip_or_host,
                                'rtts': [],
                                'sent': 0,
                                'lost': 0
                            }
                        
                        hops_data[hop_num]['sent'] += 1
                        if rtt1 == '*':
                            hops_data[hop_num]['lost'] += 1
                        else:
                            try:
                                rtt = float(rtt1.replace('ms', ''))
                                hops_data[hop_num]['rtts'].append(rtt)
                            except:
                                pass
        else:
            cmd = ['mtr', '--report', '--report-cycles', str(count), '--json', host]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 10)
            output = proc.stdout
            
            try:
                mtr_data = json.loads(output)
                
                for i, hub in enumerate(mtr_data.get('report', {}).get('hubs', [])):
                    hop_num = i + 1
                    # mtr json 输出字段: host, Loss%, Snt, Last, Avg, Best, Wrst, StDev
                    host_name = hub.get('host', '')
                    # 如果 host 是 ??? 或空，则设为 *
                    if not host_name or host_name == '???':
                        host_name = '*'
                    
                    hops_data[hop_num] = {
                        'hop': hop_num,
                        'ip': host_name,
                        'hostname': host_name,
                        'rtts': [],
                        'sent': hub.get('Snt', count),
                        'lost': 0,  # 丢包数，稍后计算
                        'lost_percent': hub.get('Loss%', 0),  # 直接使用百分比
                        'avg': hub.get('Avg', 0),
                        'best': hub.get('Best', 0),
                        'worst': hub.get('Wrst', 0),
                        'stdev': hub.get('StDev', 0)
                    }
            except:
                cmd = ['mtr', '--report', '--report-cycles', str(count), host]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 10)
                output = proc.stdout
                lines = output.strip().split('\n')
                
                for line in lines:
                    match = re.match(r'\s*(\d+)\.\s+(\S+)\s+(\S+)%\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)', line)
                    if match:
                        hop_num = int(match.group(1))
                        hops_data[hop_num] = {
                            'hop': hop_num,
                            'ip': match.group(2),
                            'hostname': match.group(2),
                            'sent': count,
                            'lost': int(float(match.group(3))),
                            'avg': float(match.group(5)),
                            'best': float(match.group(6)),
                            'worst': float(match.group(7)),
                            'stdev': float(match.group(8))
                        }
        
        hops = []
        for hop_num in sorted(hops_data.keys()):
            hop_data = hops_data[hop_num]
            # 优先使用已有的 lost_percent，否则计算
            if 'lost_percent' in hop_data:
                lost_percent = round(hop_data['lost_percent'])
            elif hop_data.get('sent', 0) > 0:
                lost_percent = round(hop_data.get('lost', 0) / hop_data['sent'] * 100)
            else:
                lost_percent = 0
            
            if 'avg' not in hop_data and hop_data.get('rtts'):
                hop_data['avg'] = sum(hop_data['rtts']) / len(hop_data['rtts'])
                hop_data['best'] = min(hop_data['rtts'])
                hop_data['worst'] = max(hop_data['rtts'])
                hop_data['stdev'] = 0
            
            hops.append({
                'hop': hop_num,
                'ip': hop_data.get('ip', ''),
                'hostname': hop_data.get('hostname', ''),
                'sent': hop_data.get('sent', count),
                'lost': hop_data.get('lost', 0),
                'lost_percent': lost_percent,
                'avg': hop_data.get('avg', 0),
                'best': hop_data.get('best', 0),
                'worst': hop_data.get('worst', 0),
                'stdev': hop_data.get('stdev', 0)
            })
        
        return jsonify({
            'success': True,
            'host': host,
            'count': count,
            'hops': hops,
            'total_hops': len(hops),
            'source': 'server',
            'source_ip': get_local_ip()
        })
    
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'error': 'MTR执行超时',
            'raw_output': '',
            'source': 'server',
            'source_ip': get_local_ip()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'raw_output': '',
            'source': 'server',
            'source_ip': get_local_ip()
        })

@app.route('/api/ip', methods=['GET'])
def get_ip_info():
    """获取公网IP和运营商信息"""
    import urllib.request
    
    # 尝试多个IP查询服务
    services = [
        'http://ip-api.com/json/?lang=zh-CN',
        'https://ipinfo.io/json',
    ]
    
    for url in services:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                
                if 'ip-api.com' in url:
                    return jsonify({
                        'success': True,
                        'ip': data.get('query', ''),
                        'country': data.get('country', ''),
                        'region': data.get('regionName', ''),
                        'city': data.get('city', ''),
                        'isp': data.get('isp', ''),
                        'org': data.get('org', ''),
                        'as': data.get('as', '')
                    })
                elif 'ipinfo.io' in url:
                    return jsonify({
                        'success': True,
                        'ip': data.get('ip', ''),
                        'country': data.get('country', ''),
                        'region': data.get('region', ''),
                        'city': data.get('city', ''),
                        'isp': data.get('org', ''),
                        'org': data.get('org', ''),
                        'as': ''
                    })
        except Exception as e:
            continue
    
    return jsonify({
        'success': False,
        'error': '无法获取IP信息'
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'version': '2.0'})

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    local_ip = get_local_ip()
    
    print("=" * 50)
    print("       网络诊断工具 - 本地服务器 v3.0")
    print("=" * 50)
    print(f"\n本机访问: http://localhost:{PORT}")
    print(f"手机访问: http://{local_ip}:{PORT}")
    print(f"\n请确保手机和电脑在同一局域网")
    print("\nAPI接口:")
    print("  POST /api/ping        - ICMP Ping检测")
    print("  POST /api/traceroute  - 路由跟踪")
    print("  POST /api/mtr         - MTR网络诊断")
    print("  POST /api/dns         - DNS查询")
    print("  POST /api/port        - TCP端口检测")
    print("  POST /api/batch_ping  - 批量Ping")
    print("  POST /api/http        - HTTP网站检测")
    print("\n按 Ctrl+C 停止服务器")
    print("=" * 50)
    print(f"\n本机访问: http://localhost:{PORT}")
    print(f"手机访问: http://{local_ip}:{PORT}")
    print(f"\n请确保手机和电脑在同一局域网")
    print("\nAPI接口:")
    print("  POST /api/ping        - ICMP Ping检测")
    print("  POST /api/traceroute  - 路由跟踪")
    print("  POST /api/mtr         - MTR网络诊断")
    print("  POST /api/dns         - DNS查询")
    print("  POST /api/port        - TCP端口检测")
    print("  POST /api/batch_ping  - 批量Ping")
    print("\n按 Ctrl+C 停止服务器")
    print("=" * 50)
    
    app.run(host='0.0.0.0', port=PORT, debug=False)

if __name__ == "__main__":
    main()
