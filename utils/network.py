#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
network.py - Network helper with Telegram integration
"""

import socket
import requests
import urllib3
import ssl
import json
import ipaddress
import subprocess
import threading
import queue
import time
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urlparse, urljoin
from datetime import datetime

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Import logger
from .logger import get_logger

logger = get_logger()

class NetworkManager:
    """Manages network operations with Telegram notifications"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.session = requests.Session()
        self.setup_session()
        
        # Telegram bot for notifications
        self.telegram_bot = None
        self.setup_telegram()
        
        # Network monitoring
        self.monitoring = False
        self.monitor_thread = None
        
        # Cache
        self.cache = {
            'interfaces': {},
            'connections': [],
            'last_scan': None
        }
    
    def setup_session(self):
        """Setup HTTP session with custom headers and settings"""
        # User-Agent rotation
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15'
        ]
        
        headers = {
            'User-Agent': user_agents[0],
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        self.session.headers.update(headers)
        
        # Proxy configuration
        proxy_config = self.config.get('proxy', {})
        if proxy_config.get('enabled', False):
            proxy_url = proxy_config.get('url')
            if proxy_url:
                self.session.proxies = {
                    'http': proxy_url,
                    'https': proxy_url
                }
                logger.info(f"Proxy configured: {proxy_url}", module="network")
        
        # SSL verification
        verify_ssl = self.config.get('verify_ssl', True)
        self.session.verify = verify_ssl
        if not verify_ssl:
            logger.warning("SSL verification disabled", module="network")
    
    def setup_telegram(self):
        """Setup Telegram bot for notifications"""
        telegram_config = self.config.get('telegram', {})
        bot_token = telegram_config.get('bot_token')
        chat_id = telegram_config.get('network_chat_id')
        
        if bot_token and chat_id:
            try:
                from telegram import Bot
                self.telegram_bot = Bot(token=bot_token)
                self.network_chat_id = chat_id
                logger.info("Telegram network bot initialized", module="network")
            except ImportError:
                logger.warning("Telegram module not available", module="network")
            except Exception as e:
                logger.error(f"Error setting up Telegram: {e}", module="network")
    
    def send_telegram_notification(self, title: str, message: str):
        """Send network notification to Telegram"""
        if not self.telegram_bot or not hasattr(self, 'network_chat_id'):
            return
        
        try:
            full_message = fb>🌐 {title}</b>\n\n{message}"
            self.telegram_bot.send_message(
                chat_id=self.network_chat_id,
                text=full_message,
                parse_mode='HTML'
            )
            logger.debug(f"Telegram network notification sent: {title}", module="network")
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}", module="network")
    
    def get_local_ip(self) -> str:
        """Get local IP address"""
        try:
            # Create a socket connection to get local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            
            logger.debug(f"Local IP: {local_ip}", module="network")
            return local_ip
        except Exception as e:
            logger.error(f"Error getting local IP: {e}", module="network")
            return "127.0.0.1"
    
    def get_public_ip(self) -> str:
        """Get public IP address"""
        services = [
            'https://api.ipify.org',
            'https://ident.me',
            'https://checkip.amazonaws.com'
        ]
        
        for service in services:
            try:
                response = self.session.get(service, timeout=5)
                if response.status_code == 200:
                    public_ip = response.text.strip()
                    logger.debug(f"Public IP: {public_ip}", module="network")
                    return public_ip
            except Exception as e:
                logger.debug(f"Failed to get IP from {service}: {e}", module="network")
                continue
        
        logger.error("Failed to get public IP from all services", module="network")
        return "Unknown"
    
    def get_network_interfaces(self) -> Dict[str, Dict]:
        """Get network interfaces information"""
        try:
            import netifaces
            
            interfaces = {}
            for iface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(iface)
                
                interface_info = {
                    'name': iface,
                    'mac': addrs.get(netifaces.AF_LINK, [{}])[0].get('addr', ''),
                    'ipv4': addrs.get(netifaces.AF_INET, [{}])[0].get('addr', ''),
                    'netmask': addrs.get(netifaces.AF_INET, [{}])[0].get('netmask', ''),
                    'ipv6': addrs.get(netifaces.AF_INET6, [{}])[0].get('addr', '')
                }
                
                interfaces[iface] = interface_info
            
            self.cache['interfaces'] = interfaces
            logger.debug(f"Found {len(interfaces)} network interfaces", module="network")
            return interfaces
            
        except ImportError:
            logger.warning("netifaces not available, using fallback", module="network")
            return self._get_interfaces_fallback()
        except Exception as e:
            logger.error(f"Error getting network interfaces: {e}", module="network")
            return {}
    
    def _get_interfaces_fallback(self) -> Dict[str, Dict]:
        """Fallback method for getting network interfaces"""
        interfaces = {}
        
        try:
            # Windows
            if os.name == 'nt':
                import ctypes
                import ctypes.wintypes
                
                # This is simplified - in production use proper Windows API
                hostname = socket.gethostname()
                local_ip = socket.gethostbyname(hostname)
                
                interfaces['Ethernet'] = {
                    'name': 'Ethernet',
                    'ipv4': local_ip,
                    'mac': '00:00:00:00:00:00'
                }
            
            # Linux/Mac
            else:
                import subprocess
                
                # Use ip command (Linux)
                try:
                    result = subprocess.run(
                        ['ip', 'addr', 'show'],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    
                    if result.returncode == 0:
                        lines = result.stdout.split('\n')
                        current_iface = None
                        
                        for line in lines:
                            if ':' in line and not line.startswith(' '):
                                # New interface
                                parts = line.split(':')
                                if len(parts) >= 2:
                                    current_iface = parts[1].strip()
                                    interfaces[current_iface] = {
                                        'name': current_iface,
                                        'mac': '',
                                        'ipv4': '',
                                        'ipv6': ''
                                    }
                            
                            elif current_iface and 'inet ' in line:
                                # IPv4 address
                                parts = line.strip().split()
                                if len(parts) >= 2:
                                    interfaces[current_iface]['ipv4'] = parts[1].split('/')[0]
                            
                            elif current_iface and 'link/ether' in line:
                                # MAC address
                                parts = line.strip().split()
                                if len(parts) >= 2:
                                    interfaces[current_iface]['mac'] = parts[1]
                
                except (subprocess.SubprocessError, FileNotFoundError):
                    pass
            
            return interfaces
            
        except Exception as e:
            logger.error(f"Fallback interface error: {e}", module="network")
            return {}
    
    def scan_network(self, network_range: str = None, ports: List[int] = None) -> List[Dict]:
        """Scan network for active hosts and open ports"""
        try:
            if network_range is None:
                # Default to local subnet
                local_ip = self.get_local_ip()
                network_range = f"{local_ip}/24"
            
            if ports is None:
                ports = [21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445, 3389, 8080]
            
            network = ipaddress.ip_network(network_range, strict=False)
            active_hosts = []
            
            logger.info(f"Scanning network {network_range}...", module="network")
            
            # Create queue for scanning
            host_queue = queue.Queue()
            result_queue = queue.Queue()
            
            # Add all hosts to queue
            for host in network.hosts():
                host_queue.put(str(host))
            
            # Worker function
            def scan_worker():
                while not host_queue.empty():
                    try:
                        host = host_queue.get_nowait()
                        open_ports = self.scan_host_ports(host, ports)
                        
                        if open_ports:
                            host_info = {
                                'ip': host,
                                'hostname': self.reverse_dns(host),
                                'open_ports': open_ports,
                                'scan_time': datetime.now().isoformat()
                            }
                            result_queue.put(host_info)
                        
                        host_queue.task_done()
                    except queue.Empty:
                        break
                    except Exception as e:
                        logger.error(f"Scan error for host: {e}", module="network")
            
            # Start worker threads
            threads = []
            for _ in range(10):  # 10 concurrent scanners
                thread = threading.Thread(target=scan_worker, daemon=True)
                thread.start()
                threads.append(thread)
            
            # Wait for completion
            for thread in threads:
                thread.join()
            
            # Collect results
            while not result_queue.empty():
                active_hosts.append(result_queue.get())
            
            # Update cache
            self.cache['connections'] = active_hosts
            self.cache['last_scan'] = datetime.now().isoformat()
            
            # Send Telegram notification
            if active_hosts:
                self.send_telegram_notification(
                    "Network Scan Results",
                    f"Scanned: {network_range}\n"
                    f"Active hosts: {len(active_hosts)}\n"
                    f"Ports scanned: {len(ports)}"
                )
            
            logger.info(f"Scan complete: {len(active_hosts)} active hosts found", module="network")
            return active_hosts
            
        except Exception as e:
            logger.error(f"Network scan error: {e}", module="network")
            return []
    
    def scan_host_ports(self, host: str, ports: List[int]) -> List[Dict]:
        """Scan specific ports on a host"""
        open_ports = []
        
        for port in ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                
                result = sock.connect_ex((host, port))
                if result == 0:
                    # Try to get service banner
                    try:
                        sock.send(b'\r\n')
                        banner = sock.recv(1024).decode('utf-8', errors='ignore').strip()
                    except:
                        banner = ''
                    
                    port_info = {
                        'port': port,
                        'service': self.get_service_name(port),
                        'banner': banner[:100] if banner else '',
                        'protocol': 'TCP'
                    }
                    open_ports.append(port_info)
                
                sock.close()
                
            except Exception:
                continue
        
        return open_ports
    
    def get_service_name(self, port: int) -> str:
        """Get service name for port"""
        common_ports = {
            21: 'FTP', 22: 'SSH', 23: 'Telnet', 25: 'SMTP',
            53: 'DNS', 80: 'HTTP', 110: 'POP3', 135: 'MSRPC',
            139: 'NetBIOS', 143: 'IMAP', 443: 'HTTPS', 445: 'SMB',
            3389: 'RDP', 5900: 'VNC', 8080: 'HTTP-Proxy'
        }
        return common_ports.get(port, f'Port {port}')
    
    def reverse_dns(self, ip: str) -> str:
        """Perform reverse DNS lookup"""
        try:
            hostname = socket.gethostbyaddr(ip)[0]
            return hostname
        except (socket.herror, socket.gaierror):
            return ip
        except Exception as e:
            logger.debug(f"Reverse DNS error for {ip}: {e}", module="network")
            return ip
    
    def download_file(self, url: str, save_path: str, 
                     headers: Dict = None, verify: bool = True) -> bool:
        """Download file from URL"""
        try:
            logger.info(f"Downloading {url} to {save_path}", module="network")
            
            response = self.session.get(
                url,
                headers=headers,
                stream=True,
                verify=verify,
                timeout=30
            )
            
            if response.status_code == 200:
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(save_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                
                # Verify download
                if os.path.exists(save_path):
                    file_size = os.path.getsize(save_path)
                    success = file_size > 0
                    
                    if success:
                        logger.info(f"Download completed: {file_size} bytes", module="network")
                        
                        # Send Telegram notification for large downloads
                        if file_size > 10*1024*1024:  # 10 MB
                            self.send_telegram_notification(
                                "File Downloaded",
                                f"URL: {url}\n"
                                f"Size: {file_size/(1024*1024):.2f} MB\n"
                                f"Saved to: {save_path}"
                            )
                    
                    return success
            
            logger.error(f"Download failed: HTTP {response.status_code}", module="network")
            return False
            
        except Exception as e:
            logger.error(f"Download error: {e}", module="network")
            return False
    
    def upload_file(self, url: str, file_path: str, 
                   field_name: str = 'file', 
                   additional_data: Dict = None) -> Dict:
        """Upload file to URL"""
        try:
            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}", module="network")
                return {'success': False, 'error': 'File not found'}
            
            file_size = os.path.getsize(file_path)
            logger.info(f"Uploading {file_path} ({file_size} bytes) to {url}", module="network")
            
            files = {field_name: open(file_path, 'rb')}
            data = additional_data or {}
            
            response = self.session.post(
                url,
                files=files,
                data=data,
                timeout=60
            )
            
            files[field_name].close()
            
            result = {
                'success': response.status_code in [200, 201],
                'status_code': response.status_code,
                'response': response.text,
                'headers': dict(response.headers)
            }
            
            if result['success']:
                logger.info(f"Upload successful: {response.status_code}", module="network")
                
                # Send Telegram notification
                self.send_telegram_notification(
                    "File Uploaded",
                    f"File: {os.path.basename(file_path)}\n"
                    f"Size: {file_size/(1024*1024):.2f} MB\n"
                    f"To: {url}\n"
                    f"Status: {response.status_code}"
                )
            else:
                logger.error(f"Upload failed: {response.status_code}", module="network")
            
            return result
            
        except Exception as e:
            logger.error(f"Upload error: {e}", module="network")
            return {'success': False, 'error': str(e)}
    
    def check_connectivity(self, targets: List[str] = None) -> Dict[str, bool]:
        """Check connectivity to targets"""
        if targets is None:
            targets = [
                '8.8.8.8',  # Google DNS
                '1.1.1.1',  # Cloudflare DNS
                'google.com',
                'github.com'
            ]
        
        results = {}
        
        for target in targets:
            try:
                # Try DNS resolution first
                socket.gethostbyname(target)
                
                # Try HTTP/HTTPS if it's a URL
                if target.startswith('http'):
                    response = self.session.get(target, timeout=5, verify=False)
                    results[target] = response.status_code == 200
                else:
                    # Try ICMP ping (simplified)
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(2)
                    result = sock.connect_ex((target, 80))
                    sock.close()
                    results[target] = result == 0
                
            except Exception as e:
                results[target] = False
                logger.debug(f"Connectivity check failed for {target}: {e}", module="network")
        
        # Send Telegram notification if connectivity issues
        failed = [t for t, r in results.items() if not r]
        if failed:
            self.send_telegram_notification(
                "Connectivity Issues",
                f"Failed to connect to:\n" + "\n".join(failed)
            )
        
        return results
    
    def start_monitoring(self, interval: int = 300):
        """Start network monitoring"""
        if self.monitoring:
            logger.warning("Monitoring already running", module="network")
            return
        
        self.monitoring = True
        
        def monitor_loop():
            while self.monitoring:
                try:
                    # Check connectivity
                    connectivity = self.check_connectivity()
                    
                    # Scan network periodically
                    current_hour = datetime.now().hour
                    if current_hour in [0, 6, 12, 18]:  # Every 6 hours
                        self.scan_network()
                    
                    # Check for new interfaces
                    interfaces = self.get_network_interfaces()
                    
                    # Log status
                    logger.debug(f"Network monitoring cycle completed", module="network")
                    
                except Exception as e:
                    logger.error(f"Monitoring error: {e}", module="network")
                
                time.sleep(interval)
        
        self.monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        logger.info(f"Network monitoring started (interval: {interval}s)", module="network")
        self.send_telegram_notification(
            "Network Monitoring Started",
            f"Monitoring interval: {interval} seconds"
        )
    
    def stop_monitoring(self):
        """Stop network monitoring"""
        self.monitoring = False
        
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        logger.info("Network monitoring stopped", module="network")
        self.send_telegram_notification(
            "Network Monitoring Stopped",
            "Monitoring has been stopped"
        )
    
    def get_status(self) -> Dict[str, Any]:
        """Get network manager status"""
        return {
            'local_ip': self.get_local_ip(),
            'public_ip': self.get_public_ip(),
            'interfaces': len(self.cache['interfaces']),
            'last_scan': self.cache['last_scan'],
            'active_hosts': len(self.cache['connections']),
            'monitoring': self.monitoring,
            'proxy_configured': bool(self.session.proxies),
            'ssl_verification': self.session.verify
        }

# Global instance
_network_manager = None

def get_network_manager(config: Dict = None) -> NetworkManager:
    """Get or create network manager instance"""
    global _network_manager
    
    if _network_manager is None:
        _network_manager = NetworkManager(config)
    
    return _network_manager

if __name__ == "__main__":
    # Test the network manager
    config = {
        'telegram': {
            'bot_token': 'test_token',
            'network_chat_id': 123456789
        }
    }
    
    manager = get_network_manager(config)
    
    # Test basic functions
    print(f"Local IP: {manager.get_local_ip()}")
    print(f"Public IP: {manager.get_public_ip()}")
    
    # Test network interfaces
    interfaces = manager.get_network_interfaces()
    print(f"Network Interfaces: {len(interfaces)}")
    
    # Test connectivity
    connectivity = manager.check_connectivity(['google.com', 'github.com'])
    print(f"Connectivity: {connectivity}")
    
    # Show status
    status = manager.get_status()
    print(f"\n🌐 Network Manager Status: {status}")
    
    print("\n✅ Network tests completed!")
