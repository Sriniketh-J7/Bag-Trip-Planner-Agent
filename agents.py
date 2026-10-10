"""
LangGraph orchestration. Gemini is used in exactly two places and nowhere
else, to keep quota usage low:
  1. recommendation_agent - writes the final narrative (called once for the
     initial plan, and only again if the user explicitly asks to regenerate).
  2. route_constraint - LLM FALLBACK ONLY. Most replan messages are handled
     by a free regex-based rule router (`rule_based_route`) with zero API
     calls; Gemini is only asked when the rules can't confidently parse the
     message.
"""
import json
import re
from typing import TypedDict, Optional, List
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI

from config import GOOGLE_API_KEY, GEMINI_MODEL
import serpapi_tools as sp
import weather_tool as wt


def get_llm():
    return ChatGoogleGenerativeAI(model=GEMINI_MODEL, google_api_key=GOOGLE_API_KEY, temperature=0.3) \
        if GOOGLE_API_KEY else None


class TripState(TypedDict, total=False):
    destination: str
    origin: str
    start_date: str
    end_date: str
    travelers: int
    budget_cap: Optional[int]
    weather: dict
    flights: dict
    selected_flight: Optional[dict]
    hotels: dict
    selected_hotel: Optional[dict]
    restaurants: dict
    attractions: dict
    budget: dict
    recommendation: str
    rerun: List[str]
    user_constraint: Optional[str]
    log: List[str]


def _log(state: TripState, msg: str):
    state.setdefault("log", []).append(msg)


def _lowest_priced(items: list[dict], field: str) -> dict:
    """Select a real, lowest-priced option; records with no price are last."""
    return min(items, key=lambda item: sp.price_sort_key(item.get(field)))


# ---------------------------------------------------------------------------
# Agent nodes (no LLM calls - pure API + data shaping)
# ---------------------------------------------------------------------------
def weather_agent(state: TripState) -> TripState:
    res = wt.get_weather_outlook(state["destination"], state["start_date"], state["end_date"])
    state["weather"] = res
    _log(state, f"Weather: {'ok' if res.get('ok') else res.get('error')}")
    return state


def flight_agent(state: TripState) -> TripState:
    res = sp.search_flights(state["origin"], state["destination"], state["start_date"],
                             state.get("end_date"), "round_trip")
    state["flights"] = res
    if res.get("ok") and res.get("flights"):
        state["selected_flight"] = _lowest_priced(res["flights"], "price_inr")
    _log(state, f"Flight: {'ok' if res.get('ok') else res.get('error')}")
    return state


def hotel_agent(state: TripState) -> TripState:
    res = sp.search_hotels(state["destination"], state["start_date"], state["end_date"], state.get("travelers", 1))
    state["hotels"] = res
    if res.get("ok") and res.get("hotels"):
        # Budget plans should not silently choose a high-rated luxury stay.
        state["selected_hotel"] = _lowest_priced(res["hotels"], "price_inr")
    _log(state, f"Hotel: {'ok' if res.get('ok') else res.get('error')}")
    return state


def restaurant_agent(state: TripState) -> TripState:
    # Request affordable local options directly instead of broad, often premium,
    # "best rated" results. Sort known price tiers before unknown prices.
    res = sp.search_places(state["destination"], "affordable budget restaurants local food")
    if res.get("ok"):
        res["places"].sort(key=lambda place: sp.price_sort_key(place.get("price_level")))
    state["restaurants"] = res
    _log(state, f"Restaurant: {'ok' if res.get('ok') else res.get('error')}")
    return state


def attractions_agent(state: TripState) -> TripState:
    combined, ok_any = [], False
    for cat in ("top tourist attractions", "hidden gem places to visit"):
        res = sp.search_places(state["destination"], cat)
        if res.get("ok"):
            ok_any = True
            combined.extend({**p, "bucket": cat} for p in res["places"])
    state["attractions"] = {"ok": ok_any, "source": "Google Maps (SerpApi)", "places": combined}
    _log(state, f"Attractions: {'ok' if ok_any else 'skipped'}")
    return state



def budget_agent(state: TripState) -> TripState:
    from datetime import datetime

    def to_number(value):
        if value is None or value == "":
            return 0

        if isinstance(value, (int, float)):
            return value

        cleaned = re.sub(r"[^\d.]", "", str(value).replace(",", ""))
        return float(cleaned) if cleaned else 0

    flight_price = (state.get("selected_flight") or {}).get("price_inr")
    hotel_price = (state.get("selected_hotel") or {}).get("price_inr")

    try:
        nights = max(
            (
                datetime.strptime(state["end_date"], "%Y-%m-%d")
                - datetime.strptime(state["start_date"], "%Y-%m-%d")
            ).days,
            1,
        )
    except Exception:
        nights = 1

    travelers = state.get("travelers", 1)

    hotel_price = to_number(hotel_price)
    flight_price = to_number(flight_price)

    hotel_total = hotel_price * nights if hotel_price else None

    actual = {
        "flight_inr": flight_price or None,
        "hotel_inr": hotel_total,
    }

    estimated = {
        "food_inr": 1200 * nights * travelers,
        "local_transport_inr": 600 * nights * travelers,
        "activities_inr": 1500 * nights * travelers,
    }

    total = sum(to_number(v) for v in actual.values()) + sum(
        to_number(v) for v in estimated.values()
    )

    cap = state.get("budget_cap")

    state["budget"] = {
        "nights": nights,
        "actual_retrieved": actual,
        "ai_estimated": estimated,
        "estimated_total_inr": total,
        "budget_cap_inr": cap,
        "within_budget": (total <= cap) if cap else None,
    }

    _log(state, f"Budget: total Rs.{total:,.0f}")

    return state




