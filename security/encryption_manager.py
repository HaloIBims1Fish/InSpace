#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
encryption_manager.py - Advanced Encryption Key Management System
"""

import os
import sys
import json
import base64
import hashlib
import secrets
import struct
import tempfile
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime, timedelta
from pathlib import Path

# Cryptography imports
from cryptography.fernet import Fernet, MultiFernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding, ec
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.primitives.keywrap import aes_key_wrap, aes_key_unwrap
from cryptography.hazmat.backends import default_backend

# Import logger
from ..utils.logger import get_logger

logger = get_logger()

class KeyType(Enum):
    """Key types"""
    SYMMETRIC = "symmetric"
    ASYMMETRIC = "asymmetric"
    SESSION = "session"
    MASTER = "master"
    DATA = "data"
    COMMUNICATION = "communication"

class KeyStatus(Enum):
    """Key status"""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    COMPROMISED = "compromised"
    PENDING = "pending"

class KeyRotationPolicy:
    """Key rotation policy"""
    
    def __init__(self, 
                 rotation_days: int = 90,
                 grace_period_days: int = 7,
                 max_keys_per_type: int = 5,
                 auto_rotate: bool = True,
                 archive_old_keys: bool = True):
        self.rotation_days = rotation_days
        self.grace_period_days = grace_period_days
        self.max_keys_per_type = max_keys_per_type
        self.auto_rotate = auto_rotate
        self.archive_old_keys = archive_old_keys

class EncryptionManager:
    """Advanced encryption key management system"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # Key storage
        self.keys_dir = self.config.get('keys_dir', 'security/keys')
        self.key_registry_file = os.path.join(self.keys_dir, 'registry.json')
        self.master_key_file = os.path.join(self.keys_dir, 'master.key')
        
        # Create directories
        os.makedirs(self.keys_dir, exist_ok=True)
        
        # Load key registry
        self.key_registry = self._load_key_registry()
        
        # Initialize master key
        self.master_key = self._get_master_key()
        
        # Key rotation policies
        self.rotation_policies = {
            KeyType.SESSION.value: KeyRotationPolicy(rotation_days=1, max_keys_per_type=10),
            KeyType.COMMUNICATION.value: KeyRotationPolicy(rotation_days=30),
            KeyType.DATA.value: KeyRotationPolicy(rotation_days=180),
            KeyType.MASTER.value: KeyRotationPolicy(rotation_days=365, auto_rotate=False)
        }
        
        # Cache for performance
        self.key_cache = {}
        
        logger.info("Encryption manager initialized", module="encryption_manager")
    
    def _load_key_registry(self) -> Dict[str, Any]:
        """Load key registry from file"""
        try:
            if os.path.exists(self.key_registry_file):
                with open(self.key_registry_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading key registry: {e}", module="encryption_manager")
        
        return {
            'keys': {},
            'metadata': {
                'created': datetime.now().isoformat(),
                'version': '1.0',
                'total_keys': 0
            }
        }
    
    def _save_key_registry(self):
        """Save key registry to file"""
        try:
            with open(self.key_registry_file, 'w') as f:
                json.dump(self.key_registry, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving key registry: {e}", module="encryption_manager")
    
    def _get_master_key(self) -> Optional[bytes]:
        """Get or generate master key"""
        try:
            if os.path.exists(self.master_key_file):
                with open(self.master_key_file, 'rb') as f:
                    encrypted_key = f.read()
                
                # Decrypt with passphrase (in production, use KMS or HSM)
                passphrase = self.config.get('master_key_passphrase', 
                                           os.environ.get('MASTER_KEY_PASSPHRASE', 'default_master_key'))
                
                # Derive key from passphrase
                salt = b'master_key_salt'
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=salt,
                    iterations=100000,
                    backend=default_backend()
                )
                key = kdf.derive(passphrase.encode())
                
                # Use first 32 bytes as AES key
                cipher = Cipher(algorithms.AES(key[:32]), modes.CBC(salt), backend=default_backend())
                decryptor = cipher.decryptor()
                
                # Decrypt (simple implementation - in production use proper authenticated encryption)
                decrypted = decryptor.update(encrypted_key) + decryptor.finalize()
                
                # Remove padding
                padding_length = decrypted[-1]
                return decrypted[:-padding_length]
            else:
                # Generate new master key
                master_key = secrets.token_bytes(32)
                
                # Encrypt and save
                passphrase = self.config.get('master_key_passphrase', 
                                           os.environ.get('MASTER_KEY_PASSPHRASE', 'default_master_key'))
                
                salt = b'master_key_salt'
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=salt,
                    iterations=100000,
                    backend=default_backend()
                )
                key = kdf.derive(passphrase.encode())
                
                # Pad to block size
                padding_length = 16 - (len(master_key) % 16)
                padded_key = master_key + bytes([padding_length] * padding_length)
                
                cipher = Cipher(algorithms.AES(key[:32]), modes.CBC(salt), backend=default_backend())
                encryptor = cipher.encryptor()
                encrypted = encryptor.update(padded_key) + encryptor.finalize()
                
                with open(self.master_key_file, 'wb') as f:
                    f.write(encrypted)
                
                logger.info("New master key generated and saved", module="encryption_manager")
                return master_key
                
        except Exception as e:
            logger.error(f"Error with master key: {e}", module="encryption_manager")
            return None
    
    def generate_symmetric_key(self, key_type: str = KeyType.DATA.value,
                              key_size: int = 32,
                              metadata: Dict[str, Any] = None) -> Optional[str]:
        """Generate symmetric encryption key"""
        try:
            # Generate key
            key_bytes = secrets.token_bytes(key_size)
            
            # Generate key ID
            key_id = self._generate_key_id(key_type)
            
            # Encrypt key with master key
            encrypted_key = self._encrypt_with_master_key(key_bytes)
            
            if not encrypted_key:
                return None
            
            # Create key record
            key_record = {
                'id': key_id,
                'type': key_type,
                'algorithm': 'AES-256' if key_size == 32 else f'AES-{key_size*8}',
                'key_size': key_size,
                'encrypted_key': base64.b64encode(encrypted_key).decode(),
                'created': datetime.now().isoformat(),
                'expires': (datetime.now() + timedelta(days=365)).isoformat(),
                'status': KeyStatus.ACTIVE.value,
                'metadata': metadata or {},
                'usage_count': 0,
                'last_used': None,
                'tags': []
            }
            
            # Save to registry
            self.key_registry['keys'][key_id] = key_record
            self.key_registry['metadata']['total_keys'] = len(self.key_registry['keys'])
            self._save_key_registry()
            
            # Cache plaintext key
            self.key_cache[key_id] = key_bytes
            
            logger.info(f"Symmetric key generated: {key_id}", module="encryption_manager")
            return key_id
            
        except Exception as e:
            logger.error(f"Error generating symmetric key: {e}", module="encryption_manager")
            return None
    
    def generate_asymmetric_keypair(self, key_type: str = KeyType.COMMUNICATION.value,
                                  key_size: int = 2048,
                                  metadata: Dict[str, Any] = None) -> Optional[Tuple[str, str]]:
        """Generate asymmetric key pair"""
        try:
            # Generate RSA key pair
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=key_size,
                backend=default_backend()
            )
            
            public_key = private_key.public_key()
            
            # Serialize keys
            private_bytes = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            
            public_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            
            # Generate key IDs
            private_key_id = self._generate_key_id(f"{key_type}_private")
            public_key_id = self._generate_key_id(f"{key_type}_public")
            
            # Encrypt private key with master key
            encrypted_private = self._encrypt_with_master_key(private_bytes)
            
            if not encrypted_private:
                return None
            
            # Create key records
            private_record = {
                'id': private_key_id,
                'type': f"{key_type}_private",
                'algorithm': f'RSA-{key_size}',
                'key_size': key_size,
                'encrypted_key': base64.b64encode(encrypted_private).decode(),
                'public_key_id': public_key_id,
                'created': datetime.now().isoformat(),
                'expires': (datetime.now() + timedelta(days=365)).isoformat(),
                'status': KeyStatus.ACTIVE.value,
                'metadata': metadata or {},
                'usage_count': 0,
                'last_used': None,
                'tags': ['private']
            }
            
            public_record = {
                'id': public_key_id,
                'type': f"{key_type}_public",
                'algorithm': f'RSA-{key_size}',
                'key_size': key_size,
                'public_key': base64.b64encode(public_bytes).decode(),
                'private_key_id': private_key_id,
                'created': datetime.now().isoformat(),
                'expires': (datetime.now() + timedelta(days=365)).isoformat(),
                'status': KeyStatus.ACTIVE.value,
                'metadata': metadata or {},
                'usage_count': 0,
                'last_used': None,
                'tags': ['public']
            }
            
            # Save to registry
            self.key_registry['keys'][private_key_id] = private_record
            self.key_registry['keys'][public_key_id] = public_record
            self.key_registry['metadata']['total_keys'] = len(self.key_registry['keys'])
            self._save_key_registry()
            
            # Cache keys
            self.key_cache[private_key_id] = private_key
            self.key_cache[public_key_id] = public_key
            
            logger.info(f"Asymmetric key pair generated: {private_key_id}, {public_key_id}", 
                       module="encryption_manager")
            return private_key_id, public_key_id
            
        except Exception as e:
            logger.error(f"Error generating asymmetric keys: {e}", module="encryption_manager")
            return None
    
    def generate_ec_keypair(self, curve: str = 'secp256r1',
                          metadata: Dict[str, Any] = None) -> Optional[Tuple[str, str]]:
        """Generate Elliptic Curve key pair"""
        try:
            # Select curve
            if curve == 'secp256r1':
                ec_curve = ec.SECP256R1()
            elif curve == 'secp384r1':
                ec_curve = ec.SECP384R1()
            elif curve == 'secp521r1':
                ec_curve = ec.SECP521R1()
            else:
                ec_curve = ec.SECP256R1()
            
            # Generate key pair
            private_key = ec.generate_private_key(ec_curve, default_backend())
            public_key = private_key.public_key()
            
            # Serialize keys
            private_bytes = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            
            public_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            
            # Generate key IDs
            private_key_id = self._generate_key_id('ec_private')
            public_key_id = self._generate_key_id('ec_public')
            
            # Encrypt private key
            encrypted_private = self._encrypt_with_master_key(private_bytes)
            
            if not encrypted_private:
                return None
            
            # Create key records
            private_record = {
                'id': private_key_id,
                'type': 'ec_private',
                'algorithm': f'EC-{curve}',
                'curve': curve,
                'encrypted_key': base64.b64encode(encrypted_private).decode(),
                'public_key_id': public_key_id,
                'created': datetime.now().isoformat(),
                'expires': (datetime.now() + timedelta(days=365)).isoformat(),
                'status': KeyStatus.ACTIVE.value,
                'metadata': metadata or {},
                'usage_count': 0,
                'last_used': None,
                'tags': ['private', 'ec']
            }
            
            public_record = {
                'id': public_key_id,
                'type': 'ec_public',
                'algorithm': f'EC-{curve}',
                'curve': curve,
                'public_key': base64.b64encode(public_bytes).decode(),
                'private_key_id': private_key_id,
                'created': datetime.now().isoformat(),
                'expires': (datetime.now() + timedelta(days=365)).isoformat(),
                'status': KeyStatus.ACTIVE.value,
                'metadata': metadata or {},
                'usage_count': 0,
                'last_used': None,
                'tags': ['public', 'ec']
            }
            
            # Save to registry
            self.key_registry['keys'][private_key_id] = private_record
            self.key_registry['keys'][public_key_id] = public_record
            self.key_registry['metadata']['total_keys'] = len(self.key_registry['keys'])
            self._save_key_registry()
            
            # Cache keys
            self.key_cache[private_key_id] = private_key
            self.key_cache[public_key_id] = public_key
            
            logger.info(f"EC key pair generated: {private_key_id}, {public_key_id}", 
                       module="encryption_manager")
            return private_key_id, public_key_id
            
        except Exception as e:
            logger.error(f"Error generating EC keys: {e}", module="encryption_manager")
            return None
    
    def get_key(self, key_id: str, decrypt: bool = True) -> Optional[Any]:
        """Get key by ID"""
        try:
            # Check cache first
            if key_id in self.key_cache:
                return self.key_cache[key_id]
            
            # Check registry
            if key_id not in self.key_registry['keys']:
                logger.warning(f"Key not found: {key_id}", module="encryption_manager")
                return None
            
            key_record = self.key_registry['keys'][key_id]
            
            # Check key status
            if key_record['status'] != KeyStatus.ACTIVE.value:
                logger.warning(f"Key not active: {key_id} ({key_record['status']})", 
                             module="encryption_manager")
                return None
            
            # Check expiry
            expires = datetime.fromisoformat(key_record['expires'])
            if datetime.now() > expires:
                logger.warning(f"Key expired: {key_id}", module="encryption_manager")
                key_record['status'] = KeyStatus.EXPIRED.value
                self._save_key_registry()
                return None
            
            # Update usage stats
            key_record['usage_count'] = key_record.get('usage_count', 0) + 1
            key_record['last_used'] = datetime.now().isoformat()
            self._save_key_registry()
            
            if not decrypt:
                return key_record
            
            # Decrypt key if needed
            if 'encrypted_key' in key_record:
                encrypted_data = base64.b64decode(key_record['encrypted_key'])
                decrypted_bytes = self._decrypt_with_master_key(encrypted_data)
                
                if not decrypted_bytes:
                    return None
                
                # Parse key based on type
                key_type = key_record['type']
                
                if 'private' in key_type:
                    if 'ec' in key_type:
                        key = serialization.load_pem_private_key(
                            decrypted_bytes,
                            password=None,
                            backend=default_backend()
                        )
                    else:
                        key = serialization.load_pem_private_key(
                            decrypted_bytes,
                            password=None,
                            backend=default_backend()
                        )
                elif 'public' in key_type:
                    if 'ec' in key_type:
                        key = serialization.load_pem_public_key(
                            decrypted_bytes,
                            backend=default_backend()
                        )
                    else:
                        key = serialization.load_pem_public_key(
                            decrypted_bytes,
                            backend=default_backend()
                        )
                else:
                    # Symmetric key
                    key = decrypted_bytes
                
                # Cache for future use
                self.key_cache[key_id] = key
                return key
            
            elif 'public_key' in key_record:
                # Public key (not encrypted)
                public_bytes = base64.b64decode(key_record['public_key'])
                
                if 'ec' in key_record['type']:
                    key = serialization.load_pem_public_key(
                        public_bytes,
                        backend=default_backend()
                    )
                else:
                    key = serialization.load_pem_public_key(
                        public_bytes,
                        backend=default_backend()
                    )
                
                self.key_cache[key_id] = key
                return key
            
            else:
                logger.error(f"Invalid key record: {key_id}", module="encryption_manager")
                return None
            
        except Exception as e:
            logger.error(f"Error getting key: {e}", module="encryption_manager")
            return None
    
    def encrypt_data(self, data: bytes, key_id: str, 
                    algorithm: str = 'AES-GCM') -> Optional[bytes]:
        """Encrypt data with specified key"""
        try:
            key = self.get_key(key_id)
            if not key:
                return None
            
            if isinstance(key, bytes):
                # Symmetric encryption
                if algorithm == 'AES-GCM':
                    return self._encrypt_aes_gcm(data, key)
                elif algorithm == 'AES-CBC':
                    return self._encrypt_aes_cbc(data, key)
                elif algorithm == 'Fernet':
                    f = Fernet(base64.urlsafe_b64encode(key))
                    return f.encrypt(data)
                else:
                    logger.error(f"Unsupported algorithm: {algorithm}", module="encryption_manager")
                    return None
            
            elif hasattr(key, 'public_bytes'):
                # Asymmetric encryption (RSA or EC)
                if isinstance(key, rsa.RSAPublicKey):
                    return self._encrypt_rsa(data, key)
                elif isinstance(key, ec.EllipticCurvePublicKey):
                    return self._encrypt_ec(data, key)
                else:
                    logger.error(f"Unsupported key type: {type(key)}", module="encryption_manager")
                    return None
            
            else:
                logger.error(f"Unknown key type: {key_id}", module="encryption_manager")
                return None
            
        except Exception as e:
            logger.error(f"Encryption error: {e}", module="encryption_manager")
            return None
    
    def decrypt_data(self, encrypted_data: bytes, key_id: str,
                    algorithm: str = 'AES-GCM') -> Optional[bytes]:
        """Decrypt data with specified key"""
        try:
            key = self.get_key(key_id)
            if not key:
                return None
            
            if isinstance(key, bytes):
                # Symmetric decryption
                if algorithm == 'AES-GCM':
                    return self._decrypt_aes_gcm(encrypted_data, key)
                elif algorithm == 'AES-CBC':
                    return self._decrypt_aes_cbc(encrypted_data, key)
                elif algorithm == 'Fernet':
                    f = Fernet(base64.urlsafe_b64encode(key))
                    return f.decrypt(encrypted_data)
                else:
                    logger.error(f"Unsupported algorithm: {algorithm}", module="encryption_manager")
                    return None
            
            elif hasattr(key, 'private_bytes'):
                # Asymmetric decryption
                if isinstance(key, rsa.RSAPrivateKey):
                    return self._decrypt_rsa(encrypted_data, key)
                elif isinstance(key, ec.EllipticCurvePrivateKey):
                    return self._decrypt_ec(encrypted_data, key)
                else:
                    logger.error(f"Unsupported key type: {type(key)}", module="encryption_manager")
                    return None
            
            else:
                logger.error(f"Unknown key type: {key_id}", module="encryption_manager")
                return None
            
        except Exception as e:
            logger.error(f"Decryption error: {e}", module="encryption_manager")
            return None
    
    def _encrypt_aes_gcm(self, data: bytes, key: bytes) -> bytes:
        """Encrypt with AES-GCM"""
        iv = secrets.token_bytes(12)  # 96-bit IV for GCM
        cipher = Cipher(algorithms.AES(key), modes.GCM(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        encrypted = encryptor.update(data) + encryptor.finalize()
        return iv + encryptor.tag + encrypted
    
    def _decrypt_aes_gcm(self, encrypted_data: bytes, key: bytes) -> Optional[bytes]:
        """Decrypt AES-GCM"""
        try:
            iv = encrypted_data[:12]
            tag = encrypted_data[12:28]
            ciphertext = encrypted_data[28:]
            
            cipher = Cipher(algorithms.AES(key), modes.GCM(iv, tag), backend=default_backend())
            decryptor = cipher.decryptor()
            return decryptor.update(ciphertext) + decryptor.finalize()
        except Exception as e:
            logger.error(f"AES-GCM decryption failed: {e}", module="encryption_manager")
            return None
    
    def _encrypt_aes_cbc(self, data: bytes, key: bytes) -> bytes:
        """Encrypt with AES-CBC"""
        iv = secrets.token_bytes(16)
        
        # Pad data to block size
        block_size = 16
        padding_length = block_size - (len(data) % block_size)
        padded_data = data + bytes([padding_length] * padding_length)
        
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        encrypted = encryptor.update(padded_data) + encryptor.finalize()
        return iv + encrypted
    
    def _decrypt_aes_cbc(self, encrypted_data: bytes, key: bytes) -> Optional[bytes]:
        """Decrypt AES-CBC"""
        try:
            iv = encrypted_data[:16]
            ciphertext = encrypted_data[16:]
            
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
            decryptor = cipher.decryptor()
            padded = decryptor.update(ciphertext) + decryptor.finalize()
            
            # Remove padding
            padding_length = padded[-1]
            return padded[:-padding_length]
        except Exception as e:
            logger.error(f"AES-CBC decryption failed: {e}", module="encryption_manager")
            return None
    
    def _encrypt_rsa(self, data: bytes, public_key: rsa.RSAPublicKey) -> bytes:
        """Encrypt with RSA"""
        # RSA can only encrypt small amounts of data
        # For larger data, use hybrid encryption
        max_size = public_key.key_size // 8 - 42  # OAEP padding
        
        if len(data) <= max_size:
            return public_key.encrypt(
                data,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
        else:
            # Generate session key for hybrid encryption
            session_key = secrets.token_bytes(32)
            
            # Encrypt data with session key
            encrypted_data = self._encrypt_aes_gcm(data, session_key)
            
            # Encrypt session key with RSA
            encrypted_key = public_key.encrypt(
                session_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            # Combine
            return struct.pack('!I', len(encrypted_key)) + encrypted_key + encrypted_data
    
    def _decrypt_rsa(self, encrypted_data: bytes, private_key: rsa.RSAPrivateKey) -> Optional[bytes]:
        """Decrypt RSA"""
        try:
            # Check if it's hybrid encryption
            if len(encrypted_data) > 256:  # RSA encrypted data is small
                key_len = struct.unpack('!I', encrypted_data[:4])[0]
                encrypted_key = encrypted_data[4:4+key_len]
                encrypted_data = encrypted_data[4+key_len:]
                
                # Decrypt session key
                session_key = private_key.decrypt(
                    encrypted_key,
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None
                    )
                )
                
                # Decrypt data with session key
                return self._decrypt_aes_gcm(encrypted_data, session_key)
            else:
                # Direct RSA decryption
                return private_key.decrypt(
                    encrypted_data,
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None
                    )
                )
        except Exception as e:
            logger.error(f"RSA decryption failed: {e}", module="encryption_manager")
            return None
    
    def _encrypt_ec(self, data: bytes, public_key: ec.EllipticCurvePublicKey) -> bytes:
        """Encrypt with Elliptic Curve"""
        # EC doesn't support direct encryption, use ECDH for key exchange
        # Generate ephemeral key pair
        ephemeral_private = ec.generate_private_key(public_key.curve, default_backend())
        ephemeral_public = ephemeral_private.public_key()
        
        # Derive shared secret
        shared_secret = ephemeral_private.exchange(ec.ECDH(), public_key)
        
        # Derive encryption key from shared secret
        kdf = hashes.Hash(hashes.SHA256(), backend=default_backend())
        kdf.update(shared_secret)
        encryption_key = kdf.finalize()[:32]
        
        # Encrypt data
        encrypted_data = self._encrypt_aes_gcm(data, encryption_key)
        
        # Serialize ephemeral public key
        ephemeral_public_bytes = ephemeral_public.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint
        )
        
        return ephemeral_public_bytes + encrypted_data
    
    def _decrypt_ec(self, encrypted_data: bytes, private_key: ec.EllipticCurvePrivateKey) -> Optional[bytes]:
        """Decrypt Elliptic Curve"""
        try:
            # Extract ephemeral public key
            curve = private_key.curve
            point_size = {
                ec.SECP256R1: 65,  # 1 byte prefix + 32 bytes x + 32 bytes y
                ec.SECP384R1: 97,
                ec.SECP521R1: 133
            }.get(type(curve), 65)
            
            ephemeral_public_bytes = encrypted_data[:point_size]
            encrypted_data = encrypted_data[point_size:]
            
            # Load ephemeral public key
            ephemeral_public = ec.EllipticCurvePublicKey.from_encoded_point(
                curve,
                ephemeral_public_bytes
            )
            
            # Derive shared secret
            shared_secret = private_key.exchange(ec.ECDH(), ephemeral_public)
            
            # Derive encryption key
            kdf = hashes.Hash(hashes.SHA256(), backend=default_backend())
            kdf.update(shared_secret)
            encryption_key = kdf.finalize()[:32]
            
            # Decrypt data
            return self._decrypt_aes_gcm(encrypted_data, encryption_key)
        except Exception as e:
            logger.error(f"EC decryption failed: {e}", module="encryption_manager")
            return None
    
    def _encrypt_with_master_key(self, data: bytes) -> Optional[bytes]:
        """Encrypt data with master key"""
        if not self.master_key:
            return None
        
        return self._encrypt_aes_gcm(data, self.master_key)
    
    def _decrypt_with_master_key(self, encrypted_data: bytes) -> Optional[bytes]:
        """Decrypt data with master key"""
        if not self.master_key:
            return None
        
        return self._decrypt_aes_gcm(encrypted_data, self.master_key)
    
    def _generate_key_id(self, key_type: str) -> str:
        """Generate unique key ID"""
        timestamp = int(datetime.now().timestamp() * 1000)
        random_part = secrets.token_hex(4)
        return f"{key_type}_{timestamp}_{random_part}"
    
    def rotate_keys(self, key_type: str = None) -> Dict[str, List[str]]:
        """Rotate keys based on policy"""
        try:
            rotated = {}
            
            for key_id, key_record in list(self.key_registry['keys'].items()):
                # Filter by type if specified
                if key_type and key_record['type'] != key_type:
                    continue
                
                # Get policy for this key type
                policy = self.rotation_policies.get(key_record['type'])
                if not policy or not policy.auto_rotate:
                    continue
                
                # Check if key needs rotation
                created = datetime.fromisoformat(key_record['created'])
                rotation_cutoff = datetime.now() - timedelta(days=policy.rotation_days)
                
                if created < rotation_cutoff and key_record['status'] == KeyStatus.ACTIVE.value:
                    # Mark old key as expired
                    key_record['status'] = KeyStatus.EXPIRED.value
                    
                    # Generate new key
                    if 'private' in key_record['type'] or 'public' in key_record['type']:
                        # Asymmetric key - need to generate new pair
                        if 'ec' in key_record['type']:
                            curve = key_record.get('curve', 'secp256r1')
                            new_private_id, new_public_id = self.generate_ec_keypair(
                                curve=curve,
                                metadata=key_record['metadata']
                            )
                        else:
                            key_size = key_record.get('key_size', 2048)
                            new_private_id, new_public_id = self.generate_asymmetric_keypair(
                                key_type=key_record['type'].replace('_private', '').replace('_public', ''),
                                key_size=key_size,
                                metadata=key_record['metadata']
                            )
                        
                        if new_private_id and new_public_id:
                            key_type_str = key_record['type'].split('_')[0]
                            if key_type_str not in rotated:
                                rotated[key_type_str] = []
                            rotated[key_type_str].extend([new_private_id, new_public_id])
                    else:
                        # Symmetric key
                        key_size = key_record.get('key_size', 32)
                        new_key_id = self.generate_symmetric_key(
                            key_type=key_record['type'],
                            key_size=key_size,
                            metadata=key_record['metadata']
                        )
                        
                        if new_key_id:
                            if key_record['type'] not in rotated:
                                rotated[key_record['type']] = []
                            rotated[key_record['type']].append(new_key_id)
            
            self._save_key_registry()
            
            if rotated:
                logger.info(f"Keys rotated: {rotated}", module="encryption_manager")
            
            return rotated
            
        except Exception as e:
            logger.error(f"Key rotation error: {e}", module="encryption_manager")
            return {}
    
    def revoke_key(self, key_id: str, reason: str = "manual_revocation") -> bool:
        """Revoke a key"""
        try:
            if key_id not in self.key_registry['keys']:
                return False
            
            key_record = self.key_registry['keys'][key_id]
            key_record['status'] = KeyStatus.REVOKED.value
            key_record['revoked_at'] = datetime.now().isoformat()
            key_record['revocation_reason'] = reason
            
            # Clear from cache
            if key_id in self.key_cache:
                del self.key_cache[key_id]
            
            self._save_key_registry()
            
            logger.info(f"Key revoked: {key_id} ({reason})", module="encryption_manager")
            return True
            
        except Exception as e:
            logger.error(f"Key revocation error: {e}", module="encryption_manager")
            return False
    
    def get_key_status(self, key_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed status of a key"""
        try:
            if key_id not in self.key_registry['keys']:
                return None
            
            key_record = self.key_registry['keys'][key_id]
            
            # Calculate days until expiry
            expires = datetime.fromisoformat(key_record['expires'])
            days_until_expiry = (expires - datetime.now()).days
            
            # Check if rotation is needed
            created = datetime.fromisoformat(key_record['created'])
            policy = self.rotation_policies.get(key_record['type'])
            days_since_creation = (datetime.now() - created).days
            
            rotation_needed = False
            if policy:
                rotation_needed = days_since_creation > policy.rotation_days
            
            return {
                'id': key_id,
                'type': key_record['type'],
                'status': key_record['status'],
                'created': key_record['created'],
                'expires': key_record['expires'],
                'days_until_expiry': days_until_expiry,
                'usage_count': key_record.get('usage_count', 0),
                'last_used': key_record.get('last_used'),
                'algorithm': key_record.get('algorithm'),
                'key_size': key_record.get('key_size'),
                'rotation_needed': rotation_needed,
                'tags': key_record.get('tags', [])
            }
            
        except Exception as e:
            logger.error(f"Error getting key status: {e}", module="encryption_manager")
            return None
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get encryption system status"""
        try:
            # Count keys by type and status
            key_stats = {}
            for key_record in self.key_registry['keys'].values():
                key_type = key_record['type']
                status = key_record['status']
                
                if key_type not in key_stats:
                    key_stats[key_type] = {}
                
                if status not in key_stats[key_type]:
                    key_stats[key_type][status] = 0
                
                key_stats[key_type][status] += 1
            
            # Check for keys needing rotation
            keys_needing_rotation = []
            for key_id, key_record in self.key_registry['keys'].items():
                if key_record['status'] != KeyStatus.ACTIVE.value:
                    continue
                
                created = datetime.fromisoformat(key_record['created'])
                policy = self.rotation_policies.get(key_record['type'])
                
                if policy:
                    days_since_creation = (datetime.now() - created).days
                    if days_since_creation > policy.rotation_days:
                        keys_needing_rotation.append(key_id)
            
            return {
                'total_keys': len(self.key_registry['keys']),
                'key_stats': key_stats,
                'keys_needing_rotation': len(keys_needing_rotation),
                'master_key_available': self.master_key is not None,
                'cache_size': len(self.key_cache),
                'rotation_policies': {
                    k: {
                        'rotation_days': v.rotation_days,
                        'auto_rotate': v.auto_rotate
                    }
                    for k, v in self.rotation_policies.items()
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting system status: {e}", module="encryption_manager")
            return {}

# Global instance
_encryption_manager = None

def get_encryption_manager(config: Dict = None) -> EncryptionManager:
    """Get or create encryption manager instance"""
    global _encryption_manager
    
    if _encryption_manager is None:
        _encryption_manager = EncryptionManager(config)
    
    return _encryption_manager

if __name__ == "__main__":
    # Test encryption manager
    config = {
        'master_key_passphrase': 'test_passphrase_123!'
    }
    
    em = get_encryption_manager(config)
    
    print("Testing encryption manager...")
    
    # Generate symmetric key
    sym_key_id = em.generate_symmetric_key(
        key_type='test_data',
        key_size=32,
        metadata={'purpose': 'test'}
    )
    print(f"Symmetric key generated: {sym_key_id}")
    
    # Generate RSA key pair
    rsa_private_id, rsa_public_id = em.generate_asymmetric_keypair(
        key_type='test_comm',
        key_size=2048,
        metadata={'purpose': 'test_communication'}
    )
    print(f"RSA key pair generated: {rsa_private_id}, {rsa_public_id}")
    
    # Generate EC key pair
    ec_private_id, ec_public_id = em.generate_ec_keypair(
        curve='secp256r1',
        metadata={'purpose': 'test_ec'}
    )
    print(f"EC key pair generated: {ec_private_id}, {ec_public_id}")
    
    # Test symmetric encryption
    test_data = b"Hello, this is a secret message!"
    encrypted = em.encrypt_data(test_data, sym_key_id, 'AES-GCM')
    decrypted = em.decrypt_data(encrypted, sym_key_id, 'AES-GCM')
    
    print(f"\nSymmetric encryption test:")
    print(f"Original: {test_data}")
    print(f"Encrypted: {len(encrypted)} bytes")
    print(f"Decrypted: {decrypted}")
    print(f"Match: {test_data == decrypted}")
    
    # Test RSA encryption
    rsa_encrypted = em.encrypt_data(test_data, rsa_public_id)
    rsa_decrypted = em.decrypt_data(rsa_encrypted, rsa_private_id)
    
    print(f"\nRSA encryption test:")
    print(f"Encrypted: {len(rsa_encrypted)} bytes")
    print(f"Decrypted: {rsa_decrypted}")
    print(f"Match: {test_data == rsa_decrypted}")
    
    # Test EC encryption
    ec_encrypted = em.encrypt_data(test_data, ec_public_id)
    ec_decrypted = em.decrypt_data(ec_encrypted, ec_private_id)
    
    print(f"\nEC encryption test:")
    print(f"Encrypted: {len(ec_encrypted)} bytes")
    print(f"Decrypted: {ec_decrypted}")
    print(f"Match: {test_data == ec_decrypted}")
    
    # Get key status
    key_status = em.get_key_status(sym_key_id)
    print(f"\nKey status for {sym_key_id}:")
    print(f"  Type: {key_status['type']}")
    print(f"  Status: {key_status['status']}")
    print(f"  Algorithm: {key_status['algorithm']}")
    print(f"  Usage count: {key_status['usage_count']}")
    
    # Get system status
    system_status = em.get_system_status()
    print(f"\n🔐 Encryption System Status:")
    print(f"  Total keys: {system_status['total_keys']}")
    print(f"  Master key available: {system_status['master_key_available']}")
    print(f"  Keys needing rotation: {system_status['keys_needing_rotation']}")
    
    # Cleanup test keys
    em.revoke_key(sym_key_id, "test_complete")
    em.revoke_key(rsa_private_id, "test_complete")
    em.revoke_key(rsa_public_id, "test_complete")
    em.revoke_key(ec_private_id, "test_complete")
    em.revoke_key(ec_public_id, "test_complete")
    
    print("\n✅ Encryption manager tests completed!")
