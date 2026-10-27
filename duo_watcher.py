#!/usr/bin/env python3
"""
iPhone Duo – Abhol-Verfügbarkeits-Watcher (Apple Store DE)

Läuft als GitHub Action alle ~5 Min (oder lokal mit --loop).
Push aufs iPhone via ntfy.sh (App "ntfy", Topic abonnieren).
"""

import os
import sys
import time
import random
from datetime import datetime

import requests

# ---------------- Konfiguration ----------------
# Artikelnummer -> (Bezeichnung, Priorität: kleiner = wichtiger)
PARTS = {
    "MK2F4ZD/A": ("512GB Sternenweiß", 1),
    "MK2G4ZD/A": ("512GB Nachthimmel", 1),
    "MK2D4ZD/A": ("256GB Sternenweiß", 2),
    "MK2E4ZD/A": ("256GB Nachthimmel", 2),  # nicht verifiziert, siehe Log
}

LOCATION = "40212"  # Düsseldorf Zentrum -> Düsseldorf, Köln, Oberhausen in Reichweite

# Stichwort im Store-Namen -> Priorität (kleiner = wichtiger)
STORES = {
    "düsseldorf": 1,
    "köln": 2,
    "schildergasse": 2,
    "rhein-center": 2,
    "oberhausen": 3,
    "centro": 3,
}

NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "duo-watch-CHANGE-ME")
# ------------------------------------------------

URL = "https://www.apple.com/de/shop/fulfillment-messages"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
                   "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                   "Version/18.0 Mobile/15E148 Safari/604.1"),
    "Accept": "application/json",
    "Referer": "https://www.apple.com/de/shop/buy-iphone",
}


def store_prio(name: str) -> int | None:
    n = name.lower()
    hits = [p for key, p in STORES.items() if key in n]
    return min(hits) if hits else None


def notify(title: str, msg: str, priority: str) -> None:
    requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=msg.encode("utf-8"),
        headers={
            "Title": title.encode("utf-8"),
            "Priority": priority,
            "Tags": "iphone",
            "Click": "https://www.apple.com/de/shop/buy-iphone",
        },
        timeout=10,
    )


def check() -> None:
    params = {"pl": "true", "mts.0": "regular", "location": LOCATION}
    for i, part in enumerate(PARTS):
        params[f"parts.{i}"] = part

    r = requests.get(URL, params=params, headers=HEADERS, timeout=20)
    r.raise_for_status()
    stores = r.json()["body"]["content"]["pickupMessage"]["stores"]

    hits = []  # (gesamt-prio, label, store, quote, modell-prio)
    for s in stores:
        name = s.get("storeName", "?")
        sp = store_prio(name)
        print(f"  Store: {name}" + ("  <- beobachtet" if sp else ""))
        if sp is None:
            continue
        pa = s.get("partsAvailability", {})
        for part, (label, mp) in PARTS.items():
            if part not in pa:
                print(f"    ! {part} ({label}) nicht in Antwort – Artikelnummer prüfen")
                continue
            if pa[part].get("pickupDisplay") == "available":
                quote = pa[part].get("pickupSearchQuote", "")
                hits.append((mp * 10 + sp, label, name, quote, mp))

    now = datetime.now().strftime("%d.%m. %H:%M")
    if not hits:
        print(f"[{now}] nichts verfügbar")
        return

    hits.sort()
    best = hits[0]
    lines = [f"• {l} – {st} ({q})" for _, l, st, q, _ in hits]
    print(f"[{now}] VERFÜGBAR:\n" + "\n".join(lines))
    notify(
        f"Duo {best[1]} in {best[2]}!",
        "\n".join(lines) + "\nJetzt reservieren!",
        "urgent" if best[4] == 1 else "high",
    )


if __name__ == "__main__":
    if "--test" in sys.argv:
        notify("Duo-Watcher", "Test-Push kommt an ✅", "default")
    elif "--loop" in sys.argv:          # lokal dauerhaft laufen lassen
        while True:
            try:
                check()
            except Exception as e:
                print("Fehler:", e)
            time.sleep(90 + random.uniform(0, 30))
    else:                               # GitHub Action: einmal prüfen
        check()
