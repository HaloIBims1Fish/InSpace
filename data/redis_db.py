#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
redis_db.py - Redis database manager with Telegram integration
"""

import redis
import json
import pickle
import hashlib
import time
import threading
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime, timedelta
from functools import wraps

# Import logger
from ..utils.logger import get_logger

logger = get_logger()

class RedisManager:
    """Manages Redis database operations with caching and Telegram notifications"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {
            'host': 'localhost',
            'port': 6379,
            'db': 0,
            'password': None,
            'socket_timeout': 5,
            'socket_connect_timeout': 5,
            'retry_on_timeout': True,
            'max_connections': 10,
            'decode_responses': True
        }
        
        # Telegram bot for notifications
        self.telegram_bot = None
        self.setup_telegram()
        
        # Redis client
        self.client = None
        self.connection_pool = None
        
        # Connection status
        self.connected = False
        self.connection_error = None
        
        # Cache configuration
        self.default_ttl = self.config.get('default_ttl', 3600)  # 1 hour
        self.cache_prefix = self.config.get('cache_prefix', 'dbk:')
        
        # Initialize connection
        self._connect()
        
        logger.info("Redis manager initialized", module="redis")
    
    def setup_telegram(self):
        """Setup Telegram bot for notifications"""
        telegram_config = self.config.get('telegram', {})
        bot_token = telegram_config.get('bot_token')
        chat_id = telegram_config.get('redis_chat_id')
        
        if bot_token and chat_id:
            try:
                from telegram import Bot
                self.telegram_bot = Bot(token=bot_token)
                self.redis_chat_id = chat_id
                logger.info("Telegram Redis bot initialized", module="redis")
            except ImportError:
                logger.warning("Telegram module not available", module="redis")
            except Exception as e:
                logger.error(f"Error setting up Telegram: {e}", module="redis")
    
    def send_telegram_notification(self, title: str, message: str):
        """Send Redis notification to Telegram"""
        if not self.telegram_bot or not hasattr(self, 'redis_chat_id'):
            return
        
        try:
            full_message = fb>⚡ {b>\n\n{message}"
            self.telegram_bot.send_message(
                chat_id=self.redis_chat_id,
                text=full_message,
                parse_mode='HTML'
            )
            logger.debug(f"Telegram Redis notification sent: {title}", module="redis")
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}", module="redis")
    
    def _connect(self):
        """Connect to Redis"""
        try:
            # Create connection pool
            self.connection_pool = redis.ConnectionPool(
                host=self.config.get('host', 'localhost'),
                port=self.config.get('port', 6379),
                db=self.config.get('db', 0),
                password=self.config.get('password'),
                socket_timeout=self.config.get('socket_timeout', 5),
                socket_connect_timeout=self.config.get('socket_connect_timeout', 5),
                retry_on_timeout=self.config.get('retry_on_timeout', True),
                max_connections=self.config.get('max_connections', 10),
                decode_responses=self.config.get('decode_responses', True)
            )
            
            # Create client
            self.client = redis.Redis(connection_pool=self.connection_pool)
            
            # Test connection
            self.client.ping()
            
            self.connected = True
            self.connection_error = None
            
            # Send Telegram notification
            self.send_telegram_notification(
                "Redis Connected",
                f"Host: {self.config.get('host')}:{self.config.get('port')}\n"
                f"Database: {self.config.get('db')}\n"
                f"Pool size: {self.config.get('max_connections', 10)}"
            )
            
            logger.info(f"Redis connected to {self.config.get('host')}:{self.config.get('port')}", module="redis")
            
        except redis.ConnectionError as e:
            self.connected = False
            self.connection_error = str(e)
            logger.error(f"Redis connection failed: {e}", module="redis")
        except Exception as e:
            self.connected = False
            self.connection_error = str(e)
            logger.error(f"Redis connection error: {e}", module="redis")
    
    def reconnect(self):
        """Reconnect to Redis"""
        try:
            if self.client:
                self.client.close()
            if self.connection_pool:
                self.connection_pool.disconnect()
            
            self._connect()
            return self.connected
            
        except Exception as e:
            logger.error(f"Reconnection failed: {e}", module="redis")
            return False
    
    def is_connected(self) -> bool:
        """Check if connected to Redis"""
        if not self.connected:
            return False
        
        try:
            self.client.ping()
            return True
        except:
            self.connected = False
            return False
    
    def _build_key(self, key: str) -> str:
        """Build full Redis key with prefix"""
        return f"{self.cache_prefix}{key}"
    
    def set_value(self, key: str, value: Any, ttl: int = None, 
                 serialize: bool = True) -> bool:
        """Set value in Redis"""
        if not self.is_connected():
            logger.error("Redis not connected", module="redis")
            return False
        
        try:
            full_key = self._build_key(key)
            
            # Serialize if needed
            if serialize and not isinstance(value, (str, bytes, int, float)):
                if isinstance(value, dict) or isinstance(value, list):
                    value = json.dumps(value)
                else:
                    value = pickle.dumps(value)
            
            # Set value
            if ttl is None:
                ttl = self.default_ttl
            
            result = self.client.setex(full_key, ttl, value)
            
            logger.debug(f"Value set for key: {key} (TTL: {ttl}s)", module="redis")
            return bool(result)
            
        except Exception as e:
            logger.error(f"Error setting value for key {key}: {e}", module="redis")
            return False
    
    def get_value(self, key: str, deserialize: bool = True) -> Any:
        """Get value from Redis"""
        if not self.is_connected():
            logger.error("Redis not connected", module="redis")
            return None
        
        try:
            full_key = self._build_key(key)
            value = self.client.get(full_key)
            
            if value is None:
                logger.debug(f"Key not found: {key}", module="redis")
                return None
            
            # Deserialize if needed
            if deserialize:
                try:
                    # Try JSON first
                    value = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    try:
                        # Try pickle
                        value = pickle.loads(value)
                    except:
                        # Return as string
                        pass
            
            logger.debug(f"Value retrieved for key: {key}", module="redis")
            return value
            
        except Exception as e:
            logger.error(f"Error getting value for key {key}: {e}", module="redis")
            return None
    
    def delete_key(self, key: str) -> bool:
        """Delete key from Redis"""
        if not self.is_connected():
            logger.error("Redis not connected", module="redis")
            return False
        
        try:
            full_key = self._build_key(key)
            result = self.client.delete(full_key)
            
            deleted = result > 0
            logger.debug(f"Key deleted: {key} - {deleted}", module="redis")
            return deleted
            
        except Exception as e:
            logger.error(f"Error deleting key {key}: {e}", module="redis")
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists"""
        if not self.is_connected():
            logger.error("Redis not connected", module="redis")
            return False
        
        try:
            full_key = self._build_key(key)
            return bool(self.client.exists(full_key))
            
        except Exception as e:
            logger.error(f"Error checking key {key}: {e}", module="redis")
            return False
    
    def expire(self, key: str, ttl: int) -> bool:
        """Set expiration for key"""
        if not self.is_connected():
            logger.error("Redis not connected", module="redis")
            return False
        
        try:
            full_key = self._build_key(key)
            result = self.client.expire(full_key, ttl)
            
            logger.debug(f"Expiration set for key {key}: {ttl}s", module="redis")
            return bool(result)
            
        except Exception as e:
            logger.error(f"Error setting expiration for key {key}: {e}", module="redis")
            return False
    
    def ttl(self, key: str) -> int:
        """Get time to live for key"""
        if not self.is_connected():
            logger.error("Redis not connected", module="redis")
            return -2
        
        try:
            full_key = self._build_key(key)
            ttl = self.client.ttl(full_key)
            return ttl
            
        except Exception as e:
            logger.error(f"Error getting TTL for key {key}: {e}", module="redis")
            return -2
    
    def increment(self, key: str, amount: int = 1) -> int:
        """Increment counter"""
        if not self.is_connected():
            logger.error("Redis not connected", module="redis")
            return 0
        
        try:
            full_key = self._build_key(key)
            result = self.client.incrby(full_key, amount)
            
            # Send Telegram notification for high counters
            if result > 1000 and result % 1000 == 0:
                self.send_telegram_notification(
                    "Counter Milestone",
                    f"Key: {key}\n"
                    f"Value: {result}\n"
                    f"Increment: {amount}"
                )
            
            logger.debug(f"Counter incremented for key {key}: {result}", module="redis")
            return result
            
        except Exception as e:
            logger.error(f"Error incrementing key {key}: {e}", module="redis")
            return 0
    
    def decrement(self, key: str, amount: int = 1) -> int:
        """Decrement counter"""
        if not self.is_connected():
            logger.error("Redis not connected", module="redis")
            return 0
        
        try:
            full_key = self._build_key(key)
            result = self.client.decrby(full_key, amount)
            
            logger.debug(f"Counter decremented for key {key}: {result}", module="redis")
            return result
            
        except Exception as e:
            logger.error(f"Error decrementing key {key}: {e}", module="redis")
            return 0
    
    def hash_set(self, hash_key: str, field: str, value: Any) -> bool:
        """Set field in hash"""
        if not self.is_connected():
            logger.error("Redis not connected", module="redis")
            return False
        
        try:
            full_key = self._build_key(hash_key)
            
            # Serialize if needed
            if not isinstance(value, (str, bytes, int, float)):
                if isinstance(value, dict) or isinstance(value, list):
                    value = json.dumps(value)
                else:
                    value = pickle.dumps(value)
            
            result = self.client.hset(full_key, field, value)
            
            logger.debug(f"Hash field set: {hash_key}.{field}", module="redis")
            return bool(result)
            
        except Exception as e:
            logger.error(f"Error setting hash field {hash_key}.{field}: {e}", module="redis")
            return False
    
    def hash_get(self, hash_key: str, field: str) -> Any:
        """Get field from hash"""
        if not self.is_connected():
            logger.error("Redis not connected", module="redis")
            return None
        
        try:
            full_key = self._build_key(hash_key)
            value = self.client.hget(full_key, field)
            
            if value is None:
                return None
            
            # Deserialize if needed
            try:
                value = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                try:
                    value = pickle.loads(value)
                except:
                    pass
            
            return value
            
        except Exception as e:
            logger.error(f"Error getting hash field {hash_key}.{field}: {e}", module="redis")
            return None
    
    def hash_get_all(self, hash_key: str) -> Dict[str, Any]:
        """Get all fields from hash"""
        if not self.is_connected():
            logger.error("Redis not connected", module="redis")
            return {}
        
        try:
            full_key = self._build_key(hash_key)
            hash_data = self.client.hgetall(full_key)
            
            result = {}
            for field, value in hash_data.items():
                try:
                    result[field] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    try:
                        result[field] = pickle.loads(value)
                    except:
                        result[field] = value
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting all hash fields for {hash_key}: {e}", module="redis")
            return {}
    
    def list_push(self, list_key: str, value: Any, side: str = 'right') -> int:
        """Push value to list"""
        if not self.is_connected():
            logger.error("Redis not connected", module="redis")
            return 0
        
        try:
            full_key = self._build_key(list_key)
            
            # Serialize if needed
            if not isinstance(value, (str, bytes, int, float)):
                if isinstance(value, dict) or isinstance(value, list):
                    value = json.dumps(value)
                else:
                    value = pickle.dumps(value)
            
            if side == 'left':
                result = self.client.lpush(full_key, value)
            else:
                result = self.client.rpush(full_key, value)
            
            # Send Telegram notification for large lists
            list_length = self.client.llen(full_key)
            if list_length > 1000 and list_length % 1000 == 0:
                self.send_telegram_notification(
                    "List Size Milestone",
                    f"List: {list_key}\n"
                    f"Size: {list_length}\n"
                    f"Operation: push {side}"
                )
            
            logger.debug(f"Value pushed to list {list_key} ({side}): new length {list_length}", module="redis")
            return result
            
        except Exception as e:
            logger.error(f"Error pushing to list {list_key}: {e}", module="redis")
            return 0
    
    def list_pop(self, list_key: str, side: str = 'right') -> Any:
        """Pop value from list"""
        if not self.is_connected():
            logger.error("Redis not connected", module="redis")
            return None
        
        try:
            full_key = self._build_key(list_key)
            
            if side == 'left':
                value = self.client.lpop(full_key)
            else:
                value = self.client.rpop(full_key)
            
            if value is None:
                return None
            
            # Deserialize if needed
            try:
                value = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                try:
                    value = pickle.loads(value)
                except:
                    pass
            
            return value
            
        except Exception as e:
            logger.error(f"Error popping from list {list_key}: {e}", module="redis")
            return None
    
    def list_range(self, list_key: str, start: int = 0, end: int = -1) -> List[Any]:
        """Get range from list"""
        if not self.is_connected():
            logger.error("Redis not connected", module="redis")
            return []
        
        try:
            full_key = self._build_key(list_key)
            values = self.client.lrange(full_key, start, end)
            
            result = []
            for value in values:
                try:
                    result.append(json.loads(value))
                except (json.JSONDecodeError, TypeError):
                    try:
                        result.append(pickle.loads(value))
                    except:
                        result.append(value)
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting range from list {list_key}: {e}", module="redis")
            return []
    
    def set_add(self, set_key: str, *values) -> int:
        """Add values to set"""
        if not self.is_connected():
            logger.error("Redis not connected", module="redis")
            return 0
        
        try:
            full_key = self._build_key(set_key)
            
            # Serialize values
            serialized_values = []
            for value in values:
                if not isinstance(value, (str, bytes, int, float)):
                    if isinstance(value, dict) or isinstance(value, list):
                        serialized_values.append(json.dumps(value))
                    else:
                        serialized_values.append(pickle.dumps(value))
                else:
                    serialized_values.append(value)
            
            result = self.client.sadd(full_key, *serialized_values)
            
            logger.debug(f"Values added to set {set_key}: {len(values)} values", module="redis")
            return result
            
        except Exception as e:
            logger.error(f"Error adding to set {set_key}: {e}", module="redis")
            return 0
    
    def set_members(self, set_key: str) -> List[Any]:
        """Get all members of set"""
        if not self.is_connected():
            logger.error("Redis not connected", module="redis")
            return []
        
        try:
            full_key = self._build_key(set_key)
            members = self.client.smembers(full_key)
            
            result = []
            for member in members:
                try:
                    result.append(json.loads(member))
                except (json.JSONDecodeError, TypeError):
                    try:
                        result.append(pickle.loads(member))
                    except:
                        result.append(member)
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting set members for {set_key}: {e}", module="redis")
            return []
    
    def sorted_set_add(self, zset_key: str, mapping: Dict[Any, float]) -> int:
        """Add members to sorted set with scores"""
        if not self.is_connected():
            logger.error("Redis not connected", module="redis")
            return 0
        
        try:
            full_key = self._build_key(zset_key)
            
            # Serialize keys
            serialized_mapping = {}
            for key, score in mapping.items():
                if not isinstance(key, (str, bytes, int, float)):
                    if isinstance(key, dict) or isinstance(key, list):
                        serialized_key = json.dumps(key)
                    else:
                        serialized_key = pickle.dumps(key)
                else:
                    serialized_key = key
                
                serialized_mapping[serialized_key] = score
            
            result = self.client.zadd(full_key, serialized_mapping)
            
            logger.debug(f"Members added to sorted set {zset_key}: {len(mapping)} members", module="redis")
            return result
            
        except Exception as e:
            logger.error(f"Error adding to sorted set {zset_key}: {e}", module="redis")
            return 0
    
    def sorted_set_range(self, zset_key: str, start: int = 0, end: int = -1, 
                        with_scores: bool = False) -> List[Any]:
        """Get range from sorted set"""
        if not self.is_connected():
            logger.error("Redis not connected", module="redis")
            return []
        
        try:
            full_key = self._build_key(zset_key)
            
            if with_scores:
                result = self.client.zrange(full_key, start, end, withscores=True)
                deserialized = []
                for member, score in result:
                    try:
                        deserialized.append((json.loads(member), score))
                    except (json.JSONDecodeError, TypeError):
                        try:
                            deserialized.append((pickle.loads(member), score))
                        except:
                            deserialized.append((member, score))
                return deserialized
            else:
                result = self.client.zrange(full_key, start, end)
                deserialized = []
                for member in result:
                    try:
                        deserialized.append(json.loads(member))
                    except (json.JSONDecodeError, TypeError):
                        try:
                            deserialized.append(pickle.loads(member))
                        except:
                            deserialized.append(member)
                return deserialized
            
        except Exception as e:
            logger.error(f"Error getting range from sorted set {zset_key}: {e}", module="redis")
            return []
    
    def keys(self, pattern: str = '*') -> List[str]:
        """Get keys matching pattern"""
        if not self.is_connected():
            logger.error("Redis not connected", module="redis")
            return []
        
        try:
            full_pattern = self._build_key(pattern)
            keys = self.client.keys(full_pattern)
            
            # Remove prefix from keys
            result = [key[len(self.cache_prefix):] for key in keys]
            
            logger.debug(f"Found {len(result)} keys matching pattern: {pattern}", module="redis")
            return result
            
        except Exception as e:
            logger.error(f"Error getting keys for pattern {pattern}: {e}", module="redis")
            return []
    
    def flush_db(self, asynchronous: bool = False) -> bool:
        """Flush database"""
        if not self.is_connected():
            logger.error("Redis not connected", module="redis")
            return False
        
        try:
            if asynchronous:
                self.client.flushdb(async_op=True)
            else:
                self.client.flushdb()
            
            # Send Telegram notification
            self.send_telegram_notification(
                "Redis Database Flushed",
                f"Async: {asynchronous}\n"
                f"All keys cleared"
            )
            
            logger.warning("Redis database flushed", module="redis")
            return True
            
        except Exception as e:
            logger.error(f"Error flushing database: {e}", module="redis")
            return False
    
    def get_info(self) -> Dict[str, Any]:
        """Get Redis server information"""
        if not self.is_connected():
            logger.error("Redis not connected", module="redis")
            return {}
        
        try:
            info = self.client.info()
            
            # Extract important metrics
            result = {
                'redis_version': info.get('redis_version'),
                'uptime_in_seconds': info.get('uptime_in_seconds'),
                'connected_clients': info.get('connected_clients'),
                'used_memory_human': info.get('used_memory_human'),
                'used_memory_peak_human': info.get('used_memory_peak_human'),
                'total_connections_received': info.get('total_connections_received'),
                'total_commands_processed': info.get('total_commands_processed'),
                'keyspace_hits': info.get('keyspace_hits'),
                'keyspace_misses': info.get('keyspace_misses'),
                'keys': {}
            }
            
            # Get key counts by type
            for db_key, db_info in info.get('keyspace', {}).items():
                result['keys'][db_key] = db_info.get('keys', 0)
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting Redis info: {e}", module="redis")
            return {}
    
    def cache_function(self, ttl: int = None, key_prefix: str = None):
        """Decorator to cache function results"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Generate cache key
                if key_prefix:
                    cache_key = key_prefix
                else:
                    cache_key = f"func:{func.__module__}:{func.__name__}"
                
                # Include args and kwargs in key
                if args:
                    cache_key += f":args:{hashlib.md5(str(args).encode()).hexdigest()[:8]}"
                if kwargs:
                    cache_key += f":kwargs:{hashlib.md5(str(kwargs).encode()).hexdigest()[:8]}"
                
                # Try to get from cache
                cached_result = self.get_value(cache_key)
                if cached_result is not None:
                    logger.debug(f"Cache hit for {cache_key}", module="redis")
                    return cached_result
                
                # Execute function
                result = func(*args, **kwargs)
                
                # Store in cache
                self.set_value(cache_key, result, ttl=ttl or self.default_ttl)
                logger.debug(f"Cache miss for {cache_key}, stored result", module="redis")
                
                return result
            
            return wrapper
 if analysis['memory_stats']:
                analysis['memory_avg_gb'] = statistics.mean(analysis['memory_stats']) / (1024**3)
                analysis['memory_total_gb'] = sum(analysis['memory_stats']) / (1024**3)
            
            if analysis['disk_stats']:
                analysis['disk_avg_gb'] = statistics.mean(analysis['disk_stats']) / (1024**3)
                analysis['disk_total_gb'] = sum(analysis['disk_stats']) / (1024**3)
            
            # Sort platforms by count
            analysis['platforms'] = dict(sorted(
                analysis['platforms'].items(),
                key=lambda x: x[1],
                reverse=True
            ))
            
            logger.debug(f"Analyzed {len(data)} system records", module="processor")
            return analysis
            
        except Exception as e:
            logger.error(f"System info analysis error: {e}", module="processor")
            return {'error': str(e)}
    
    def _process_network_scan(self, data: List[Dict]) -> Dict:
        """Process network scan results"""
        try:
            if not data:
                return {'error': 'No data provided'}
            
            analysis = {
                'total_hosts': len(data),
                'open_ports': Counter(),
                'services': Counter(),
                'operating_systems': Counter(),
                'vulnerabilities': [],
                'hosts_by_network': defaultdict(int)
            }
            
            for host in data:
                ip = host.get('ip')
                if not ip:
                    continue
                
                # Network classification
                network_part = '.'.join(ip.split('.')[:3]) + '.x'
                analysis['hosts_by_network'][network_part] += 1
                
                # Ports and services
                ports = host.get('ports', [])
                for port_info in ports:
                    port = port_info.get('port')
                    service = port_info.get('service', 'unknown')
                    
                    if port:
                        analysis['open_ports'][port] += 1
                    
                    if service and service != 'unknown':
                        analysis['services'][service] += 1
                
                # OS detection
                os_info = host.get('os', '')
                if os_info:
                    analysis['operating_systems'][os_info] += 1
                
                # Vulnerabilities
                vulns = host.get('vulnerabilities', [])
                analysis['vulnerabilities'].extend(vulns)
            
            # Calculate statistics
            analysis['unique_ports'] = len(analysis['open_ports'])
            analysis['unique_services'] = len(analysis['services'])
            analysis['total_vulnerabilities'] = len(analysis['vulnerabilities'])
            
            # Most common ports and services
            analysis['top_ports'] = dict(sorted(
                analysis['open_ports'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:10])
            
            analysis['top_services'] = dict(sorted(
                analysis['services'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:10])
            
            # Most common OS
            analysis['top_os'] = dict(sorted(
                analysis['operating_systems'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:5])
            
            logger.debug(f"Processed {len(data)} network hosts", module="processor")
            return analysis
            
        except Exception as e:
            logger.error(f"Network scan processing error: {e}", module="processor")
            return {'error': str(e)}
    
    def _analyze_processes(self, data: List[Dict]) -> Dict:
        """Analyze process information"""
        try:
            if not data:
                return {'error': 'No data provided'}
            
            analysis = {
                'total_processes': len(data),
                'processes_by_user': Counter(),
                'processes_by_name': Counter(),
                'cpu_usage': [],
                'memory_usage': [],
                'suspicious_processes': [],
                'timeline': []
            }
            
            suspicious_keywords = [
                'mimikatz', 'powersploit', 'empire', 'cobalt', 'metasploit',
                'bloodhound', 'responder', 'impacket', 'psexec', 'wmiexec',
                'nc.exe', 'netcat', 'ncat', 'socat', 'plink', 'putty',
                'keylogger', 'rat', 'backdoor', 'rootkit', 'trojan'
            ]
            
            for process in data:
                # User distribution
                user = process.get('username', 'unknown')
                analysis['processes_by_user'][user] += 1
                
                # Process name distribution
                name = process.get('name', 'unknown')
                analysis['processes_by_name'][name] += 1
                
                # CPU and memory usage
                cpu = process.get('cpu_percent', 0)
                memory = process.get('memory_percent', 0)
                
                if cpu > 0:
                    analysis['cpu_usage'].append(cpu)
                if memory > 0:
                    analysis['memory_usage'].append(memory)
                
                # Check for suspicious processes
                name_lower = name.lower()
                exe_path = process.get('exe_path', '').lower()
                cmdline = ' '.join(process.get('cmdline', [])).lower()
                
                for keyword in suspicious_keywords:
                    if (keyword in name_lower or 
                        keyword in exe_path or 
                        keyword in cmdline):
                        
                        analysis['suspicious_processes'].append({
                            'pid': process.get('pid'),
                            'name': name,
                            'user': user,
                            'exe_path': process.get('exe_path'),
                            'cmdline': process.get('cmdline'),
                            'keyword': keyword,
                            'timestamp': process.get('timestamp')
                        })
                        break
                
                # Timeline
                timestamp = process.get('timestamp')
                if timestamp:
                    analysis['timeline'].append(timestamp)
            
            # Calculate statistics
            if analysis['cpu_usage']:
                analysis['cpu_avg'] = statistics.mean(analysis['cpu_usage'])
                analysis['cpu_max'] = max(analysis['cpu_usage'])
            
            if analysis['memory_usage']:
                analysis['memory_avg'] = statistics.mean(analysis['memory_usage'])
                analysis['memory_max'] = max(analysis['memory_usage'])
            
            # Most active users and processes
            analysis['top_users'] = dict(sorted(
                analysis['processes_by_user'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:10])
            
            analysis['top_processes'] = dict(sorted(
                analysis['processes_by_name'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:10])
            
            # Send Telegram notification for suspicious processes
            if analysis['suspicious_processes']:
                self.send_telegram_notification(
                    "⚠️ Suspicious Processes Detected",
                    f"Count: {len(analysis['suspicious_processes'])}\n"
                    f"Processes: {', '.join(set(p['name'] for p in analysis['suspicious_processes'][:5]))}"
                )
            
            logger.debug(f"Analyzed {len(data)} processes, found {len(analysis['suspicious_processes'])} suspicious", module="processor")
            return analysis
            
       _keys': set(),
                'counts': {}
            }
            
            # Regex patterns for IOC extraction
            patterns = {
                'ip': r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
                'domain': r'\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b',
                'url': r'https?://[^\s]+',
                'md5': r'\b[a-fA-F0-9]{32}\b',
                'sha1': r'\b[a-fA-F0-9]{40}\b',
                'sha256': r'\b[a-fA-F0-9]{64}\b',
                'filename': r'\b[\w\-]+\.[a-zA-Z]{2,4}\b'
            }
            
            for item in data:
                # Convert item to string for pattern matching
                item_str = json.dumps(item)
                
                for ioc_type, pattern in patterns.items():
                    matches = re.findall(pattern, item_str)
                    if matches:
                        ioc_set = iocs.get(ioc_type + 's')
                        if ioc_set is not None:
                            ioc_set.update(matches)
            
            # Convert sets to lists for JSON serialization
            for key in ['ips', 'domains', 'urls', 'hashes', 'filenames', 'registry_keys']:
                iocs[key] = list(iocs[key])
                iocs['counts'][key] = len(iocs[key])
            
            # Send Telegram notification for IOCs
            total_iocs = sum(iocs['counts'].values())
            if total_iocs > 0:
                self.send_telegram_notification(
                    "🔍 IOCs Extracted",
                    f"Total IOCs: {total_iocs}\n"
                    f"IPs: {iocs['counts']['ips']}\n"
                    f"Domains: {iocs['counts']['domains']}\n"
                    f"Hashes: {iocs['counts']['hashes']}"
                )
            
            logger.debug(f"Extracted {total_iocs} IOCs from {len(data)} items", module="processor")
            return iocs
            
        except Exception as e:
            logger.error(f"IOC extraction error: {e}", module="processor")
            return {'error': str(e)}
    
    def _enrich_data(self, data: List[Dict]) -> List[Dict]:
        """Enrich data with additional information"""
        try:
            if not data:
                return []
            
            enriched_data = []
            
            for item in data:
                enriched = item.copy()
                
                # Add enrichment fields
                enriched['_enriched_at'] = datetime.now().isoformat()
                enriched['_hash'] = hashlib.md5(
                    json.dumps(item, sort_keys=True).encode()
                ).hexdigest()
                
                # Enrich based on data type
                if 'ip' in item:
                    # GeoIP enrichment (simulated)
                    ip = item['ip']
                    enriched['_geo'] = {
                        'country': self._get_country_from_ip(ip),
                        'asn': self._get_asn_from_ip(ip),
                        'location': 'Unknown'
                    }
                
                if 'timestamp' in item:
                    # Add time-based enrichment
                    try:
                        dt = datetime.fromisoformat(item['timestamp'].replace('Z', '+00:00'))
                        enriched['_time'] = {
                            'hour': dt.hour,
                            'day_of_week': dt.strftime('%A'),
                            'is_weekend': dt.weekday() >= 5
                        }
                    except:
                        pass
                
                enriched_data.append(enriched)
            
            logger.debug(f"Enriched {len(data)} items", module="processor")
            return enriched_data
            
        except Exception as e:
            logger.error(f"Data enrichment error: {e}", module="processor")
            return data
    
    def _get_country_from_ip(self, ip: str) -> str:
        """Simulated GeoIP lookup"""
        # In production, use a real GeoIP database
        ip_prefix = ip.split('.')[0]
        country_map = {
            '1': 'US', '2': 'FR', '3': 'DE', '4': 'UK',
            '5': 'CA', '6': 'AU', '7': 'JP', '8': 'CN',
            '9': 'RU', '10': 'BR'
        }
        return country_map.get(ip_prefix, 'Unknown')
    
    def _get_asn_from_ip(self, ip: str) -> str:
        """Simulated ASN lookup"""
        # In production, use a real ASN database
        ip_prefix = ip.split('.')[0]
        asn_map = {
            '1': 'AS7018', '2': 'AS3215', '3': 'AS3320',
            '4': 'AS3356', '5': 'AS6453', '6': 'AS1299',
            '7': 'AS2914', '8': 'AS4134', '9': 'AS8359',
            '10': 'AS27699'
        }
        return asn_map.get(ip_prefix, 'Unknown')
    
    def batch_process(self, tasks: List[Dict]) -> Dict[str, Any]:
        """Process multiple tasks in batch"""
        try:
            task_ids = []
            
            for task in tasks:
                task_id = self.submit_task(
                    task_type=task['type'],
                    data=task['data'],
                    priority=task.get('priority', 0)
                )
                task_ids.append(task_id)
            
            # Wait for all tasks to complete
            results = {}
            for task_id in task_ids:
                result = self.get_result(task_id, timeout=30)
                if result:
                    results[task_id] = result
            
            logger.info(f"Batch processed {len(tasks)} tasks, {len(results)} completed", module="processor")
            return {
                'total_tasks': len(tasks),
                'completed_tasks': len(results),
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Batch processing error: {e}", module="processor")
            return {'error': str(e)}
    
    def stop(self):
        """Stop data processor"""
        self.running = False
        
        # Send poison pills to workers
        for _ in range(len(self.workers)):
            self.processing_queue.put(None)
        
        # Wait for workers to finish
        for worker in self.workers:
            worker.join(timeout=5)
        
        self.workers.clear()
        
        logger.info("Data processor stopped", module="processor")
    
    def get_status(self) -> Dict[str, Any]:
        """Get processor status"""
        return {
            'running': self.running,
            'workers': len(self.workers),
            'queue_size': self.processing_queue.qsize(),
            'results_waiting': self.results_queue.qsize(),
            'telegram_available': self.telegram_bot is not None
        }

# Global instance
_data_processor = None

def get_data_processor(config: Dict = None) -> DataProcessor:
    """ data: Any, output_path: str = None,
                        protocol: int = pickle.HIGHEST_PROTOCOL) -> str:
        """Export data to pickle format"""
        try:
            if output_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"data/exports/export_{timestamp}.pkl"
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'wb') as f:
                pickle.dump(data, f, protocol=protocol)
            
            file_size = os.path.getsize(output_path)
            
            # Send Telegram notification
            self.send_telegram_notification(
                "Pickle Export Completed",
                f"File: {output_path}\n"
                f"Size: {file_size/(1024*1024):.2f} MB\n"
                f"Protocol: {protocol}",
                output_path
            )
            
            logger.info(f"Exported to pickle: {output_path} ({file_size} bytes)", module="exporter")
            return output_path
            
        except Exception as e:
            logger.error(f"Pickle export error: {e}", module="exporter")
            raise
    
    def export_to_zip(self, files: Dict[str, str], output_path: str = None,
                     compression: int = zipfile.ZIP_DEFLATED) -> str:
        """Export multiple files to ZIP archive"""
        try:
            if not files:
                raise ValueError("No files to export")
            
            if output_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"data/exports/export_{timestamp}.zip"
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with zipfile.ZipFile(output_path, 'w', compression) as zipf:
                for arcname, filepath in files.items():
                    if os.path.exists(filepath):
                        zipf.write(filepath, arcname=arcname)
            
            file_size = os.path.getsize(output_path)
            
            # Send Telegram notification
            self.send_telegram_notification(
                "ZIP Export Completed",
                f"File: {output_path}\n"
                f"Size: {file_size/(1024*1024):.2f} MB\n"
                f"Files: {len(files)}\n"
                f"Compression: {'DEFLATE' if compression == zipfile.ZIP_DEFLATED else 'STORED'}",
                output_path
            )
            
            logger.info(f"Exported to ZIP: {output_path} ({file_size} bytes, {len(files)} files)", module="exporter")
            return output_path
            
        except Exception as e:
            logger.error(f"ZIP export error: {e}", module="exporter")
            raise
    
    def export_to_tar(self, files: Dict[str, str], output_path: str = None,
                     compression: str = 'gz') -> str:
        """Export multiple files to TAR archive"""
        try:
            if not files:
                raise ValueError("No files to export")
            
            if output_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"data/exports/export_{timestamp}.tar.{compression}"
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            mode = 'w:gz' if compression == 'gz' else 'w:bz2' if compression == 'bz2' else 'w'
            
            with tarfile.open(output_path, mode) as tar:
                for arcname, filepath in files.items():
                    if os.path.exists(filepath):
                        tar.add(filepath, arcname=arcname)
            
            file_size = os.path.getsize(output_path)
            
            # Send Telegram notification
            self.send_telegram_notification(
                "TAR Export Completed",
                f"File: {output_path}\n"
                f"Size: {file_size/(1024*1024):.2f} MB\n"
                f"Files: {len(files)}\n"
                f"Compression: {compression.upper()}",
                output_path
            )
            
            logger.info(f"Exported to TAR: {output_path} ({file_size} bytes, {len(files)} files)", module="exporter")
            return output_path
            
        except Exception as e:
            logger.error(f"TAR export error: {e}", module="exporter")
            raise
    
    def export_encrypted(self, data: Any, output_path: str = None,
                        format: str = 'json', password: str = None) -> str:
        """Export data with encryption"""
        try:
            # First export to temporary file
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=f'.{format}') as tmp:
                tmp_path = tmp.name
                
                # Export to specified format
                if format == 'json':
                    json.dump(data, tmp, indent=2, default=str)
                elif format == 'csv' and isinstance(data, list):
                    fieldnames = data[0].keys() if data else []
                    writer = csv.DictWriter(tmp, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(data)
                else:
                    raise ValueError(f"Unsupported format for encryption: {format}")
            
            # Encrypt the file
            from ..utils.encryption import get_encryption_manager
            
            encryptor = get_encryption_manager({'key': password} if password else {})
            
            if output_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"data/exports/export_encrypted_{timestamp}.enc"
            
            encrypted_path = encryptor.encrypt_file(tmp_path, output_path)
            
            # Cleanup temporary file
            os.unlink(tmp_path)
            
            file_size = os.path.getsize(encrypted_path)
            
            # Send Telegram notification
            self.send_telegram_notification(
                "Encrypted Export Completed",
                f"File: {encrypted_path}\n"
                f"Size: {file_size/(1024*1024):.2f} MB\n"
                f"Format: {format}\n"
                f"Encrypted: AES-256",
                encrypted_path
            )
            
            logger.info(f"Exported encrypted: {encrypted_path} ({file_size} bytes)", module="exporter")
            return encrypted_path
            
        except Exception as e:
            logger.error(f"Encrypted export error: {e}", module="exporter")
            raise
    
    def export_to_multiple_formats(self, data: Any, formats: List[str],
                                  output_dir: str = None) -> Dict[str, str]:
        """Export data to multiple formats"""
        try:
            if output_dir is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_dir = f"data/exports/multi_{timestamp}"
            
            os.makedirs(output_dir, exist_ok=True)
            
            results = {}
            
            for fmt in formats:
                try:
                    if fmt == 'json':
                        output_path = os.path.join(output_dir, 'data.json')
                        results['json'] = self.export_to_json(data, output_path)
                    
                    elif fmt == 'csv' and isinstance(data, list):
                        output_path = os.path.join(output
