#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tor_integration.py - Advanced Tor Integration and Anonymization System
"""

import os
import sys
import json
import time
import random
import threading
import subprocess
import socket
import struct
import hashlib
import base64
import select
from typing import Dict, List, Optional, Tuple, Any, Union, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import stem
import stem.control
import stem.process
import stem.socket
import socks
from stem.util import term
import aiohttp
import asyncio

# Import utilities
from ..utils.logger import get_logger
from ..security.encryption_manager import get_encryption_manager
from ..security.audit_log import get_audit_log_manager, AuditEventType, AuditSeverity

logger = get_logger()
audit_log = get_audit_log_manager()

class TorState(Enum):
    """Tor process states"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    RESTARTING = "restarting"
    ERROR = "error"

class CircuitStatus(Enum):
    """Tor circuit status"""
    NEW = "new"
    EXTENDED = "extended"
    BUILT = "built"
    CLOSED = "closed"
    FAILED = "failed"

@dataclass
class TorCircuit:
    """Tor circuit representation"""
    circuit_id: str
    status: CircuitStatus
    path: List[str]  # List of relay fingerprints
    created_at: datetime
    last_used: Optional[datetime] = None
    bytes_sent: int = 0
    bytes_received: int = 0
    stream_count: int = 0
    is_internal: bool = False
    
    @property
    def age(self) -> float:
        """Get circuit age in seconds"""
        return (datetime.now() - self.created_at).total_seconds()
    
    @property
    def idle_time(self) -> float:
        """Get idle time in seconds"""
        if self.last_used:
            return (datetime.now() - self.last_used).total_seconds()
        return self.age
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'circuit_id': self.circuit_id,
            'status': self.status.value,
            'path': self.path,
            'created_at': self.created_at.isoformat(),
            'last_used': self.last_used.isoformat() if self.last_used else None,
            'bytes_sent': self.bytes_sent,
            'bytes_received': self.bytes_received,
            'stream_count': self.stream_count,
            'is_internal': self.is_internal,
            'age_seconds': self.age,
            'idle_seconds': self.idle_time
        }

