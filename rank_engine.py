"""
מודול rank_engine - מנוע דירוג שבודק את דירוג הנכסים בחיפוש טלגרם
"""

import logging
import json
import time
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any

from constants import Constants
from db import get_connection
from rank_checker import rank_checker
from assets_manager import assets_manager
from profile_editor import profile_editor
from session_manager import session_manager

logger = logging.getLogger(__name__)

class RankEngine:
    """
    מנוע דירוג - בודק את דירוגי הנכסים בחיפוש טלגרם
    """
    
    def __init__(self):
        """
        אתחול מנוע הדירוג
        """
        # מטמון לתוצאות דירוג
        self.rank_cache = {}
        # זמן מטמון (בשעות)
        self.cache_hours = Constants.RANK_CACHE_TTL // 3600  # Convert seconds to hours
        # טוען מטמון קיים
        self._load_cache()
    
    def _load_cache(self):
        """
        טוען את מטמון הדירוגים ממסד הנתונים
        """
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT * FROM rank_cache
                        WHERE created_at > NOW() - INTERVAL '%s hours'
                    """, (self.cache_hours,))
                    
                    for row in cur.fetchall():
                        cache_key = f"{row['asset_id']}:{row['keyword']}"
                        self.rank_cache[cache_key] = {
                            'rank': row['rank'],
                            'tier': row['tier'],
                            'created_at': row['created_at']
                        }
                    
            logger.info(f"מטמון דירוגים נטען בהצלחה: {len(self.rank_cache)} רשומות")
            
        except Exception as e:
            logger.error(f"שגיאה בטעינת מטמון דירוגים: {str(e)}")
    
    def _save_to_cache(self, asset_id: int, keyword: str, rank: int, tier: str):
        """
        שומר תוצאת דירוג למטמון
        
        Args:
            asset_id: מזהה הנכס
            keyword: מילת מפתח
            rank: דירוג
            tier: רמת דירוג
        """
        cache_key = f"{asset_id}:{keyword}"
        self.rank_cache[cache_key] = {
            'rank': rank,
            'tier': tier,
            'created_at': datetime.now()
        }
        
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    # מחק רשומות ישנות
                    cur.execute("""
                        DELETE FROM rank_cache
                        WHERE asset_id = %s AND keyword = %s
                    """, (asset_id, keyword))
                    
                    # הוסף רשומה חדשה
                    cur.execute("""
                        INSERT INTO rank_cache
                        (asset_id, keyword, rank, tier, created_at)
                        VALUES (%s, %s, %s, %s, NOW())
                    """, (asset_id, keyword, rank, tier))
                    
        except Exception as e:
            logger.error(f"שגיאה בשמירת דירוג למטמון: {str(e)}")
    
    def _get_from_cache(self, asset_id: int, keyword: str) -> Optional[Dict[str, Any]]:
        """
        מקבל תוצאת דירוג ממטמון
        
        Args:
            asset_id: מזהה הנכס
            keyword: מילת מפתח
            
        Returns:
            תוצאת דירוג ממטמון או None אם לא נמצא
        """
        cache_key = f"{asset_id}:{keyword}"
        if cache_key in self.rank_cache:
            cached = self.rank_cache[cache_key]
            # בדוק אם המטמון תקף
            cache_time = cached.get('created_at')
            if cache_time:
                # אם עדיין בתוקף
                now = datetime.now()
                if isinstance(cache_time, str):
                    cache_time = datetime.fromisoformat(cache_time)
                
                if now - cache_time < timedelta(hours=self.cache_hours):
                    return {
                        'rank': cached.get('rank'),
                        'tier': cached.get('tier'),
                        'from_cache': True
                    }
        
        return None
    
    async def check_rank(self, asset_id: int, keyword: str, force_fresh: bool = False) -> Tuple[int, str, bool]:
        """
        בודק את דירוג הנכס לפי מילת מפתח
        
        Args:
            asset_id: מזהה הנכס
            keyword: מילת מפתח
            force_fresh: האם לאלץ בדיקה טרייה (לא ממטמון)
            
        Returns:
            (דירוג, tier, האם ממטמון)
        """
        # נסה לקבל ממטמון אם לא מאולץ
        if not force_fresh:
            cached_result = self._get_from_cache(asset_id, keyword)
            if cached_result:
                logger.info(f"דירוג נמצא במטמון: נכס {asset_id}, מילה '{keyword}', דירוג {cached_result['rank']}")
                return cached_result['rank'], cached_result['tier'], True
        
        # קבל פרטי נכס
        asset = assets_manager.get_asset(asset_id)
        if not asset:
            logger.error(f"נכס לא נמצא: {asset_id}")
            return -1, Constants.TIER_UNAVAILABLE, False
        
        # שנה שם זמני עם מילת המפתח + סיומת מיוחדת
        temp_name = f"{keyword}{Constants.SPECIAL_SUFFIX}"
        success, msg = await profile_editor.change_asset_name(asset_id, temp_name)
        
        if not success:
            logger.error(f"שגיאה בשינוי שם נכס: {msg}")
            return -1, Constants.TIER_UNAVAILABLE, False
        
        try:
            # המתן 30 שניות לאינדקס
            logger.info(f"ממתין לאינדקס של נכס {asset_id} עם השם '{temp_name}'")
            await asyncio.sleep(30)
            
            # בדוק דירוג
            rank_result = await rank_checker.check_asset_rank(asset, keyword)
            rank = rank_result[0]
            
            # קבע tier לפי דירוג
            tier = Constants.get_tier_for_rank(rank)
            
            # שמור למטמון
            self._save_to_cache(asset_id, keyword, rank, tier)
            
            logger.info(f"דירוג נבדק: נכס {asset_id}, מילה '{keyword}', דירוג {rank}, tier {tier}")
            
            return rank, tier, False
            
        except Exception as e:
            logger.error(f"שגיאה בבדיקת דירוג: {str(e)}")
            return -1, Constants.TIER_UNAVAILABLE, False
            
        finally:
            # החזר שם מקורי
            original_name = assets_manager.get_asset_original_name(asset_id)
            if original_name:
                await profile_editor.change_asset_name(asset_id, original_name)
    
    async def find_best_assets_for_keyword(self, keyword: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        מחפש את הנכסים הטובים ביותר למילת מפתח
        
        Args:
            keyword: מילת מפתח
            limit: מקסימום נכסים להחזיר
            
        Returns:
            רשימת נכסים ממויינת לפי דירוג (הטובים ביותר קודם)
        """
        # קבל נכסים זמינים
        available_assets = assets_manager.get_available_assets()
        
        if not available_assets:
            logger.warning(f"אין נכסים זמינים לבדיקה עבור המילה '{keyword}'")
            return []
        
        results = []
        
        # בדוק דירוג לכל נכס
        for asset in available_assets:
            rank, tier, from_cache = await self.check_rank(asset['id'], keyword)
            
            # דלג על נכסים שלא זמינים
            if tier == Constants.TIER_UNAVAILABLE:
                continue
            
            # הוסף מידע רלוונטי
            result = {
                'asset_id': asset['id'],
                'name': asset['name'],
                'type': asset['type'],
                'keyword': keyword,
                'rank': rank,
                'tier': tier,
                'price': Constants.get_price_for_rank(rank),
                'from_cache': from_cache
            }
            
            results.append(result)
        
        # מיין לפי דירוג (הדירוג הטוב ביותר קודם)
        results.sort(key=lambda x: (0 if x['rank'] > 0 else 999, x['rank']))
        
        # החזר עד limit תוצאות
        return results[:limit]
    
    async def get_rank_history(self, asset_id: int, keyword: str, days: int = 7) -> List[Dict[str, Any]]:
        """
        מקבל היסטוריית דירוג של נכס למילת מפתח
        
        Args:
            asset_id: מזהה הנכס
            keyword: מילת מפתח
            days: מספר ימים אחורה
            
        Returns:
            רשימת רשומות דירוג
        """
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT * FROM rank_cache
                        WHERE asset_id = %s AND keyword = %s
                        AND created_at > NOW() - INTERVAL '%s days'
                        ORDER BY created_at ASC
                    """, (asset_id, keyword, days))
                    
                    history = []
                    for row in cur.fetchall():
                        history.append(dict(row))
                    
                    return history
                    
        except Exception as e:
            logger.error(f"שגיאה בקבלת היסטוריית דירוג: {str(e)}")
            return []
    
    def clear_cache(self, asset_id: Optional[int] = None, keyword: Optional[str] = None):
        """
        מנקה את מטמון הדירוגים
        
        Args:
            asset_id: מזהה נכס ספציפי לניקוי (אופציונלי)
            keyword: מילת מפתח ספציפית לניקוי (אופציונלי)
        """
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    if asset_id and keyword:
                        # נקה רשומה ספציפית
                        cur.execute("""
                            DELETE FROM rank_cache
                            WHERE asset_id = %s AND keyword = %s
                        """, (asset_id, keyword))
                        
                        # הסר ממטמון מקומי
                        cache_key = f"{asset_id}:{keyword}"
                        if cache_key in self.rank_cache:
                            del self.rank_cache[cache_key]
                            
                    elif asset_id:
                        # נקה את כל הרשומות לנכס מסוים
                        cur.execute("""
                            DELETE FROM rank_cache
                            WHERE asset_id = %s
                        """, (asset_id,))
                        
                        # הסר ממטמון מקומי
                        keys_to_remove = [k for k in self.rank_cache if k.startswith(f"{asset_id}:")]
                        for key in keys_to_remove:
                            del self.rank_cache[key]
                            
                    elif keyword:
                        # נקה את כל הרשומות למילת מפתח מסוימת
                        cur.execute("""
                            DELETE FROM rank_cache
                            WHERE keyword = %s
                        """, (keyword,))
                        
                        # הסר ממטמון מקומי
                        keys_to_remove = [k for k in self.rank_cache if k.endswith(f":{keyword}")]
                        for key in keys_to_remove:
                            del self.rank_cache[key]
                            
                    else:
                        # נקה את כל המטמון
                        cur.execute("DELETE FROM rank_cache")
                        self.rank_cache = {}
                        
            logger.info(f"מטמון דירוגים נוקה: asset_id={asset_id}, keyword={keyword}")
            
        except Exception as e:
            logger.error(f"שגיאה בניקוי מטמון דירוגים: {str(e)}")


# יצירת אינסטנס לשימוש מחוץ למודול
rank_engine = RankEngine()
