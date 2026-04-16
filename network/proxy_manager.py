#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
proxy_manager.py - Advanced Proxy Management and Rotation System
"""

import os
import sys
import json
import time
import random
import threading
import concurrent.futures
from typing import Dict, List, Optional, Tuple, Any, Union, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass
from collections import defaultdict, deque
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import socket
import socks
import aiohttp
import asyncio
import re

# Import utilities
from ..utils.logger import get_logger
from ..security.audit_log import get_audit_log_manager, AuditEventType, AuditSeverity

logger = get_logger()
audit_log = get_audit_log_manager()

class ProxyType(Enum):
    """Proxy types"""
    HTTP = "http"
    HTTPS = "https"
    SOCKS4 = "socks4"
    SOCKS5 = "socks5"
    TRANSPARENT = "transparent"
    ELITE = "elite"
    ANONYMOUS = "anonymous"

class ProxyStatus(Enum):
    """Proxy status"""
    ACTIVE = "active"
    TESTING = "testing"
    DEAD = "dead"
    BANNED = "banned"
    SLOW = "slow"
    UNSTABLE = "unstable"

@dataclass
class Proxy:
    """Proxy representation"""
    host: str
    port: int
    proxy_type: ProxyType
    username: Optional[str] = None
    password: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    latency: float = 0.0
    success_rate: float = 0.0
    last_used: Optional[datetime] = None
    last_tested: Optional[datetime] = None
    status: ProxyStatus = ProxyStatus.TESTING
    tags: List[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.metadata is None:
            self.metadata = {}
    
    @property
    def address(self) -> str:
        """Get proxy address"""
        return f"{self.host}:{self.port}"
    
    @property
    def full_url(self) -> str:
        """Get full proxy URL"""
        if self.username and self.password:
            return f"{self.proxy_type.value}://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"{self.proxy_type.value}://{self.host}:{self.port}"
    
    @property
    def dict_format(self) -> Dict[str, str]:
        """Get proxy in dict format for requests"""
        if self.proxy_type == ProxyType.SOCKS4:
            return {'http': f'socks4://{self.address}', 'https': f'socks4://{self.address}'}
        elif self.proxy_type == ProxyType.SOCKS5:
            return {'http': f'socks5://{self.address}', 'https': f'socks5://{self.address}'}
        else:
            return {'http': self.full_url, 'https': self.full_url}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'host': self.host,
            'port': self.port,
            'proxy_type': self.proxy_type.value,
            'username': self.username,
            'password': self.password,
            'country': self.country,
            'city': self.city,
            'latency': self.latency,
            'success_rate': self.success_rate,
            'last_used': self.last_used.isoformat() if self.last_used else None,
            'last_tested': self.last_tested.isoformat() if self.last_tested else None,
            'status': self.status.value,
            'tags': self.tags,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Proxy':
        """Create from dictionary"""
        return cls(
            host=data['host'],
            port=data['port'],
            proxy_type=ProxyType(data['proxy_type']),
            username=data.get('username'),
            password=data.get('password'),
            country=data.get('country'),
            city=data.get('city'),
            latency=data.get('latency', 0.0),
            success_rate=data.get('success_rate', 0.0),
            last_used=datetime.fromisoformat(data['last_used']) if data.get('last_used') else None,
            last_tested=datetime.fromisoformat(data['last_tested']) if data.get('last_tested') else None,
            status=ProxyStatus(data.get('status', 'testing')),
            tags=data.get('tags', []),
            metadata=data.get('metadata', {})
        )

class ProxyManager:
    """Advanced proxy management and rotation system"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # Proxy storage
        self.proxies = []  # List of Proxy objects
        self.proxy_lock = threading.Lock()
        
        # Proxy pools by type/status
        self.proxy_pools = defaultdict(list)
        self._build_pools()
        
        # Rotation settings
        self.rotation_mode = self.config.get('rotation_mode', 'round_robin')  # round_robin, random, smart
        self.max_retries = self.config.get('max_retries', 3)
        self.timeout = self.config.get('timeout', 10.0)
        
        # Testing configuration
        self.test_urls = self.config.get('test_urls', [
            'http://httpbin.org/ip',
            'http://httpbin.org/user-agent',
            'https://api.ipify.org?format=json'
        ])
        self.test_interval = self.config.get('test_interval', 300)  # 5 minutes
        self.min_success_rate = self.config.get('min_success_rate', 0.7)
        self.max_latency = self.config.get('max_latency', 5.0)
        
        # Statistics
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_proxies': 0,
            'active_proxies': 0,
            'dead_proxies': 0,
            'total_data_transferred': 0,
            'start_time': datetime.now()
        }
        
        # Session management
        self.sessions = {}
        self.session_timeout = self.config.get('session_timeout', 600)
        
        # Thread pool for testing
        self.thread_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get('max_test_workers', 10)
        )
        
        # Start maintenance thread
        self.running = True
        self.maintenance_thread = threading.Thread(target=self._maintenance_loop, daemon=True)
        self.maintenance_thread.start()
        
        # Load initial proxies
        self._load_initial_proxies()
        
        logger.info("Proxy manager initialized", module="proxy_manager")
    
    def _load_initial_proxies(self):
        """Load initial proxies from config or files"""
        try:
            # Load from config
            config_proxies = self.config.get('proxies', [])
            
            for proxy_data in config_proxies:
                try:
                    proxy = Proxy(
                        host=proxy_data['host'],
                        port=proxy_data['port'],
                        proxy_type=ProxyType(proxy_data.get('type', 'http')),
                        username=proxy_data.get('username'),
                        password=proxy_data.get('password'),
                        country=proxy_data.get('country'),
                        city=proxy_data.get('city')
                    )
                    self.add_proxy(proxy)
                except Exception as e:
                    logger.error(f"Error loading proxy from config: {e}", module="proxy_manager")
            
            # Load from file if specified
            proxy_file = self.config.get('proxy_file')
            if proxy_file and os.path.exists(proxy_file):
                self.load_from_file(proxy_file)
            
            # Test initial proxies
            if self.proxies:
                self.test_all_proxies_async()
            
        except Exception as e:
            logger.error(f"Initial proxy load error: {e}", module="proxy_manager")
    
    def _build_pools(self):
        """Build proxy pools"""
        with self.proxy_lock:
            self.proxy_pools.clear()
            
            for proxy in self.proxies:
                # Pool by type
                self.proxy_pools[f"type_{proxy.proxy_type.value}"].append(proxy)
                
                # Pool by status
                self.proxy_pools[f"status_{proxy.status.value}"].append(proxy)
                
                # Pool by country
                if proxy.country:
                    self.proxy_pools[f"country_{proxy.country.lower()}"].append(proxy)
                
                # Pool by tags
                for tag in proxy.tags:
                    self.proxy_pools[f"tag_{tag}"].append(proxy)
    
    def add_proxy(self, proxy: Proxy) -> bool:
        """Add proxy to manager"""
        try:
            with self.proxy_lock:
                # Check if proxy already exists
                for existing in self.proxies:
                    if existing.host == proxy.host and existing.port == proxy.port:
                        # Update existing proxy
                        existing.proxy_type = proxy.proxy_type
                        existing.username = proxy.username
                        existing.password = proxy.password
                        existing.country = proxy.country
                        existing.city = proxy.city
                        existing.tags = proxy.tags
                        existing.metadata = proxy.metadata
                        logger.debug(f"Updated existing proxy: {proxy.address}", module="proxy_manager")
                        return True
                
                # Add new proxy
                self.proxies.append(proxy)
                self.stats['total_proxies'] = len(self.proxies)
                
                # Rebuild pools
                self._build_pools()
                
                logger.info(f"Added proxy: {proxy.address} ({proxy.proxy_type.value})", module="proxy_manager")
                
                # Log audit event
                audit_log.log_event(
                    event_type=AuditEventType.SYSTEM_CHANGE.value,
                    severity=AuditSeverity.INFO.value,
                    user='system',
                    source_ip='localhost',
                    description=f"Proxy added: {proxy.address}",
                    details={
                        'proxy': proxy.address,
                        'type': proxy.proxy_type.value,
                        'country': proxy.country,
                        'tags': proxy.tags
                    },
                    resource='proxy_manager',
                    action='add_proxy'
                )
                
                return True
                
        except Exception as e:
            logger.error(f"Add proxy error: {e}", module="proxy_manager")
            return False
    
    def remove_proxy(self, host: str, port: int) -> bool:
        """Remove proxy from manager"""
        try:
            with self.proxy_lock:
                for i, proxy in enumerate(self.proxies):
                    if proxy.host == host and proxy.port == port:
                        removed = self.proxies.pop(i)
                        self.stats['total_proxies'] = len(self.proxies)
                        
                        # Update dead proxy count
                        if removed.status == ProxyStatus.DEAD:
                            self.stats['dead_proxies'] = max(0, self.stats['dead_proxies'] - 1)
                        
                        # Rebuild pools
                        self._build_pools()
                        
                        logger.info(f"Removed proxy: {removed.address}", module="proxy_manager")
                        return True
                
                return False
                
        except Exception as e:
            logger.error(f"Remove proxy error: {e}", module="proxy_manager")
            return False
    
    def get_proxy(self, 
                 proxy_type: Optional[ProxyType] = None,
                 country: Optional[str] = None,
                 tags: Optional[List[str]] = None,
                 min_success_rate: float = 0.0,
                 max_latency: float = float('inf'),
                 strategy: str = "smart") -> Optional[Proxy]:
        """Get a proxy based on criteria and strategy"""
        try:
            with self.proxy_lock:
                # Filter proxies
                candidates = []
                
                for proxy in self.proxies:
                    # Skip dead/banned proxies
                    if proxy.status in [ProxyStatus.DEAD, ProxyStatus.BANNED]:
                        continue
                    
                    # Filter by type
                    if proxy_type and proxy.proxy_type != proxy_type:
                        continue
                    
                    # Filter by country
                    if country and proxy.country != country:
                        continue
                    
                    # Filter by tags
                    if tags and not all(tag in proxy.tags for tag in tags):
                        continue
                    
                    # Filter by success rate
                    if proxy.success_ratemin_success_rate:
                        continue
                    
                    # Filter by latency
                    if proxy.latencymax_latency:
                        continue
                    
                    candidates.append(proxy)
                
                if not candidates:
                    logger.warning("No proxies match criteria", module="proxy_manager")
                    return None
                
                # Apply strategy
                if strategy == "round_robin":
                    # Sort by last used
                    candidates.sort(key=lambda p: p.last_used or datetime.min)
                    selected = candidates[0]
                    
                elif strategy == "random":
                    selected = random.choice(candidates)
                    
                elif strategy == "smart":
                    # Weighted selection based on success rate and latency
                    weights = []
                    for proxy in candidates:
                        # Base weight on success rate (70%) and latency (30%)
                        success_weight = proxy.success_rate * 0.7
                        latency_weight = (1.0 / (proxy.latency + 0.1)) * 0.3  # Avoid division by zero
                        weight = success_weight + latency_weight
                        weights.append(weight)
                    
                    # Normalize weights
                    total_weight = sum(weights)
                    if total_weight > 0:
                        weights = [w / total_weight for w in weights]
                        selected = random.choices(candidates, weights=weights, k=1)[0]
                    else:
                        selected = random.choice(candidates)
                    
                elif strategy == "fastest":
                    # Select fastest proxy
                    selected = min(candidates, key=lambda p: p.latency)
                    
                elif strategy == "most_reliable":
                    # Select most reliable proxy
                    selected = max(candidates, key=lambda p: p.success_rate)
                    
                else:
                    selected = candidates[0]
                
                # Update last used
                selected.last_used = datetime.now()
                
                logger.debug(f"Selected proxy: {selected.address} (strategy: {strategy})", 
                           module="proxy_manager")
                
                return selected
                
        except Exception as e:
            logger.error(f"Get proxy error: {e}", module="proxy_manager")
            return None
    
    def get_proxy_for_request(self, 
                             url: str,
                             proxy_type: Optional[ProxyType] = None,
                             **kwargs) -> Optional[Proxy]:
        """Get proxy optimized for specific request"""
        try:
            # Analyze URL to determine optimal proxy
            url_lower = url.lower()
            
            # Default strategy
            strategy = "smart"
            
            # Adjust strategy based on URL
            if 'api.' in url_lower or 'json' in url_lower:
                # API endpoints need reliable proxies
                strategy = "most_reliable"
            elif 'download' in url_lower or 'large' in url_lower:
                # Large downloads need fast proxies
                strategy = "fastest"
            elif 'scrape' in url_lower or 'crawl' in url_lower:
                # Scraping needs rotating proxies
                strategy = "round_robin"
            
            # Get proxy
            proxy = self.get_proxy(
                proxy_type=proxy_type,
                strategy=strategy,
                **kwargs
            )
            
            return proxy
            
        except Exception as e:
            logger.error(f"Get proxy for request error: {e}", module="proxy_manager")
            return None
    
    def make_request(self, 
                    url: str,
                    method: str = 'GET',
                    proxy: Optional[Proxy] = None,
                    proxy_type: Optional[ProxyType] = None,
                    retry_on_failure: bool = True,
                    max_retries: Optional[int] = None,
                    **kwargs) -> Optional[requests.Response]:
        """Make HTTP request through proxy"""
        try:
            if max_retries is None:
                max_retries = self.max_retries
            
            # Get proxy if not provided
            if not proxy:
                proxy = self.get_proxy_for_request(url, proxy_type)
            
            if not proxy:
                logger.error("No proxy available for request", module="proxy_manager")
                return None
            
            # Prepare session
            session = self._get_session(proxy)
            
            # Update statistics
            self.stats['total_requests'] += 1
            
            # Make request with retries
            for attempt in range(max_retries + 1):
                try:
                    start_time = time.time()
                    
                    response = session.request(
                        method=method,
                        url=url,
                        timeout=self.timeout,
                        **kwargs
                    )
                    
                    latency = time.time() - start_time
                    
                    # Update proxy stats
                    proxy.latency = (proxy.latency + latency) / 2  # Moving average
                    
                    if response.status_code200:
                        # Successful request
                        self.stats['successful_requests'] += 1
                        proxy.success_rate = min(1.0, proxy.success_rate + 0.05)  # Increase success rate
                        proxy.status = ProxyStatus.ACTIVE
                        
                        # Update data transfer stats
                        content_length = response.headers.get('Content-Length')
                        if content_length:
                            try:
                                self.stats['total_data_transferred'] += int(content_length)
                            except:
                                pass
                        
                        logger.debug(f"Request successful through {proxy.address}: {response.status_code}", 
                                   module="proxy_manager")
                        
                        return response
                    else:
                        # Failed request
                        self.stats['failed_requests'] += 1
                        proxy.success_rate = max(0.0, proxy.success_rate - 0.1)  # Decrease success rate
                        
                        if response.status_code in [403, 429, 503]:
                            # Proxy might be banned
                            proxy.status = ProxyStatus.BANNED
                            logger.warning(f"Proxy {proxy.address} might be banned: {response.status_code}", 
                                         module="proxy_manager")
                        
                        logger.debug(f"Request failed through {proxy.address}: {response.status_code}", 
                                   module="proxy_manager")
                        
                        if not retry_on_failure:
                            break
                        
                except (requests.exceptions.ProxyError, 
                       requests.exceptions.ConnectTimeout,
                       requests.exceptions.ConnectionError,
                       requests.exceptions.ReadTimeout) as e:
                    
                    self.stats['failed_requests'] += 1
                    proxy.success_rate = max(0.0, proxy.success_rate - 0.2)  # Significant decrease
                    proxy.status = ProxyStatus.DEAD
                    
                    logger.debug(f"Proxy {proxy.address} failed: {e}", module="proxy_manager")
                    
                    if not retry_on_failure:
                        break
                    
                except Exception as e:
                    self.stats['failed_requests'] += 1
                    logger.error(f"Request error: {e}", module="proxy_manager")
                    break
                
                # Try different proxy for retry
                if attemptmax_retries and retry_on_failure:
                    proxy = self.get_proxy(proxy_type=proxy_type)
                    if proxy:
                        session = self._get_session(proxy)
                    else:
                        break
            
            return None
            
        except Exception as e:
            logger.error(f"Make request error: {e}", module="proxy_manager")
            return None
    
    async def make_async_request(self,
                                url: str,
                                method: str = 'GET',
                                proxy: Optional[Proxy] = None,
                                proxy_type: Optional[ProxyType] = None,
                                **kwargs) -> Optional[aiohttp.ClientResponse]:
        """Make async HTTP request through proxy"""
        try:
            if not proxy:
                proxy = self.get_proxy_for_request(url, proxy_type)
            
            if not proxy:
                logger.error("No proxy available for async request", module="proxy_manager")
                return None
            
            # Update statistics
            self.stats['total_requests'] += 1
            
            # Prepare proxy URL
            proxy_url = proxy.full_url
            
            # Configure connector based on proxy type
            connector = None
            if proxy.proxy_type in [ProxyType.SOCKS4, ProxyType.SOCKS5]:
                # SOCKS proxy
                import aiohttp_socks
                
                socks_version = aiohttp_socks.SocksVer.SOCKS5 if proxy.proxy_type == ProxyType.SOCKS5 else aiohttp_socks.SocksVer.SOCKS4
                
                connector = aiohttp_socks.ProxyConnector.from_url(
                    proxy_url,
                    rdns=True
                )
            else:
                # HTTP/HTTPS proxy
                connector = aiohttp.TCPConnector(ssl=False)
            
            # Make request
            async with aiohttp.ClientSession(connector=connector) as session:
                start_time = time.time()
                
                try:
                    async with session.request(
                        method=method,
                        url=url,
                        timeout=aiohttp.ClientTimeout(total=self.timeout),
                        **kwargs
                    ) as response:
                        
                        latency = time.time() - start_time
                        
                        # Update proxy stats
                        proxy.latency = (proxy.latency + latency) / 2
                        
                        if response.status200:
                            self.stats['successful_requests'] += 1
                            proxy.success_rate = min(1.0, proxy.success_rate + 0.05)
                            proxy.status = ProxyStatus.ACTIVE
                            
                            logger.debug(f"Async request successful through {proxy.address}: {response.status}", 
                                       module="proxy_manager")
                            
                            return response
                        else:
                            self.stats['failed_requests'] += 1
                            proxy.success_rate = max(0.0, proxy.success_rate - 0.1)
                            
                            if response.status in [403, 429, 503]:
                                proxy.status = ProxyStatus.BANNED
                            
                            logger.debug(f"Async request failed through {proxy.address}: {response.status}", 
                                       module="proxy_manager")
                            
                            return response
                            
                except (aiohttp.ClientProxyConnectionError,
                       aiohttp.ClientConnectorError,
                       asyncio.TimeoutError) as e:
                    
                    self.stats['failed_requests'] += 1
                    proxy.success_rate = max(0.0, proxy.success_rate - 0.2)
                    proxy.status = ProxyStatus.DEAD
                    
                    logger.debug(f"Async proxy {proxy.address} failed: {e}", module="proxy_manager")
                    return None
                    
        except Exception as e:
            logger.error(f"Async request error: {e}", module="proxy_manager")
            return None
    
    def _get_session(self, proxy: Proxy) -> requests.Session:
        """Get or create session for proxy"""
        session_key = proxy.address
        
        if session_key in self.sessions:
            session, created_at = self.sessions[session_key]
            
            # Check if session is expired
            if (datetime.now() - created_at).total_seconds()self.session_timeout:
                # Session expired, create new one
                return self._create_session(proxy)
            
            return session
        else:
            return self._create_session(proxy)
    
    def _create_session(self, proxy: Proxy) -> requests.Session:
        """Create new session for proxy"""
        try:
            session = requests.Session()
            
            # Configure retry strategy
            retry_strategy = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["HEAD", "GET", "OPTIONS", "POST", "PUT", "DELETE"]
            )
            
            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            
            # Set proxy
            session.proxies = proxy.dict_format
            
            # Set default headers
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            })
            
            # Store session
            self.sessions[proxy.address] = (session, datetime.now())
            
            return session
            
        except Exception as e:
            logger.error(f"Create session error: {e}", module="proxy_manager")
            raise
    
    def test_proxy(self, proxy: Proxy) -> Tuple[bool, float, Dict[str, Any]]:
        """Test proxy functionality"""
        try:
            start_time = time.time()
            results = {}
            
            # Test each test URL
            successes = 0
            total_tests = len(self.test_urls)
            
            for test_url in self.test_urls:
                try:
                    session = self._get_session(proxy)
                    
                    response = session.get(
                        test_url,
                        timeout=self.timeout,
                        allow_redirects=True
                    )
                    
                    if response.status_code200:
                        successes += 1
                        results[test_url] = {
                            'status': response.status_code,
                            'latency': response.elapsed.total_seconds(),
                            'size': len(response.content)
                        }
                    else:
                        results[test_url] = {
                            'status': response.status_code,
                            'error': 'Non-200 status'
                        }
                        
                except Exception as e:
                    results[test_url] = {
                        'status': 'error',
                        'error': str(e)
                    }
            
            # Calculate success rate
            success_rate = successes / total_tests if total_tests > 0 else 0
            
            # Calculate average latency
            latencies = [r.get('latency', 0) for r in results.values() if 'latency' in r]
            avg_latency = sum(latencies) / len(latencies) if latencies else 0
            
            # Update proxy
            proxy.success_rate = success_rate
            proxy.latency = avg_latency
            proxy.last_tested = datetime.now()
            
            # Determine status
            if success_rateself.min_success_rate:
                proxy.status = ProxyStatus.ACTIVE
            elif success_rate0.3:
                proxy.status = ProxyStatus.DEAD
            elif avg_latencyself.max_latency:
                proxy.status = ProxyStatus.SLOW
            else:
                proxy.status = ProxyStatus.UNSTABLE
            
            test_duration = time.time() - start_time
            
            logger.debug(f"Proxy test completed: {proxy.address} - "
                        f"Success: {success_rate:.2%}, Latency: {avg_latency:.2f}s, "
                        f"Status: {proxy.status.value}", module="proxy_manager")
            
            return success_rateself.min_success_rate, avg_latency, results
            
        except Exception as e:
            logger.error(f"Proxy test error for {proxy.address}: {e}", module="proxy_manager")
            return False, float('inf'), {'error': str(e)}
    
    def test_all_proxies(self) -> Dict[str, Any]:
        """Test all proxies"""
        results = {
            'total': len(self.proxies),
            'tested': 0,
            'active': 0,
            'dead': 0,
            'slow': 0,
            'unstable': 0,
            'average_latency': 0.0,
            'average_success_rate': 0.0,
            'details': {}
        }
        
        try:
            with self.proxy_lock:
                for proxy in self.proxies:
                    success, latency, detail = self.test_proxy(proxy)
                    
                    results['tested'] += 1
                    results['details'][proxy.address] = {
                        'success': success,
                        'latency': latency,
                        'status': proxy.status.value,
                        'detail': detail
                    }
                    
                    # Update counts
                    if proxy.status == ProxyStatus.ACTIVE:
                        results['active'] += 1
                    elif proxy.status == ProxyStatus.DEAD:
                        results['dead'] += 1
                    elif proxy.status == ProxyStatus.SLOW:
                        results['slow'] += 1
                    elif proxy.status == ProxyStatus.UNSTABLE:
                        results['unstable'] += 1
                    
                    # Update averages
                    results['average_latency'] += latency
                    results['average_success_rate'] += proxy.success_rate
            
            # Calculate averages
            if results['tested'] > 0:
                results['average_latency'] /= results['tested']
                results['average_success_rate'] /= results['tested']
            
            # Update statistics
            self.stats['active_proxies'] = results['active']
            self.stats['dead_proxies'] = results['dead']
            
            logger.info(f"Proxy testing completed: {results['active']}/{results['total']} active", 
                       module="proxy_manager")
            
            # Log audit event
            audit_log.log_event(
                event_type=AuditEventType.SYSTEM_CHANGE.value,
                severity=AuditSeverity.INFO.value,
                user='system',
                source_ip='localhost',
                description=f"Proxy testing completed: {results['active']} active out of {results['total']}",
                details=results,
                resource='proxy_manager',
                action='test_proxies'
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Test all proxies error: {e}", module="proxy_manager")
            return results
    
    def test_all_proxies_async(self):
        """Test all proxies asynchronously"""
        try:
            # Submit test tasks to thread pool
            futures = []
            
            with self.proxy_lock:
                for proxy in self.proxies:
                    future = self.thread_pool.submit(self.test_proxy, proxy)
                    futures.append(future)
            
            # Wait for completion
            concurrent.futures.wait(futures, timeout=300)
            
            # Update statistics
            active_count = sum(1 for proxy in self.proxies if proxy.status == ProxyStatus.ACTIVE)
            self.stats['active_proxies'] = active_count
            self.stats['dead_proxies'] = len(self.proxies) - active_count
            
            logger.info(f"Async proxy testing completed: {active_count}/{len(self.proxies)} active", 
                       module="proxy_manager")
            
        except Exception as e:
            logger.error(f"Async proxy testing error: {e}", module="proxy_manager")
    
    def import_from_file(self, filepath: str, format: str = 'auto') -> int:
        """Import proxies from file"""
        imported = 0
        
        try:
            if not os.path.exists(filepath):
                logger.error(f"Proxy file not found: {filepath}", module="proxy_manager")
                return 0
            
            with open(filepath, 'r') as f:
                content = f.read().strip()
            
            proxies_data = []
            
            # Auto-detect format
            if format == 'auto':
                # Try JSON
                try:
                    data = json.loads(content)
                    if isinstance(data, list):
                        format = 'json'
                    elif 'proxies' in data:
                        format = 'json_with_wrapper'
                except:
                    pass
                
                # Try text (host:port)
                if not format:
                    lines = content.split('\n')
                    if all(':' in line for line in lines if line.strip()):
                        format = 'text'
            
            # Parse based on format
            if format == 'json':
                proxies_data = json.loads(content)
                
            elif format == 'json_with_wrapper':
                data = json.loads(content)
                proxies_data = data.get('proxies', [])
                
            elif format == 'text':
                for line in content.split('\n'):
                    line = line.strip()
                    if line and ':' in line:
                        parts = line.split(':')
                        host = parts[0].strip()
                        
                        # Handle host:port:username:password format
                        if len(parts) >= 2:
                            port = int(parts[1].strip()) if parts[1].strip().isdigit() else 8080
                            
                            proxy_data = {
                                'host': host,
                                'port': port,
                                'type': 'http'
                            }
                            
                            if len(parts) >= 4:
                                proxy_data['username'] = parts[2].strip()
                                proxy_data['password'] = parts[3].strip()
                            
                            proxies_data.append(proxy_data)
            
            # Import proxies
            for proxy_data in proxies_data:
                try:
                    proxy = Proxy(
                        host=proxy_data.get('host', proxy_data.get('ip', '')),
                        port=int(proxy_data.get('port', proxy_data.get('port', 8080))),
                        proxy_type=ProxyType(proxy_data.get('type', proxy_data.get('protocol', 'http'))),
                        username=proxy_data.get('username', proxy_data.get('user')),
                        password=proxy_data.get('password', proxy_data.get('pass')),
                        country=proxy_data.get('country'),
                        city=proxy_data.get('city'),
                        tags=proxy_data.get('tags', [])
                    )
                    
                    if self.add_proxy(proxy):
                        imported += 1
                        
                except Exception as e:
                    logger.error(f"Error importing proxy data: {e}", module="proxy_manager")
            
            logger.info(f"Imported {imported} proxies from {filepath}", module="proxy_manager")
            
            # Test imported proxies
            if imported > 0:
                self.test_all_proxies_async()
            
            return imported
            
        except Exception as e:
            logger.error(f"Import from file error: {e}", module="proxy_manager")
            return 0
    
    def export_to_file(self, filepath: str, format: str = 'json', only_active: bool = True) -> int:
        """Export proxies to file"""
        exported = 0
        
        try:
            with self.proxy_lock:
                # Filter proxies
                proxies_to_export = []
                
                for proxy in self.proxies:
                    if only_active and proxy.status != ProxyStatus.ACTIVE:
                        continue
                    
                    proxies_to_export.append(proxy.to_dict())
                    exported += 1
            
            # Export based on format
            if format == 'json':
                with open(filepath, 'w') as f:
                    json.dump(proxies_to_export, f, indent=2, default=str)
                    
            elif format == 'text':
                with open(filepath, 'w') as f:
                    for proxy in proxies_to_export:
                        if proxy.get('username') and proxy.get('password'):
                            f.write(f"{proxy['host']}:{proxy['port']}:{proxy['username']}:{proxy['password']}\n")
                        else:
                            f.write(f"{proxy['host']}:{proxy['port']}\n")
            
            logger.info(f"Exported {exported} proxies to {filepath}", module="proxy_manager")
            return exported
            
        except Exception as e:
            logger.error(f"Export to file error: {e}", module="proxy_manager")
            return 0
    
    def scrape_proxies(self, sources: List[str] = None) -> int:
        """Scrape proxies from online sources"""
        scraped = 0
        
        try:
            if not sources:
                sources = [
                    'https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all',
                    'https://www.proxy-list.download/api/v1/get?type=http',
                    'https://www.proxy-list.download/api/v1/get?type=https',
                    'https://www.proxy-list.download/api/v1/get?type=socks4',
                    'https://www.proxy-list.download/api/v1/get?type=socks5',
                    'https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt',
                    'https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt',
                    'https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt'
                ]
            
            for source in sources:
                try:
                    response = requests.get(source, timeout=10)
                    
                    if response.status_code200:
                        content = response.text
                        
                        # Parse proxy list
                        proxies = []
                        for line in content.split('\n'):
                            line = line.strip()
                            if line and ':' in line:
                                parts = line.split(':')
                                host = parts[0].strip()
                                
                                if len(parts) >= 2 and parts[1].strip().isdigit():
                                    port = int(parts[1].strip())
                                    
                                    # Determine proxy type from source URL
                                    proxy_type = ProxyType.HTTP
                                    if 'socks4' in source.lower():
                                        proxy_type = ProxyType.SOCKS4
                                    elif 'socks5' in source.lower():
                                        proxy_type = ProxyType.SOCKS5
                                    elif 'https' in source.lower():
                                        proxy_type = ProxyType.HTTPS
                                    
                                    proxy = Proxy(
                                        host=host,
                                        port=port,
                                        proxy_type=proxy_type,
                                        tags=['scraped', source]
                                    )
                                    
                                    if self.add_proxy(proxy):
                                        scraped += 1
                                        
                except Exception as e:
                    logger.error(f"Error scraping from {source}: {e}", module="proxy_manager")
            
            # Test scraped proxies
            if scraped > 0:
                logger.info(f"Scraped {scraped} new proxies", module="proxy_manager")
                self.test_all_proxies_async()
            
            return scraped
            
        except Exception as e:
            logger.error(f"Scrape proxies error: {e}", module="proxy_manager")
            return 0
    
    def _maintenance_loop(self):
        """Maintenance loop for proxy management"""
        while self.running:
            try:
                # Test proxies periodically
                if self.proxies:
                    self.test_all_proxies_async()
                
                # Clean up old sessions
                self._cleanup_sessions()
                
                # Remove dead proxies if configured
                if self.config.get('auto_remove_dead', False):
                    self._remove_dead_proxies()
                
                # Scrape new proxies if configured
                if self.config.get('auto_scrape', False):
                    scrape_interval = self.config.get('auto_scrape_interval', 3600)
                    if int(time.time()) % scrape_interval1:
                        self.scrape_proxies()
                
                # Sleep until next maintenance
                time.sleep(self.test_interval)
                
            except Exception as e:
                logger.error(f"Maintenance loop error: {e}", module="proxy_manager")
                time.sleep(60)
    
    def _cleanup_sessions(self):
        """Clean up old sessions"""
        try:
            now = datetime.now()
            expired_sessions = []
            
            for session_key, (session, created_at) in list(self.sessions.items()):
                if (now - created_at).total_seconds()self.session_timeout:
                    expired_sessions.append(session_key)
            
            for session_key in expired_sessions:
                try:
                    session, _ = self.sessions.pop(session_key)
                    session.close()
                except:
                    pass
            
            if expired_sessions:
                logger.debug(f"Cleaned up {len(expired_sessions)} expired sessions", 
                           module="proxy_manager")
                
        except Exception as e:
            logger.error(f"Session cleanup error: {e}", module="proxy_manager")
    
    def _remove_dead_proxies(self):
        """Remove dead proxies"""
        try:
            with self.proxy_lock:
                dead_proxies = []
                
                for proxy in self.proxies:
                    if proxy.status == ProxyStatus.DEAD:
                        # Check if dead for more than 1 hour
                        if proxy.last_tested and (datetime.now() - proxy.last_tested).total_seconds()3600:
                            dead_proxies.append(proxy)
                
                for proxy in dead_proxies:
                    self.proxies.remove(proxy)
                
                if dead_proxies:
                    logger.info(f"Removed {len(dead_proxies)} dead proxies", module="proxy_manager")
                    self._build_pools()
                    
        except Exception as e:
            logger.error(f"Remove dead proxies error: {e}", module="proxy_manager")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get proxy manager statistics"""
        uptime = (datetime.now() - self.stats['start_time']).total_seconds()
        
        return {
            **self.stats,
            'uptime_seconds': uptime,
            'uptime_human': str(timedelta(seconds=int(uptime))),
            'proxy_count': len(self.proxies),
            'active_proxy_percentage': (self.stats['active_proxies'] / len(self.proxies) * 100 
                                      if len(self.proxies) > 0 else 0),
            'request_success_rate': (self.stats['successful_requests'] / self.stats['total_requests'] * 100 
                                   if self.stats['total_requests'] > 0 else 0),
            'data_transferred_mb': self.stats['total_data_transferred'] / 1024 / 1024,
            'session_count': len(self.sessions)
        }
    
    def get_detailed_statistics(self) -> Dict[str, Any]:
        """Get detailed statistics"""
        stats = self.get_statistics()
        
        # Add proxy type distribution
        type_dist = defaultdict(int)
        status_dist = defaultdict(int)
        country_dist = defaultdict(int)
        
        with self.proxy_lock:
            for proxy in self.proxies:
                type_dist[proxy.proxy_type.value] += 1
                status_dist[proxy.status.value] += 1
                if proxy.country:
                    country_dist[proxy.country] += 1
        
        stats['proxy_type_distribution'] = dict(type_dist)
        stats['proxy_status_distribution'] = dict(status_dist)
        stats['proxy_country_distribution'] = dict(country_dist)
        
        # Add performance metrics
        if self.proxies:
            avg_latency = sum(p.latency for p in self.proxies) / len(self.proxies)
            avg_success_rate = sum(p.success_rate for p in self.proxies) / len(self.proxies)
            
            stats['average_proxy_latency'] = avg_latency
            stats['average_proxy_success_rate'] = avg_success_rate
        
        return stats
    
    def stop(self):
        """Stop proxy manager"""
        self.running = False
        
        # Shutdown thread pool
        self.thread_pool.shutdown(wait=True)
        
        # Close all sessions
        for session_key, (session, _) in list(self.sessions.items()):
            try:
                session.close()
            except:
                pass
        self.sessions.clear()
        
        logger.info("Proxy manager stopped", module="proxy_manager")

# Global instance
_proxy_manager = None

def get_proxy_manager(config: Dict = None) -> ProxyManager:
    """Get or create proxy manager instance"""
    global _proxy_manager
    
    if _proxy_manager is None:
        _proxy_manager = ProxyManager(config)
    
    return _proxy_manager

if __name__ == "__main__":
    # Test proxy manager
    config = {
        'proxies': [
            {'host': 'proxy1.example.com', 'port': 8080, 'type': 'http'},
            {'host': 'proxy2.example.com', 'port': 8888, 'type': 'https'},
            {'host': 'socks.example.com', 'port': 1080, 'type': 'socks5'}
        ],
        'test_urls': ['http://httpbin.org/ip', 'https://api.ipify.org?format=json'],
        'test_interval': 60,
        'auto_remove_dead': True,
        'auto_scrape': False
    }
    
    pm = get_proxy_manager(config)
    
    print("Testing proxy manager...")
    
    # Test proxy selection
    proxy = pm.get_proxy(strategy="smart")
    if proxy:
        print(f"Selected proxy: {proxy.address} ({proxy.proxy_type.value})")
    
    # Make test request
    print("\nMaking test request...")
    response = pm.make_request('http://httpbin.org/ip')
    if response:
        print(f"Request successful: {response.json()}")
    else:
        print("Request failed")
    
    # Test all proxies
    print("\nTesting all proxies...")
    test_results = pm.test_all_proxies()
    print(f"Test results: {test_results['active']}/{test_results['total']} active")
    
    # Get statistics
    print("\n📊 Proxy Manager Statistics:")
    stats = pm.get_detailed_statistics()
    print(f"  Total proxies: {stats['proxy_count']}")
    print(f"  Active proxies: {stats['active_proxies']}")
    print(f"  Dead proxies: {stats['dead_proxies']}")
    print(f"  Total requests: {stats['total_requests']}")
    print(f"  Success rate: {stats['request_success_rate']:.1f}%")
    print(f"  Data transferred: {stats['data_transferred_mb']:.2f} MB")
    
    print("\nProxy type distribution:")
    for proxy_type, count in stats['proxy_type_distribution'].items():
        print(f"  {proxy_type}: {count}")
    
    # Stop manager
    pm.stop()
    
    print("\n✅ Proxy manager tests completed!")