class TorIntegration:
    """Advanced Tor integration and management system"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # Tor configuration
        self.tor_path = self.config.get('tor_path', 'tor')
        self.tor_data_dir = self.config.get('tor_data_dir', 'tor_data')
        self.tor_config_file = self.config.get('tor_config_file')
        
        # Connection configuration
        self.socks_port = self.config.get('socks_port', 9050)
        self.control_port = self.config.get('control_port', 9051)
        self.control_password = self.config.get('control_password')
        
        # If no password provided, generate one
        if not self.control_password:
            self.control_password = self._generate_control_password()
        
        # Security configuration
        self.use_bridges = self.config.get('use_bridges', False)
        self.bridges = self.config.get('bridges', [])
        self.exclude_nodes = self.config.get('exclude_nodes', [])
        self.exclude_countries = self.config.get('exclude_countries', [])
        
        # Performance configuration
        self.max_circuits = self.config.get('max_circuits', 10)
        self.circuit_timeout = self.config.get('circuit_timeout', 60)
        self.new_circuit_period = self.config.get('new_circuit_period', 600)  # 10 minutes
        self.max_streams_per_circuit = self.config.get('max_streams_per_circuit', 100)
        
        # Process management
        self.tor_process = None
        self.controller = None
        self.state = TorState.STOPPED
        
        # Circuit management
        self.circuits = {}  # circuit_id -> TorCircuit
        self.circuit_lock = threading.Lock()
        self.next_circuit_id = 1
        
        # Statistics
        self.stats = {
            'total_circuits_created': 0,
            'total_streams': 0,
            'total_bytes_sent': 0,
            'total_bytes_received': 0,
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'tor_restarts': 0,
            'start_time': datetime.now()
        }
        
        # Session management
        self.sessions = {}
        self.session_timeout = self.config.get('session_timeout', 300)
        
        # Maintenance thread
        self.running = True
        self.maintenance_thread = threading.Thread(target=self._maintenance_loop, daemon=True)
        self.maintenance_thread.start()
        
        # Start Tor if configured
        if self.config.get('auto_start', True):
            self.start()
        
        logger.info("Tor integration initialized", module="tor_integration")
    
    def _generate_control_password(self) -> str:
        """Generate control password for Tor"""
        # Generate random password
        random_bytes = os.urandom(32)
        password_hash = hashlib.sha256(random_bytes).hexdigest()[:16]
        
        # Hash it for Tor's HashedControlPassword
        from stem.control import Controller
        hashed_password = Controller.get_auth_password_hash(password_hash)
        
        # Store plain password for authentication
        self.control_password_plain = password_hash
        
        return hashed_password
    
    def _create_tor_config(self) -> str:
        """Create Tor configuration"""
        config_lines = []
        
        # Basic configuration
        config_lines.append(f"SOCKSPort {self.socks_port}")
        config_lines.append(f"ControlPort {self.control_port}")
        config_lines.append(f"HashedControlPassword {self.control_password}")
        config_lines.append(f"DataDirectory {self.tor_data_dir}")
        
        # Security settings
        config_lines.append("SafeSocks 1")
        config_lines.append("TestSocks 1")
        config_lines.append("WarnUnsafeSocks 1")
        
        # Performance settings
        config_lines.append("MaxCircuitDirtiness 600")
        config_lines.append("MaxClientCircuitsPending 48")
        config_lines.append("CircuitBuildTimeout 60")
        config_lines.append("LearnCircuitBuildTimeout 1")
        config_lines.append("CircuitStreamTimeout 60")
        
        # Connection settings
        config_lines.append("KeepalivePeriod 60")
        config_lines.append("NumEntryGuards 3")
        config_lines.append("NumDirectoryGuards 3")
        
        # Logging
        config_lines.append("Log notice stdout")
        config_lines.append("Log info stdout")
        
        # Bridge configuration
        if self.use_bridges and self.bridges:
            config_lines.append("UseBridges 1")
            for bridge in self.bridges:
                config_lines.append(f"Bridge {bridge}")
        
        # Exclude nodes/countries
        if self.exclude_nodes:
            config_lines.append(f"ExcludeNodes {','.join(self.exclude_nodes)}")
        
        if self.exclude_countries:
            config_lines.append(f"ExcludeExitNodes {{{','.join(self.exclude_countries)}}}")
            config_lines.append(f"ExcludeEntryNodes {{{','.join(self.exclude_countries)}}}")
        
        # Additional custom config
        custom_config = self.config.get('custom_config', [])
        config_lines.extend(custom_config)
        
        return '\n'.join(config_lines)
    
    def start(self) -> bool:
        """Start Tor process"""
        try:
            if self.state != TorState.STOPPED:
                logger.warning(f"Tor is already {self.state.value}", module="tor_integration")
                return self.state == TorState.RUNNING
            
            self.state = TorState.STARTING
            
            # Create data directory
            os.makedirs(self.tor_data_dir, exist_ok=True)
            
            # Create config file
            config_content = self._create_tor_config()
            config_path = self.tor_config_file or os.path.join(self.tor_data_dir, 'torrc')
            
            with open(config_path, 'w') as f:
                f.write(config_content)
            
            logger.info(f"Starting Tor with config: {config_path}", module="tor_integration")
            
            # Start Tor process
            try:
                self.tor_process = stem.process.launch_tor_with_config(
                    config={
                        'SocksPort': str(self.socks_port),
                        'ControlPort': str(self.control_port),
                        'DataDirectory': self.tor_data_dir,
                        'HashedControlPassword': self.control_password,
                    },
                    tor_cmd=self.tor_path,
                    init_msg_handler=self._tor_msg_handler,
                    timeout=120
                )
                
            except Exception as e:
                # Fallback to subprocess
                logger.warning(f"Stem launch failed, using subprocess: {e}", module="tor_integration")
                
                cmd = [
                    self.tor_path,
                    '-f', config_path,
                    '--SocksPort', str(self.socks_port),
                    '--ControlPort', str(self.control_port),
                    '--DataDirectory', self.tor_data_dir
                ]
                
                self.tor_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                # Wait for Tor to start
                time.sleep(5)
            
            # Connect controller
            if not self._connect_controller():
                logger.error("Failed to connect to Tor controller", module="tor_integration")
                self.stop()
                return False
            
            self.state = TorState.RUNNING
            
            # Initialize circuits
            self._initialize_circuits()
            
            logger.info(f"✅ Tor started successfully on SOCKS port {self.socks_port}", 
                       module="tor_integration")
            
            # Log audit event
            audit_log.log_event(
                event_type=AuditEventType.SYSTEM_CHANGE.value,
                severity=AuditSeverity.INFO.value,
                user='system',
                source_ip='127.0.0.1',
                description=f"Tor process started on port {self.socks_port}",
                details={
                    'socks_port': self.socks_port,
                    'control_port': self.control_port,
                    'use_bridges': self.use_bridges,
                    'bridge_count': len(self.bridges)
                },
                resource='tor_integration',
                action='start_tor'
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start Tor: {e}", module="tor_integration")
            self.state = TorState.ERROR
            return False
    
    def _tor_msg_handler(self, line: str):
        """Handle Tor process messages"""
        if line:
            logger.debug(f"Tor: {line.strip()}", module="tor_integration")
    
    def _connect_controller(self) -> bool:
        """Connect to Tor control port"""
        try:
            self.controller = stem.control.Controller.from_port(port=self.control_port)
            
            # Authenticate
            if self.control_password_plain:
                self.controller.authenticate(password=self.control_password_plain)
            else:
                self.controller.authenticate()
            
            logger.info("Connected to Tor controller", module="tor_integration")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect controller: {e}", module="tor_integration")
            return False
    
    def stop(self):
        """Stop Tor process"""
        try:
            self.running = False
            
            # Close controller
            if self.controller:
                try:
                    self.controller.close()
                except:
                    pass
                self.controller = None
            
            # Terminate Tor process
            if self.tor_process:
                try:
                    self.tor_process.terminate()
                    self.tor_process.wait(timeout=10)
                except:
                    try:
                        self.tor_process.kill()
                    except:
                        pass
                self.tor_process = None
            
            self.state = TorState.STOPPED
            
            # Clear circuits
            with self.circuit_lock:
                self.circuits.clear()
            
            logger.info("Tor stopped", module="tor_integration")
            
        except Exception as e:
            logger.error(f"Error stopping Tor: {e}", module="tor_integration")
    
    def restart(self) -> bool:
        """Restart Tor process"""
        try:
            logger.info("Restarting Tor...", module="tor_integration")
            
            self.stop()
            time.sleep(2)
            
            success = self.start()
            
            if success:
                self.stats['tor_restarts'] += 1
                logger.info("Tor restarted successfully", module="tor_integration")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to restart Tor: {e}", module="tor_integration")
            return False
    
    def _initialize_circuits(self):
        """Initialize initial circuits"""
        try:
            # Create initial circuits
            for _ in range(min(3, self.max_circuits)):
                self.create_new_circuit()
            
            logger.info(f"Initialized {len(self.circuits)} circuits", module="tor_integration")
            
        except Exception as e:
            logger.error(f"Circuit initialization error: {e}", module="tor_integration")
    
    def create_new_circuit(self, is_internal: bool = False) -> Optional[str]:
        """Create new Tor circuit"""
        try:
            with self.circuit_lock:
                # Check circuit limit
                active_circuits = sum(1 for c in self.circuits.values() 
                                    if c.status in [CircuitStatus.NEW, CircuitStatus.BUILT, CircuitStatus.EXTENDED])
                
                if active_circuits >= self.max_circuits:
                    # Close oldest circuit
                    self._close_oldest_circuit()
                
                # Generate circuit ID
                circuit_id = f"circuit_{self.next_circuit_id}"
                self.next_circuit_id += 1
                
                # Create circuit
                circuit = TorCircuit(
                    circuit_id=circuit_id,
                    status=CircuitStatus.NEW,
                    path=[],
                    created_at=datetime.now(),
                    is_internal=is_internal
                )
                
                self.circuits[circuit_id] = circuit
                self.stats['total_circuits_created'] += 1
                
                # Actually build circuit through controller
                if self.controller and not is_internal:
                    try:
                        # Build new circuit
                        self.controller.new_circuit()
                        
                        # Get circuit info
                        circuits = self.controller.get_circuits()
                        if circuits:
                            # Find our new circuit
                            for circ in circuits:
                                if circ.id not in self.circuits:
                                    # Update our circuit with real ID
                                    circuit.circuit_id = circ.id
                                    circuit.status = CircuitStatus(circ.status.lower())
                                    circuit.path = [hop[0] for hop in circ.path]
                                    
                                    # Update dictionary
                                    self.circuits[circ.id] = circuit
                                    del self.circuits[circuit_id]
                                    
                                    circuit_id = circ.id
                                    break
                    
                    except Exception as e:
                        logger.error(f"Controller circuit creation error: {e}", module="tor_integration")
                
                logger.debug(f"Created new circuit: {circuit_id}", module="tor_integration")
                return circuit_id
                
        except Exception as e:
            logger.error(f"Create circuit error: {e}", module="tor_integration")
            return None
    
    def _close_oldest_circuit(self):
        """Close the oldest circuit"""
        try:
            with self.circuit_lock:
                if not self.circuits:
                    return
                
                # Find oldest circuit
                oldest_circuit = min(self.circuits.values(), key=lambda c: c.created_at)
                
                # Close through controller
                if self.controller and not oldest_circuit.is_internal:
                    try:
                        self.controller.close_circuit(oldest_circuit.circuit_id)
                    except:
                        pass
                
                # Remove from our tracking
                del self.circuits[oldest_circuit.circuit_id]
                
                logger.debug(f"Closed oldest circuit: {oldest_circuit.circuit_id}", 
                           module="tor_integration")
                
        except Exception as e:
            logger.error(f"Close oldest circuit error: {e}", module="tor_integration")
    
    def get_circuit(self, 
                   min_age: float = 0,
                   max_age: float = float('inf'),
                   require_built: bool = True,
                   allow_internal: bool = True) -> Optional[TorCircuit]:
        """Get suitable circuit for use"""
        try:
            with self.circuit_lock:
                candidates = []
                
                for circuit in self.circuits.values():
                    # Check status
                    if require_built and circuit.status != CircuitStatus.BUILT:
                        continue
                    
                    # Check age
                    if circuit.agemin_age or circuit.agemax_age:
                        continue
                    
                    # Check internal flag
                    if not allow_internal and circuit.is_internal:
                        continue
                    
                    # Check stream limit
                    if circuit.stream_count >= self.max_streams_per_circuit:
                        continue
                    
                    candidates.append(circuit)
                
                if not candidates:
                    # Create new circuit
                    circuit_id = self.create_new_circuit()
                    if circuit_id and circuit_id in self.circuits:
                        return self.circuits[circuit_id]
                    return None
                
                # Select circuit with least streams and oldest last used
                selected = min(candidates, key=lambda c: (c.stream_count, c.idle_time))
                
                return selected
                
        except Exception as e:
            logger.error(f"Get circuit error: {e}", module="tor_integration")
            return None
    
    def make_request(self,
                    url: str,
                    method: str = 'GET',
                    circuit_id: Optional[str] = None,
                    timeout: float = 30.0,
                    retries: int = 3,
                    **kwargs) -> Optional[requests.Response]:
        """Make HTTP request through Tor"""
        try:
            # Get or create circuit
            circuit = None
            if circuit_id and circuit_id in self.circuits:
                circuit = self.circuits[circuit_id]
            else:
                circuit = self.get_circuit()
            
            if not circuit:
                logger.error("No circuit available for request", module="tor_integration")
                return None
            
            # Update statistics
            self.stats['total_requests'] += 1
            circuit.stream_count += 1
            circuit.last_used = datetime.now()
            
            # Prepare session with circuit
            session = self._get_session_for_circuit(circuit)
            
            # Make request with retries
            for attempt in range(retries + 1):
                try:
                    start_time = time.time()
                    
                    response = session.request(
                        method=method,
                        url=url,
                        timeout=timeout,
                        **kwargs
                    )
                    
                    request_time = time.time() - start_time
                    
                    # Update circuit stats
                    if response.content:
                        circuit.bytes_received += len(response.content)
                        self.stats['total_bytes_received'] += len(response.content)
                    
                    # Update request stats
                    if response.status_code200:
                        self.stats['successful_requests'] += 1
                        
                        logger.debug(f"Tor request successful: {url} via circuit {circuit.circuit_id} "
                                   f"({request_time:.2f}s)", module="tor_integration")
                        
                        return response
                    else:
                        self.stats['failed_requests'] += 1
                        
                        logger.warning(f"Tor request failed: {url} - {response.status_code}", 
                                     module="tor_integration")
                        
                        if attemptretries:
                            # Try with new circuit
                            circuit = self.get_circuit()
                            if circuit:
                                session = self._get_session_for_circuit(circuit)
                            else:
                                break
                        else:
                            break
                        
                except Exception as e:
                    self.stats['failed_requests'] += 1
                    
                    logger.error(f"Tor request error: {e}", module="tor_integration")
                    
                    # Mark circuit as failed
                    circuit.status = CircuitStatus.FAILED
                    
                    if attemptretries:
                        # Try with new circuit
                        circuit = self.get_circuit()
                        if not circuit:
                            break
                    else:
                        break
            
            return None
            
        except Exception as e:
            logger.error(f"Make request error: {e}", module="tor_integration")
            return None
    
    async def make_async_request(self,
                                url: str,
                                method: str = 'GET',
                                circuit_id: Optional[str] = None,
                                timeout: float = 30.0,
                                **kwargs) -> Optional[aiohttp.ClientResponse]:
        """Make async HTTP request through Tor"""
        try:
            # Get or create circuit
            circuit = None
            if circuit_id and circuit_id in self.circuits:
                circuit = self.circuits[circuit_id]
            else:
                circuit = self.get_circuit()
            
            if not circuit:
                logger.error("No circuit available for async request", module="tor_integration")
                return None
            
            # Update statistics
            self.stats['total_requests'] += 1
            circuit.stream_count += 1
            circuit.last_used = datetime.now()
            
            # Prepare SOCKS proxy URL
            proxy_url = f"socks5://127.0.0.1:{self.socks_port}"
            
            # Make async request
            connector = aiohttp.TCPConnector(ssl=False)
            
            async with aiohttp.ClientSession(connector=connector) as session:
                start_time = time.time()
                
                try:
                    async with session.request(
                        method=method,
                        url=url,
                        proxy=proxy_url,
                        timeout=aiohttp.ClientTimeout(total=timeout),
                        **kwargs
                    ) as response:
                        
                        request_time = time.time() - start_time
                        
                        # Update circuit stats
                        content = await response.read()
                        if content:
                            circuit.bytes_received += len(content)
                            self.stats['total_bytes_received'] += len(content)
                        
                        # Update request stats
                        if response.status200:
                            self.stats['successful_requests'] += 1
                            
                            logger.debug(f"Async Tor request successful: {url} via circuit {circuit.circuit_id} "
                                       f"({request_time:.2f}s)", module="tor_integration")
                            
                            return response
                        else:
                            self.stats['failed_requests'] += 1
                            
                            logger.warning(f"Async Tor request failed: {url} - {response.status}", 
                                         module="tor_integration")
                            
                            return response
                            
                except Exception as e:
                    self.stats['failed_requests'] += 1
                    
                    logger.error(f"Async Tor request error: {e}", module="tor_integration")
                    
                    # Mark circuit as failed
                    circuit.status = CircuitStatus.FAILED
                    
                    return None
                    
        except Exception as e:
            logger.error(f"Make async request error: {e}", module="tor_integration")
            return None
    
    def _get_session_for_circuit(self, circuit: TorCircuit) -> requests.Session:
        """Get or create session for circuit"""
        session_key = circuit.circuit_id
        
        if session_key in self.sessions:
            session, created_at = self.sessions[session_key]
            
            # Check if session is expired
            if (datetime.now() - created_at).total_seconds()self.session_timeout:
                # Session expired, create new one
                return self._create_session_for_circuit(circuit)
            
            return session
        else:
            return self._create_session_for_circuit(circuit)
    
    def _create_session_for_circuit(self, circuit: TorCircuit) -> requests.Session:
        """Create new session for circuit"""
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
            
            # Configure SOCKS proxy
            session.proxies = {
                'http': f'socks5://127.0.0.1:{self.socks_port}',
                'https': f'socks5://127.0.0.1:{self.socks_port}'
            }
            
            # Set default headers
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; rv:91.0) Gecko/20100101 Firefox/91.0',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'DNT': '1'
            })
            
            # Store session
            self.sessions[circuit.circuit_id] = (session, datetime.now())
            
            return session
            
        except Exception as e:
            logger.error(f"Create session error: {e}", module="tor_integration")
            raise
    
    def get_identity(self, renew: bool = False) -> Optional[Dict[str, Any]]:
        """Get current Tor identity (exit IP)"""
        try:
            if not self.controller:
                logger.error("Controller not connected", module="tor_integration")
                return None
            
            if renew:
                # Signal new identity
                self.controller.signal(stem.Signal.NEWNYM)
                time.sleep(5)  # Wait for new identity
            
            # Make request to check IP
            response = self.make_request('https://api.ipify.org?format=json')
            
            if response:
                ip_data = response.json()
                
                # Get additional info
                response2 = self.make_request('http://httpbin.org/user-agent')
                user_agent = None
                
                if response2:
                    ua_data = response2.json()
                    user_agent = ua_data.get('user-agent')
                
                identity = {
                    'ip': ip_data.get('ip'),
                    'user_agent': user_agent,
                    'timestamp': datetime.now().isoformat(),
                    'circuit_count': len(self.circuits)
                }
                
                logger.info(f"Current Tor identity: {identity['ip']}", module="tor_integration")
                return identity
            
            return None
            
        except Exception as e:
            logger.error(f"Get identity error: {e}", module="tor_integration")
            return None
    
    def renew_identity(self) -> bool:
        """Renew Tor identity (new circuit)"""
        try:
            if not self.controller:
                logger.error("Controller not connected", module="tor_integration")
                return False
            
            # Signal new identity
            self.controller.signal(stem.Signal.NEWNYM)
            
            # Clear old circuits
            with self.circuit_lock:
                circuits_to_close = []
                
                for circuit_id, circuit in self.circuits.items():
                    if not circuit.is_internal and circuit.status != CircuitStatus.CLOSED:
                        circuits_to_close.append(circuit_id)
                
                for circuit_id in circuits_to_close:
                    try:
                        self.controller.close_circuit(circuit_id)
                    except:
                        pass
                    
                    del self.circuits[circuit_id]
            
            # Create new circuits
            self._initialize_circuits()
            
            logger.info("Tor identity renewed", module="tor_integration")
            
            # Log audit event
            audit_log.log_event(
                event_type=AuditEventType.SYSTEM_CHANGE.value,
                severity=AuditSeverity.INFO.value,
                user='system',
                source_ip='127.0.0.1',
                description="Tor identity renewed",
                details={
                    'new_circuit_count': len(self.circuits),
                    'total_circuits_created': self.stats['total_circuits_created']
                },
                resource='tor_integration',
                action='renew_identity'
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Renew identity error: {e}", module="tor_integration")
            return False
    
    def add_bridge(self, bridge: str) -> bool:
        """Add Tor bridge"""
        try:
            if bridge not in self.bridges:
                self.bridges.append(bridge)
                
                logger.info(f"Added bridge: {bridge}", module="tor_integration")
                
                # Restart Tor to apply bridge
                if self.state == TorState.RUNNING:
                    return self.restart()
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Add bridge error: {e}", module="tor_integration")
            return False
    
    def test_connection(self) -> Dict[str, Any]:
        """Test Tor connection and performance"""
        results = {
            'tor_running': self.state == TorState.RUNNING,
            'controller_connected': self.controller is not None,
            'circuit_count': len(self.circuits),
            'active_circuits': sum(1 for c in self.circuits.values() 
                                 if c.status == CircuitStatus.BUILT),
            'test_results': {}
        }
        
        try:
            if self.state != TorState.RUNNING:
                results['error'] = 'Tor not running'
                return results
            
            # Test URLs
            test_urls = [
                ('https://check.torproject.org', 'Tor check'),
                ('https://api.ipify.org?format=json', 'IP check'),
                ('http://httpbin.org/ip', 'HTTP IP'),
                ('http://httpbin.org/user-agent', 'User agent')
            ]
            
            for url, name in test_urls:
                try:
                    start_time = time.time()
                    response = self.make_request(url, timeout=10)
                    elapsed = time.time() - start_time
                    
                    if response:
                        results['test_results'][name] = {
                            'success': True,
                            'status_code': response.status_code,
                            'time_seconds': elapsed,
                            'data': response.json() if 'json' in response.headers.get('content-type', '') 
                                   else response.text[:100]
                        }
                    else:
                        results['test_results'][name] = {
                            'success': False,
                            'error': 'No response'
                        }
                        
                except Exception as e:
                    results['test_results'][name] = {
                        'success': False,
                        'error': str(e)
                    }
            
            # Check if we're using Tor
            if 'Tor check' in results['test_results']:
                tor_check = results['test_results']['Tor check']
                if tor_check['success'] and 'data' in tor_check:
                    results['using_tor'] = 'Congratulations' in tor_check['data']
            
            logger.info(f"Connection test completed: {results['active_circuits']} active circuits", 
                       module="tor_integration")
            
            return results
            
        except Exception as e:
            logger.error(f"Connection test error: {e}", module="tor_integration")
            results['error'] = str(e)
            return results
    
    def _maintenance_loop(self):
        """Maintenance loop for Tor management"""
        while self.running:
            try:
                # Check Tor status
                if self.state == TorState.RUNNING:
                    # Renew circuits periodically
                    self._renew_old_circuits()
                    
                    # Clean up old sessions
                    self._cleanup_sessions()
                    
                    # Test connection periodically
                    if int(time.time()) % 3001:  # Every 5 minutes
                        self.test_connection()
                
                # Sleep
                time.sleep(60)
                
            except Exception as e:
                logger.error(f"Maintenance loop error: {e}", module="tor_integration")
                time.sleep(10)
    
    def _renew_old_circuits(self):
        """Renew old circuits"""
        try:
            with self.circuit_lock:
                circuits_to_renew = []
                
                for circuit_id, circuit in self.circuits.items():
                    # Skip internal circuits
                    if circuit.is_internal:
                        continue
                    
                    # Check age
                    if circuit.age > self.new_circuit_period:
                        circuits_to_renew.append(circuit_id)
                    
                    # Check idle time
                    elif circuit.idle_time > self.circuit_timeout:
                        circuits_to_renew.append(circuit_id)
                
                # Renew circuits
                for circuit_id in circuits_to_renew:
                    try:
                        if self.controller:
                            self.controller.close_circuit(circuit_id)
                    except:
                        pass
                    
                    del self.circuits[circuit_id]
                    
                    # Create new circuit
                    self.create_new_circuit()
                
                if circuits_to_renew:
                    logger.debug(f"Renewed {len(circuits_to_renew)} old circuits", 
                               module="tor_integration")
                    
        except Exception as e:
            logger.error(f"Renew circuits error: {e}", module="tor_integration")
    
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
                           module="tor_integration")
                
        except Exception as e:
            logger.error(f"Session cleanup error: {e}", module="tor_integration")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get Tor integration statistics"""
        uptime = (datetime.now() - self.stats['start_time']).total_seconds()
        
        # Circuit statistics
        circuit_stats = {
            'total': len(self.circuits),
            'built': sum(1 for c in self.circuits.values() if c.status == CircuitStatus.BUILT),
            'new': sum(1 for c in self.circuits.values() if c.status == CircuitStatus.NEW),
            'failed': sum(1 for c in self.circuits.values() if c.status == CircuitStatus.FAILED),
            'closed': sum(1 for c in self.circuits.values() if c.status == CircuitStatus.CLOSED),
            'internal': sum(1 for c in self.circuits.values() if c.is_internal)
        }
        
        return {
            **self.stats,
            'state': self.state.value,
            'uptime_seconds': uptime,
            'uptime_human': str(timedelta(seconds=int(uptime))),
            'circuit_stats': circuit_stats,
            'request_success_rate': (self.stats['successful_requests'] / self.stats['total_requests'] * 100 
                                   if self.stats['total_requests'] > 0 else 0),
            'data_transferred_mb': self.stats['total_bytes_received'] / 1024 / 1024,
            'session_count': len(self.sessions),
            'socks_port': self.socks_port,
            'control_port': self.control_port,
            'use_bridges': self.use_bridges,
            'bridge_count': len(self.bridges)
        }
    
    def get_detailed_statistics(self) -> Dict[str, Any]:
        """Get detailed statistics"""
        stats = self.get_statistics()
        
        # Add circuit details
        circuit_details = {}
        with self.circuit_lock:
            for circuit_id, circuit in self.circuits.items():
                circuit_details[circuit_id] = circuit.to_dict()
        
        stats['circuit_details'] = circuit_details
        
        return stats

