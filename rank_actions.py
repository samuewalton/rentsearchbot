import json
from datetime import datetime

ALERTS_FILE = "rank_alerts.json"
ACTIONS_FILE = "rank_actions.json"


class ActionType:
    NOTIFY = "notify"
    SUGGEST_REPLACEMENT = "suggest_replacement"
    REFUND_PARTIAL = "refund_partial"


def load_alerts():
    with open(ALERTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_actions(alerts):
    actions = []
    for alert in alerts:
        rank = alert["new_rank"]
        if rank <= 3:
            action = ActionType.NOTIFY
        elif 4 <= rank <= 7:
            action = ActionType.SUGGEST_REPLACEMENT
        else:
            action = ActionType.REFUND_PARTIAL

        actions.append({
            "asset_name": alert["asset_name"],
            "keyword": alert["keyword"],
            "rank": rank,
            "action": action,
            "timestamp": datetime.now().isoformat()
        })
    return actions


def save_actions(actions):
    with open(ACTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(actions, f, ensure_ascii=False, indent=2)


def main():
    alerts = load_alerts()
    actions = generate_actions(alerts)
    save_actions(actions)
    print(f"[✔] Actions generated: {len(actions)}")


if __name__ == "__main__":
    main()