def recommendation_agent(state: TripState) -> TripState:
    llm = get_llm()
    if llm is None:
        state["recommendation"] = "GOOGLE_API_KEY not set - cannot generate the narrative recommendation."
        return state
    context = {
        "destination": state.get("destination"), "dates": f"{state.get('start_date')} to {state.get('end_date')}",
        "travelers": state.get("travelers"),
        "weather": state.get("weather", {}).get("daily") if state.get("weather", {}).get("ok") else "unavailable",
        "selected_flight": state.get("selected_flight"), "selected_hotel": state.get("selected_hotel"),
        "top_restaurants": (state.get("restaurants", {}).get("places") or [])[:5],
        "top_attractions": (state.get("attractions", {}).get("places") or [])[:8],
        "budget": state.get("budget"),
    }
    prompt = (
        "You are a travel planning assistant. Using this trip data (JSON), write a concise, scannable "
        "recommendation: best flight + why, best hotel + why, 3-4 restaurant picks, 3-4 attraction picks, "
        "best travel day if weather data exists, total estimated cost, one cheaper alternative if budget is "
        "tight, and 2-3 practical tips. Be honest about unavailable data instead of inventing it.\n\n"
        f"TRIP DATA:\n{json.dumps(context, indent=2, default=str)}"
    )
    try:
        state["recommendation"] = llm.invoke(prompt).content
    except Exception as e:
        state["recommendation"] = f"Could not generate recommendation: {e}"
    _log(state, "Recommendation: generated")
    return state


# ---------------------------------------------------------------------------
# Router - free rule-based parser first, Gemini only as fallback
# ---------------------------------------------------------------------------
ALL_AGENTS = ["weather", "flight", "hotel", "restaurant", "attractions", "budget"]
AGENT_KEYWORDS = {
    "flight": ["flight", "airline", "flying"],
    "hotel": ["hotel", "stay", "accommodation", "airbnb", "room"],
    "restaurant": ["restaurant", "food", "eat", "dining"],
    "attractions": ["attraction", "places to visit", "sightseeing", "things to do"],
    "weather": ["weather", "rain", "forecast"],
}
AMOUNT_RE = re.compile(r"(?:rs\.?|inr|₹)?\s*([\d,]+)\s*(k|lakh|lac)?", re.IGNORECASE)


def _extract_amount(text: str) -> Optional[int]:
    best = None
    for m in AMOUNT_RE.finditer(text):
        digits, unit = m.group(1), (m.group(2) or "").lower()
        if not any(c.isdigit() for c in digits):
            continue
        value = int(digits.replace(",", ""))
        if unit == "k":
            value *= 1_000
        elif unit in ("lakh", "lac"):
            value *= 100_000
        if value >= 500:  # ignore tiny numbers like "2 people" false-matching
            best = value
    return best


def rule_based_route(message: str, state: TripState) -> Optional[dict]:
    """Returns a routing decision with zero API calls, or None if the message
    isn't clearly parseable (caller should fall back to the LLM router)."""
    text = message.lower()
    rerun = set()
    budget_cap = None

    is_cost_related = any(w in text for w in ("cheap", "budget", "spend", "afford", "cost", "₹", "rs.", "rs "))
    amount = _extract_amount(text)
    if amount:
        budget_cap = amount

    for agent, keywords in AGENT_KEYWORDS.items():
        if any(k in text for k in keywords):
            # "keep the flight" / "keep my hotel" -> explicitly excluded even if mentioned
            keep_pattern = any(f"keep {k}" in text or f"keep the {k}" in text or f"keep my {k}" in text
                                for k in keywords)
            if keep_pattern:
                continue
            if agent in ("flight", "hotel") and is_cost_related:
                rerun.add(agent)
            elif agent not in ("flight", "hotel"):
                rerun.add(agent)

    if is_cost_related and not rerun and not amount:
        return None  # ambiguous cost mention with nothing concrete - let the LLM interpret it

    if not rerun and not amount:
        return None  # nothing recognizable at all - fall back to LLM

    if amount:
        # A total-budget request must refresh the choices that determine the
        # total, not merely recompute the old selections. Respect explicit
        # "keep" instructions if the user supplied them.
        if not any(f"keep {word}" in text or f"keep the {word}" in text for word in AGENT_KEYWORDS["flight"]):
            rerun.add("flight")
        if not any(f"keep {word}" in text or f"keep the {word}" in text for word in AGENT_KEYWORDS["hotel"]):
            rerun.add("hotel")
        if not any(f"keep {word}" in text or f"keep the {word}" in text for word in AGENT_KEYWORDS["restaurant"]):
            rerun.add("restaurant")
        rerun.add("budget")
    elif rerun & {"flight", "hotel"}:
        rerun.add("budget")  # cost changes if flight/hotel changes

    return {"agents_to_rerun": sorted(rerun), "budget_cap": budget_cap}


