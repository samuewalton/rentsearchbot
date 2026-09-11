# -*- coding: utf-8 -*-
"""Rental management — DB-backed (S4).

מחזור חיים: pending -> active/monitoring/expiring -> expired -> archived.
שינויי שם נכס (הפעלה/סיום/החלפה) מבוצעים כאן מול profile_editor.
`user_id` במילונים המוחזרים הוא alias ל-user_telegram_id (תאימות callers).
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from constants import Constants
from db import get_connection
from utils import AsyncHelper
from assets_manager import assets_manager
from profile_editor import profile_editor

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = (
    Constants.RENTAL_STATUS_ACTIVE,
    Constants.RENTAL_STATUS_MONITORING,
    Constants.RENTAL_STATUS_EXPIRING,
)


def _row_to_rental(row: Any) -> Dict[str, Any]:
    d = dict(row)
    d["user_id"] = d.get("user_telegram_id")
    return d


def _fetch_rental(cur: Any, rental_id: int) -> Optional[Dict[str, Any]]:
    cur.execute("SELECT * FROM rentals WHERE id = %s", (rental_id,))
    row = cur.fetchone()
    return _row_to_rental(row) if row else None


def get_all_rentals() -> List[Dict[str, Any]]:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM rentals ORDER BY created_at DESC")
                return [_row_to_rental(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"שגיאה בקבלת השכרות: {e}")
        return []


def get_rental_price(rank: int, tier: str) -> float:
    """מחיר לפי דירוג (tier נשמר לחתימה עתידית)."""
    return float(Constants.get_price_for_rank(rank))


def create_rental_request(
    user_id: int, keyword: str
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """יוצר בקשת השכרה בסטטוס pending."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO rentals (user_telegram_id, keyword, status)
                    VALUES (%s, %s, %s)
                    RETURNING *
                    """,
                    (user_id, keyword, Constants.RENTAL_STATUS_PENDING),
                )
                row = cur.fetchone()
                if not row:
                    return None, "failed to create rental"
                return _row_to_rental(row), None
    except Exception as e:
        logger.error(f"שגיאה ביצירת בקשת השכרה: {e}")
        return None, str(e)


def create_rental(data: Dict[str, Any]) -> int:
    """יוצר רשומת השכרה ממילון (מיפוי מפתחות גמיש). מחזיר id (0 בכשלון)."""
    user_telegram_id = data.get("user_telegram_id", data.get("user_id"))
    if not user_telegram_id:
        logger.error("יצירת השכרה נכשלה: חסר user_id")
        return 0
    duration_hours = data.get("duration_hours")
    if duration_hours is None and data.get("duration_days") is not None:
        try:
            duration_hours = int(data["duration_days"]) * 24
        except (TypeError, ValueError):
            duration_hours = None
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO rentals
                        (user_telegram_id, asset_id, asset_type, keyword,
                         tier, rank, price, duration_hours, status,
                         payment_id, start_time, end_time)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        user_telegram_id,
                        data.get("asset_id"),
                        data.get("asset_type"),
                        data.get("keyword"),
                        data.get("tier"),
                        data.get("rank"),
                        data.get("price"),
                        duration_hours,
                        data.get("status", Constants.RENTAL_STATUS_PENDING),
                        data.get("payment_id"),
                        data.get("start_time"),
                        data.get("end_time"),
                    ),
                )
                row = cur.fetchone()
                return row["id"] if row else 0
    except Exception as e:
        logger.error(f"שגיאה ביצירת השכרה: {e}")
        return 0


def get_rental(rental_id: int) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                rental = _fetch_rental(cur, rental_id)
                if not rental:
                    return None, "rental not found"
                return rental, None
    except Exception as e:
        logger.error(f"שגיאה בקבלת השכרה {rental_id}: {e}")
        return None, str(e)


def activate_rental(
    rental_id: int, payment_id: str, duration_hours: int
) -> Tuple[bool, str]:
    """מפעיל השכרה: סטטוס + חלון זמן + שינוי שם הנכס ל-keyword@@@@@@."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                rental = _fetch_rental(cur, rental_id)
                if not rental:
                    return False, "rental not found"
                cur.execute(
                    """
                    UPDATE rentals
                    SET status = %s, payment_id = %s,
                        start_time = NOW(),
                        end_time = NOW() + make_interval(secs => %s),
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (
                        Constants.RENTAL_STATUS_ACTIVE,
                        payment_id,
                        int(duration_hours) * 3600,
                        rental_id,
                    ),
                )
        # שינוי שם הנכס (מחוץ לטרנזקציה; כשלון מחזיר ל-pending)
        asset_id = rental.get("asset_id")
        keyword = rental.get("keyword")
        if asset_id and keyword:
            try:
                coro = profile_editor.change_asset_name(
                    asset_id, f"{keyword}{Constants.SPECIAL_SUFFIX}"
                )
                success, msg = AsyncHelper.run_async(coro)
            except Exception as e:
                success, msg = False, str(e)
            if not success:
                logger.error(f"שינוי שם נכשל להפעלה {rental_id}: {msg}")
                update_rental_status(rental_id, Constants.RENTAL_STATUS_PENDING)
                return False, f"asset rename failed: {msg}"
        return True, ""
    except Exception as e:
        logger.error(f"שגיאה בהפעלת השכרה {rental_id}: {e}")
        return False, str(e)


def cancel_rental(rental_id: int) -> Tuple[bool, str]:
    """מבטל השכרה (ומשחזר שם נכס אם היתה פעילה)."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                rental = _fetch_rental(cur, rental_id)
                if not rental:
                    return False, "rental not found"
                if rental.get("status") in ACTIVE_STATUSES and rental.get("asset_id"):
                    try:
                        coro = profile_editor.restore_asset_name(rental["asset_id"])
                        AsyncHelper.run_async(coro)
                    except Exception as e:
                        logger.error(f"שחזור שם נכשל בביטול {rental_id}: {e}")
                cur.execute(
                    "UPDATE rentals SET status = %s, updated_at = NOW() WHERE id = %s",
                    (Constants.RENTAL_STATUS_CANCELED, rental_id),
                )
        return True, ""
    except Exception as e:
        logger.error(f"שגיאה בביטול השכרה {rental_id}: {e}")
        return False, str(e)


def extend_rental(
    rental_id: int, payment_id: str, duration_hours: int
) -> Tuple[bool, str]:
    """מאריך השכרה (end_time קיים, או מעכשיו אם חסר)."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE rentals
                    SET end_time = COALESCE(end_time, NOW())
                                 + make_interval(secs => %s),
                        payment_id = %s, updated_at = NOW()
                    WHERE id = %s
                    """,
                    (int(duration_hours) * 3600, payment_id, rental_id),
                )
                if cur.rowcount == 0:
                    return False, "rental not found"
        return True, ""
    except Exception as e:
        logger.error(f"שגיאה בהארכת השכרה {rental_id}: {e}")
        return False, str(e)


