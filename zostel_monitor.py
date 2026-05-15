"""
Zostel Availability Monitor — GitHub Actions edition
Intercepts the rooms-availability JSON API call directly instead of scraping text.
"""
import os
import asyncio
import requests
from playwright.async_api import async_playwright

CHECKIN = "2026-05-23"
CHECKOUT = "2026-05-25"
URL = (
    f"https://www.zostel.com/destination/poombarai/stay/"
    f"zostel-plus-kodaikanal-poombarai-kdkh833"
    f"?checkin={CHECKIN}&checkout={CHECKOUT}"
)
NTFY_TOPIC = os.environ["NTFY_TOPIC"]

# Only notify for rooms whose name contains one of these (case-insensitive).
# Empty list = notify for ANY available room.
# Example: ["mixed dorm"] to only watch the mixed dorm.
ROOM_FILTER = ["dorm"]


def send_push(title: str, body: str) -> None:
    requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=body.encode("utf-8"),
        headers={
            "Title": title,
            "Priority": "urgent",
            "Tags": "rotating_light,bed",
            "Click": URL,
        },
        timeout=15,
    )


async def fetch_rooms():
    captured = {"data": None}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 900},
        )
        page = await context.new_page()

        async def on_response(response):
            try:
                ct = (response.headers or {}).get("content-type", "")
                if "application/json" not in ct:
                    return
                body = await response.json()
                if (
                    isinstance(body, dict)
                    and "rooms" in body
                    and "dates" in body
                    and body.get("dates", {}).get("checkin") == CHECKIN
                    and body.get("dates", {}).get("checkout") == CHECKOUT
                ):
                    captured["data"] = body
            except Exception:
                pass

        page.on("response", lambda r: asyncio.create_task(on_response(r)))

        await page.goto(URL, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(5000)
        await browser.close()

    return captured["data"]


async def main():
    data = await fetch_rooms()

    if not data:
        print("ERROR: Did not capture the rooms availability API response.")
        print("Either the site changed its API or the page didn't load in time.")
        return

    currency = data.get("currency", {}).get("symbol", "")
    print(f"Checking {data['dates']['checkin']} -> {data['dates']['checkout']}")

    matching_available = []
    for room in data.get("rooms", []):
        name = room.get("name", "Unknown")
        avail = room.get("availability", {}) or {}
        units = avail.get("units", 0) or 0
        is_available = bool(avail.get("available")) and units > 0
        price = (room.get("price") or {}).get("final", 0)

        print(f"  - {name}: available={is_available}, units={units}, price={currency}{price}")

        if not is_available:
            continue
        if ROOM_FILTER and not any(f.lower() in name.lower() for f in ROOM_FILTER):
            continue
        matching_available.append(
            {"name": name, "units": units, "price": price}
        )

    if matching_available:
        lines = [
            f"• {r['name']} — {r['units']} unit(s) at {currency}{r['price']}"
            for r in matching_available
        ]
        body = f"Available for {CHECKIN} → {CHECKOUT}:\n\n" + "\n".join(lines)
        print("\nAVAILABLE — sending notification")
        send_push("🎉 Zostel Poombarai available!", body)
    else:
        print("\nNothing matching is available. No notification sent.")


if __name__ == "__main__":
    asyncio.run(main())
