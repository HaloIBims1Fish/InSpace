#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
data package - Database and data management modules for DerBöseKollege framework
"""

from .sqlite_db import get_sqlite_manager, SQLiteManager
from .mongodb_db import get_mongodb_manager, MongoDBManager
from .redis_db import get_redis_manager, RedisManager
from .processor import get_data_processor, DataProcessor
from .exporter import get_data_exporter, DataExporter

__all__ = [
    # SQLite
    'get_sqlite_manager',
    'SQLiteManager',
    
    # MongoDB
    'get_mongodb_manager',
    'MongoDBManager',
    
    # Redis
    'get_redis_manager',
    'RedisManager',
    
    # Processor
    'get_data_processor',
    'DataProcessor',
    
    # Exporter
    'get_data_exporter',
    'DataExporter',
]

# Version
__version__ = '1.0.0'
__author__ = 'DerBöseKollege Team'
__description__ = 'Advanced data management and processing modules'
