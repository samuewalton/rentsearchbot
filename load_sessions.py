"""
סקריפט לטעינת סשנים קיימים למסד הנתונים
"""

import os
import json
import logging
from telethon.sessions import StringSession
from telethon import TelegramClient
import asyncio
from dotenv import load_dotenv

from db import get_connection
from constants import Constants
from proxy_manager import proxy_manager
from session_classifier import SessionClassifier

# טעינת משתני סביבה
load_dotenv()

# הגדרת לוגר
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# תיקיית סשנים
SESSIONS_DIR = 'session'

# API Credentials
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")

async def load_session_to_db(session_path, session_id, metadata):
    """
    טוען סשן למסד הנתונים
    """
    try:
        # ניסיון להמיר את הסשן לפורמט StringSession
        client = TelegramClient(session_path, API_ID, API_HASH)
        await client.connect()
        
        session_string = StringSession.save(client.session)
        await client.disconnect()
        
        # הכנת פרטי הפרוקסי אם יש
        proxy_id = None
        if 'proxy' in metadata and metadata['proxy']:
            # בדיקה אם הפרוקסי כבר קיים
            proxy_data = metadata['proxy']
            proxy_host = proxy_data[1] if len(proxy_data) > 1 else None
            proxy_port = proxy_data[2] if len(proxy_data) > 2 else None
            
            if proxy_host and proxy_port:
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT id FROM proxies 
                            WHERE address = %s AND port = %s
                        """, (proxy_host, proxy_port))
                        proxy_result = cur.fetchone()
                        
                        if proxy_result:
                            proxy_id = proxy_result['id']
                        else:
                            # הוסף פרוקסי חדש
                            proxy_username = proxy_data[4] if len(proxy_data) > 4 else None
                            proxy_password = proxy_data[5] if len(proxy_data) > 5 else None
                            
                            cur.execute("""
                                INSERT INTO proxies 
                                (address, port, username, password, protocol, status)
                                VALUES (%s, %s, %s, %s, 'socks5', 'active')
                                RETURNING id
                            """, (proxy_host, proxy_port, proxy_username, proxy_password))
                            
                            proxy_id = cur.fetchone()['id']
        
        # קביעת סוג הסשן בהתבסס על שם הקובץ או נתונים אחרים
        # לצורך הדגמה, נקבע את הסוג בהתאם למספר הסשן
        session_type = Constants.SESSION_TYPE_CLEAN
        
        # בדיקה אם הסשן כבר קיים
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id FROM sessions 
                    WHERE session_id = %s
                """, (session_id,))
                
                if cur.fetchone():
                    logger.info(f"סשן {session_id} כבר קיים במסד הנתונים")
                    return
                
                # הוסף את הסשן למסד הנתונים
                cur.execute("""
                    INSERT INTO sessions 
                    (session_id, session_string, type, status, dc_id, proxy_id)
                    VALUES (%s, %s, %s, 'active', %s, %s)
                    RETURNING id
                """, (
                    session_id, 
                    session_string,
                    session_type,
                    client.session.dc_id,
                    proxy_id
                ))
                
                db_session_id = cur.fetchone()['id']
                
                # אם יש פרוקסי, הוסף לטבלת session_proxy
                if proxy_id:
                    cur.execute("""
                        INSERT INTO session_proxy
                        (session_id, proxy_id)
                        VALUES (%s, %s)
                    """, (session_id, proxy_id))
                
                logger.info(f"סשן {session_id} נוסף למסד הנתונים בהצלחה עם מזהה {db_session_id}")
                return db_session_id
    
    except Exception as e:
        logger.error(f"שגיאה בהוספת סשן {session_id}: {str(e)}")
        return None

async def main():
    """
    פונקציה ראשית
    """
    # ודא שמסד הנתונים מוכן
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
    except Exception as e:
        logger.error(f"שגיאה בחיבור למסד הנתונים: {str(e)}")
        return
    
    # סרוק את ספריית הסשנים
    session_files = []
    
    for filename in os.listdir(SESSIONS_DIR):
        if filename.endswith('.session'):
            session_id = filename[:-8]  # הסר את הסיומת .session
            json_path = os.path.join(SESSIONS_DIR, f"{session_id}.json")
            session_path = os.path.join(SESSIONS_DIR, filename)
            
            if os.path.exists(json_path):
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    
                    session_files.append((session_path, session_id, metadata))
                except Exception as e:
                    logger.error(f"שגיאה בקריאת קובץ מטה-דאטה {json_path}: {str(e)}")
    
    # הוסף את הסשנים למסד הנתונים
    count = 0
    for session_path, session_id, metadata in session_files:
        session_db_id = await load_session_to_db(session_path, session_id, metadata)
        if session_db_id:
            count += 1
    
    logger.info(f"נוספו {count} סשנים למסד הנתונים מתוך {len(session_files)}")

if __name__ == "__main__":
    asyncio.run(main())