def update_rental_status(rental_id: int, new_status: str) -> Tuple[bool, str]:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE rentals SET status = %s, updated_at = NOW() WHERE id = %s",
                    (new_status, rental_id),
                )
                if cur.rowcount == 0:
                    return False, "rental not found"
        return True, ""
    except Exception as e:
        logger.error(f"שגיאה בעדכון סטטוס {rental_id}: {e}")
        return False, str(e)


def get_rentals_by_status(status: str) -> List[Dict[str, Any]]:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM rentals WHERE status = %s ORDER BY created_at DESC",
                    (status,),
                )
                return [_row_to_rental(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"שגיאה בקבלת השכרות בסטטוס {status}: {e}")
        return []


def get_rentals_expiring_soon(hours: int) -> List[Dict[str, Any]]:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM rentals
                    WHERE status IN (%s, %s, %s)
                      AND end_time IS NOT NULL
                      AND end_time <= NOW() + make_interval(secs => %s)
                    ORDER BY end_time ASC
                    """,
                    (
                        Constants.RENTAL_STATUS_ACTIVE,
                        Constants.RENTAL_STATUS_MONITORING,
                        Constants.RENTAL_STATUS_EXPIRING,
                        int(hours) * 3600,
                    ),
                )
                return [_row_to_rental(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"שגיאה בקבלת השכרות פגות: {e}")
        return []


async def expire_rental(rental_id: int) -> Tuple[bool, str]:
    """מסיים השכרה: שחזור שם + סטטוס expired + שורת היסטוריה."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                rental = _fetch_rental(cur, rental_id)
                if not rental:
                    return False, "rental not found"
                if rental.get("asset_id"):
                    try:
                        await profile_editor.restore_asset_name(rental["asset_id"])
                    except Exception as e:
                        logger.error(f"שחזור שם נכשל בסיום {rental_id}: {e}")
                cur.execute(
                    "UPDATE rentals SET status = %s, updated_at = NOW() WHERE id = %s",
                    (Constants.RENTAL_STATUS_EXPIRED, rental_id),
                )
                cur.execute(
                    """
                    INSERT INTO rental_history
                        (rental_id, user_telegram_id, asset_id, keyword, status)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        rental_id,
                        rental.get("user_telegram_id"),
                        rental.get("asset_id"),
                        rental.get("keyword"),
                        Constants.RENTAL_STATUS_EXPIRED,
                    ),
                )
        return True, ""
    except Exception as e:
        logger.error(f"שגיאה בסיום השכרה {rental_id}: {e}")
        return False, str(e)


async def replace_rental_asset(
    rental_id: int, new_asset_id: int, rank: int, tier: str
) -> Tuple[bool, str]:
    """מחליף נכס בהשכרה: שחזור ישן + שינוי חדש + עדכון שורה."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                rental = _fetch_rental(cur, rental_id)
                if not rental:
                    return False, "rental not found"
                old_asset_id = rental.get("asset_id")
                keyword = rental.get("keyword")
                if old_asset_id and old_asset_id != new_asset_id:
                    try:
                        await profile_editor.restore_asset_name(old_asset_id)
                    except Exception as e:
                        logger.error(f"שחזור ישן נכשל בהחלפה {rental_id}: {e}")
                if keyword:
                    try:
                        ok, msg = await profile_editor.change_asset_name(
                            new_asset_id, f"{keyword}{Constants.SPECIAL_SUFFIX}"
                        )
                        if not ok:
                            logger.error(f"שינוי חדש נכשל בהחלפה {rental_id}: {msg}")
                    except Exception as e:
                        logger.error(f"שינוי חדש נכשל בהחלפה {rental_id}: {e}")
                cur.execute(
                    """
                    UPDATE rentals
                    SET asset_id = %s, rank = %s, tier = %s, updated_at = NOW()
                    WHERE id = %s
                    """,
                    (new_asset_id, rank, tier, rental_id),
                )
        return True, ""
    except Exception as e:
        logger.error(f"שגיאה בהחלפת נכס {rental_id}: {e}")
        return False, str(e)


async def get_suitable_asset_for_keyword(
    keyword: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """מוצא את הנכס הטוב ביותר למילה: Premium קודם, ואז rank נמוך.

    מחזיר ({'asset', 'rank', 'tier'}, None) — המבנה שה-watchdog מצפה לו.
    """
    try:
        # יבוא עצל — rank_engine מייבא את rental_manager (מעגל פוטנציאלי)
        from rank_engine import rank_engine

        available_assets = assets_manager.get_available_assets()
        if not available_assets:
            return None, "no available assets"

        best: Optional[Dict[str, Any]] = None
        for asset in available_assets:
            try:
                rank, tier, _ = await rank_engine.check_rank(asset["id"], keyword)
            except Exception as e:
                logger.error(f"דירוג נכשל לנכס {asset.get('id')}: {e}")
                continue
            if tier == Constants.TIER_UNAVAILABLE or rank is None or rank < 0:
                continue
            candidate = {"asset": asset, "rank": rank, "tier": tier}
            if best is None or _is_better(candidate, best):
                best = candidate

        if best is None:
            return None, "no suitable asset found"
        return best, None
    except Exception as e:
        logger.error(f"שגיאה בחיפוש נכס למילה '{keyword}': {e}")
        return None, str(e)


def _is_better(
    candidate: Dict[str, Any], best: Dict[str, Any]
) -> bool:
    """Premium גובר על Regular; בתוך tier — rank נמוך wins."""
    tier_order = {
        Constants.TIER_PREMIUM: 0,
        Constants.TIER_REGULAR: 1,
        Constants.TIER_UNAVAILABLE: 2,
    }
    cand_tier = tier_order.get(candidate["tier"], 2)
    best_tier = tier_order.get(best["tier"], 2)
    if cand_tier != best_tier:
        return cand_tier < best_tier
    return candidate["rank"] < best["rank"]


def archive_expired_rentals(days_threshold: int = 0) -> int:
    """מעביר השכרות שפגו/בוטלו מזמן לארכיון. מחזיר כמות."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE rentals
                    SET status = %s, updated_at = NOW()
                    WHERE status IN (%s, %s)
                      AND COALESCE(end_time, updated_at, created_at)
                          < NOW() - make_interval(secs => %s)
                    """,
                    (
                        Constants.RENTAL_STATUS_ARCHIVED,
                        Constants.RENTAL_STATUS_EXPIRED,
                        Constants.RENTAL_STATUS_CANCELED,
                        int(days_threshold) * 86400,
                    ),
                )
                return cur.rowcount or 0
    except Exception as e:
        logger.error(f"שגיאה בארכוב השכרות: {e}")
        return 0


class RentalManager:
    """מעטפת מחלקתית ל-API המודולרי."""

    def get_all_rentals(self) -> List[Dict[str, Any]]:
        return get_all_rentals()

    def get_rentals_by_status(self, status: str) -> List[Dict[str, Any]]:
        return get_rentals_by_status(status)

    def get_rental_price(self, rank: int, tier: str) -> float:
        return get_rental_price(rank, tier)

    def create_rental_request(
        self, user_id: int, keyword: str
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        return create_rental_request(user_id, keyword)

    def create_rental(self, data: Dict[str, Any]) -> int:
        return create_rental(data)

    def get_rental(self, rental_id: int) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        return get_rental(rental_id)

    def activate_rental(
        self, rental_id: int, payment_id: str, duration_hours: int
    ) -> Tuple[bool, str]:
        return activate_rental(rental_id, payment_id, duration_hours)

    def cancel_rental(self, rental_id: int) -> Tuple[bool, str]:
        return cancel_rental(rental_id)

    def extend_rental(
        self, rental_id: int, payment_id: str, duration_hours: int
    ) -> Tuple[bool, str]:
        return extend_rental(rental_id, payment_id, duration_hours)

    def update_rental_status(self, rental_id: int, new_status: str) -> Tuple[bool, str]:
        return update_rental_status(rental_id, new_status)

    def get_rentals_expiring_soon(self, hours: int) -> List[Dict[str, Any]]:
        return get_rentals_expiring_soon(hours)

    async def expire_rental(self, rental_id: int) -> Tuple[bool, str]:
        return await expire_rental(rental_id)

    async def replace_rental_asset(
        self, rental_id: int, new_asset_id: int, rank: int, tier: str
    ) -> Tuple[bool, str]:
        return await replace_rental_asset(rental_id, new_asset_id, rank, tier)

    async def get_suitable_asset_for_keyword(
        self, keyword: str
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        return await get_suitable_asset_for_keyword(keyword)

    def archive_expired_rentals(self, days_threshold: int = 0) -> int:
        return archive_expired_rentals(days_threshold)


default_manager = RentalManager()
# alias used in other modules
rental_manager = default_manager
