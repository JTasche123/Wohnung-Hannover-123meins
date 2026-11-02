"""Prüft Wohnungsseiten auf neue Angebote und schickt eine Push-Nachricht via ntfy."""
import hashlib
import json
import os
import re
import sys
import urllib.request
from html.parser import HTMLParser

SITES = {
    "VE Üstra": {
        "url": "https://ve-uestra.de/wohnen/wohnungsangebot/",
        "leer": "keine freien Wohnungen im Angebot",
    },
    "WOLpert-WOhnen": {
        "url": "https://wol-wo.de/wohnungen",
        "leer": "keine freien Wohnungen",
    },
}

STATE_FILE = "state.json"
TOPIC = os.environ.get("NTFY_TOPIC", "").strip()
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def page_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        html = r.read().decode("utf-8", errors="replace")
    p = TextExtractor()
    p.feed(html)
    return re.sub(r"\s+", " ", " ".join(p.parts)).strip()


def notify(title, message, url=None):
    if not TOPIC:
        print("Kein NTFY_TOPIC gesetzt – Nachricht:", title, message)
        return
    headers = {"Title": title.encode("utf-8").decode("latin-1"), "Tags": "house", "Priority": "high"}
    if url:
        headers["Click"] = url
    req = urllib.request.Request(f"https://ntfy.sh/{TOPIC}", data=message.encode("utf-8"),
                                 headers=headers, method="POST")
    urllib.request.urlopen(req, timeout=30)


def main():
    if os.environ.get("TEST") == "true":
        notify("Wohnungscheck: Test", "Benachrichtigungen funktionieren!")
        return

    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            state = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        state = {}

    for name, cfg in SITES.items():
        try:
            text = page_text(cfg["url"])
        except Exception as e:
            print(f"{name}: Fehler beim Abruf ({e}) – übersprungen")
            continue

        if cfg["leer"].lower() in text.lower():
            new = "leer"
        else:
            new = hashlib.sha256(text.encode()).hexdigest()

        old = state.get(name)
        print(f"{name}: {'keine Wohnungen' if new == 'leer' else 'Angebot vorhanden'}")

        if old is not None and new != old and new != "leer":
            m = re.search(r"(\d+)\s+freie Wohnung", text)
            extra = f" ({m.group(1)} frei)" if m else ""
            notify(f"Neue Wohnung: {name}", f"Das Angebot hat sich geändert{extra}. Tippen zum Öffnen.", cfg["url"])
        state[name] = new

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    sys.exit(main())
