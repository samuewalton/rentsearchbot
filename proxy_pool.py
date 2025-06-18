import json
import random
import os

PROXY_FILE = "proxies.json"


def ensure_proxy_file():
    if not os.path.exists(PROXY_FILE):
        with open(PROXY_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)


def load_proxies():
    ensure_proxy_file()
    try:
        with open(PROXY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [(p["ip"], p["port"], p.get("user"), p.get("pass")) for p in data]
    except Exception as e:
        print(f"[!] Failed to load proxies: {e}")
        return []


def add_proxy(ip, port, user=None, password=None):
    ensure_proxy_file()
    proxy_entry = {"ip": ip, "port": port}
    if user:
        proxy_entry["user"] = user
    if password:
        proxy_entry["pass"] = password

    proxies = load_proxies()
    proxies.append((ip, port, user, password))

    with open(PROXY_FILE, "w", encoding="utf-8") as f:
        json.dump([
            {"ip": p[0], "port": p[1], "user": p[2], "pass": p[3]} for p in proxies
        ], f, indent=2)


PROXIES = load_proxies()


def get_random_proxy():
    if not PROXIES:
        return None
    return random.choice(PROXIES)


if __name__ == "__main__":
    print("Loaded proxies:")
    for proxy in PROXIES:
        print(proxy)
