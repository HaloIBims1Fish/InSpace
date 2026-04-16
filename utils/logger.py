#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
logger.py - Advanced logging system with Telegram integration
"""

import logging
import logging.handlers
import os
import sys
import json
import threading
import queue
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

# Telegram imports
try:
    from telegram import Bot
    from telegram.error import TelegramError
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("⚠️  Telegram module not available, Telegram logging disabled")

class TelegramLogHandler(logging.Handler):
    """Log handler that sends logs to Telegram"""
    
    def __init__(self, bot_token: str, chat_id: int, 
                 level=logging.WARNING, max_length=4000):
        super().__init__(level)
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.max_length = max_length
        self.bot = None
        self.queue = queue.Queue()
        self.worker_thread = None
        self.start_worker()
    
    def start_worker(self):
        """Start background worker for sending messages"""
        if not TELEGRAM_AVAILABLE:
            return
        
        self.bot = Bot(token=self.bot_token)
        self.worker_thread = threading.Thread(
            target=self._send_worker,
            daemon=True,
            name="TelegramLogWorker"
        )
        self.worker_thread.start()
    
    def _send_worker(self):
        """Background worker that sends queued messages"""
        while True:
            try:
                message = self.queue.get()
                if message is None:  # Poison pill
                    break
                
                self.bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    parse_mode='HTML',
                    disable_web_page_preview=True
                )
            except TelegramError as e:
                print(f"❌ Telegram send error: {e}")
            except Exception as e:
                print(f"❌ Telegram worker error: {e}")
            finally:
                self.queue.task_done()
    
    def emit(self, record):
        """Emit a log record to Telegram"""
        if not TELEGRAM_AVAILABLE or not self.bot:
            return
        
        try:
            # Format message
            msg = self.format(record)
            
            # Truncate if too long
            if len(msg) > self.max_length:
                msg = msg[:self.max_length - 100] + "...\n[TRUNCATED]"
            
            # Add timestamp and level
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            level_emoji = {
                'DEBUG': '🔍',
                'INFO': 'ℹ️',
                'WARNING': '⚠️',
                'ERROR': '❌',
                'CRITICAL': '💀'
            }.get(record.levelname, '📝')
            
            formatted_msg = (
                f"<b>{level_emoji} {record.levelname}</b>\n"
                f"<code>{timestamp}</code>\n"
                fpre>{msg}</pre>\n"
                f"i>Module: {record.modulei>"
            )
            
            # Queue for sending
            self.queue.put(formatted_msg)
            
        except Exception as e:
            print(f"❌ Error formatting Telegram log: {e}")
    
    def close(self):
        """Clean up handler"""
        if self.worker_thread:
            self.queue.put(None)  # Send poison pill
            self.worker_thread.join(timeout=5)
        super().close()

class AdvancedLogger:
    """Advanced logging system with multiple outputs"""
    
    def __init__(self, name: str, config: Dict[str, Any] = None):
        self.name = name
        self.config = config or {}
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # Remove existing handlers
        self.logger.handlers.clear()
        
        # Setup handlers
        self.setup_handlers()
        
        # Statistics
        self.stats = {
            'total_logs': 0,
            'by_level': {},
            'last_log': None
        }
    
    def setup_handlers(self):
        """Setup all log handlers"""
        log_dir = self.config.get('log_dir', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        # 1. Console Handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_format)
        console_handler.setLevel(logging.INFO)
        self.logger.addHandler(console_handler)
        
        # 2. File Handler (Rotating)
        log_file = os.path.join(log_dir, f"{self.name}.log")
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10 MB
            backupCount=5,
            encoding='utf-8'
        )
        file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - '
            '%(module)s:%(funcName)s:%(lineno)d - %(message)s'
        )
        file_handler.setFormatter(file_format)
        file_handler.setLevel(logging.DEBUG)
        self.logger.addHandler(file_handler)
        
        # 3. JSON Handler (for structured logging)
        json_file = os.path.join(log_dir, f"{self.name}_structured.json")
        json_handler = logging.handlers.RotatingFileHandler(
            json_file,
            maxBytes=5*1024*1024,  # 5 MB
            backupCount=3,
            encoding='utf-8'
        )
        json_handler.setFormatter(JSONFormatter())
        json_handler.setLevel(logging.INFO)
        self.logger.addHandler(json_handler)
        
        # 4. Telegram Handler (if configured)
        telegram_config = self.config.get('telegram', {})
        bot_token = telegram_config.get('bot_token')
        chat_id = telegram_config.get('log_chat_id')
        
        if bot_token and chat_id and TELEGRAM_AVAILABLE:
            telegram_handler = TelegramLogHandler(
                bot_token=bot_token,
                chat_id=chat_id,
                level=logging.WARNING  # Only warnings and above
            )
            telegram_format = logging.Formatter('%(message)s')
            telegram_handler.setFormatter(telegram_format)
            self.logger.addHandler(telegram_handler)
        
        # 5. Error Email Handler (optional)
        if self.config.get('email_alerts', {}).get('enabled', False):
            email_config = self.config['email_alerts']
            email_handler = logging.handlers.SMTPHandler(
                mailhost=email_config.get('smtp_server'),
                fromaddr=email_config.get('from_email'),
                toaddrs=email_config.get('to_emails', []),
                subject=f"🚨 {self.name} - Critical Error",
                credentials=(
                    email_config.get('username'),
                    email_config.get('password')
                ),
                secure=()
            )
            email_handler.setLevel(logging.ERROR)
            self.logger.addHandler(email_handler)
    
    def log(self, level: str, message: str, **kwargs):
        """Log with additional context"""
        extra = {
            'module': kwargs.get('module', 'unknown'),
            'user_id': kwargs.get('user_id'),
            'action': kwargs.get('action'),
            'data': kwargs.get('data'),
            'telegram_update': kwargs.get('telegram_update')
        }
        
        # Update statistics
        self.stats['total_logs'] += 1
        self.stats['by_level'][level] = self.stats['by_level'].get(level, 0) + 1
        self.stats['last_log'] = datetime.now().isoformat()
        
        # Log based on level
        if level == 'DEBUG':
            self.logger.debug(message, extra=extra)
        elif level == 'INFO':
            self.logger.info(message, extra=extra)
        elif level == 'WARNING':
            self.logger.warning(message, extra=extra)
        elif level == 'ERROR':
            self.logger.error(message, extra=extra)
        elif level == 'CRITICAL':
            self.logger.critical(message, extra=extra)
    
    def debug(self, message: str, **kwargs):
        """Debug log"""
        self.log('DEBUG', message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Info log"""
        self.log('INFO', message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Warning log"""
        self.log('WARNING', message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Error log"""
        self.log('ERROR', message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Critical log"""
        self.log('CRITICAL', message, **kwargs)
    
    def telegram_command(self, update, context, command: str):
        """Log Telegram command with context"""
        user = update.effective_user
        self.info(
            f"Telegram command: {command}",
            module="telegram",
            user_id=user.id,
            username=user.username,
            action=command,
            telegram_update=update.update_id
        )
    
    def module_start(self, module_name: str):
        """Log module startup"""
        self.info(
            f"Module '{module_name}' started",
            module=module_name,
            action="start"
        )
    
    def module_stop(self, module_name: str):
        """Log module shutdown"""
        self.info(
            f"Module '{module_name}' stopped",
            module=module_name,
            action="stop"
        )
    
    def encryption_event(self, action: str, details: str):
        """Log encryption events"""
        self.info(
            f"Encryption: {action} - {details}",
            module="encryption",
            action=action,
            data=details
        )
    
    def network_event(self, action: str, target: str, success: bool):
        """Log network events"""
        level = 'INFO' if success else 'ERROR'
        self.log(
            level,
            f"Network {action}: {target} - {'Success' if success else 'Failed'}",
            module="network",
            action=action,
            data=target
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get logging statistics"""
        return {
            **self.stats,
            'handlers': len(self.logger.handlers),
            'level': self.logger.level,
            'name': self.name
        }
    
    def export_logs(self, output_file: str, level: str = 'INFO'):
        """Export logs to file"""
        try:
            logs = []
            log_dir = self.config.get('log_dir', 'logs')
            log_file = os.path.join(log_dir, f"{self.name}.log")
            
            if os.path.exists(log_file):
                with open(log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if level in line or level == 'ALL':
                            logs.append(line.strip())
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(logs))
            
            self.info(f"Logs exported to {output_file}", action="export")
            return True
        except Exception as e:
            self.error(f"Failed to export logs: {e}", action="export")
            return False
    
    def clear_logs(self, days_old: int = 30):
        """Clear logs older than X days"""
        try:
            log_dir = self.config.get('log_dir', 'logs')
            cutoff = datetime.now().timestamp() - (days_old * 86400)
            cleared = 0
            
            for file in Path(log_dir).glob('*.log*'):
                if file.stat().st_m cutoff:
                    file.unlink()
                    cleared += 1
            
            self.info(f"Cleared {cleared} old log files", action="cleanup")
            return cleared
        except Exception as e:
            self.error(f"Failed to clear logs: {e}", action="cleanup")
            return 0

class JSONFormatter(logging.Formatter):
    """Formatter for JSON structured logging"""
    
    def format(self, record):
        """Format record as JSON"""
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'module': getattr(record, 'module', 'unknown'),
            'function': record.funcName,
            'line': record.lineno,
            'message': record.getMessage(),
            'user_id': getattr(record, 'user_id', None),
            'action': getattr(record, 'action', None),
            'data': getattr(record, 'data', None)
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry, ensure_ascii=False)

# Global logger instance
_logger_instance = None

def get_logger(name: str = "DerBoeseKollege", config: Dict = None) -> AdvancedLogger:
    """Get or create logger instance"""
    global _logger_instance
    
    if _logger_instance is None or _logger_instance.name != name:
        _logger_instance = AdvancedLogger(name, config)
    
    return _logger_instance

if __name__ == "__main__":
    # Test the logger
    config = {
        'log_dir': 'logs',
        'telegram': {
            'bot_token': 'test_token',
            'log_chat_id': 123456789
        }
    }
    
    logger = get_logger("TestLogger", config)
    
    # Test different log levels
    logger.debug("Debug message", module="test")
    logger.info("Info message", module="test", user_id=123)
    logger.warning("Warning message", module="test", action="test_action")
    logger.error("Error message", module="test", data={"test": "data"})
    logger.critical("Critical message", module="test")
    
    # Test module events
    logger.module_start("datensammler")
    logger.encryption_event("encrypt", "file.txt")
    logger.network_event("connect", "192.168.1.1", True)
    
    # Show statistics
    stats = logger.get_statistics()
    print(f"\n📊 Log Statistics: {stats}")
    
    print("\n✅ Logger test completed!")
