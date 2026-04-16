#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mongodb_db.py - MongoDB database manager with Telegram integration
"""

import pymongo
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import ConnectionFailure, OperationFailure
import bson
from bson import ObjectId, json_util
import json
import hashlib
import os
import time
import threading
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime
from urllib.parse import quote_plus

# Import logger
from ..utils.logger import get_logger

logger = get_logger()

class MongoDBManager:
    """Manages MongoDB database operations with encryption and Telegram notifications"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {
            'host': 'localhost',
            'port': 27017,
            'database': 'derboesekollege',
            'username': None,
            'password': None,
            'auth_source': 'admin',
            'use_tls': False,
            'replica_set': None,
            'timeout': 5000,
            'max_pool_size': 100
        }
        
        # Update config with provided values
        if config:
            self.config.update(config)
        
        # Telegram bot for notifications
        self.telegram_bot = None
        self.setup_telegram()
        
        # MongoDB client
        self.client = None
        self.db = None
        self.collections = {}
        
        # Connection status
        self.connected = False
        self.connection_error = None
        
        # Initialize connection
        self._connect()
        
        logger.info("MongoDB manager initialized", module="mongodb")
    
    def setup_telegram(self):
        """Setup Telegram bot for notifications"""
        telegram_config = self.config.get('telegram', {})
        bot_token = telegram_config.get('bot_token')
        chat_id = telegram_config.get('mongodb_chat_id')
        
        if bot_token and chat_id:
            try:
                from telegram import Bot
                self.telegram_bot = Bot(token=bot_token)
                self.mongodb_chat_id = chat_id
                logger.info("Telegram MongoDB bot initialized", module="mongodb")
            except ImportError:
                logger.warning("Telegram module not available", module="mongodb")
            except Exception as e:
                logger.error(f"Error setting up Telegram: {e}", module="mongodb")
    
    def send_telegram_notification(self, title: str, message: str):
        """Send MongoDB notification to Telegram"""
        if not self.telegram_bot or not hasattr(self, 'mongodb_chat_id'):
            return
        
        try:
            full_message = fb>🌐 {b>\n\n{message}"
            self.telegram_bot.send_message(
                chat_id=self.mongodb_chat_id,
                text=full_message,
                parse_mode='HTML'
            )
            logger.debug(f"Telegram MongoDB notification sent: {title}", module="mongodb")
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}", module="mongodb")
    
    def _connect(self):
        """Connect to MongoDB"""
        try:
            # Build connection string
            if self.config.get('username') and self.config.get('password'):
                username = quote_plus(self.config['username'])
                password = quote_plus(self.config['password'])
                host = self.config.get('host', 'localhost')
                port = self.config.get('port', 27017)
                auth_source = self.config.get('auth_source', 'admin')
                
                connection_string = f"mongodb://{username}:{password}@{host}:{port}/?authSource={auth_source}"
            else:
                host = self.config.get('host', 'localhost')
                port = self.config.get('port', 27017)
                connection_string = f"mongodb://{host}:{port}/"
            
            # Add TLS option
            if self.config.get('use_tls', False):
                connection_string += "&tls=true"
            
            # Add replica set
            if self.config.get('replica_set'):
                connection_string += f"&replicaSet={self.config['replica_set']}"
            
            # Create client
            self.client = MongoClient(
                connection_string,
                serverSelectionTimeoutMS=self.config.get('timeout', 5000),
                maxPoolSize=self.config.get('max_pool_size', 100),
                connectTimeoutMS=5000,
                socketTimeoutMS=30000
            )
            
            # Test connection
            self.client.admin.command('ping')
            
            # Get database
            database_name = self.config.get('database', 'derboesekollege')
            self.db = self.client[database_name]
            
            # Initialize collections
            self._initialize_collections()
            
            self.connected = True
            self.connection_error = None
            
            # Send Telegram notification
            self.send_telegram_notification(
                "MongoDB Connected",
                f"Host: {self.config.get('host')}\n"
                f"Database: {database_name}\n"
                f"Collections: {len(self.collections)}"
            )
            
            logger.info(f"MongoDB connected to {database_name}", module="mongodb")
            
        except ConnectionFailure as e:
            self.connected = False
            self.connection_error = str(e)
            logger.error(f"MongoDB connection failed: {e}", module="mongodb")
        except Exception as e:
            self.connected = False
            self.connection_error = str(e)
            logger.error(f"MongoDB connection error: {e}", module="mongodb")
    
    def _initialize_collections(self):
        """Initialize MongoDB collections"""
        collections = [
            'system_info',
            'network_scans',
            'processes',
            'file_operations',
            'command_history',
            'telegram_interactions',
            'keylogger_data',
            'screenshots',
            'webcam_captures',
            'audio_recordings',
            'network_traffic',
            'credentials',
            'users',
            'sessions',
            'logs'
        ]
        
        for collection_name in collections:
            self.collections[collection_name] = self.db[collection_name]
            
            # Create indexes for performance
            if collection_name in ['system_info', 'processes', 'command_history', 'telegram_interactions']:
                self.collections[collection_name].create_index([('timestamp', DESCENDING)])
            
            if collection_name == 'network_scans':
                self.collections[collection_name].create_index([('scan_type', ASCENDING)])
            
            if collection_name == 'credentials':
                self.collections[collection_name].create_index([('username', ASCENDING)])
                self.collections[collection_name].create_index([('application', ASCENDING)])
        
        logger.debug(f"Initialized {len(collections)} MongoDB collections", module="mongodb")
    
    def reconnect(self):
        """Reconnect to MongoDB"""
        try:
            if self.client:
                self.client.close()
            
            self._connect()
            return self.connected
            
        except Exception as e:
            logger.error(f"Reconnection failed: {e}", module="mongodb")
            return False
    
    def is_connected(self) -> bool:
        """Check if connected to MongoDB"""
        if not self.connected:
            return False
        
        try:
            self.client.admin.command('ping')
            return True
        except:
            self.connected = False
            return False
    
    def insert_document(self, collection: str, document: Dict) -> Optional[str]:
        """Insert a document into collection"""
        if not self.is_connected():
            logger.error("MongoDB not connected", module="mongodb")
            return None
        
        try:
            # Add timestamp if not present
            if 'timestamp' not in document:
                document['timestamp'] = datetime.now()
            
            # Insert document
            result = self.collections[collection].insert_one(document)
            document_id = str(result.inserted_id)
            
            logger.debug(f"Document inserted into {collection} with ID: {document_id}", module="mongodb")
            return document_id
            
        except Exception as e:
            logger.error(f"Error inserting document into {collection}: {e}", module="mongodb")
            return None
    
    def insert_many(self, collection: str, documents: List[Dict]) -> List[str]:
        """Insert multiple documents"""
        if not self.is_connected():
            logger.error("MongoDB not connected", module="mongodb")
            return []
        
        try:
            # Add timestamps
            for doc in documents:
                if 'timestamp' not in doc:
                    doc['timestamp'] = datetime.now()
            
            # Insert documents
            result = self.collections[collection].insert_many(documents)
            document_ids = [str(id) for id in result.inserted_ids]
            
            # Send Telegram notification for large inserts
            if len(documents) > 100:
                self.send_telegram_notification(
                    "Bulk Insert Completed",
                    f"Collection: {collection}\n"
                    f"Documents: {len(documents)}\n"
                    f"IDs: {len(document_ids)}"
                )
            
            logger.debug(f"Inserted {len(documents)} documents into {collection}", module="mongodb")
            return document_ids
            
        except Exception as e:
            logger.error(f"Error inserting documents into {collection}: {e}", module="mongodb")
            return []
    
    def find_documents(self, collection: str, query: Dict = None, 
                      projection: Dict = None, limit: int = 100, 
                      skip: int = 0, sort: List[Tuple] = None) -> List[Dict]:
        """Find documents in collection"""
        if not self.is_connected():
            logger.error("MongoDB not connected", module="mongodb")
            return []
        
        try:
            query = query or {}
            projection = projection or {}
            sort = sort or [('timestamp', DESCENDING)]
            
            cursor = self.collections[collection].find(
                query,
                projection,
                limit=limit,
                skip=skip
            ).sort(sort)
            
            documents = list(cursor)
            
            # Convert ObjectId to string
            for doc in documents:
                if '_id' in doc:
                    doc['_id'] = str(doc['_id'])
            
            logger.debug(f"Found {len(documents)} documents in {collection}", module="mongodb")
            return documents
            
        except Exception as e:
            logger.error(f"Error finding documents in {collection}: {e}", module="mongodb")
            return []
    
    def find_one(self, collection: str, query: Dict = None, 
                projection: Dict = None) -> Optional[Dict]:
        """Find one document in collection"""
        if not self.is_connected():
            logger.error("MongoDB not connected", module="mongodb")
            return None
        
        try:
            query = query or {}
            projection = projection or {}
            
            document = self.collections[collection].find_one(query, projection)
            
            if document and '_id' in document:
                document['_id'] = str(document['_id'])
            
            return document
            
        except Exception as e:
            logger.error(f"Error finding document in {collection}: {e}", module="mongodb")
            return None
    
    def update_document(self, collection: str, query: Dict, 
                       update: Dict, upsert: bool = False) -> bool:
        """Update document in collection"""
        if not self.is_connected():
            logger.error("MongoDB not connected", module="mongodb")
            return False
        
        try:
            # Add update timestamp
            if '$set' in update:
                update['$set']['updated_at'] = datetime.now()
            else:
                update['$set'] = {'updated_at': datetime.now()}
            
            result = self.collections[collection].update_one(query, update, upsert=upsert)
            
            modified = result.modified_count > 0
            upserted = result.upserted_id is not None
            
            logger.debug(f"Document updated in {collection}: modified={modified}, upserted={upserted}", module="mongodb")
            return True
            
        except Exception as e:
            logger.error(f"Error updating document in {collection}: {e}", module="mongodb")
            return False
    
    def update_many(self, collection: str, query: Dict, update: Dict) -> int:
        """Update multiple documents"""
        if not self.is_connected():
            logger.error("MongoDB not connected", module="mongodb")
            return 0
        
        try:
            # Add update timestamp
            if '$set' in update:
                update['$set']['updated_at'] = datetime.now()
            else:
                update['$set'] = {'updated_at': datetime.now()}
            
            result = self.collections[collection].update_many(query, update)
            
            logger.debug(f"Updated {result.modified_count} documents in {collection}", module="mongodb")
            return result.modified_count
            
        except Exception as e:
            logger.error(f"Error updating documents in {collection}: {e}", module="mongodb")
            return 0
    
    def delete_document(self, collection: str, query: Dict) -> bool:
        """Delete document from collection"""
        if not self.is_connected():
            logger.error("MongoDB not connected", module="mongodb")
            return False
        
        try:
            result = self.collections[collection].delete_one(query)
            
            deleted = result.deleted_count > 0
            logger.debug(f"Document deleted from {collection}: {deleted}", module="mongodb")
            return deleted
            
        except Exception as e:
            logger.error(f"Error deleting document from {collection}: {e}", module="mongodb")
            return False
    
    def delete_many(self, collection: str, query: Dict) -> int:
        """Delete multiple documents"""
        if not self.is_connected():
            logger.error("MongoDB not connected", module="mongodb")
            return 0
        
        try:
            result = self.collections[collection].delete_many(query)
            
            # Send Telegram notification for large deletions
            if result.deleted_count > 100:
                self.send_telegram_notification(
                    "Bulk Deletion",
                    f"Collection: {collection}\n"
                    f"Documents deleted: {result.deleted_count}\n"
                    f"Query: {str(query)[:100]}..."
                )
            
            logger.debug(f"Deleted {result.deleted_count} documents from {collection}", module="mongodb")
            return result.deleted_count
            
        except Exception as e:
            logger.error(f"Error deleting documents from {collection}: {e}", module="mongodb")
            return 0
    
    def count_documents(self, collection: str, query: Dict = None) -> int:
        """Count documents in collection"""
        if not self.is_connected():
            logger.error("MongoDB not connected", module="mongodb")
            return 0
        
        try:
            query = query or {}
            count = self.collections[collection].count_documents(query)
            return count
            
        except Exception as e:
            logger.error(f"Error counting documents in {collection}: {e}", module="mongodb")
            return 0
    
    def aggregate(self, collection: str, pipeline: List[Dict]) -> List[Dict]:
        """Aggregate documents"""
        if not self.is_connected():
            logger.error("MongoDB not connected", module="mongodb")
            return []
        
        try:
            cursor = self.collections[collection].aggregate(pipeline)
            results = list(cursor)
            
            # Convert ObjectId to string
            for doc in results:
                if '_id' in doc:
                    if isinstance(doc['_id'], ObjectId):
                        doc['_id'] = str(doc['_id'])
            
            logger.debug(f"Aggregation returned {len(results)} documents from {collection}", module="mongodb")
            return results
            
        except Exception as e:
            logger.error(f"Error aggregating documents in {collection}: {e}", module="mongodb")
            return []
    
    def create_index(self, collection: str, keys: List[Tuple], 
                    unique: bool = False, background: bool = True) -> bool:
        """Create index on collection"""
        if not self.is_connected():
            logger.error("MongoDB not connected", module="mongodb")
            return False
        
        try:
            index_name = self.collections[collection].create_index(
                keys,
                unique=unique,
                background=background
            )
            
            logger.debug(f"Index created on {collection}: {index_name}", module="mongodb")
            return True
            
        except Exception as e:
            logger.error(f"Error creating index on {collection}: {e}", module="mongodb")
            return False
    
    def get_collection_stats(self, collection: str) -> Dict[str, Any]:
        """Get collection statistics"""
        if not self.is_connected():
            logger.error("MongoDB not connected", module="mongodb")
            return {}
        
        try:
            # Use MongoDB stats command
            stats = self.db.command('collStats', collection)
            
            # Convert to serializable format
            result = {
                'count': stats.get('count', 0),
                'size': stats.get('size', 0),
                'storage_size': stats.get('storageSize', 0),
                'total_index_size': stats.get('totalIndexSize', 0),
                'avg_object_size': stats.get('avgObjSize', 0),
                'num_indexes': stats.get('nindexes', 0)
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting stats for {collection}: {e}", module="mongodb")
            return {}
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        if not self.is_connected():
            logger.error("MongoDB not connected", module="mongodb")
            return {}
        
        try:
            # Get database stats
            db_stats = self.db.command('dbStats')
            
            # Get collection stats for each collection
            collections_stats = {}
            for collection_name in self.collections.keys():
                coll_stats = self.get_collection_stats(collection_name)
                if coll_stats:
                    collections_stats[collection_name] = coll_stats
            
            result = {
                'database': self.config.get('database'),
                'collections': len(self.collections),
                'total_size': db_stats.get('dataSize', 0),
                'storage_size': db_stats.get('storageSize', 0),
                'objects': db_stats.get('objects', 0),
                'collections_stats': collections_stats
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting database stats: {e}", module="mongodb")
            return {}
    
    def backup_collection(self, collection: str, output_file: str = None) -> bool:
        """Backup collection to JSON file"""
        if not self.is_connected():
            logger.error("MongoDB not connected", module="mongodb")
            return False
        
        try:
            if output_file is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = f"data/backups/mongodb_{collection}_{timestamp}.json"
            
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            # Get all documents
            documents = self.find_documents(collection, limit=1000000)
            
            # Write to JSON with BSON serialization
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(documents, f, indent=2, default=json_util.default)
            
            file_size = os.path.getsize(output_file)
            
            # Send Telegram notification
            self.send_telegram_notification(
                "MongoDB Backup Created",
                f"Collection: {collection}\n"
                f"Documents: {len(documents)}\n"
                f"Backup file: {output_file}\n"
                f"Size: {file_size/(1024*1024):.2f} MB"
            )
            
            logger.info(f"Backup created for {collection}: {len(documents)} documents, {file_size} bytes", module="mongodb")
            return True
            
        except Exception as e:
            logger.error(f"Error backing up collection {collection}: {e}", module="mongodb")
            return False
    
    def cleanup_old_data(self, collection: str, days_to_keep: int = 30) -> int:
        """Cleanup old data from collection"""
        if not self.is_connected():
            logger.error("MongoDB not connected", module="mongodb")
            return 0
        
        try:
            # Calculate cutoff date
            cutoff_date = datetime.now().timestamp() - (days_to_keep * 24 * 60 * 60)
            cutoff_datetime = datetime.fromtimestamp(cutoff_date)
            
            # Delete old documents
            query = {'timestamp': {'$lt': cutoff_datetime}}
            result = self.delete_many(collection, query)
            
            logger.info(f"Cleaned up {result} documents from {collection} older than {days_to_keep} days", module="mongodb")
            return result
            
        except Exception as e:
            logger.error(f"Error cleaning up {collection}: {e}", module="mongodb")
            return 0
    
    def export_to_csv(self, collection: str, output_file: str = None, 
                     fields: List[str] = None) -> bool:
        """Export collection to CSV"""
        if not self.is_connected():
            logger.error("MongoDB not connected", module="mongodb")
            return False
        
        try:
            if output_file is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = f"data/exports/mongodb_{collection}_{timestamp}.csv"
            
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            # Get documents
            documents = self.find_documents(collection, limit=100000)
            
            if not documents:
                logger.warning(f"No documents to export from {collection}", module="mongodb")
                return False
            
            # Determine fields
            if fields is None:
                # Get all fields from first document
                fields = list(documents[0].keys())
                # Remove _id if present
                if '_id' in fields:
                    fields.remove('_id')
            
            # Write CSV
            import csv
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                
                for doc in documents:
                    # Filter and flatten document
                    row = {}
                    for field in fields:
                        value = doc.get(field, '')
                        # Convert complex types to string
                        if isinstance(value, (dict, list)):
                            value = json.dumps(value, default=str)
                        elif isinstance(value, datetime):
                            value = value.isoformat()
                        row[field] = str(value)
                    writer.writerow(row)
            
            file_size = os.path.getsize(output_file)
            
            logger.info(f"Exported {len(documents)} documents from {collection} to CSV: {output_file} ({file_size} bytes)", module="mongodb")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting {collection} to CSV: {e}", module="mongodb")
            return False
    
    def close(self):
        """Close MongoDB connection"""
        try:
            if self.client:
                self.client.close()
                self.connected = False
                logger.info("MongoDB connection closed", module="mongodb")
        except Exception as e:
            logger.error(f"Error closing MongoDB connection: {e}", module="mongodb")
    
    def get_status(self) -> Dict[str, Any]:
        """Get MongoDB manager status"""
        stats = self.get_database_stats() if self.is_connected() else {}
        
        return {
            'connected': self.is_connected(),
            'connection_error': self.connection_error,
            'database': self.config.get('database'),
            'host': self.config.get('host'),
            'port': self.config.get('port'),
            'collections': len(self.collections),
            'total_documents': stats.get('objects', 0),
            'total_size': stats.get('total_size', 0),
            'telegram_available': self.telegram_bot is not None
        }

# Global instance
_mongodb_manager = None

def get_mongodb_manager(config: Dict = None) -> MongoDBManager:
    """Get or create MongoDB manager instance"""
    global _mongodb_manager
    
    if _mongodb_manager is None:
        _mongodb_manager = MongoDBManager(config)
    
    return _mongodb_manager

if __name__ == "__main__":
    # Test the MongoDB manager
    config = {
        'host': 'localhost',
        'port': 27017,
        'database': 'test_db',
        'telegram': {
            'bot_token': 'test_token',
            'mongodb_chat_id': 123456789
        }
    }
    
    manager = get_mongodb_manager(config)
    
    if manager.is_connected():
        print("MongoDB connected successfully!")
        
        # Test insert
        test_doc = {
            'test_field': 'test_value',
            'number': 42,
            'list': [1, 2, 3],
            'nested': {'key': 'value'}
        }
        
        doc_id = manager.insert_document('test_collection', test_doc)
        print(f"Document inserted with ID: {doc_id}")
        
        # Test find
        documents = manager.find_documents('test_collection', limit=5)
        print(f"Found {len(documents)} documents")
        
        # Test stats
        stats = manager.get_database_stats()
        print(f"Database stats: {stats.get('objects', 0)} documents")
        
        # Cleanup
        manager.delete_many('test_collection', {})
        
    else:
        print(f"MongoDB connection failed: {manager.connection_error}")
    
    # Show status
    status = manager.get_status()
    print(f"\n🌐 MongoDB Manager Status: {status}")
    
    # Close connection
    manager.close()
    
    print("\n✅ MongoDB tests completed!")
