"""Weather via SerpApi's Google Search answer box - no separate weather API/key.
Google's forecast only covers ~10 days from today; dates outside that window
are reported as unavailable rather than guessed."""
import requests
from datetime import datetime, timedelta
from config import SERPAPI_KEY

BASE_URL = "https://serpapi.com/search.json"


def get_weather_outlook(destination: str, start_date: str, end_date: str) -> dict:
    source = "Google Search Weather (SerpApi)"
    if not SERPAPI_KEY:
        return {"ok": False, "source": source, "error": "SERPAPI_KEY not set in .env"}

    try:
        r = requests.get(BASE_URL, params={"engine": "google", "q": f"weather in {destination}",
                                            "api_key": SERPAPI_KEY}, timeout=30)
        r.raise_for_status()
        forecast = r.json().get("answer_box", {}).get("forecast")
    except requests.exceptions.RequestException as e:
        return {"ok": False, "source": source, "error": str(e)}

    if not forecast:
        return {"ok": False, "source": source, "error": f"No weather forecast returned for '{destination}'."}

    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    today = datetime.now().date()

    summary = {}
    for i, entry in enumerate(forecast):
        day = today + timedelta(days=i)
        if start <= day <= end:
            temp = entry.get("temperature", {})
            summary[str(day)] = {
                "day_name": entry.get("day"), "condition": entry.get("weather"),
                "high_c": temp.get("high"), "low_c": temp.get("low"), "humidity": entry.get("humidity"),
            }

    if not summary:
        return {"ok": False, "source": source,
                "error": "Trip dates are outside Google's ~10-day forecast window."}
    return {"ok": True, "source": source, "daily": summary}
