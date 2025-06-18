#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
מעקב פשוט אחר סיווג סשן חדש
"""

import time
import os
from datetime import datetime

def watch_for_new_session():
    """מעקב אחר הוספת סשן חדש"""
    print("👀 מחכה לסיווג סשן חדש...")
    print("הוסף עכשיו את הסשן דרך הבוט!\n")
    
    # נצפה לקבצי לוג
    log_files = ['bot.log', 'debug_bot.log']
    last_positions = {}
    
    # אתחול מיקומים
    for log_file in log_files:
        if os.path.exists(log_file):
            with open(log_file, 'rb') as f:
                f.seek(0, 2)  # עבור לסוף הקובץ
                last_positions[log_file] = f.tell()
        else:
            last_positions[log_file] = 0
    
    classification_found = False
    
    try:
        while not classification_found:
            for log_file in log_files:
                if os.path.exists(log_file):
                    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                        f.seek(last_positions[log_file])
                        new_lines = f.readlines()
                        
                        if new_lines:
                            print(f"📈 עדכון ב-{log_file}:")
                            
                            for line in new_lines:
                                line = line.strip()
                                if line:
                                    # בדוק אם זה קשור לסיווג
                                    if any(keyword in line.lower() for keyword in [
                                        'סיווג', 'classify', 'סשן', 'session_type', 
                                        'clean', 'dirty', 'manager', 'נכסים', 'assets',
                                        'הוסף', 'נוסף', 'added'
                                    ]):
                                        print(f"🔥 {datetime.now().strftime('%H:%M:%S')} - {line}")
                                        
                                        # בדוק אם זה סיווג סשן
                                        if any(word in line.lower() for word in ['clean', 'dirty', 'manager']):
                                            classification_found = True
                                    else:
                                        print(f"   {datetime.now().strftime('%H:%M:%S')} - {line}")
                        
                        last_positions[log_file] = f.tell()
            
            if not classification_found:
                print(".", end="", flush=True)
                time.sleep(1)
    
    except KeyboardInterrupt:
        print("\n\n🛑 מעקב הופסק")

if __name__ == '__main__':
    watch_for_new_session()
