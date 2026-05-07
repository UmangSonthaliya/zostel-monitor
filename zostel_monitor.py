"""
Zostel Availability Monitor — GitHub Actions edition
Runs once per invocation, exits, and sends a phone push via ntfy.sh
when a room opens up for the configured dates.
"""
import os
import asyncio
import requests
from playwright.async_api import async_playwright

URL = "https://www.zostel.com/destination/poombarai/stay/zostel-plus-kodaikanal-poombarai-kdkh833?checkin=2026-05-22&checkout=2026-05-24"
NTFY_TOPIC = os.environ["NTFY_TOPIC"]  # set as a GitHub secret

SOLD_OUT_PHRASES = [
    "sold out", "not available", "fully booked",
    "no rooms available", "unavailable for these dates",
]
AVAILABLE_PHRASES = ["book now", "select room", "add to cart", "reserve now"]


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


async def fetch_page_text() -> str:
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
        await page.goto(URL, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(4000)
        text = (await page.inner_text("body")).lower()
        await browser.close()
        return text


async def main():
    body = await fetch_page_text()
    sold_out = next((p for p in SOLD_OUT_PHRASES if p in body), None)
    available = next((p for p in AVAILABLE_PHRASES if p in body), None)

    if available and not sold_out:
        print(f"AVAILABLE — matched '{available}'")
        send_push(
            "🎉 Zostel Poombarai available!",
            "A room just opened up for 22–24 May 2026. Tap to book before someone else grabs it.",
        )
    elif sold_out:
        print(f"Still sold out — matched '{sold_out}'")
    else:
        print("Unclear signal — neither phrase set matched. May need to tune phrases.")


if __name__ == "__main__":
    asyncio.run(main())
