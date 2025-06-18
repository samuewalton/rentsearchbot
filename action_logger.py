import json
import os
from datetime import datetime

from constants import Constants
from utils import ensure_dir, save_json


class ActionLogger:
    def __init__(self, path: str = Constants.ACTIONS_FILE):
        self.path = path
        ensure_dir(Constants.DATA_DIR)
        self.actions = self.load()

    def load(self):
        if not os.path.exists(self.path):
            return []
        with open(self.path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def log(self, action: dict):
        action['timestamp'] = datetime.now().isoformat()
        self.actions.append(action)
        save_json(self.path, self.actions)
        print(f"[+] Logged action: {action}")


if __name__ == "__main__":
    print("[INFO] ActionLogger module ready.")