# Global instance
_tor_integration = None

def get_tor_integration(config: Dict = None) -> TorIntegration:
    """Get or create Tor integration instance"""
    global _tor_integration
    
    if _tor_integration is None:
        _tor_integration = TorIntegration(config)
    
    return _tor_integration

if __name__ == "__main__":
    # Test Tor integration
    config = {
        'tor_data_dir': 'test_tor_data',
        'socks_port': 9050,
        'control_port': 9051,
        'use_bridges': False,
        'max_circuits': 5,
        'auto_start': True
    }
    
    ti = get_tor_integration(config)
    
    print("Testing Tor integration...")
    
    # Wait for Tor to start
    print("Waiting for Tor to start...")
    time.sleep(10)
    
    if ti.state != TorState.RUNNING:
        print("❌ Tor failed to start")
        ti.stop()
        sys.exit(1)
    
    print("✅ Tor started successfully")
    
    # Test connection
    print("\nTesting connection...")
    test_results = ti.test_connection()
    
    print(f"Tor running: {test_results['tor_running']}")
    print(f"Controller connected: {test_results['controller_connected']}")
    print(f"Active circuits: {test_results['active_circuits']}")
    
    if test_results.get('using_tor'):
        print("✅ Successfully using Tor network")
    else:
        print("❌ Not using Tor network")
    
    # Get current identity
    print("\nGetting current identity...")
    identity = ti.get_identity()
    if identity:
        print(f"Current IP: {identity['ip']}")
        print(f"User Agent: {identity['user_agent']}")
    
    # Make test request
    print("\nMaking test request...")
    response = ti.make_request('http://httpbin.org/ip')
    if response:
        print(f"Test request successful: {response.json()}")
    else:
        print("Test request failed")
    
    # Get statistics
    print("\n📊 Tor Integration Statistics:")
    stats = ti.get_detailed_statistics()
    print(f"  State: {stats['state']}")
    print(f"  Uptime: {stats['uptime_human']}")
    print(f"  Total circuits created: {stats['total_circuits_created']}")
    print(f"  Active circuits: {stats['circuit_stats']['built']}")
    print(f"  Total requests: {stats['total_requests']}")
    print(f"  Success rate: {stats['request_success_rate']:.1f}%")
    print(f"  Data transferred: {stats['data_transferred_mb']:.2f} MB")
    
    # Stop Tor
    print("\nStopping Tor...")
    ti.stop()
    
    print("\n✅ Tor integration tests completed!")
