# -*- coding: utf-8 -*-
"""Simplified rental management placeholder."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from constants import Constants

logger = logging.getLogger(__name__)

# In-memory storage for rentals
_rentals: Dict[int, Dict[str, Any]] = {}
_next_id = 1


def get_all_rentals() -> List[Dict[str, Any]]:
    return list(_rentals.values())


def get_rental_price(rank: int, tier: str) -> float:
    """Return a rental price based on rank/tier."""
    return float(Constants.get_price_for_rank(rank))


def create_rental_request(user_id: int, keyword: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Create a new rental entry in pending state."""
    global _next_id
    rental = {
        "id": _next_id,
        "user_id": user_id,
        "keyword": keyword,
        "asset_id": None,
        "asset_name": None,
        "asset_type": None,
        "rank": -1,
        "tier": Constants.TIER_UNAVAILABLE,
        "price": 0,
        "status": Constants.RENTAL_STATUS_PENDING,
    }
    _rentals[_next_id] = rental
    _next_id += 1
    return rental, None


def create_rental(data: Dict[str, Any]) -> int:
    """Add a rental to the store and return its id."""
    global _next_id
    data = dict(data)
    data.setdefault("id", _next_id)
    _rentals[_next_id] = data
    _next_id += 1
    return data["id"]


def get_rental(rental_id: int) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    rental = _rentals.get(rental_id)
    if not rental:
        return None, "rental not found"
    return rental, None


def activate_rental(rental_id: int, payment_id: str, duration_hours: int) -> Tuple[bool, str]:
    rental = _rentals.get(rental_id)
    if not rental:
        return False, "rental not found"
    rental["status"] = Constants.RENTAL_STATUS_ACTIVE
    rental["payment_id"] = payment_id
    rental["start_time"] = datetime.now()
    rental["end_time"] = datetime.now() + timedelta(hours=duration_hours)
    return True, ""


def cancel_rental(rental_id: int) -> Tuple[bool, str]:
    rental = _rentals.get(rental_id)
    if not rental:
        return False, "rental not found"
    rental["status"] = Constants.RENTAL_STATUS_CANCELED
    return True, ""


def extend_rental(rental_id: int, payment_id: str, duration_hours: int) -> Tuple[bool, str]:
    rental = _rentals.get(rental_id)
    if not rental:
        return False, "rental not found"
    rental["end_time"] = rental.get("end_time", datetime.now()) + timedelta(hours=duration_hours)
    rental["payment_id"] = payment_id
    return True, ""


def update_rental_status(rental_id: int, new_status: str) -> Tuple[bool, str]:
    rental = _rentals.get(rental_id)
    if not rental:
        return False, "rental not found"
    rental["status"] = new_status
    return True, ""


def get_rentals_by_status(status: str) -> List[Dict[str, Any]]:
    return [r for r in _rentals.values() if r.get("status") == status]


def get_rentals_expiring_soon(hours: int) -> List[Dict[str, Any]]:
    upcoming = []
    threshold = datetime.now() + timedelta(hours=hours)
    for r in _rentals.values():
        end_time = r.get("end_time")
        if end_time and end_time <= threshold and r.get("status") in [
            Constants.RENTAL_STATUS_ACTIVE,
            Constants.RENTAL_STATUS_MONITORING,
            Constants.RENTAL_STATUS_EXPIRING,
        ]:
            upcoming.append(r)
    return upcoming


async def expire_rental(rental_id: int) -> Tuple[bool, str]:
    rental = _rentals.get(rental_id)
    if not rental:
        return False, "rental not found"
    rental["status"] = Constants.RENTAL_STATUS_EXPIRED
    return True, ""


async def replace_rental_asset(rental_id: int, new_asset_id: int, rank: int, tier: str) -> Tuple[bool, str]:
    rental = _rentals.get(rental_id)
    if not rental:
        return False, "rental not found"
    rental["asset_id"] = new_asset_id
    rental["rank"] = rank
    rental["tier"] = tier
    return True, ""


async def get_suitable_asset_for_keyword(keyword: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Placeholder that returns None. Real implementation would query assets."""
    return None, "not implemented"


def archive_expired_rentals(days_threshold: int = 0) -> int:
    count = 0
    now = datetime.now() - timedelta(days=days_threshold)
    for r in list(_rentals.values()):
        end = r.get("end_time")
        if end and end < now and r.get("status") in [Constants.RENTAL_STATUS_EXPIRED, Constants.RENTAL_STATUS_CANCELED]:
            r["status"] = Constants.RENTAL_STATUS_ARCHIVED
            count += 1
    return count


class RentalManager:
    def get_all_rentals(self) -> List[Dict[str, Any]]:
        return get_all_rentals()

    def get_rentals_by_status(self, status: str) -> List[Dict[str, Any]]:
        return get_rentals_by_status(status)

    def get_rental_price(self, rank: int, tier: str) -> float:
        return get_rental_price(rank, tier)

    def create_rental_request(self, user_id: int, keyword: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        return create_rental_request(user_id, keyword)

    def create_rental(self, data: Dict[str, Any]) -> int:
        return create_rental(data)

    def get_rental(self, rental_id: int) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        return get_rental(rental_id)

    def activate_rental(self, rental_id: int, payment_id: str, duration_hours: int) -> Tuple[bool, str]:
        return activate_rental(rental_id, payment_id, duration_hours)

    def cancel_rental(self, rental_id: int) -> Tuple[bool, str]:
        return cancel_rental(rental_id)

    def extend_rental(self, rental_id: int, payment_id: str, duration_hours: int) -> Tuple[bool, str]:
        return extend_rental(rental_id, payment_id, duration_hours)

    def update_rental_status(self, rental_id: int, new_status: str) -> Tuple[bool, str]:
        return update_rental_status(rental_id, new_status)

    def get_rentals_expiring_soon(self, hours: int) -> List[Dict[str, Any]]:
        return get_rentals_expiring_soon(hours)

    async def expire_rental(self, rental_id: int) -> Tuple[bool, str]:
        return await expire_rental(rental_id)

    async def replace_rental_asset(self, rental_id: int, new_asset_id: int, rank: int, tier: str) -> Tuple[bool, str]:
        return await replace_rental_asset(rental_id, new_asset_id, rank, tier)

    async def get_suitable_asset_for_keyword(self, keyword: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        return await get_suitable_asset_for_keyword(keyword)

    def archive_expired_rentals(self, days_threshold: int = 0) -> int:
        return archive_expired_rentals(days_threshold)


default_manager = RentalManager()
# alias used in other modules
rental_manager = default_manager

