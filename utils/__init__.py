#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
utils package - Helper modules for DerBöseKollege framework
"""

from .logger import get_logger, AdvancedLogger
from .encryption import get_encryption_manager, EncryptionManager
from .network import get_network_manager, NetworkManager
from .system import get_system_manager, SystemManager
from .persistence import get_persistence_manager, PersistenceManager
from .obfuscation import get_obfuscation_manager, ObfuscationManager
from .evasion import get_evasion_manager, EvasionManager

__all__ = [
    # Logger
    'get_logger',
    'AdvancedLogger',
    
    # Encryption
    'get_encryption_manager',
    'EncryptionManager',
    
    # Network
    'get_network_manager',
    'NetworkManager',
    
    # System
    'get_system_manager',
    'SystemManager',
    
    # Persistence
    'get_persistence_manager',
    'PersistenceManager',
    
    # Obfuscation
    'get_obfuscation_manager',
    'ObfuscationManager',
    
    # Evasion
    'get_evasion_manager',
    'EvasionManager',
]

# Version
__version__ = '1.0.0'
__author__ = 'DerBöseKollege Team'
__description__ = 'Advanced utility modules for penetration testing and security research'
