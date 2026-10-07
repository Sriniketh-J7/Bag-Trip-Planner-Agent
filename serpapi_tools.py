"""SerpApi wrappers: Google Flights, Google Hotels, Google Maps. Each call
returns {"ok": bool, "source": str, ...} so a failure never crashes the graph."""
import requests
from config import SERPAPI_KEY

BASE_URL = "https://serpapi.com/search.json"

# City name -> IATA airport code. Google Flights requires a code, not a city
# name - this was the Chennai bug: "Chennai" was being sent straight to the
# API as arrival_id instead of "MAA". Add more entries here as you need them.
AIRPORT_CODES = {
    "hyderabad": "HYD", "bangalore": "BLR", "bengaluru": "BLR", "chennai": "MAA",
    "mumbai": "BOM", "delhi": "DEL", "new delhi": "DEL", "goa": "GOI",
    "pune": "PNQ", "kolkata": "CCU", "ahmedabad": "AMD", "jaipur": "JAI",
    "kochi": "COK", "lucknow": "LKO", "chandigarh": "IXC", "nagpur": "NAG",
    "indore": "IDR", "bhubaneswar": "BBI", "visakhapatnam": "VTZ",
    "coimbatore": "CJB", "trivandrum": "TRV", "guwahati": "GAU",
    "london": "LHR", "new york": "JFK", "dubai": "DXB", "singapore": "SIN",
    "bangkok": "BKK", "paris": "CDG", "tokyo": "HND", "bali": "DPS",
}


def to_airport_code(place: str) -> str | None:
    place = place.strip()
    if len(place) == 3 and place.isalpha():
        return place.upper()  # already a code
    return AIRPORT_CODES.get(place.lower())


def _call(engine: str, params: dict, source: str) -> dict:
    if not SERPAPI_KEY:
        return {"ok": False, "source": source, "error": "SERPAPI_KEY not set in .env"}
    try:
        r = requests.get(BASE_URL, params={**params, "engine": engine, "api_key": SERPAPI_KEY}, timeout=30)
        r.raise_for_status()
        return {"ok": True, "source": source, "data": r.json()}
    except requests.exceptions.RequestException as e:
        return {"ok": False, "source": source, "error": str(e)}


def search_flights(origin: str, destination: str, outbound_date: str,
                    return_date: str | None = None, trip_type: str = "round_trip") -> dict:
    """Dates: YYYY-MM-DD. origin/destination can be a city name or airport code."""
    dep_code = to_airport_code(origin)
    arr_code = to_airport_code(destination)
    missing = [name for name, code in [("origin", dep_code), ("destination", arr_code)] if not code]
    if missing:
        bad = origin if "origin" in missing else destination
        return {
            "ok": False, "source": "Google Flights (SerpApi)",
            "error": f"No airport code known for '{bad}'. Type the 3-letter airport code directly "
                     f"(e.g. MAA for Chennai) or add it to AIRPORT_CODES in serpapi_tools.py.",
        }

    params = {
        "departure_id": dep_code, "arrival_id": arr_code, "outbound_date": outbound_date,
        "type": "1" if trip_type == "round_trip" else "2", "currency": "INR", "hl": "en",
    }
    if trip_type == "round_trip" and return_date:
        params["return_date"] = return_date

    result = _call("google_flights", params, "Google Flights (SerpApi)")
    if not result["ok"]:
        return result

    flights = []
    for key in ("best_flights", "other_flights"):
        for f in result["data"].get(key, []):
            legs = f.get("flights", [])
            if not legs:
                continue
            first, last = legs[0], legs[-1]
            flights.append({
                "airline": first.get("airline", "Unknown"),
                "departure_time": first.get("departure_airport", {}).get("time"),
                "arrival_time": last.get("arrival_airport", {}).get("time"),
                "duration_minutes": f.get("total_duration"),
                "stops": len(legs) - 1,
                "price_inr": f.get("price"),
                "baggage": first.get("airplane", "N/A"),
            })
    result["flights"] = flights
    if not flights:
        result["ok"] = False
        result["error"] = "No flights returned for this route/date (route may not exist or dates too far out)."
    return result


def search_hotels(destination: str, check_in: str, check_out: str, adults: int = 1) -> dict:
    params = {"q": f"hotels in {destination}", "check_in_date": check_in,
              "check_out_date": check_out, "adults": adults, "currency": "INR", "hl": "en"}
    result = _call("google_hotels", params, "Google Hotels (SerpApi)")
    if not result["ok"]:
        return result
    result["hotels"] = [{
        "name": h.get("name"),
        "price_inr": h.get("rate_per_night", {}).get("lowest"),
        "rating": h.get("overall_rating"),
        "reviews_count": h.get("reviews"),
        "location": h.get("address"),
        "amenities": h.get("amenities", [])[:8],
    } for h in result["data"].get("properties", [])]
    return result


def search_places(destination: str, category: str) -> dict:
    """category: free-text like 'best rated restaurants' or 'top tourist attractions'."""
    result = _call("google_maps", {"q": f"{category} in {destination}", "type": "search"}, "Google Maps (SerpApi)")
    if not result["ok"]:
        return result
    result["places"] = [{
        "name": p.get("title"), "rating": p.get("rating"), "reviews_count": p.get("reviews"),
        "price_level": p.get("price"), "type": p.get("type"), "address": p.get("address"),
    } for p in result["data"].get("local_results", [])]
    return result
