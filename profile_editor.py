import logging
import asyncio
import json
from typing import Union, List, Dict, Any, Optional, Tuple

from db import get_connection
from constants import Constants
from session_manager import session_manager
from proxy_manager import proxy_manager

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.channels import EditTitleRequest
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.bots import SetBotCommandsRequest
from telethon.tl.types import BotCommand, Channel, User, Chat

logger = logging.getLogger(__name__)

class ProfileEditor:
    """
    עורך פרופילים - שינוי שמות נכסים (בוטים, קבוצות, ערוצים)
    """
    
    def __init__(self):
        """
        יוצר עורך פרופילים חדש
        """
        # שמירת שמות מקוריים לזיכרון
        self.original_names = {}  # {asset_id: original_name}
    
    async def change_asset_name(self, asset_id: int, new_name: str) -> Tuple[bool, str]:
        """
        משנה את שם הנכס
        
        Args:
            asset_id: מזהה הנכס
            new_name: השם החדש
            
        Returns:
            האם הפעולה הצליחה ותיאור השגיאה אם הייתה
        """
        try:
            # קבל את פרטי הנכס
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT * FROM assets WHERE id = %s
                    """, (asset_id,))
                    asset = cur.fetchone()
                    
            if not asset:
                return False, f"לא נמצא נכס עם מזהה {asset_id}"
            
            # שמור את השם המקורי אם עוד לא נשמר
            if asset_id not in self.original_names:
                self.original_names[asset_id] = asset['name']
            
            # לפי סוג הנכס, בצע שינוי שם מתאים
            if asset['type'] == Constants.ASSET_TYPE_BOT:
                return await self._change_bot_name(asset, new_name)
            elif asset['type'] == Constants.ASSET_TYPE_CHANNEL:
                return await self._change_channel_name(asset, new_name)
            elif asset['type'] == Constants.ASSET_TYPE_GROUP:
                return await self._change_group_name(asset, new_name)
            else:
                return False, f"סוג נכס לא מוכר: {asset['type']}"
                
        except Exception as e:
            logger.error(f"שגיאה בשינוי שם נכס {asset_id}: {str(e)}")
            return False, f"שגיאה בשינוי שם: {str(e)}"
    
    async def restore_asset_name(self, asset_id: int) -> Tuple[bool, str]:
        """
        משחזר את השם המקורי של נכס
        
        Args:
            asset_id: מזהה הנכס
            
        Returns:
            האם הפעולה הצליחה ותיאור השגיאה אם הייתה
        """
        # בדוק אם יש שם מקורי שמור
        if asset_id in self.original_names:
            original_name = self.original_names[asset_id]
            return await self.change_asset_name(asset_id, original_name)
        
        # אם לא, נסה לקבל מהמסד
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT original_name FROM assets WHERE id = %s
                    """, (asset_id,))
                    result = cur.fetchone()
                    
                    if result and result['original_name']:
                        return await self.change_asset_name(asset_id, result['original_name'])
                    else:
                        return False, f"לא נמצא שם מקורי לנכס {asset_id}"
                        
        except Exception as e:
            logger.error(f"שגיאה בשחזור שם נכס {asset_id}: {str(e)}")
            return False, f"שגיאה בשחזור שם: {str(e)}"
    
    async def _change_bot_name(self, asset: Dict[str, Any], new_name: str) -> Tuple[bool, str]:
        """
        משנה שם של בוט
        
        Args:
            asset: פרטי הנכס
            new_name: השם החדש
            
        Returns:
            האם הפעולה הצליחה ותיאור השגיאה אם הייתה
        """
        # בדוק אם יש טוקן שמור לבוט הזה
        bot_token = asset.get('bot_token')
        if not bot_token:
            return False, "אין טוקן שמור לבוט זה - לא ניתן לשנות את השם"
            
        try:
            # התחבר כבוט עם הטוקן שלו
            from telethon import TelegramClient
            client = TelegramClient(StringSession(), 6, "eb06d4abfb49dc3eeb1aeb98ae0f581e")
            await client.start(bot_token=bot_token)
            
            try:
                # עדכן את פרופיל הבוט
                result = await client(UpdateProfileRequest(
                    first_name=new_name
                ))
                
                # עדכן את מסד הנתונים
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE assets
                            SET name = %s, updated_at = NOW()
                            WHERE id = %s
                        """, (new_name, asset['id']))
                
                return True, f"שם הבוט עודכן ל: {new_name}"
                
            finally:
                # וודא ניתוק הclint
                await client.disconnect()
                
        except Exception as e:
            logger.error(f"שגיאה בשינוי שם בוט {asset['id']}: {str(e)}")
            return False, f"שגיאה בשינוי שם בוט: {str(e)}"
    
    async def _change_channel_name(self, asset: Dict[str, Any], new_name: str) -> Tuple[bool, str]:
        """
        משנה שם של ערוץ
        
        Args:
            asset: פרטי הנכס
            new_name: השם החדש
            
        Returns:
            האם הפעולה הצליחה ותיאור השגיאה אם הייתה
        """
        # קבל סשן לסוג 'manager' - כלומר סשן עם הרשאות ניהול
        session = await session_manager.get_session(Constants.SESSION_TYPE_MANAGER)
        
        if not session:
            return False, "לא נמצא סשן זמין לעריכת ערוץ"
            
        try:
            # קבל פרוקסי מתאים
            proxy = proxy_manager.get_proxy_for_session(session['id']) if 'id' in session else None
            
            # התחבר לטלגרם
            async with TelegramClient(
                StringSession(session['session_string']),
                api_id=session.get('api_id'),
                api_hash=session.get('api_hash'),
                proxy=proxy
            ) as client:
                # קבל את האובייקט של הערוץ
                channel = await client.get_entity(asset['telegram_id'])
                
                # עדכן את שם הערוץ
                result = await client(EditTitleRequest(
                    channel=channel,
                    title=new_name
                ))
                
                # עדכן את מסד הנתונים
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE assets
                            SET name = %s, updated_at = NOW()
                            WHERE id = %s
                        """, (new_name, asset['id']))
                
                # שחרר את הסשן
                session_manager.release_session(session['id'])
                
                return True, f"שם הערוץ עודכן ל: {new_name}"
                
        except Exception as e:
            # שחרר את הסשן
            if session and 'id' in session:
                session_manager.release_session(session['id'])
                
            logger.error(f"שגיאה בשינוי שם ערוץ {asset['id']}: {str(e)}")
            return False, f"שגיאה בשינוי שם ערוץ: {str(e)}"
    
    async def _change_group_name(self, asset: Dict[str, Any], new_name: str) -> Tuple[bool, str]:
        """
        משנה שם של קבוצה
        
        Args:
            asset: פרטי הנכס
            new_name: השם החדש
            
        Returns:
            האם הפעולה הצליחה ותיאור השגיאה אם הייתה
        """
        # משתמש באותו מנגנון כמו ערוץ
        return await self._change_channel_name(asset, new_name)
    
    async def get_assets_by_name(self, name_part: str) -> List[Dict[str, Any]]:
        """
        מחפש נכסים לפי חלק משם
        
        Args:
            name_part: חלק מהשם לחיפוש
            
        Returns:
            רשימת נכסים שנמצאו
        """
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT * FROM assets
                        WHERE name ILIKE %s OR username ILIKE %s
                        ORDER BY name
                    """, (f"%{name_part}%", f"%{name_part}%"))
                    
                    assets = cur.fetchall()
                    result = []
                    
                    for asset in assets:
                        result.append(dict(asset))
                    
                    return result
                    
        except Exception as e:
            logger.error(f"שגיאה בחיפוש נכסים לפי שם '{name_part}': {str(e)}")
            return []


# יצירת אינסטנס לשימוש מחוץ למודול
profile_editor = ProfileEditor()
