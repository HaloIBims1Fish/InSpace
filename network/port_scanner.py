#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
port_scanner.py - Advanced Multi-Threaded Port Scanner with Stealth Techniques
"""

import os
import sys
import json
import time
import random
import threading
import socket
import struct
import ipaddress
import select
import subprocess
from typing import Dict, List, Optional, Tuple, Any, Union, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
import nmap
import scapy.all as scapy
from scapy.layers.inet import IP, TCP, UDP, ICMP
from scapy.layers.inet6 import IPv6
from scapy.sendrecv import sr1, sr

# Import utilities
from ..utils.logger import get_logger
from ..security.audit_log import get_audit_log_manager, AuditEventType, AuditSeverity

logger = get_logger()
audit_log = get_audit_log_manager()

class ScanType(Enum):
    """Port scanning techniques"""
    TCP_SYN = "tcp_syn"          # SYN scan (half-open)
    TCP_CONNECT = "tcp_connect"  # TCP connect scan
    TCP_ACK = "tcp_ack"          # ACK scan
    TCP_WINDOW = "tcp_window"    # Window scan
    TCP_MAIMON = "tcp_maimon"    # Maimon scan
    TCP_FIN = "tcp_fin"          # FIN scan
    TCP_NULL = "tcp_null"        # NULL scan
    TCP_XMAS = "tcp_xmas"        # XMAS scan
    UDP = "udp"                  # UDP scan
    SCTP = "sctp"                # SCTP scan
    IP_PROTO = "ip_proto"        # IP protocol scan
    IDLE = "idle"                # Idle scan (zombie)
    FTP_BOUNCE = "ftp_bounce"    # FTP bounce scan
    SERVICE = "service"          # Service version detection
    OS = "os"                    # OS detection
    PING = "ping"                # Ping scan
    DISCOVERY = "discovery"      # Network discovery

class PortStatus(Enum):
    """Port status"""
    OPEN = "open"
    CLOSED = "closed"
    FILTERED = "filtered"
    UNFILTERED = "unfiltered"
    OPEN_FILTERED = "open|filtered"
    CLOSED_FILTERED = "closed|filtered"

@dataclass
class PortResult:
    """Port scan result"""
    host: str
    port: int
    protocol: str
    status: PortStatus
    service: Optional[str] = None
    version: Optional[str] = None
    banner: Optional[str] = None
    response_time: Optional[float] = None
    ttl: Optional[int] = None
    os_guess: Optional[str] = None
    timestamp: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'host': self.host,
            'port': self.port,
            'protocol': self.protocol,
            'status': self.status.value,
            'service': self.service,
            'version': self.version,
            'banner': self.banner,
            'response_time': self.response_time,
            'ttl': self.ttl,
            'os_guess': self.os_guess,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }

@dataclass
class HostResult:
    """Host scan result"""
    host: str
    status: str  # up, down, unknown
    ports: List[PortResult]
    os_info: Optional[Dict[str, Any]] = None
    hostnames: List[str] = None
    mac_address: Optional[str] = None
    vendor: Optional[str] = None
    distance: Optional[int] = None
    last_boot: Optional[datetime] = None
    
    def __post_init__(self):
        if self.hostnames is None:
            self.hostnames = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'host': self.host,
            'status': self.status,
            'port_count': len(self.ports),
            'open_ports': [p.port for p in self.ports if p.status == PortStatus.OPEN],
            'os_info': self.os_info,
            'hostnames': self.hostnames,
            'mac_address': self.mac_address,
            'vendor': self.vendor,
            'distance': self.distance,
            'last_boot': self.last_boot.isoformat() if self.last_boot else None,
            'ports': [p.to_dict() for p in self.ports]
        }

class PortScanner:
    """Advanced port scanner with multiple techniques"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # Scanning configuration
        self.timeout = self.config.get('timeout', 2.0)
        self.retries = self.config.get('retries', 1)
        self.delay = self.config.get('delay', 0.0)  # Delay between scans
        self.max_threads = self.config.get('max_threads', 100)
        self.max_hosts = self.config.get('max_hosts', 10)
        
        # Stealth configuration
        self.use_stealth = self.config.get('use_stealth', True)
        self.spoof_ip = self.config.get('spoof_ip')
        self.spoof_mac = self.config.get('spoof_mac')
        self.randomize_order = self.config.get('randomize_order', True)
        self.fragment_packets = self.config.get('fragment_packets', False)
        self.ttl = self.config.get('ttl', 64)
        
        # Service detection
        self.service_detection = self.config.get('service_detection', True)
        self.version_detection = self.config.get('version_detection', False)
        self.banner_grabbing = self.config.get('banner_grabbing', True)
        self.os_detection = self.config.get('os_detection', False)
        
        # Port ranges
        self.top_ports = self.config.get('top_ports', 1000)
        self.common_ports = [
            21, 22, 23, 25, 53, 80, 110, 111, 135, 139, 143, 443, 445,
            993, 995, 1723, 3306, 3389, 5900, 8080, 8443
        ]
        
        # Nmap integration
        self.use_nmap = self.config.get('use_nmap', True)
        self.nmap_path = self.config.get('nmap_path', 'nmap')
        
        # Statistics
        self.stats = {
            'total_scans': 0,
            'hosts_scanned': 0,
            'ports_scanned': 0,
            'open_ports_found': 0,
            'closed_ports_found': 0,
            'filtered_ports_found': 0,
            'scan_duration': 0.0,
            'start_time': datetime.now()
        }
        
        # Results storage
        self.results = {}  # host -> HostResult
        self.results_lock = threading.Lock()
        
        # Thread pool
        self.thread_pool = ThreadPoolExecutor(max_workers=self.max_threads)
        
        # Nmap scanner instance
        self.nm = None
        if self.use_nmap:
            try:
                self.nm = nmap.PortScanner()
            except Exception as e:
                logger.warning(f"Nmap initialization failed: {e}", module="port_scanner")
                self.use_nmap = False
        
        logger.info("Port scanner initialized", module="port_scanner")
    
    def _resolve_hosts(self, targets: Union[str, List[str]]) -> List[str]:
        """Resolve target hosts to IP addresses"""
        resolved_hosts = []
        
        try:
            if isinstance(targets, str):
                targets = [targets]
            
            for target in targets:
                target = target.strip()
                if not target:
                    continue
                
                # Check if it's an IP range/CIDR
                if '/' in target:
                    try:
                        network = ipaddress.ip_network(target, strict=False)
                        for ip in network.hosts():
                            resolved_hosts.append(str(ip))
                        continue
                    except:
                        pass
                
                # Check if it's an IP range with hyphen
                elif '-' in target and '.' in target:
                    try:
                        base, end = target.split('-')
                        
                        # Handle IP range like 192.168.1.1-100
                        if '.' in end:
                            # Full IP range
                            start_ip = ipaddress.ip_address(base)
                            end_ip = ipaddress.ip_address(end)
                            
                            current = int(start_ip)
                            end_int = int(end_ip)
                            
                            while current <= end_int:
                                resolved_hosts.append(str(ipaddress.ip_address(current)))
                                current += 1
                            
                        else:
                            # Partial range like 192.168.1.1-100
                            base_parts = base.split('.')
                            start = int(base_parts[3])
                            end = int(end)
                            
                            for i in range(start, end + 1):
                                ip = f"{base_parts[0]}.{base_parts[1]}.{base_parts[2]}.{i}"
                                resolved_hosts.append(ip)
                        
                        continue
                    except:
                        pass
                
                # Check if it's a single IP
                try:
                    ipaddress.ip_address(target)
                    resolved_hosts.append(target)
                    continue
                except:
                    pass
                
                # Try to resolve hostname
                try:
                    addrinfo = socket.getaddrinfo(target, None)
                    for addr in addrinfo:
                        ip = addr[4][0]
                        if ip not in resolved_hosts:
                            resolved_hosts.append(ip)
                except:
                    logger.warning(f"Could not resolve hostname: {target}", module="port_scanner")
            
            # Remove duplicates and limit
            resolved_hosts = list(dict.fromkeys(resolved_hosts))
            
            if self.max_hosts and len(resolved_hosts)self.max_hosts:
                resolved_hosts = resolved_hosts[:self.max_hosts]
            
            return resolved_hosts
            
        except Exception as e:
            logger.error(f"Host resolution error: {e}", module="port_scanner")
            return []
    
    def _get_ports_to_scan(self, ports: Union[str, List[int], int]) -> List[int]:
        """Parse and validate port list"""
        port_list = []
        
        try:
            if isinstance(ports, int):
                port_list = [ports]
            
            elif isinstance(ports, str):
                if ports.lower() == 'all':
                    port_list = list(range(1, 65536))
                elif ports.lower() == 'top':
                    # Get top N ports
                    port_list = self._get_top_ports(self.top_ports)
                elif ports.lower() == 'common':
                    port_list = self.common_ports
                else:
                    # Parse port ranges like "80,443,1000-2000"
                    for part in ports.split(','):
                        part = part.strip()
                        if '-' in part:
                            start_str, end_str = part.split('-')
                            start = int(start_str.strip())
                            end = int(end_str.strip())
                            port_list.extend(range(start, end + 1))
                        else:
                            port_list.append(int(part))
            
            elif isinstance(ports, list):
                port_list = ports
            
            # Validate ports
            valid_ports = []
            for port in port_list:
                if 1 <= port <= 65535:
                    valid_ports.append(port)
            
            # Randomize order if configured
            if self.randomize_order:
                random.shuffle(valid_ports)
            
            return valid_ports
            
        except Exception as e:
            logger.error(f"Port parsing error: {e}", module="port_scanner")
            return []
    
    def _get_top_ports(self, count: int) -> List[int]:
        """Get top N most common ports"""
        # Common ports based on real-world statistics
        top_ports_all = [
            80, 443, 22, 21, 25, 110, 445, 139, 143, 53, 135, 3306, 8080, 1723, 111,
            995, 993, 5900, 1025, 587, 8888, 199, 1720, 465, 548, 113, 81, 6001, 10000,
            514, 5060, 179, 1026, 2000, 8443, 8000, 32768, 554, 26, 1433, 49152, 2001,
            515, 8008, 49154, 1027, 5666, 646, 5000, 5631, 631, 49153, 8081, 2049, 88,
            79, 5800, 106, 2121, 1110, 49155, 6000, 513, 990, 5357, 427, 49156, 543,
            544, 5101, 144, 7, 389, 8009, 3128, 444, 9999, 5009, 7070, 5190, 3000,
            5432, 1900, 3986, 13, 1029, 9, 5051, 6646, 49157, 1028, 873, 1755, 2717,
            4899, 9100, 119, 37, 1000, 3001, 5001, 82, 10010, 1030, 9090, 2107, 1024,
            2103, 6004, 1801, 5050, 19, 8031, 1041, 255, 2967, 1049, 1048, 1053, 3703,
            17, 808, 3689, 1031, 1044, 1071, 5901, 9102, 100, 8010, 2869, 1039, 5120,
            4001, 9000, 2105, 636, 1038, 2601, 7000, 1, 1065, 1066, 1064, 1056, 1054,
            1058, 1059, 1069, 1434, 1521, 1067, 13782, 5902, 51413, 902, 1100, 9001,
            27017, 1503, 6881, 8021, 512, 123, 1080, 5555, 27015, 4443, 5222, 1998,
            5632, 161, 9200, 9300, 11211, 10001, 27018, 33848, 33899, 3389, 3390, 33890,
            33891, 33892, 33893, 33894, 33895, 33896, 33897, 33898, 33899
        ]
        
        return top_ports_all[:count]
    
    def scan(self,
            targets: Union[str, List[str]],
            ports: Union[str, List[int], int] = 'top',
            scan_type: ScanType = ScanType.TCP_SYN,
            **kwargs) -> Dict[str, HostResult]:
        """Perform port scan"""
        start_time = time.time()
        
        try:
            # Resolve targets
            hosts = self._resolve_hosts(targets)
            
            if not hosts:
                logger.error("No valid hosts to scan", module="port_scanner")
                return {}
            
            # Get ports to scan
            port_list = self._get_ports_to_scan(ports)
            
            if not port_list:
                logger.error("No valid ports to scan", module="port_scanner")
                return {}
            
            logger.info(f"Starting scan of {len(hosts)} hosts, {len(port_list)} ports "
                       f"using {scan_type.value} scan", module="port_scanner")
            
            # Clear previous results
            with self.results_lock:
                self.results.clear()
            
            # Update statistics
            self.stats['total_scans'] += 1
            self.stats['hosts_scanned'] = len(hosts)
            self.stats['ports_scanned'] = len(port_list) * len(hosts)
            
            # Choose scan method
            if scan_type == ScanType.TCP_SYN:
                results = self._tcp_syn_scan(hosts, port_list, **kwargs)
            elif scan_type == ScanType.TCP_CONNECT:
                results = self._tcp_connect_scan(hosts, port_list, **kwargs)
            elif scan_type == ScanType.TCP_ACK:
                results = self._tcp_ack_scan(hosts, port_list, **kwargs)
            elif scan_type == ScanType.UDP:
                results = self._udp_scan(hosts, port_list, **kwargs)
            elif scan_type == ScanType.PING:
                results = self._ping_scan(hosts, **kwargs)
            elif scan_type == ScanType.SERVICE and self.use_nmap:
                results = self._nmap_service_scan(hosts, port_list, **kwargs)
            elif scan_type == ScanType.OS and self.use_nmap:
                results = self._nmap_os_scan(hosts, **kwargs)
            else:
                # Default to TCP connect scan
                results = self._tcp_connect_scan(hosts, port_list, **kwargs)
            
            # Calculate scan duration
            self.stats['scan_duration'] = time.time() - start_time
            
            logger.info(f"Scan completed in {self.stats['scan_duration']:.2f} seconds. "
                       f"Found {self.stats['open_ports_found']} open ports.", 
                       module="port_scanner")
            
            # Log audit event
            audit_log.log_event(
                event_type=AuditEventType.NETWORK_SCAN.value,
                severity=AuditSeverity.INFO.value,
                user='system',
                source_ip='localhost',
                description=f"Port scan completed: {len(hosts)} hosts, {len(port_list)} ports",
                details={
                    'target_count': len(hosts),
                    'port_count': len(port_list),
                    'scan_type': scan_type.value,
                    'duration_seconds': self.stats['scan_duration'],
                    'open_ports_found': self.stats['open_ports_found']
                },
                resource='port_scanner',
                action='scan'
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Scan error: {e}", module="port_scanner")
            return {}
    
    def _tcp_syn_scan(self, hosts: List[str], ports: List[int], **kwargs) -> Dict[str, HostResult]:
        """TCP SYN (half-open) scan"""
        results = {}
        
        try:
            # Create futures for each host:port combination
            futures = []
            
            for host in hosts:
                # Initialize host result
                host_result = HostResult(host=host, status='unknown', ports=[])
                results[host] = host_result
                
                for port in ports:
                    future = self.thread_pool.submit(
                        self._scan_port_syn,
                        host,
                        port,
                        **kwargs
                    )
                    futures.append((future, host, port))
            
            # Process results as they complete
            for future, host, port in futures:
                try:
                    result = future.result(timeout=self.timeout * 2)
                    
                    if result:
                        results[host].ports.append(result)
                        
                        # Update host status if we found an open port
                        if result.status == PortStatus.OPEN and results[host].status == 'unknown':
                            results[host].status = 'up'
                        
                        # Update statistics
                        if result.status == PortStatus.OPEN:
                            self.stats['open_ports_found'] += 1
                        elif result.status == PortStatus.CLOSED:
                            self.stats['closed_ports_found'] += 1
                        elif result.status == PortStatus.FILTERED:
                            self.stats['filtered_ports_found'] += 1
                    
                except Exception as e:
                    logger.debug(f"Port scan failed for {host}:{port}: {e}", module="port_scanner")
            
            # Update host status for hosts with no open ports
            for host in hosts:
                if results[host].status == 'unknown':
                    # Try ICMP ping to check if host is up
                    if self._ping_host(host):
                        results[host].status = 'up'
                    else:
                        results[host].status = 'down'
            
            # Store results
            with self.results_lock:
                for host, result in results.items():
                    self.results[host] = result
            
            return results
            
        except Exception as e:
            logger.error(f"TCP SYN scan error: {e}", module="port_scanner")
            return results
    
    def _scan_port_syn(self, host: str, port: int, **kwargs) -> Optional[PortResult]:
        """Scan single port using SYN technique"""
        try:
            # Create raw socket for SYN scan
            sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_TCP)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
            sock.settimeout(self.timeout)
            
            # Build SYN packet
            src_port = random.randint(1024, 65535)
            
            # TCP header
            tcp_header = struct.pack('!HHIIBBHHH',
                src_port,          # Source port
                port,              # Destination port
                0,                 # Sequence number
                0,                 # Acknowledgement number
                54,            # Data offset (5 * 4 = 20 bytes)
                0x02,              # SYN flag
                8192,              # Window size
                0,                 # Checksum (calculated later)
                0                  # Urgent pointer
            )
            
            # Pseudo header for checksum calculation
            src_ip = socket.inet_aton(self.spoof_ip if self.spoof_ip else socket.gethostbyname(socket.gethostname()))
            dst_ip = socket.inet_aton(host)
            placeholder = 0
            protocol = socket.IPPROTO_TCP
            tcp_length = len(tcp_header)
            
            psh = struct.pack('!4s4sBBH',
                src_ip,
                dst_ip,
                placeholder,
                protocol,
                tcp_length
            )
            psh = psh + tcp_header
            
            # Calculate checksum
            tcp_checksum = self._calculate_checksum(psh)
            
            # Update TCP header with checksum
            tcp_header = struct.pack('!HHIIBBHHH',
                src_port,
                port,
                0,
                0,
                54,
                0x02,
                8192,
                tcp_checksum,
                0
            )
            
            # Send SYN packet
            packet = tcp_header
            sock.sendto(packet, (host, 0))
            
            # Wait for response
            start_time = time.time()
            
            try:
                response = sock.recv(1024)
                response_time = time.time() - start_time
                
                # Parse response
                if len(response) >= 20:
                    # Get TCP flags from response
                    tcp_flags = response[13]  # Byte 13 contains flags
                    
                    if tcp_flags & 0x12:  # SYN-ACK (0x12 = SYN + ACK)
                        # Port is open
                        
                        # Send RST to close connection
                        rst_packet = struct.pack('!HHIIBBHHH',
                            src_port,
                            port,
                            1,  # Sequence number
                            0,
                            54,
                            0x04,  # RST flag
                            0,
                            0,
                            0
                        )
                        sock.sendto(rst_packet, (host, 0))
                        
                        # Try banner grabbing if enabled
                        banner = None
                        if self.banner_grabbing:
                            banner = self._grab_banner(host, port)
                        
                        return PortResult(
                            host=host,
                            port=port,
                            protocol='tcp',
                            status=PortStatus.OPEN,
                            response_time=response_time,
                            banner=banner,
                            timestamp=datetime.now()
                        )
                    
                    elif tcp_flags & 0x14:  # RST-ACK (0x14 = RST + ACK)
                        # Port is closed
                        return PortResult(
                            host=host,
                            port=port,
                            protocol='tcp',
                            status=PortStatus.CLOSED,
                            response_time=response_time,
                            timestamp=datetime.now()
                        )
                
            except socket.timeout:
                # No response - port might be filtered
                return PortResult(
                    host=host,
                    port=port,
                    protocol='tcp',
                    status=PortStatus.FILTERED,
                    timestamp=datetime.now()
                )
            
            finally:
                sock.close()
            
            return None
            
        except Exception as e:
            logger.debug(f"SYN scan error for {host}:{port}: {e}", module="port_scanner")
            return None
    
    def _tcp_connect_scan(self, hosts: List[str], ports: List[int], **kwargs) -> Dict[str, HostResult]:
        """TCP connect scan (full connection)"""
        results = {}
        
        try:
            for host in hosts:
                host_result = HostResult(host=host, status='unknown', ports=[])
                results[host] = host_result
                
                # Check if host is up first
                if not self._ping_host(host):
                    host_result.status = 'down'
                    continue
                
                host_result.status = 'up'
                
                # Scan ports for this host
                for port in ports:
                    try:
                        start_time = time.time()
                        
                        # Create socket
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(self.timeout)
                        
                        # Attempt connection
                        result = sock.connect_ex((host, port))
                        response_time = time.time() - start_time
                        
                        if result == 0:
                            # Connection successful - port is open
                            
                            # Try banner grabbing
                            banner = None
                            if self.banner_grabbing:
                                try:
                                    sock.settimeout(2.0)
                                    banner = sock.recv(1024).decode('utf-8', errors='ignore').strip()
                                except:
                                    pass
                            
                            port_result = PortResult(
                                host=host,
                                port=port,
                                protocol='tcp',
                                status=PortStatus.OPEN,
                                response_time=response_time,
                                banner=banner,
                                timestamp=datetime.now()
                            )
                            
                            self.stats['open_ports_found'] += 1
                            
                        else:
                            # Connection failed
                            port_result = PortResult(
                                host=host,
                                port=port,
                                protocol='tcp',
                                status=PortStatus.CLOSED,
                                response_time=response_time,
                                timestamp=datetime.now()
                            )
                            
                            self.stats['closed_ports_found'] += 1
                        
                        host_result.ports.append(port_result)
                        sock.close()
                        
                        # Delay between scans
                        if self.delay > 0:
                            time.sleep(self.delay)
                        
                    except Exception as e:
                        logger.debug(f"Connect scan error for {host}:{port}: {e}", module="port_scanner")
                        continue
            
            # Store results
            with self.results_lock:
                for host, result in results.items():
                    self.results[host] = result
            
            return results
            
        except Exception as e:
            logger.error(f"TCP connect scan error: {e}", module="port_scanner")
            return results
    
    def _tcp_ack_scan(self, hosts: List[str], ports: List[int], **kwargs) -> Dict[str, HostResult]:
        """TCP ACK scan (firewall detection)"""
        results = {}
        
        try:
            # Use scapy for ACK scans
            for host in hosts:
                host_result = HostResult(host=host, status='unknown', ports=[])
                results[host] = host_result
                
                for port in ports:
                    try:
                        # Create ACK packet
                        ack_packet = IP(dst=host)/TCP(dport=port, flags='A')
                        
                        # Send and receive
                        response = sr1(ack_packet, timeout=self.timeout, verbose=0)
                        
                        if response:
                            tcp_layer = response.getlayer(TCP)
                            
                            if tcp_layer:
                                flags = tcp_layer.flags
                                
                                if flags & 0x04:  # RST flag
                                    # Port is unfiltered
                                    port_result = PortResult(
                                        host=host,
                                        port=port,
                                        protocol='tcp',
                                        status=PortStatus.UNFILTERED,
                                        timestamp=datetime.now()
                                    )
                                else:
                                    # Port is filtered
                                    port_result = PortResult(
                                        host=host,
                                        port=port,
                                        protocol='tcp',
                                        status=PortStatus.FILTERED,
                                        timestamp=datetime.now()
                                    )
                                    
                                    self.stats['filtered_ports_found'] += 1
                                
                                host_result.ports.append(port_result)
                        
                    except Exception as e:
                        logger.debug(f"ACK scan error for {host}:{port}: {e}", module="port_scanner")
                        continue
            
            # Store results
            with self.results_lock:
                for host, result in results.items():
                    self.results[host] = result
            
            return results
            
        except Exception as e:
            logger.error(f"TCP ACK scan error: {e}", module="port_scanner")
            return results
    
    def _udp_scan(self, hosts: List[str], ports: List[int], **kwargs) -> Dict[str, HostResult]:
        """UDP port scan"""
        results = {}
        
        try:
            for host in hosts:
                host_result = HostResult(host=host, status='unknown', ports=[])
                results[host] = host_result
                
                # Check if host is up
                if not self._ping_host(host):
                    host_result.status = 'down'
                    continue
                
                host_result.status = 'up'
                
                for port in ports:
                    try:
                        # Create UDP socket
                        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        sock.settimeout(self.timeout)
                        
                        # Send empty UDP packet
                        sock.sendto(b'', (host, port))
                        
                        start_time = time.time()
                        
                        try:
                            # Try to receive response
                            data, addr = sock.recvfrom(1024)
                            response_time = time.time() - start_time
                            
                            # Got response - port might be open
                            port_result = PortResult(
                                host=host,
                                port=port,
                                protocol='udp',
                                status=PortStatus.OPEN,
                                response_time=response_time,
                                timestamp=datetime.now()
                            )
                            
                            self.stats['open_ports_found'] += 1
                            
                        except socket.timeout:
                            # No response - port might be open or filtered
                            port_result = PortResult(
                                host=host,
                                port=port,
                                protocol='udp',
                                status=PortStatus.OPEN_FILTERED,
                                timestamp=datetime.now()
                            )
                            
                            self.stats['filtered_ports_found'] += 1
                        
                        except ConnectionResetError:
                            # ICMP port unreachable - port is closed
                            port_result = PortResult(
                                host=host,
                                port=port,
                                protocol='udp',
                                status=PortStatus.CLOSED,
                                timestamp=datetime.now()
                            )
                            
                            self.stats['closed_ports_found'] += 1
                        
                        host_result.ports.append(port_result)
                        sock.close()
                        
                        # Delay
                        if self.delay > 0:
                            time.sleep(self.delay)
                        
                    except Exception as e:
                        logger.debug(f"UDP scan error for {host}:{port}: {e}", module="port_scanner")
                        continue
            
            # Store results
            with self.results_lock:
                for host, result in results.items():
                    self.results[host] = result
            
            return results
            
        except Exception as e:
            logger.error(f"UDP scan error: {e}", module="port_scanner")
            return results
    
    def _ping_scan(self, hosts: List[str], **kwargs) -> Dict[str, HostResult]:
        """Ping scan (host discovery)"""
        results = {}
        
        try:
            futures = []
            
            for host in hosts:
                future = self.thread_pool.submit(self._ping_host_with_info, host)
                futures.append((future, host))
            
            for future, host in futures:
                try:
                    host_info = future.result(timeout=self.timeout * 2)
                    
                    if host_info['alive']:
                        host_result = HostResult(
                            host=host,
                            status='up',
                            ports=[],
                            mac_address=host_info.get('mac'),
                            vendor=host_info.get('vendor'),
                            distance=host_info.get('ttl')
                        )
                    else:
                        host_result = HostResult(
                            host=host,
                            status='down',
                            ports=[]
                        )
                    
                    results[host] = host_result
                    
                except Exception as e:
                    logger.debug(f"Ping scan error for {host}: {e}", module="port_scanner")
                    results[host] = HostResult(host=host, status='unknown', ports=[])
            
            # Store results
            with self.results_lock:
                for host, result in results.items():
                    self.results[host] = result
            
            return results
            
        except Exception as e:
            logger.error(f"Ping scan error: {e}", module="port_scanner")
            return results
    
    def _ping_host(self, host: str) -> bool:
        """Ping a host to check if it's alive"""
        try:
            # Try ICMP ping
            if os.name == 'nt':  # Windows
                param = '-n'
            else:  # Linux/Mac
                param = '-c'
            
            command = ['ping', param, '1', '-W', '1', host]
            
            result = subprocess.run(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2
            )
            
            return result.returncode == 0
            
        except:
            # Fallback to TCP ping on port 80
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex((host, 80))
                sock.close()
                return result == 0
            except:
                return False
    
    def _ping_host_with_info(self, host: str) -> Dict[str, Any]:
        """Ping host with additional information"""
        result = {
            'alive': False,
            'mac': None,
            'vendor': None,
            'ttl': None
        }
        
        try:
            # Use scapy for detailed ping
            packet = IP(dst=host)/ICMP()
            response = sr1(packet, timeout=self.timeout, verbose=0)
            
            if response:
                result['alive'] = True
                result['ttl'] = response.ttl
                
                # Try to get MAC address (ARP)
                arp_packet = scapy.ARP(pdst=host)
                arp_response = scapy.srp(arp_packet, timeout=1, verbose=0)[0]
                
                if arp_response:
                    result['mac'] = arp_response[0][1].hwsrc
                    
                    # Try to get vendor from MAC
                    try:
                        import requests
                        mac_url = f"https://api.macvendors.com/{result['mac'].replace(':', '')}"
                        vendor_response = requests.get(mac_url, timeout=2)
                        if vendor_response.status_code == 200:
                            result['vendor'] = vendor_response.text
                    except:
                        pass
        
        except Exception as e:
            logger.debug(f"Detailed ping error for {host}: {e}", module="port_scanner")
        
        return result
    
    def _nmap_service_scan(self, hosts: List[str], ports: List[int], **kwargs) -> Dict[str, HostResult]:
        """Service detection scan using Nmap"""
        results = {}
        
        try:
            if not self.nm:
                logger.error("Nmap not available", module="port_scanner")
                return results
            
            # Convert port list to string
            port_str = ','.join(str(p) for p in ports)
            
            # Perform Nmap scan
            scan_args = f'-sV --version-intensity 5 -p {port_str}'
            
            if self.service_detection:
                scan_args += ' -sV'
            
            if self.version_detection:
                scan_args += ' --version-all'
            
            if self.os_detection:
                scan_args += ' -O'
            
            logger.info(f"Running Nmap scan with args: {scan_args}", module="port_scanner")
            
            for host in hosts:
                try:
                    self.nm.scan(hosts=host, arguments=scan_args)
                    
                    host_result = HostResult(host=host, status='unknown', ports=[])
                    
                    if host in self.nm.all_hosts():
                        nmap_host = self.nm[host]
                        
                        # Set host status
                        if nmap_host.state() == 'up':
                            host_result.status = 'up'
                        else:
                            host_result.status = 'down'
                        
                        # Get OS information
                        if 'osmatch' in nmap_host:
                            os_matches = nmap_host['osmatch']
                            if os_matches:
                                host_result.os_info = {
                                    'name': os_matches[0]['name'],
                                    'accuracy': os_matches[0]['accuracy'],
                                    'osclass': os_matches[0]['osclass']
                                }
                        
                        # Get hostnames
                        if 'hostnames' in nmap_host:
                            host_result.hostnames = [h['name'] for h in nmap_host['hostnames']]
                        
                        # Process ports
                        for proto in nmap_host.all_protocols():
                            ports_info = nmap_host[proto]
                            
                            for port, port_info in ports_info.items():
                                status = PortStatus.CLOSED
                                
                                if port_info['state'] == 'open':
                                    status = PortStatus.OPEN
                                    self.stats['open_ports_found'] += 1
                                elif port_info['state'] == 'closed':
                                    status = PortStatus.CLOSED
                                    self.stats['closed_ports_found'] += 1
                                elif port_info['state'] == 'filtered':
                                    status = PortStatus.FILTERED
                                    self.stats['filtered_ports_found'] += 1
                                
                                port_result = PortResult(
                                    host=host,
                                    port=port,
                                    protocol=proto,
                                    status=status,
                                    service=port_info.get('name'),
                                    version=port_info.get('version'),
                                    product=port_info.get('product'),
                                    extrainfo=port_info.get('extrainfo'),
                                    timestamp=datetime.now()
                                )
                                
                                host_result.ports.append(port_result)
                    
                    results[host] = host_result
                    
                except Exception as e:
                    logger.error(f"Nmap scan error for {host}: {e}", module="port_scanner")
                    results[host] = HostResult(host=host, status='error', ports=[])
            
            # Store results
            with self.results_lock:
                for host, result in results.items():
                    self.results[host] = result
            
            return results
            
        except Exception as e:
            logger.error(f"Nmap service scan error: {e}", module="port_scanner")
            return results
    
    def _nmap_os_scan(self, hosts: List[str], **kwargs) -> Dict[str, HostResult]:
        """OS detection scan using Nmap"""
        results = {}
        
        try:
            if not self.nm:
                logger.error("Nmap not available", module="port_scanner")
                return results
            
            for host in hosts:
                try:
                    self.nm.scan(hosts=host, arguments='-O')
                    
                    host_result = HostResult(host=host, status='unknown', ports=[])
                    
                    if host in self.nm.all_hosts():
                        nmap_host = self.nm[host]
                        
                        # Set host status
                        host_result.status = nmap_host.state()
                        
                        # Get OS information
                        if 'osmatch' in nmap_host:
                            os_matches = nmap_host['osmatch']
                            if os_matches:
                                host_result.os_info = {
                                    'matches': os_matches,
                                    'best_guess': os_matches[0] if os_matches else None
                                }
                    
                    results[host] = host_result
                    
                except Exception as e:
                    logger.error(f"Nmap OS scan error for {host}: {e}", module="port_scanner")
                    results[host] = HostResult(host=host, status='error', ports=[])
            
            # Store results
            with self.results_lock:
                for host, result in results.items():
                    self.results[host] = result
            
            return results
            
        except Exception as e:
            logger.error(f"Nmap OS scan error: {e}", module="port_scanner")
            return results
    
    def _grab_banner(self, host: str, port: int) -> Optional[str]:
        """Grab banner from open port"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            sock.connect((host, port))
            
            # Send generic probe based on port
            if port == 80 or port == 443 or port == 8080:
                sock.send(b'GET / HTTP/1.0\r\n\r\n')
            elif port == 21:
                sock.send(b'\r\n')
            elif port == 22:
                sock.send(b'SSH-2.0-Client\r\n')
            elif port == 25 or port == 587:
                sock.send(b'EHLO example.com\r\n')
            elif port == 110:
                sock.send(b'USER test\r\n')
            elif port == 143:
                sock.send(b'a001 LOGIN test test\r\n')
            
            # Receive banner
            banner = sock.recv(1024).decode('utf-8', errors='ignore').strip()
            sock.close()
            
            return banner if banner else None
            
        except:
            return None
    
    def _calculate_checksum(self, data: bytes) -> int:
        """Calculate TCP/IP checksum"""
        if len(data) % 2:
            data += b'\x00'
        
        total = 0
        for i in range(0, len(data), 2):
            total += (data[i 8) + data[i + 1]
        
        while total > 0xffff:
            total = (total & 0xffff) + (total >> 16)
        
        return ~total & 0xffff
    
    def get_results(self) -> Dict[str, HostResult]:
        """Get scan results"""
        with self.results_lock:
            return self.results.copy()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get scanner statistics"""
        uptime = (datetime.now() - self.stats['start_time']).total_seconds()
        
        open_rate = (self.stats['open_ports_found'] / self.stats['ports_scanned'] * 100 
                    if self.stats['ports_scanned'] > 0 else 0)
        
        return {
            **self.stats,
            'uptime_seconds': uptime,
            'uptime_human': str(timedelta(seconds=int(uptime))),
            'open_port_rate': open_rate,
            'scan_speed_ports_per_second': (self.stats['ports_scanned'] / self.stats['scan_duration'] 
                                          if self.stats['scan_duration'] > 0 else 0),
            'current_threads': self.thread_pool._max_workers,
            'use_stealth': self.use_stealth,
            'service_detection': self.service_detection,
            'banner_grabbing': self.banner_grabbing,
            'os_detection': self.os_detection,
            'use_nmap': self.use_nmap
        }
    
    def export_results(self, format: str = 'json', filepath: Optional[str] = None) -> Optional[str]:
        """Export scan results"""
        try:
            results = self.get_results()
            
            if format.lower() == 'json':
                data = {
                    'scan_results': {host: result.to_dict() for host, result in results.items()},
                    'statistics': self.get_statistics(),
                    'timestamp': datetime.now().isoformat()
                }
                
                output = json.dumps(data, indent=2, default=str)
            
            elif format.lower() == 'csv':
                import csv
                import io
                
                output_io = io.StringIO()
                writer = csv.writer(output_io)
                
                # Write header
                writer.writerow(['Host', 'Port', 'Protocol', 'Status', 'Service', 'Version', 'Banner', 'Response Time'])
                
                # Write data
                for host, host_result in results.items():
                    for port_result in host_result.ports:
                        writer.writerow([
                            host,
                            port_result.port,
                            port_result.protocol,
                            port_result.status.value,
                            port_result.service or '',
                            port_result.version or '',
                            port_result.banner or '',
                            port_result.response_time or ''
                        ])
                
                output = output_io.getvalue()
            
            elif format.lower() == 'text':
                output_lines = []
                
                for host, host_result in results.items():
                    output_lines.append(f"Host: {host} ({host_result.status})")
                    
                    if host_result.os_info:
                        output_lines.append(f"  OS: {host_result.os_info}")
                    
                    if host_result.hostnames:
                        output_lines.append(f"  Hostnames: {', '.join(host_result.hostnames)}")
                    
                    if host_result.ports:
                        output_lines.append("  Open ports:")
                        for port_result in host_result.ports:
                            if port_result.status == PortStatus.OPEN:
                                service_info = f" - {port_result.service}" if port_result.service else ""
                                version_info = f" {port_result.version}" if port_result.version else ""
                                output_lines.append(f"    {port_result.port}/{port_result.protocol}{service_info}{version_info}")
                    
                    output_lines.append("")
                
                output = '\n'.join(output_lines)
            
            else:
                logger.error(f"Unsupported export format: {format}", module="port_scanner")
                return None
            
            # Write to file if specified
            if filepath:
                with open(filepath, 'w') as f:
                    f.write(output)
                logger.info(f"Results exported to {filepath}", module="port_scanner")
            
            return output
            
        except Exception as e:
            logger.error(f"Export error: {e}", module="port_scanner")
            return None
    
    def stop(self):
        """Stop scanner and cleanup"""
        try:
            self.thread_pool.shutdown(wait=True)
            logger.info("Port scanner stopped", module="port_scanner")
        except Exception as e:
            logger.error(f"Stop error: {e}", module="port_scanner")

