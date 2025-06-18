import json
import random
import os
from session_classifier import SessionClassifier

RANK_INPUT_FILE = "rank_input.json"
SESSIONS_DIR = "sessions"
ASSETS_DIR = "assets"


def load_assets():
    assets = []
    for filename in os.listdir(ASSETS_DIR):
        if filename.endswith(".json"):
            with open(os.path.join(ASSETS_DIR, filename), "r", encoding="utf-8") as f:
                asset = json.load(f)
                # Add @@@@@@ to each keyword for forced indexing
                asset["keywords"] = [kw + "@@@@@@" for kw in asset.get("keywords", [])]
                assets.append(asset)
    return assets


def get_clean_sessions():
    clean_sessions = []
    for file in os.listdir(SESSIONS_DIR):
        if file.endswith(".session"):
            path = os.path.join(SESSIONS_DIR, file)
            with open(path, "r", encoding="utf-8") as f:
                session_string = f.read()
            if SessionClassifier.is_clean(session_string):
                clean_sessions.append(session_string)
    return clean_sessions


def generate_schedule():
    assets = load_assets()
    clean_sessions = get_clean_sessions()

    if not clean_sessions:
        raise ValueError("No clean sessions available for scheduling.")

    schedule = []
    for i, asset in enumerate(assets):
        session = clean_sessions[i % len(clean_sessions)]
        schedule.append({
            "session": session,
            "keywords": asset["keywords"],
            "target_id": asset["target_id"]
        })

    with open(RANK_INPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(schedule[0], f, ensure_ascii=False, indent=2)

    print("[✔] rank_input.json generated with clean session assigned.")


if __name__ == "__main__":
    generate_schedule()
