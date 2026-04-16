#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exporter.py - Data export functions for various formats
"""

import json
import csv
import pandas as pd
import yaml
import xml.etree.ElementTree as ET
import xml.dom.minidom
import pickle
import sqlite3
import zipfile
import tarfile
import hashlib
import base64
import io
import os
import tempfile
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime
from pathlib import Path
import threading

# Import logger
from ..utils.logger import get_logger

logger = get_logger()

class DataExporter:
    """Exports data to various formats with encryption and compression"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # Telegram bot for notifications
        self.telegram_bot = None
        self.setup_telegram()
        
        # Export formats
        self.supported_formats = [
            'json', 'csv', 'xlsx', 'xml', 'yaml', 'html', 
            'pdf', 'sqlite', 'pickle', 'zip', 'tar'
        ]
        
        logger.info("Data exporter initialized", module="exporter")
    
    def setup_telegram(self):
        """Setup Telegram bot for notifications"""
        telegram_config = self.config.get('telegram', {})
        bot_token = telegram_config.get('bot_token')
        chat_id = telegram_config.get('exporter_chat_id')
        
        if bot_token and chat_id:
            try:
                from telegram import Bot
                self.telegram_bot = Bot(token=bot_token)
                self.exporter_chat_id = chat_id
                logger.info("Telegram exporter bot initialized", module="exporter")
            except ImportError:
                logger.warning("Telegram module not available", module="exporter")
            except Exception as e:
                logger.error(f"Error setting up Telegram: {e}", module="exporter")
    
    def send_telegram_notification(self, title: str, message: str, 
                                 file_path: str = None):
        """Send export notification to Telegram"""
        if not self.telegram_bot or not hasattr(self, 'exporter_chat_id'):
            return
        
        try:
            full_message = fb>📤 {b>\n\n{message}"
            
            if file_path and os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                
                # Check file size (Telegram has 50MB limit)
                if file_size50 * 1024 * 1024:  # 50 MB
                    with open(file_path, 'rb') as f:
                        self.telegram_bot.send_document(
                            chat_id=self.exporter_chat_id,
                            document=f,
                            caption=full_message,
                            parse_mode='HTML'
                        )
                    logger.debug(f"File sent via Telegram: {file_path} ({file_size} bytes)", module="exporter")
                else:
                    self.telegram_bot.send_message(
                        chat_id=self.exporter_chat_id,
                        text=full_message + f"\n\nFile too large for Telegram: {file_size/(1024*1024):.1f} MB",
                        parse_mode='HTML'
                    )
            else:
                self.telegram_bot.send_message(
                    chat_id=self.exporter_chat_id,
                    text=full_message,
                    parse_mode='HTML'
                )
                
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}", module="exporter")
    
    def export_to_json(self, data: Any, output_path: str = None, 
                      indent: int = 2, sort_keys: bool = True) -> str:
        """Export data to JSON format"""
        try:
            if output_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"data/exports/export_{timestamp}.json"
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=indent, sort_keys=sort_keys, default=str)
            
            file_size = os.path.getsize(output_path)
            
            # Send Telegram notification
            self.send_telegram_notification(
                "JSON Export Completed",
                f"File: {output_path}\n"
                f"Size: {file_size/(1024*1024):.2f} MB\n"
                f"Items: {self._count_items(data)}",
                output_path
            )
            
            logger.info(f"Exported to JSON: {output_path} ({file_size} bytes)", module="exporter")
            return output_path
            
        except Exception as e:
            logger.error(f"JSON export error: {e}", module="exporter")
            raise
    
    def export_to_csv(self, data: List[Dict], output_path: str = None,
                     delimiter: str = ',', encoding: str = 'utf-8') -> str:
        """Export data to CSV format"""
        try:
            if not data:
                raise ValueError("No data to export")
            
            if output_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"data/exports/export_{timestamp}.csv"
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Get all fieldnames
            fieldnames = set()
            for row in data:
                fieldnames.update(row.keys())
            fieldnames = list(fieldnames)
            
            with open(output_path, 'w', newline='', encoding=encoding) as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=delimiter)
                writer.writeheader()
                
                for row in data:
                    # Flatten nested structures
                    flat_row = {}
                    for key, value in row.items():
                        if isinstance(value, (dict, list)):
                            flat_row[key] = json.dumps(value, default=str)
                        else:
                            flat_row[key] = str(value) if value is not None else ''
                    writer.writerow(flat_row)
            
            file_size = os.path.getsize(output_path)
            
            # Send Telegram notification
            self.send_telegram_notification(
                "CSV Export Completed",
                f"File: {output_path}\n"
                f"Size: {file_size/(1024*1024):.2f} MB\n"
                f"Rows: {len(data)}\n"
                f"Columns: {len(fieldnames)}",
                output_path
            )
            
            logger.info(f"Exported to CSV: {output_path} ({file_size} bytes, {len(data)} rows)", module="exporter")
            return output_path
            
        except Exception as e:
            logger.error(f"CSV export error: {e}", module="exporter")
            raise
    
    def export_to_excel(self, data: Dict[str, List[Dict]], output_path: str = None) -> str:
        """Export data to Excel format (multiple sheets)"""
        try:
            if not data:
                raise ValueError("No data to export")
            
            if output_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"data/exports/export_{timestamp}.xlsx"
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Create Excel writer
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                for sheet_name, sheet_data in data.items():
                    if sheet_data:
                        # Convert to DataFrame
                        df = pd.DataFrame(sheet_data)
                        
                        # Write to Excel sheet
                        df.to_excel(writer, sheet_name=sheet_name[:31], index=False)  # Sheet names max 31 chars
            
            file_size = os.path.getsize(output_path)
            
            # Send Telegram notification
            self.send_telegram_notification(
                "Excel Export Completed",
                f"File: {output_path}\n"
                f"Size: {file_size/(1024*1024):.2f} MB\n"
                f"Sheets: {len(data)}\n"
                f"Total rows: {sum(len(sheet) for sheet in data.values())}",
                output_path
            )
            
            logger.info(f"Exported to Excel: {output_path} ({file_size} bytes, {len(data)} sheets)", module="exporter")
            return output_path
            
        except Exception as e:
            logger.error(f"Excel export error: {e}", module="exporter")
            raise
    
    def export_to_xml(self, data: Dict, output_path: str = None,
                     root_tag: str = 'data') -> str:
        """Export data to XML format"""
        try:
            if output_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"data/exports/export_{timestamp}.xml"
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            def dict_to_xml(tag: str, d: Dict) -> ET.Element:
                """Convert dictionary to XML element"""
                elem = ET.Element(tag)
                
                for key, val in d.items():
                    if isinstance(val, dict):
                        child = dict_to_xml(key, val)
                        elem.append(child)
                    elif isinstance(val, list):
                        for item in val:
                            if isinstance(item, dict):
                                child = dict_to_xml(key, item)
                            else:
                                child = ET.Element(key)
                                child.text = str(item)
                            elem.append(child)
                    else:
                        child = ET.Element(key)
                        child.text = str(val)
                        elem.append(child)
                
                return elem
            
            # Create root element
            root = dict_to_xml(root_tag, data)
            
            # Create XML tree
            tree = ET.ElementTree(root)
            
            # Write to file with pretty formatting
            xml_str = ET.tostring(root, encoding='unicode')
            dom = xml.dom.minidom.parseString(xml_str)
            pretty_xml = dom.toprettyxml(indent='  ')
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(pretty_xml)
            
            file_size = os.path.getsize(output_path)
            
            # Send Telegram notification
            self.send_telegram_notification(
                "XML Export Completed",
                f"File: {output_path}\n"
                f"Size: {file_size/(1024*1024):.2f} MB\n"
                f"Root tag: {root_tag}",
                output_path
            )
            
            logger.info(f"Exported to XML: {output_path} ({file_size} bytes)", module="exporter")
            return output_path
            
        except Exception as e:
            logger.error(f"XML export error: {e}", module="exporter")
            raise
    
    def export_to_yaml(self, data: Any, output_path: str = None,
                      default_flow_style: bool = False) -> str:
        """Export data to YAML format"""
        try:
            if output_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"data/exports/export_{timestamp}.yaml"
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=default_flow_style, 
                         allow_unicode=True, sort_keys=False)
            
            file_size = os.path.getsize(output_path)
            
            # Send Telegram notification
            self.send_telegram_notification(
                "YAML Export Completed",
                f"File: {output_path}\n"
                f"Size: {file_size/(1024*1024):.2f} MB",
                output_path
            )
            
            logger.info(f"Exported to YAML: {output_path} ({file_size} bytes)", module="exporter")
            return output_path
            
        except Exception as e:
            logger.error(f"YAML export error: {e}", module="exporter")
            raise
    
    def export_to_html(self, data: List[Dict], output_path: str = None,
                      title: str = "Data Export") -> str:
        """Export data to HTML format"""
        try:
            if not data:
                raise ValueError("No data to export")
            
            if output_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"data/exports/export_{timestamp}.html"
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Get fieldnames
            fieldnames = list(data[0].keys()) if data else []
            
            # Generate HTML
            html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