ROUTER_PROMPT = """Decide which trip-planning agents must re-run for this user request.
Available agents: weather, flight, hotel, restaurant, attractions, budget.
Current trip: {context}
User message: "{message}"
Rules: include "budget" if flight/hotel changes; never include an agent the user says to "keep".
Respond ONLY with JSON: {{"agents_to_rerun": [...], "budget_cap": <number or null>}}"""


def route_constraint(state: TripState, message: str) -> TripState:
    decision = rule_based_route(message, state)
    if decision is not None:
        state["rerun"] = [a for a in decision["agents_to_rerun"] if a in ALL_AGENTS]
        if decision.get("budget_cap"):
            state["budget_cap"] = decision["budget_cap"]
        _log(state, f"Router (rules, no API call): re-running {state['rerun'] or 'nothing'}")
        state["user_constraint"] = message
        return state

    llm = get_llm()
    if llm is None:
        state["rerun"] = []
        _log(state, "Router: no LLM available, skipped re-plan")
        return state
    context = {"destination": state.get("destination"), "selected_flight": state.get("selected_flight"),
               "selected_hotel": state.get("selected_hotel"), "budget_cap": state.get("budget_cap")}
    try:
        raw = llm.invoke(ROUTER_PROMPT.format(context=json.dumps(context, default=str), message=message)).content
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(raw)
        state["rerun"] = [a for a in parsed.get("agents_to_rerun", []) if a in ALL_AGENTS]
        if parsed.get("budget_cap"):
            state["budget_cap"] = parsed["budget_cap"]
        _log(state, f"Router (LLM fallback): re-running {state['rerun'] or 'nothing'}")
    except Exception as e:
        state["rerun"] = []
        _log(state, f"Router: failed to parse constraint ({e})")
    state["user_constraint"] = message
    return state


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------
def build_initial_graph():
    g = StateGraph(TripState)
    for name, fn in [("weather_node", weather_agent), ("flight_node", flight_agent),
                      ("hotel_node", hotel_agent), ("restaurant_node", restaurant_agent),
                      ("attractions_node", attractions_agent), ("budget_node", budget_agent),
                      ("recommend_node", recommendation_agent)]:
        g.add_node(name, fn)
    g.set_entry_point("weather_node")
    order = ["weather_node", "flight_node", "hotel_node", "restaurant_node",
             "attractions_node", "budget_node", "recommend_node"]
    for a, b in zip(order, order[1:]):
        g.add_edge(a, b)
    g.add_edge("recommend_node", END)
    return g.compile()


AGENT_FN = {"weather": weather_agent, "flight": flight_agent, "hotel": hotel_agent,
            "restaurant": restaurant_agent, "attractions": attractions_agent, "budget": budget_agent}


def summarize_changes(state: TripState) -> str:
    """Summarize trip changes without additional LLM calls."""
    parts = []

    if state.get("selected_flight"):
        f = state["selected_flight"]
        price = f.get("price_inr")

        if price:
            try:
                price = float(str(price).replace(",", "").replace("₹", "").strip())
                parts.append(f"Flight: {f.get('airline')} - Rs.{price:,.0f}")
            except (ValueError, TypeError):
                parts.append(f"Flight: {f.get('airline')} - price unavailable")

    if state.get("selected_hotel"):
        h = state["selected_hotel"]
        price = h.get("price_inr")

        if price:
            try:
                price = float(str(price).replace(",", "").replace("₹", "").strip())
                parts.append(f"Hotel: {h.get('name')} - Rs.{price:,.0f}/night")
            except (ValueError, TypeError):
                parts.append(f"Hotel: {h.get('name')} - price unavailable")

    b = state.get("budget", {})

    if b.get("estimated_total_inr") is not None:
        try:
            total = float(b["estimated_total_inr"])
            status = ""

            if b.get("budget_cap_inr"):
                status = (
                    " (within budget)"
                    if b.get("within_budget")
                    else " (over budget)"
                )

            parts.append(f"Updated total: Rs.{total:,.0f}{status}")
        except (ValueError, TypeError):
            pass

    return " | ".join(parts) or "Updated - see tabs above."


def run_replan(state: TripState, message: str) -> TripState:
    """Routes the constraint (free, rule-based where possible), re-runs only
    the needed agents, recomputes budget, and returns a free deterministic
    summary. Does NOT call Gemini for a full recommendation rewrite - call
    recommendation_agent(state) separately if the user wants that."""
    state = route_constraint(state, message)
    # Budget must run last: it depends on the freshly selected flight/hotel.
    # Previously an alphabetic route order ran it first, showing stale totals.
    for agent_name in state.get("rerun", []):
        if agent_name != "budget":
            state = AGENT_FN[agent_name](state)
    if state.get("rerun"):
        state = budget_agent(state)
    return state
