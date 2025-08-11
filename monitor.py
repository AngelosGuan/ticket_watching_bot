import time
import random
import requests
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# 🔹 PASTE YOUR WEBHOOK HERE
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1404567050042736761/ZP67tCMqpLdHUGD5UsdwZRbpNhM0KPh_8g2k43K-igc6mHC6gEAPNQ1TzaPBHN0NM3wl"

# 🔹 PASTE YOUR EVENT URL HERE
TARGET_URL = "https://www.ticketmaster.com/sleep-token-even-in-arcadia-duluth-georgia-09-16-2025/event/0E00626ABEEB28A5"

# Check every ~45 minutes with jitter
SLEEP_MIN_MINUTES = 40
SLEEP_MAX_MINUTES = 55

# Phrases that usually indicate availability
POSITIVE_TRIGGERS = [
    "Buy Tickets",
    "Find Tickets",
    "Resale",
    "Tickets Available",
    "Standard Tickets",
    "Available now",
]
NEGATIVE_BLOCKERS = [
    "Tickets not available at this time",
    "Check back later",
    "No tickets available",
    "On sale soon",
]

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def jitter_sleep():
    minutes = random.randint(SLEEP_MIN_MINUTES, SLEEP_MAX_MINUTES)
    seconds = max(60, int((minutes + random.uniform(-0.5, 0.5)) * 60))
    return seconds

def send_discord(message: str):
    if not DISCORD_WEBHOOK_URL:
        print("[WARN] DISCORD_WEBHOOK_URL is empty; printing instead:\n", message)
        return
    payload = {"content": message[:1900]}
    try:
        r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=15)
        if r.status_code >= 300:
            print(f"[ERR] Discord webhook error: {r.status_code} {r.text}")
    except Exception as e:
        print(f"[ERR] Discord webhook exception: {e}")

def page_signals(page) -> dict:
    result = {"positive": False, "positive_hit": None, "negative": False, "negative_hit": None}
    body_text = page.inner_text("body")
    for phrase in POSITIVE_TRIGGERS:
        if phrase.lower() in body_text.lower():
            result["positive"] = True
            result["positive_hit"] = phrase
            break
    for phrase in NEGATIVE_BLOCKERS:
        if phrase.lower() in body_text.lower():
            result["negative"] = True
            result["negative_hit"] = phrase
            break
    return result

def check_once():
    with sync_playwright() as p:
        context = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        page = context.new_page()
        page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        })

        try:
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=120000)
            page.wait_for_timeout(4000)
        except PWTimeout:
            context.close()
            return {"ok": False, "error": "timeout loading"}

        sig = page_signals(page)
        context.close()
        return {"ok": True, "signals": sig}

def main():
    print(f"[*] Watcher started {now_iso()} for:\n{TARGET_URL}")
    alerted_once = False

    while True:
        result = check_once()
        if not result["ok"]:
            print(f"[WARN] Check failed: {result.get('error')}. Will retry.")
        else:
            sig = result["signals"]
            pos, pos_hit = sig["positive"], sig["positive_hit"]
            neg, neg_hit = sig["negative"], sig["negative_hit"]

            print(f"[{now_iso()}] positive={pos} ({pos_hit})  negative={neg} ({neg_hit})")

            if not neg and pos and not alerted_once:
                msg = (
                    "**Ticketmaster update detected**\n"
                    f"- Positive signal: **{pos_hit}**\n"
                    f"- URL: {TARGET_URL}\n"
                    f"- Time (UTC): {now_iso()}\n"
                    "\nIf this is a false positive, the site may be A/B testing text. Double-check manually."
                )
                send_discord(msg)
                alerted_once = True

        sleep_s = jitter_sleep()
        print(f"[*] Sleeping ~{sleep_s // 60} minutes…")
        time.sleep(sleep_s)

if __name__ == "__main__":
    main()