meta name="viewport" content="width=device-width, initial-scale=1.0">
title>{title>
style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .metadata {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
        .timestamp {{ color: #666; font-size: 0.9em; }}
    </stylehead>
<body>
h1>{title}</h1>
    
    <div class="metadata">
strong>Export Informationp>
p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%Sp>
p>Total Records: {len(datap>
p>Fields: {len(fieldnames)}</p>
    </div>
    
table>
thead>
tr>
"""
            
            # Add table headers
            for field in fieldnames:
                html += f'th>{th>\n'
            
            html += """            </tr>
        </thead>
        <tbody>
"""
            
            # Add table rows
            for row in data:
                html += '            <tr>\n'
                for field in fieldnames:
                    value = row.get(field, '')
                    # Convert complex values to string
                    if isinstance(value, (dict, list)):
                        value = json.dumps(value, default=str)
                    html += f'                <td>{value}</td>\n'
                html += '            </tr>\n'
            
            html += """tbody>
table>
    
    <div class="timestamp">
p>Export generated by DerBöseKollegep>
div>
</bodyhtml>
"""
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html)
            
            file_size = os.path.getsize(output_path)
            
            # Send Telegram notification
            self.send_telegram_notification(
                "HTML Export Completed",
                f"File: {output_path}\n"
                f"Size: {file_size/(1024*1024):.2f} MB\n"
                f"Rows: {len(data)}\n"
                f"Columns: {len(fieldnames)}",
                output_path
            )
            
            logger.info(f"Exported to HTML: {output_path} ({file_size} bytes)", module="exporter")
            return output_path
            
        except Exception as e:
            logger.error(f"HTML export error: {e}", module="exporter")
            raise
    
    def export_to_sqlite(self, data: Dict[str, List[Dict]], output_path: str = None) -> str:
        """Export data to SQLite database"""
        try:
            if not data:
                raise ValueError("No data to export")
            
            if output_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"data/exports/export_{timestamp}.db"
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Connect to SQLite database
            conn = sqlite3.connect(output_path)
            cursor = conn.cursor()
            
            # Create tables and insert data
            for table_name, table_data in data.items():
                if not table_data:
                    continue
                
                # Clean table name
                table_name_clean = ''.join(c if c.isalnum() else '_' for c in table_name)
                
                # Get column names from first row
                first_row = table_data[0]
                columns = list(first_row.keys())
                
                # Create table
                column_defs = ', '.join([f'"{col}" TEXT' for col in columns])
                create_sql = f'CREATE TABLE IF NOT EXISTS "{table_name_clean}" ({column_defs})'
                cursor.execute(create_sql)
                
                # Insert data
                for row in table_data:
                    placeholders = ', '.join(['?'] * len(columns))
                    values = [str(row.get(col, '')) for col in columns]
                    insert_sql = f'INSERT INTO "{table_name_clean}" VALUES ({placeholders})'
                    cursor.execute(insert_sql, values)
            
            conn.commit()
            conn.close()
            
            file_size = os.path.getsize(output_path)
            
            # Send Telegram notification
            self.send_telegram_notification(
                "SQLite Export Completed",
                f"File: {output_path}\n"
                f"Size: {file_size/(1024*1024):.2f} MB\n"
                f"Tables: {len(data)}\n"
                f"Total rows: {sum(len(table) for table in data.values())}",
                output_path
            )
            
            logger.info(f"Exported to SQLite: {output_path} ({file_size} bytes, {len(data)} tables)", module="exporter")
            return output_path
            
        except Exception as e:
            logger.error(f"SQLite export error: {e}", module="exporter")
            raise
    
    def export_to_pickle(self, data: Any, output_path: str = None,
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
                        output_path = os.path.join(output_dir, 'data.csv')
                        results['csv'] = self.export_to_csv(data, output_path)
                    
                    elif fmt == 'xlsx' and isinstance(data, dict):
                        output_path = os.path.join(output_dir, 'data.xlsx')
                        results['xlsx'] = self.export_to_excel(data, output_path)
                    
                    elif fmt == 'xml':
                        output_path = os.path.join(output_dir, 'data.xml')
                        results['xml'] = self.export_to_xml(data, output_path)
                    
                    elif fmt == 'yaml':
                        output_path = os.path.join(output_dir, 'data.yaml')
                        results['yaml'] = self.export_to_yaml(data, output_path)
                    
                    elif fmt == 'html' and isinstance(data, list):
                        output_path = os.path.join(output_dir, 'data.html')
                        results['html'] = self.export_to_html(data, output_path)
                    
                    elif fmt == 'sqlite' and isinstance(data, dict):
                        output_path = os.path.join(output_dir, 'data.db')
                        results['sqlite'] = self.export_to_sqlite(data, output_path)
                    
                    elif fmt == 'pickle':
                        output_path = os.path.join(output_dir, 'data.pkl')
                        results['pickle'] = self.export_to_pickle(data, output_path)
                    
                    else:
                        logger.warning(f"Unsupported format or data type: {fmt}", module="exporter")
                        
                except Exception as e:
                    logger.error(f"Failed to export to {fmt}: {e}", module="exporter")
                    results[fmt] = f"Error: {str(e)}"
            
            # Create README file
            readme_path = os.path.join(output_dir, 'README.txt')
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(f"Data Export - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 50 + "\n\n")
                f.write("Generated by DerBöseKollege Framework\n\n")
                f.write("Formats exported:\n")
                for fmt, path in results.items():
                    if isinstance(path, str) and os.path.exists(path):
                        size = os.path.getsize(path)
                        f.write(f"  - {fmt.upper()}: {os.path.basename(path)} ({size/(1024*1024):.2f} MB)\n")
            
            # Send Telegram notification
            successful = sum(1 for path in results.values() if isinstance(path, str) and os.path.exists(path))
            total = len(formats)
            
            self.send_telegram_notification(
                "Multi-Format Export Completed",
                f"Directory: {output_dir}\n"
                f"Formats: {successful}/{total} successful\n"
                f"Total size: {self._get_directory_size(output_dir)/(1024*1024):.2f} MB"
            )
            
            logger.info(f"Exported to {successful}/{total} formats in {output_dir}", module="exporter")
            return results
            
        except Exception as e:
            logger.error(f"Multi-format export error: {e}", module="exporter")
            raise
    
    def export_database_tables(self, db_manager, tables: List[str] = None,
                              output_dir: str = None) -> Dict[str, str]:
        """Export database tables to files"""
        try:
            from .sqlite_db import get_sqlite_manager
            
            if isinstance(db_manager, str):
                db_manager = get_sqlite_manager(db_manager)
            
            if output_dir is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_dir = f"data/exports/db_export_{timestamp}"
            
            os.makedirs(output_dir, exist_ok=True)
            
            if tables is None:
                # Get all tables
                stats = db_manager.get_statistics()
                tables = list(stats.get('tables', {}).keys())
            
            results = {}
            
            for table in tables:
                try:
                    # Query table data
                    data = db_manager.query(table, limit=100000)
                    
                    if data:
                        # Export to JSON
                        json_path = os.path.join(output_dir, f"{table}.json")
                        with open(json_path, 'w', encoding='utf-8') as f:
                            json.dump(data, f, indent=2, default=str)
                        
                        # Export to CSV
                        csv_path = os.path.join(output_dir, f"{table}.csv")
                        self.export_to_csv(data, csv_path)
                        
                        results[table] = {
                            'json': json_path,
                            'csv': csv_path,
                            'rows': len(data)
                        }
                        
                        logger.debug(f"Exported table {table}: {len(data)} rows", module="exporter")
                    
                except Exception as e:
                    logger.error(f"Failed to export table {table}: {e}", module="exporter")
                    results[table] = f"Error: {str(e)}"
            
            # Create summary
            summary_path = os.path.join(output_dir, 'export_summary.json')
            with open(summary_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'tables_exported': len([r for r in results.values() if isinstance(r, dict)]),
                    'total_rows': sum(r.get('rows', 0) for r in results.values() if isinstance(r, dict)),
                    'results': results
                }, f, indent=2)
            
            total_size = self._get_directory_size(output_dir)
            
            # Send Telegram notification
            self.send_telegram_notification(
                "Database Export Completed",
                f"Directory: {output_dir}\n"
                f"Tables: {len([r for r in results.values() if isinstance(r, dict)])}\n"
                f"Total size: {total_size/(1024*1024):.2f} MB"
            )
            
            logger.info(f"Exported {len(tables)} database tables to {output_dir}", module="exporter")
            return results
            
        except Exception as e:
            logger.error(f"Database export error: {e}", module="exporter")
            raise
    
    def _count_items(self, data: Any) -> int:
        """Count items in data structure"""
        if isinstance(data, list):
            return len(data)
        elif isinstance(data, dict):
            return sum(self._count_items(v) for v in data.values())
        else:
            return 1
    
    def _get_directory_size(self, directory: str) -> int:
        """Get total size of directory"""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(directory):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.exists(filepath):
                    total_size += os.path.getsize(filepath)
        return total_size
    
    def get_supported_formats(self) -> List[str]:
        """Get list of supported export formats"""
        return self.supported_formats.copy()
    
    def get_status(self) -> Dict[str, Any]:
        """Get exporter status"""
        return {
            'supported_formats': len(self.supported_formats),
            'telegram_available': self.telegram_bot is not None
        }

# Global instance
_data_exporter = None

def get_data_exporter(config: Dict = None) -> DataExporter:
    """Get or create data exporter instance"""
    global _data_exporter
    
    if _data_exporter is None:
        _data_exporter = DataExporter(config)
    
    return _data_exporter

if __name__ == "__main__":
    # Test the data exporter
    config = {
        'telegram': {
            'bot_token': 'test_token',
            'exporter_chat_id': 123456789
        }
    }
    
    exporter = get_data_exporter(config)
    
    print("Testing data exporter...")
    
    # Test data
    test_data = [
        {'id': 1, 'name': 'Alice', 'age': 30, 'city': 'Berlin'},
        {'id': 2, 'name': 'Bob', 'age': 25, 'city': 'Munich'},
        {'id': 3, 'name': 'Charlie', 'age': 35, 'city': 'Hamburg'}
    ]
    
    # Test JSON export
    print("\n1. Testing JSON export...")
    try:
        json_path = exporter.export_to_json(test_data)
        print(f"JSON exported to: {json_path}")
    except Exception as e:
        print(f"JSON export failed: {e}")
    
    # Test CSV export
    print("\n2. Testing CSV export...")
    try:
        csv_path = exporter.export_to_csv(test_data)
        print(f"CSV exported to: {csv_path}")
    except Exception as e:
        print(f"CSV export failed: {e}")
    
    # Test multi-format export
    print("\n3. Testing multi-format export...")
    try:
        results = exporter.export_to_multiple_formats(
            test_data,
            formats=['json', 'csv', 'html']
        )
        print(f"Multi-format export results: {len(results)} formats")
    except Exception as e:
        print(f"Multi-format export failed: {e}")
    
    # Show supported formats
    print(f"\nSupported formats: {exporter.get_supported_formats()}")
    
    # Show status
    status = exporter.get_status()
    print(f"\n📤 Data Exporter Status: {status}")
    
    print("\n✅ Data exporter tests completed!")