# Global instance
_port_scanner = None

def get_port_scanner(config: Dict = None) -> PortScanner:
    """Get or create port scanner instance"""
    global _port_scanner
    
    if _port_scanner is None:
        _port_scanner = PortScanner(config)
    
    return _port_scanner

if __name__ == "__main__":
    print("Testing Port Scanner...")
    
    # Test configuration
    config = {
        'timeout': 1.0,
        'max_threads': 50,
        'delay': 0.01,
        'use_stealth': True,
        'banner_grabbing': True,
        'service_detection': True,
        'use_nmap': False  # Disable Nmap for basic test
    }
    
    scanner = get_port_scanner(config)
    
    print("\n1. Testing ping scan...")
    ping_results = scanner.scan(
        targets=['127.0.0.1', 'google.com', '8.8.8.8'],
        scan_type=ScanType.PING
    )
    
    print("Ping results:")
    for host, result in ping_results.items():
        print(f"  {host}: {result.status}")
    
    print("\n2. Testing TCP connect scan (localhost only)...")
    tcp_results = scanner.scan(
        targets=['127.0.0.1'],
        ports=[80, 443, 22, 8080, 3306],
        scan_type=ScanType.TCP_CONNECT
    )
    
    print("TCP scan results for localhost:")
    for host, result in tcp_results.items():
        print(f"  Host: {host} ({result.status})")
        for port_result in result.ports:
            status_symbol = '✅' if port_result.status == PortStatus.OPEN else '❌'
            print(f"    {status_symbol} Port {port_result.port}: {port_result.status.value}")
    
    print("\n3. Getting statistics...")
    stats = scanner.get_statistics()
    
    print(f"📊 Port Scanner Statistics:")
    print(f"  Total scans: {stats['total_scans']}")
    print(f"  Hosts scanned: {stats['hosts_scanned']}")
    print(f"  Ports scanned: {stats['ports_scanned']}")
    print(f"  Open ports found: {stats['open_ports_found']}")
    print(f"  Scan duration: {stats['scan_duration']:.2f}s")
    print(f"  Scan speed: {stats['scan_speed_ports_per_second']:.1f} ports/sec")
    
    print("\n4. Exporting results to JSON...")
    json_output = scanner.export_results('json')
    if json_output:
        print(f"Exported {len(json_output)} characters of JSON data")
    
    print("\n5. Testing export to text...")
    text_output = scanner.export_results('text')
    if text_output:
        print(text_output[:500] + "..." if len(text_output)500 else text_output)
    
    # Stop scanner
    scanner.stop()
    
    print("\n✅ Port Scanner tests completed!")
