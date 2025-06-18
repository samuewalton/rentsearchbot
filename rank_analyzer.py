import json
import os
from datetime import datetime
from typing import Dict, List

CACHE_FILE = "rank_cache.json"
INPUT_FILE = "rank_schedule.json"
ALERTS_FILE = "rank_alerts.json"

MAX_ACCEPTED_RANK = 7


def load_json(path: str) -> Dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: Dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def analyze_rank_changes(schedule: List[Dict], cache: Dict) -> List[Dict]:
    alerts = []
    now = datetime.now().isoformat()

    for asset in schedule:
        asset_name = asset["asset_name"]
        target_id = asset["target_id"]
        keywords = asset["keywords"]

        for keyword in keywords:
            key = f"{asset_name}:{keyword}"
            new_rank = asset.get("rank", {}).get(keyword, -1)
            prev_rank = cache.get(key, -1)

            if new_rank == -1:
                continue

            cache[key] = new_rank

            if new_rank > MAX_ACCEPTED_RANK:
                alerts.append({
                    "asset_name": asset_name,
                    "keyword": keyword,
                    "prev_rank": prev_rank,
                    "new_rank": new_rank,
                    "target_id": target_id,
                    "timestamp": now
                })

    return alerts


def main():
    schedule = load_json(INPUT_FILE)
    cache = load_json(CACHE_FILE)

    alerts = analyze_rank_changes(schedule, cache)

    save_json(CACHE_FILE, cache)
    save_json(ALERTS_FILE, alerts)

    print(f"Analyzed {len(schedule)} assets. Alerts: {len(alerts)}")


if __name__ == "__main__":
    main()
