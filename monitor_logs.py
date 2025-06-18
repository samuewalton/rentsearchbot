#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
מעקב אחר לוגים בזמן אמת - מיוחד לבדיקת סיווג סשנים
"""

import os
import time
import sys
from pathlib import Path
from datetime import datetime

def tail_file(filepath, lines=20):
    """מחזיר את השורות האחרונות מקובץ"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.readlines()
            return content[-lines:] if len(content) > lines else content
    except Exception as e:
        return [f"שגיאה בקריאת קובץ: {e}"]

def monitor_logs():
    """מעקב אחר לוגים"""
    log_files = {
        'bot.log': 'בוט ראשי',
        'debug_bot.log': 'בוט דיבאג', 
        'load_sessions.log': 'טעינת סשנים',
        'reclassify_sessions.log': 'סיווג מחדש'
    }
    
    print("🔍 מעקב אחר לוגים - מיוחד לסיווג סשנים")
    print("=" * 60)
    
    last_sizes = {}
    
    # אתחול גדלים
    for log_file in log_files.keys():
        if Path(log_file).exists():
            last_sizes[log_file] = Path(log_file).stat().st_size
        else:
            last_sizes[log_file] = 0
    
    print("👀 מחכה לעדכונים בלוגים...\n")
    
    try:
        while True:
            found_updates = False
            
            for log_file, description in log_files.items():
                if Path(log_file).exists():
                    current_size = Path(log_file).stat().st_size
                    
                    if current_size > last_sizes[log_file]:
                        found_updates = True
                        print(f"📈 עדכון ב-{description} ({log_file}):")
                        print("-" * 40)
                        
                        # הצג שורות חדשות
                        recent_lines = tail_file(log_file, 10)
                        for line in recent_lines:
                            line = line.strip()
                            if line:
                                # סנן שורות חשובות לסיווג
                                if any(keyword in line.lower() for keyword in [
                                    'סיווג', 'classify', 'session', 'clean', 'dirty', 'manager',
                                    'נכסים', 'assets', 'טעינה', 'הוספ'
                                ]):
                                    print(f"🔥 {line}")
                                else:
                                    print(f"   {line}")
                        
                        print("-" * 40)
                        print()
                        last_sizes[log_file] = current_size
            
            if not found_updates:
                # הדפס נקודה כדי להראות שהסקריפט פועל
                print(".", end="", flush=True)
            
            time.sleep(2)  # בדוק כל 2 שניות
            
    except KeyboardInterrupt:
        print("\n\n🛑 מעקב לוגים הופסק")

def show_recent_classification_logs():
    """הצג לוגים אחרונים של סיווג"""
    print("📊 לוגים אחרונים של סיווג סשנים:")
    print("=" * 50)
    
    for log_file in ['bot.log', 'debug_bot.log', 'load_sessions.log']:
        if Path(log_file).exists():
            print(f"\n📄 {log_file}:")
            print("-" * 30)
            
            recent_lines = tail_file(log_file, 15)
            for line in recent_lines:
                line = line.strip()
                if line and any(keyword in line.lower() for keyword in [
                    'סיווג', 'classify', 'session', 'clean', 'dirty', 'manager',
                    'נכסים', 'assets'
                ]):
                    print(f"🔍 {line}")

def main():
    """פונקציה ראשית"""
    print("🕵️ מעקב לוגים לסיווג סשנים\n")
    print("בחר אפשרות:")
    print("1. מעקב בזמן אמת")
    print("2. הצג לוגים אחרונים")
    print("3. שניהם")
    
    choice = input("\nבחירה (1-3): ").strip()
    
    if choice == '1':
        monitor_logs()
    elif choice == '2':
        show_recent_classification_logs()
    elif choice == '3':
        show_recent_classification_logs()
        print("\n" + "=" * 60)
        print("עובר למעקב בזמן אמת...\n")
        time.sleep(2)
        monitor_logs()
    else:
        print("❌ בחירה לא תקפה")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"❌ שגיאה: {e}")
        input("לחץ Enter לסגירה...")
