#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
authentication.py - Multi-Factor Authentication System
"""

import os
import sys
import hashlib
import hmac
import base64
import json
import time
import secrets
import uuid
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Import logger
from ..utils.logger import get_logger

logger = get_logger()

class AuthenticationSystem:
    """Multi-factor authentication system for bot commands"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # Storage for users and sessions
        self.users_file = self.config.get('users_file', 'data/users.json')
        self.sessions_file = self.config.get('sessions_file', 'data/sessions.json')
        self.mfa_codes_file = self.config.get('mfa_codes_file', 'data/mfa_codes.json')
        
        # Load or initialize data
        self.users = self._load_data(self.users_file, {})
        self.sessions = self._load_data(self.sessions_file, {})
        self.mfa_codes = self._load_data(self.mfa_codes_file, {})
        
        # Security settings
        self.session_timeout = self.config.get('session_timeout', 3600)  # 1 hour
        self.max_login_attempts = self.config.get('max_login_attempts', 5)
        self.lockout_duration = self.config.get('lockout_duration', 300)  # 5 minutes
        self.mfa_code_expiry = self.config.get('mfa_code_expiry', 300)  # 5 minutes
        
        # Telegram bot for MFA notifications
        self.telegram_bot = None
        self.setup_telegram()
        
        # Initialize encryption for sensitive data
        self.encryption_key = self._get_encryption_key()
        self.cipher = Fernet(self.encryption_key) if self.encryption_key else None
        
        logger.info("Authentication system initialized", module="authentication")
    
    def _load_data(self, filename: str, default: Any) -> Any:
        """Load JSON data from file"""
        try:
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading {filename}: {e}", module="authentication")
        
        return default
    
    def _save_data(self, filename: str, data: Any):
        """Save JSON data to file"""
        try:
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving {filename}: {e}", module="authentication")
    
    def _get_encryption_key(self) -> Optional[bytes]:
        """Get or generate encryption key"""
        key_file = self.config.get('encryption_key_file', 'security/encryption.key')
        
        try:
            if os.path.exists(key_file):
                with open(key_file, 'rb') as f:
                    return f.read()
            else:
                # Generate new key
                key = Fernet.generate_key()
                os.makedirs(os.path.dirname(key_file), exist_ok=True)
                with open(key_file, 'wb') as f:
                    f.write(key)
                return key
        except Exception as e:
            logger.error(f"Error with encryption key: {e}", module="authentication")
            return None
    
    def setup_telegram(self):
        """Setup Telegram bot for MFA notifications"""
        telegram_config = self.config.get('telegram', {})
        bot_token = telegram_config.get('bot_token')
        chat_id = telegram_config.get('auth_chat_id')
        
        if bot_token and chat_id:
            try:
                from telegram import Bot
                self.telegram_bot = Bot(token=bot_token)
                self.auth_chat_id = chat_id
                logger.info("Telegram auth bot initialized", module="authentication")
            except ImportError:
                logger.warning("Telegram module not available", module="authentication")
            except Exception as e:
                logger.error(f"Error setting up Telegram: {e}", module="authentication")
    
    def _encrypt_sensitive(self, data: str) -> str:
        """Encrypt sensitive data"""
        if not self.cipher or not data:
            return data
        
        try:
            encrypted = self.cipher.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            logger.error(f"Encryption error: {e}", module="authentication")
            return data
    
    def _decrypt_sensitive(self, encrypted_data: str) -> str:
        """Decrypt sensitive data"""
        if not self.cipher or not encrypted_data:
            return encrypted_data
        
        try:
            decoded = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = self.cipher.decrypt(decoded)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Decryption error: {e}", module="authentication")
            return encrypted_data
    
    def hash_password(self, password: str, salt: str = None) -> Tuple[str, str]:
        """Hash password with salt using PBKDF2"""
        if not salt:
            salt = secrets.token_hex(16)
        
        try:
            # Use PBKDF2 for password hashing
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt.encode(),
                iterations=100000
            )
            
            key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
            return key.decode(), salt
        except Exception as e:
            logger.error(f"Password hashing error: {e}", module="authentication")
            # Fallback to simple hash
            combined = password + salt
            return hashlib.sha256(combined.encode()).hexdigest(), salt
    
    def create_user(self, username: str, password: str, 
                   telegram_id: str = None, permissions: List[str] = None,
                   mfa_enabled: bool = False, mfa_secret: str = None) -> bool:
        """Create new user account"""
        try:
            if username in self.users:
                logger.warning(f"User already exists: {username}", module="authentication")
                return False
            
            # Hash password
            password_hash, salt = self.hash_password(password)
            
            # Generate MFA secret if enabled
            if mfa_enabled and not mfa_secret:
                mfa_secret = base64.b32encode(secrets.token_bytes(20)).decode()
            
            # Create user record
            user_record = {
                'username': username,
                'password_hash': password_hash,
                'salt': salt,
                'telegram_id': self._encrypt_sensitive(telegram_id) if telegram_id else None,
                'permissions': permissions or ['basic'],
                'mfa_enabled': mfa_enabled,
                'mfa_secret': self._encrypt_sensitive(mfa_secret) if mfa_secret else None,
                'created_at': datetime.now().isoformat(),
                'last_login': None,
                'failed_attempts': 0,
                'locked_until': None,
                'active': True
            }
            
            self.users[username] = user_record
            self._save_data(self.users_file, self.users)
            
            logger.info(f"User created: {username}", module="authentication")
            return True
            
        except Exception as e:
            logger.error(f"User creation error: {e}", module="authentication")
            return False
    
    def authenticate(self, username: str, password: str, 
                    mfa_code: str = None, telegram_id: str = None) -> Tuple[bool, str]:
        """Authenticate user with optional MFA"""
        try:
            # Check if user exists
            if username not in self.users:
                logger.warning(f"Authentication failed: User not found - {username}", module="authentication")
                return False, "Invalid credentials"
            
            user = self.users[username]
            
            # Check if account is locked
            if user.get('locked_until'):
                lock_time = datetime.fromisoformat(user['locked_until'])
                if datetime.now()lock_time:
                    logger.warning(f"Account locked: {username}", module="authentication")
                    return False, "Account locked"
                else:
                    # Lock expired
                    user['locked_until'] = None
                    user['failed_attempts'] = 0
            
            # Check if account is active
            if not user.get('active', True):
                logger.warning(f"Account inactive: {username}", module="authentication")
                return False, "Account inactive"
            
            # Verify password
            stored_hash = user['password_hash']
            salt = user['salt']
            input_hash, _ = self.hash_password(password, salt)
            
            if not hmac.compare_digest(stored_hash, input_hash):
                # Failed attempt
                user['failed_attempts'] = user.get('failed_attempts', 0) + 1
                
                if user['failed_attempts'] >= self.max_login_attempts:
                    lock_time = datetime.now() + timedelta(seconds=self.lockout_duration)
                    user['locked_until'] = lock_time.isoformat()
                    logger.warning(f"Account locked due to too many failed attempts: {username}", module="authentication")
                
                self._save_data(self.users_file, self.users)
                logger.warning(f"Authentication failed: Invalid password - {username}", module="authentication")
                return False, "Invalid credentials"
            
            # Check MFA if enabled
            if user.get('mfa_enabled'):
                if not mfa_code:
                    # Generate and send MFA code
                    mfa_code = self.generate_mfa_code(username, telegram_id)
                    
                    if mfa_code and telegram_id:
                        self.send_mfa_notification(username, telegram_id, mfa_code)
                        return False, "MFA_REQUIRED"
                    else:
                        logger.warning(f"MFA required but no telegram ID: {username}", module="authentication")
                        return False, "MFA setup required"
                
                # Verify MFA code
                if not self.verify_mfa_code(username, mfa_code):
                    logger.warning(f"MFA verification failed: {username}", module="authentication")
                    return False, "Invalid MFA code"
            
            # Authentication successful
            user['failed_attempts'] = 0
            user['locked_until'] = None
            user['last_login'] = datetime.now().isoformat()
            self._save_data(self.users_file, self.users)
            
            # Create session
            session_token = self.create_session(username, telegram_id)
            
            logger.info(f"Authentication successful: {username}", module="authentication")
            return True, session_token
            
        except Exception as e:
            logger.error(f"Authentication error: {e}", module="authentication")
            return False, "Authentication error"
    
    def generate_mfa_code(self, username: str, telegram_id: str = None) -> Optional[str]:
        """Generate time-based MFA code"""
        try:
            # Generate 6-digit code
            code = ''.join(str(secrets.randbelow(10)) for _ in range(6))
            
            # Store code with expiry
            expiry = datetime.now() + timedelta(seconds=self.mfa_code_expiry)
            
            self.mfa_codes[username] = {
                'code': code,
                'expires_at': expiry.isoformat(),
                'telegram_id': telegram_id,
                'generated_at': datetime.now().isoformat()
            }
            
            self._save_data(self.mfa_codes_file, self.mfa_codes)
            
            logger.debug(f"MFA code generated for {username}: {code}", module="authentication")
            return code
            
        except Exception as e:
            logger.error(f"MFA code generation error: {e}", module="authentication")
            return None
    
    def verify_mfa_code(self, username: str, code: str) -> bool:
        """Verify MFA code"""
        try:
            if username not in self.mfa_codes:
                return False
            
            mfa_data = self.mfa_codes[username]
            stored_code = mfa_data.get('code')
            expiry_str = mfa_data.get('expires_at')
            
            if not stored_code or not expiry_str:
                return False
            
            # Check expiry
            expiry = datetime.fromisoformat(expiry_str)
            if datetime.now() > expiry:
                # Remove expired code
                del self.mfa_codes[username]
                self._save_data(self.mfa_codes_file, self.mfa_codes)
                return False
            
            # Verify code
            if not hmac.compare_digest(stored_code, code):
                return False
            
            # Code verified, remove it
            del self.mfa_codes[username]
            self._save_data(self.mfa_codes_file, self.mfa_codes)
            
            return True
            
        except Exception as e:
            logger.error(f"MFA verification error: {e}", module="authentication")
            return False
    
    def send_mfa_notification(self, username: str, telegram_id: str, code: str):
        """Send MFA code via Telegram"""
        if not self.telegram_bot or not hasattr(self, 'auth_chat_id'):
            return
        
        try:
            message = fb>🔐 MFA Code for {username}\n\nCode: {b>\n\nThis code expires in {self.mfa_code_expiry//60} minutes."
            
            self.telegram_bot.send_message(
                chat_id=telegram_id,
                text=message,
                parse_mode='HTML'
            )
            
            logger.debug(f"MFA code sent to {username} via Telegram", module="authentication")
            
        except Exception as e:
            logger.error(f"Error sending MFA notification: {e}", module="authentication")
    
    def create_session(self, username: str, telegram_id: str = None) -> str:
        """Create new session token"""
        try:
            # Generate session token
            session_token = secrets.token_urlsafe(32)
            
            # Create session record
            session_record = {
                'username': username,
                'telegram_id': telegram_id,
                'created_at': datetime.now().isoformat(),
                'last_activity': datetime.now().isoformat(),
                'expires_at': (datetime.now() + timedelta(seconds=self.session_timeout)).isoformat(),
                'ip_address': self._get_client_ip(),
                'user_agent': self._get_user_agent(),
                'active': True
            }
            
            self.sessions[session_token] = session_record
            self._save_data(self.sessions_file, self.sessions)
            
            logger.debug(f"Session created for {username}", module="authentication")
            return session_token
            
        except Exception as e:
            logger.error(f"Session creation error: {e}", module="authentication")
            return ""
    
    def validate_session(self, session_token: str) -> Tuple[bool, Optional[str]]:
        """Validate session token"""
        try:
            if session_token not in self.sessions:
                return False, None
            
            session = self.sessions[session_token]
            
            # Check if session is active
            if not session.get('active', True):
                return False, None
            
            # Check expiry
            expiry_str = session.get('expires_at')
            if expiry_str:
                expiry = datetime.fromisoformat(expiry_str)
                if datetime.now() > expiry:
                    # Session expired
                    session['active'] = False
                    self._save_data(self.sessions_file, self.sessions)
                    return False, None
            
            # Update last activity
            session['last_activity'] = datetime.now().isoformat()
            
            # Extend session if needed
            if self.config.get('extend_session_on_activity', True):
                new_expiry = datetime.now() + timedelta(seconds=self.session_timeout)
                session['expires_at'] = new_expiry.isoformat()
            
            self._save_data(self.sessions_file, self.sessions)
            
            username = session.get('username')
            return True, username
            
        except Exception as e:
            logger.error(f"Session validation error: {e}", module="authentication")
            return False, None
    
    def invalidate_session(self, session_token: str):
        """Invalidate session"""
        try:
            if session_token in self.sessions:
                self.sessions[session_token]['active'] = False
                self._save_data(self.sessions_file, self.sessions)
                logger.debug(f"Session invalidated: {session_token}", module="authentication")
        except Exception as e:
            logger.error(f"Session invalidation error: {e}", module="authentication")
    
    def invalidate_all_sessions(self, username: str):
        """Invalidate all sessions for a user"""
        try:
            for token, session in list(self.sessions.items()):
                if session.get('username') == username:
                    session['active'] = False
            
            self._save_data(self.sessions_file, self.sessions)
            logger.info(f"All sessions invalidated for {username}", module="authentication")
        except Exception as e:
            logger.error(f"Error invalidating all sessions: {e}", module="authentication")
    
    def get_user_permissions(self, username: str) -> List[str]:
        """Get user permissions"""
        try:
            if username in self.users:
                return self.users[username].get('permissions', [])
        except Exception as e:
            logger.error(f"Error getting user permissions: {e}", module="authentication")
        
        return []
    
    def update_user_permissions(self, username: str, permissions: List[str]) -> bool:
        """Update user permissions"""
        try:
            if username in self.users:
                self.users[username]['permissions'] = permissions
                self._save_data(self.users_file, self.users)
                logger.info(f"Permissions updated for {username}: {permissions}", module="authentication")
                return True
        except Exception as e:
            logger.error(f"Error updating user permissions: {e}", module="authentication")
        
        return False
    
    def enable_mfa(self, username: str, telegram_id: str = None) -> Tuple[bool, Optional[str]]:
        """Enable MFA for user"""
        try:
            if username not in self.users:
                return False, None
            
            # Generate new MFA secret
            mfa_secret = base64.b32encode(secrets.token_bytes(20)).decode()
            
            # Update user record
            self.users[username]['mfa_enabled'] = True
            self.users[username]['mfa_secret'] = self._encrypt_sensitive(mfa_secret)
            
            if telegram_id:
                self.users[username]['telegram_id'] = self._encrypt_sensitive(telegram_id)
            
            self._save_data(self.users_file, self.users)
            
            logger.info(f"MFA enabled for {username}", module="authentication")
            return True, mfa_secret
            
        except Exception as e:
            logger.error(f"Error enabling MFA: {e}", module="authentication")
            return False, None
    
    def disable_mfa(self, username: str) -> bool:
        """Disable MFA for user"""
        try:
            if username in self.users:
                self.users[username]['mfa_enabled'] = False
                self.users[username]['mfa_secret'] = None
                self._save_data(self.users_file, self.users)
                
                logger.info(f"MFA disabled for {username}", module="authentication")
                return True
        except Exception as e:
            logger.error(f"Error disabling MFA: {e}", module="authentication")
        
        return False
    
    def change_password(self, username: str, old_password: str, new_password: str) -> bool:
        """Change user password"""
        try:
            if username not in self.users:
                return False
            
            user = self.users[username]
            
            # Verify old password
            stored_hash = user['password_hash']
            salt = user['salt']
            input_hash, _ = self.hash_password(old_password, salt)
            
            if not hmac.compare_digest(stored_hash, input_hash):
                return False
            
            # Update password
            new_hash, new_salt = self.hash_password(new_password)
            user['password_hash'] = new_hash
            user['salt'] = new_salt
            
            # Invalidate all sessions
            self.invalidate_all_sessions(username)
            
            self._save_data(self.users_file, self.users)
            
            logger.info(f"Password changed for {username}", module="authentication")
            return True
            
        except Exception as e:
            logger.error(f"Error changing password: {e}", module="authentication")
            return False
    
    def _get_client_ip(self) -> str:
        """Get client IP address (simplified)"""
        try:
            # This would need to be implemented based on your framework
            # For now, return placeholder
            return "127.0.0.1"
        except:
            return "unknown"
    
    def _get_user_agent(self) -> str:
        """Get user agent (simplified)"""
        try:
            # This would need to be implemented based on your framework
            return "TelegramBot/1.0"
        except:
            return "unknown"
    
    def get_active_sessions(self, username: str = None) -> List[Dict[str, Any]]:
        """Get active sessions"""
        try:
            active_sessions = []
            
            for token, session in self.sessions.items():
                if not session.get('active', True):
                    continue
                
                # Check expiry
                expiry_str = session.get('expires_at')
                if expiry_str:
                    expiry = datetime.fromisoformat(expiry_str)
                    if datetime.now() > expiry:
                        continue
                
                if username and session.get('username') != username:
                    continue
                
                active_sessions.append({
                    'token': token[:8] + '...',  # Partial token for security
                    'username': session.get('username'),
                    'created_at': session.get('created_at'),
                    'last_activity': session.get('last_activity'),
                    'expires_at': session.get('expires_at'),
                    'ip_address': session.get('ip_address'),
                    'user_agent': session.get('user_agent')
                })
            
            return active_sessions
            
        except Exception as e:
            logger.error(f"Error getting active sessions: {e}", module="authentication")
            return []
    
    def cleanup_expired_sessions(self):
        """Cleanup expired sessions"""
        try:
            expired_count = 0
            
            for token, session in list(self.sessions.items()):
                expiry_str = session.get('expires_at')
                if expiry_str:
                    expiry = datetime.fromisoformat(expiry_str)
                    if datetime.now() > expiry:
                        del self.sessions[token]
                        expired_count += 1
            
            if expired_count > 0:
                self._save_data(self.sessions_file, self.sessions)
                logger.info(f"Cleaned up {expired_count} expired sessions", module="authentication")
            
        except Exception as e:
            logger.error(f"Error cleaning up sessions: {e}", module="authentication")
    
    def get_status(self) -> Dict[str, Any]:
        """Get authentication system status"""
        return {
            'total_users': len(self.users),
            'active_sessions': len([s for s in self.sessions.values() if s.get('active', True)]),
            'mfa_enabled_users': len([u for u in self.users.values() if u.get('mfa_enabled')]),
            'locked_accounts': len([u for u in self.users.values() if u.get('locked_until')]),
            'session_timeout': self.session_timeout,
            'telegram_available': self.telegram_bot is not None
        }

# Global instance
_auth_system = None

def get_authentication_system(config: Dict = None) -> AuthenticationSystem:
    """Get or create authentication system instance"""
    global _auth_system
    
    if _auth_system is None:
        _auth_system = AuthenticationSystem(config)
    
    return _auth_system

if __name__ == "__main__":
    # Test authentication system
    config = {
        'telegram': {
            'bot_token': 'test_token',
            'auth_chat_id': 123456789
        }
    }
    
    auth = get_authentication_system(config)
    
    print("Testing authentication system...")
    
    # Create test user
    auth.create_user(
        username="testuser",
        password="SecurePass123!",
        telegram_id="123456789",
        permissions=["admin", "execute", "read"],
        mfa_enabled=True
    )
    
    # Test authentication without MFA (should fail with MFA_REQUIRED)
    success, result = auth.authenticate(
        username="testuser",
        password="SecurePass123!",
        telegram_id="123456789"
    )
    
    print(f"Authentication result: {success}, {result}")
    
    if result == "MFA_REQUIRED":
        # Simulate MFA code entry
        test_code = "123456"  # Would come from Telegram
        success, session = auth.authenticate(
            username="testuser",
            password="SecurePass123!",
            mfa_code=test_code
        )
        
        print(f"MFA authentication result: {success}, session: {session[:20]}...")
    
    # Show status
    status = auth.get_status()
    print(f"\n🔐 Authentication System Status: {status}")
    
    # Cleanup test data
    import os
    for f in ['data/users.json', 'data/sessions.json', 'data/mfa_codes.json', 'security/encryption.key']:
        if os.path.exists(f):
            os.remove(f)
    
    print("\n✅ Authentication tests completed!")
