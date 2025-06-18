import logging
import time
import json
import datetime
from typing import List, Dict, Any, Optional, Tuple

from db import get_connection
from constants import Constants
from session_manager import session_manager
from proxy_manager import proxy_manager

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon import functions, types

logger = logging.getLogger(__name__)

class RankChecker:
    """
    בודק דירוגים - בדיקת דירוג חיפוש לנכס מסוים
    """
    
    def __init__(self):
        """
        יוצר בודק דירוגים חדש
        """
        # מטמון דירוגים (מניעת בדיקות חוזרות)
        self.rank_cache = {}  # {(asset_id, keyword): {"rank": X, "tier": Y, "time": datetime}}
    
    def get_cached_rank(self, asset_id: int, keyword: str) -> Tuple[Optional[int], Optional[str], Optional[str]]:
        """
        בודק אם יש דירוג במטמון שתקף עדיין
        
        Args:
            asset_id: מזהה הנכס
            keyword: מילת המפתח
            
        Returns:
            צמד של (דירוג, tier, שגיאה אם יש)
        """
        cache_key = (asset_id, keyword)
        if cache_key in self.rank_cache:
            cache_data = self.rank_cache[cache_key]
            cache_time = cache_data.get('time')
            cache_expiry = Constants.RANK_CACHE_HOURS * 3600  # המרה לשניות
            
            # אם המטמון עדיין תקף
            if (datetime.datetime.now() - cache_time).total_seconds() < cache_expiry:
                return cache_data.get('rank'), cache_data.get('tier'), None
        
        return None, None, None
    
    async def check_asset_rank(self, asset_id: int, keyword: str) -> Tuple[int, str, Optional[str]]:
        """
        בודק את הדירוג של נכס עבור מילת מפתח
        
        Args:
            asset_id: מזהה הנכס
            keyword: מילת המפתח
            
        Returns:
            שלשה של (דירוג, tier, שגיאה אם יש)
        """
        # בדוק קודם במטמון
        cached_rank, cached_tier, _ = self.get_cached_rank(asset_id, keyword)
        if cached_rank is not None and cached_tier is not None:
            return cached_rank, cached_tier, None
        
        # קבל את פרטי הנכס
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT * FROM assets WHERE id = %s
                """, (asset_id,))
                asset = cur.fetchone()
                
        if not asset:
            return -1, Constants.TIER_UNAVAILABLE, f"לא נמצא נכס עם מזהה {asset_id}"
            
        # קבל סשן נקי לבדיקת דירוג
        session = await session_manager.get_session(Constants.SESSION_TYPE_CLEAN)
        
        if not session:
            return -1, Constants.TIER_UNAVAILABLE, "לא נמצא סשן נקי זמין"
        
        try:
            # התחבר לטלגרם
            proxy = proxy_manager.get_proxy_for_session(session['id']) if 'id' in session else None
            
            # בדוק את הדירוג
            rank = await self._check_global_search_rank(session, proxy, keyword, asset)
            
            # שחרר את הסשן
            session_manager.release_session(session['id'])
            
            # חשב Tier לפי הדירוג
            tier = Constants.get_tier_for_rank(rank)
            
            # שמור במטמון
            self._cache_rank(asset_id, keyword, rank, tier)
            
            # שמור במסד הנתונים
            self._save_rank_to_db(asset_id, keyword, rank, tier)
            
            return rank, tier, None
            
        except Exception as e:
            # שחרר את הסשן
            if session and 'id' in session:
                session_manager.release_session(session['id'])
                
            logger.error(f"שגיאה בבדיקת דירוג: {str(e)}")
            return -1, Constants.TIER_UNAVAILABLE, f"שגיאה בבדיקת דירוג: {str(e)}"
    
    async def _check_global_search_rank(self, session: Dict[str, Any], proxy: Dict[str, str], 
                                   keyword: str, asset: Dict[str, Any]) -> int:
        """
        בודק את הדירוג בחיפוש גלובלי
        
        Args:
            session: סשן לשימוש
            proxy: פרוקסי (אם יש)
            keyword: מילת המפתח
            asset: פרטי הנכס
            
        Returns:
            הדירוג (1-N) או -1 אם לא נמצא
        """
        # יצירת פרמטרי פרוקסי אם יש
        proxy_params = None
        if proxy:
            proxy_params = {
                'proxy_type': proxy.get('protocol', 'socks5'),
                'addr': proxy.get('host'),
                'port': int(proxy.get('port')),
                'username': proxy.get('username'),
                'password': proxy.get('password')
            }
        
        # התחבר לטלגרם
        async with TelegramClient(
            StringSession(session['session_string']),
            api_id=session.get('api_id'),
            api_hash=session.get('api_hash'),
            proxy=proxy_params
        ) as client:
            # בדוק את סוג הנכס ובצע חיפוש בהתאם
            result = await client(functions.contacts.SearchGlobalRequest(
                q=keyword,
                offset_rate=0,
                offset_peer=types.InputPeerEmpty(),
                limit=100
            ))
            
            # מצא את הנכס בתוצאות החיפוש
            rank = -1
            
            # חיפוש שונה לפי סוג הנכס
            if asset['type'] == Constants.ASSET_TYPE_BOT:
                # חפש בין המשתמשים
                users = [user for user in result.users if hasattr(user, 'bot') and user.bot]
                user_ids = [user.id for user in users]
                
                if asset['telegram_id'] in user_ids:
                    rank = user_ids.index(asset['telegram_id']) + 1
                
            elif asset['type'] == Constants.ASSET_TYPE_CHANNEL:
                # חפש בין הערוצים
                chats = [chat for chat in result.chats if hasattr(chat, 'broadcast') and chat.broadcast]
                chat_ids = [chat.id for chat in chats]
                
                if asset['telegram_id'] in chat_ids:
                    rank = chat_ids.index(asset['telegram_id']) + 1
                
            elif asset['type'] == Constants.ASSET_TYPE_GROUP:
                # חפש בין הקבוצות
                chats = [chat for chat in result.chats if hasattr(chat, 'megagroup') and chat.megagroup]
                chat_ids = [chat.id for chat in chats]
                
                if asset['telegram_id'] in chat_ids:
                    rank = chat_ids.index(asset['telegram_id']) + 1
            
            # השהיה קצרה לפני החזרת התוצאה
            await client.disconnect()
            time.sleep(1)
            
            return rank
    
    def _cache_rank(self, asset_id: int, keyword: str, rank: int, tier: str):
        """
        שומר דירוג במטמון
        
        Args:
            asset_id: מזהה הנכס
            keyword: מילת המפתח
            rank: הדירוג
            tier: הדירוג המדורג (tier)
        """
        # עדכן את המטמון הפנימי
        cache_key = (asset_id, keyword)
        self.rank_cache[cache_key] = {
            'rank': rank,
            'tier': tier,
            'time': datetime.datetime.now()
        }
    
    def _save_rank_to_db(self, asset_id: int, keyword: str, rank: int, tier: str):
        """
        שומר דירוג במסד הנתונים
        
        Args:
            asset_id: מזהה הנכס
            keyword: מילת המפתח
            rank: הדירוג
            tier: הדירוג המדורג (tier)
        """
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    # עדכן את מטמון הדירוגים
                    cur.execute("""
                        INSERT INTO rank_cache (asset_id, keyword, rank, tier, created_at)
                        VALUES (%s, %s, %s, %s, NOW())
                        ON CONFLICT (asset_id, keyword) 
                        DO UPDATE SET rank = %s, tier = %s, created_at = NOW()
                    """, (asset_id, keyword, rank, tier, rank, tier))
                    
                    # עדכן את הנכס עם הדירוג האחרון
                    cur.execute("""
                        UPDATE assets
                        SET last_rank = %s, last_rank_keyword = %s, last_rank_time = NOW()
                        WHERE id = %s
                    """, (rank, keyword, asset_id))
                    
        except Exception as e:
            logger.error(f"שגיאה בשמירת דירוג במסד הנתונים: {str(e)}")
    
    def clear_cache(self):
        """
        מנקה את מטמון הדירוגים
        """
        self.rank_cache = {}
    
    def get_rankings_for_keyword(self, keyword: str, asset_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        מקבל דירוגים של נכסים עבור מילת מפתח
        
        Args:
            keyword: מילת מפתח
            asset_type: סוג נכס לסינון (אופציונלי)
            
        Returns:
            רשימת נכסים מדורגים
        """
        try:
            type_condition = ""
            params = [keyword]
            
            if asset_type:
                type_condition = "AND a.type = %s"
                params.append(asset_type)
            
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(f"""
                        SELECT a.*, rc.rank, rc.tier, rc.created_at as rank_time
                        FROM assets a
                        JOIN rank_cache rc ON a.id = rc.asset_id
                        WHERE rc.keyword = %s
                        {type_condition}
                        ORDER BY rc.rank ASC
                    """, params)
                    
                    assets = cur.fetchall()
                    result = []
                    
                    for asset in assets:
                        result.append(dict(asset))
                    
                    return result
                    
        except Exception as e:
            logger.error(f"שגיאה בקבלת דירוגים למילת מפתח '{keyword}': {str(e)}")
            return []


# יצירת אינסטנס לשימוש מחוץ למודול
rank_checker = RankChecker()
