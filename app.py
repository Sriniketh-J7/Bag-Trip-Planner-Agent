import streamlit as st
import html
from datetime import date, timedelta
from config import MISSING_KEYS
from agents import build_initial_graph, run_replan, recommendation_agent, TripState, summarize_changes

st.set_page_config(page_title="BagTrip Planner", page_icon="🎒", layout="wide")
st.markdown("""
<style>
 .stApp { background: #09111f; color: #eaf0fa; }
 [data-testid="stSidebar"] { background: linear-gradient(180deg,#081522,#102a43); }
 [data-testid="stSidebar"] * { color: #f8fbff; }
 [data-testid="stSidebar"] .stTextInput input, [data-testid="stSidebar"] .stNumberInput input, [data-testid="stSidebar"] input { background:rgba(255,255,255,.12); color:white; }
 .hero { padding:2rem 2.2rem; margin:0 0 1.2rem; border-radius:24px; color:white; background:radial-gradient(circle at 90% 15%,#f5b942 0,#f5b94200 24%),linear-gradient(120deg,#0b2340,#174d6d 56%,#176f78); }
 .hero h1 { margin:.3rem 0; font-size:2.45rem; } .hero p { margin:0; opacity:.9; }
 .eyebrow { font-size:.72rem; font-weight:800; letter-spacing:.13em; text-transform:uppercase; opacity:.8; }
 .section-title { margin:.35rem 0 1rem; font-size:1.35rem; font-weight:800; color:#f4f7fb; }
 .card { padding:1rem 1.1rem; margin:.55rem 0; background:#111d2e; border:1px solid #263850; border-radius:16px; color:#ecf3fc; box-shadow:0 8px 22px rgba(0,0,0,.2); }
 .tag { display:inline-block; margin:.45rem .3rem 0 0; padding:.22rem .55rem; border-radius:99px; background:#153d4e; color:#8be5d0; font-size:.76rem; font-weight:700; }
 .selected { background:#5b4311; color:#ffd87b; } .source { color:#9fb0c8; font-size:.8rem; }
 .flight-card { margin:.75rem 0; padding:1.2rem 1.35rem; border-radius:18px; background:linear-gradient(110deg,#111f34,#172d4a); border:1px solid #2a4c69; }
 .flight-route { color:#f5f8fc; font-size:1.1rem; font-weight:800; } .flight-meta { color:#aebed2; margin-top:.35rem; }
 .fare { display:inline-block; margin-top:.75rem; padding:.55rem .8rem; background:#f5b942; border-radius:10px; color:#152238; font-weight:900; font-size:1.05rem; }
 .stop-direct { color:#6ee7b7; } .stop-one { color:#f8ce67; } .stop-many { color:#ff9c9c; }
 .visual-fallback { min-height:126px; display:flex; align-items:center; justify-content:center; border-radius:14px; font-size:3.3rem; background:linear-gradient(135deg,#203b5e,#145760); }
 .budget-hero { padding:2rem; border-radius:22px; background:linear-gradient(120deg,#15486e,#1a7f78); color:white; text-align:center; } .budget-hero .total { font-size:2.7rem; font-weight:900; margin:.2rem 0; }
 [data-testid="stImage"] img { border-radius:14px; object-fit:cover; min-height:126px; } .stTabs [data-baseweb="tab"] { font-weight:700; color:#afbdd0; } .stTabs [aria-selected="true"] { color:#69e0c5!important; }
 [data-testid="stTextInput"] input { background:#111d2e; color:#edf4fb; border-color:#314964; }
</style>
""", unsafe_allow_html=True)
st.markdown("""
<section class="hero"><div class="eyebrow">Your smarter travel companion</div>
<h1>Plan less. Experience more.</h1><p>Live flights, stays, local food and experiences — shaped around your trip.</p></section>
""", unsafe_allow_html=True)

if MISSING_KEYS:
    st.warning(f"Missing keys in .env: {', '.join(MISSING_KEYS)}. Affected agents will report "
               "unavailable data instead of crashing. See README.md.")

st.session_state.setdefault("trip_state", None)
st.session_state.setdefault("chat_history", [])


def pretty_date(value):
    """Human-friendly date used in the UI; API calls continue using ISO dates."""
    try:
        parsed = value if isinstance(value, date) else date.fromisoformat(str(value))
        return parsed.strftime("%a, %d %b %Y")
    except (TypeError, ValueError):
        return str(value)


with st.sidebar:
    st.markdown("## 🎒 BagTrip")
    st.caption("Plan a new trip")
    origin = st.text_input("Flying from (city or airport code)", value="HYD")
    destination = st.text_input("Destination (city or airport code)", value="Chennai")
    c1, c2 = st.columns(2)
    start_date = c1.date_input("Depart", value=date.today() + timedelta(days=2), format="DD/MM/YYYY")
    end_date = c2.date_input("Return", value=date.today() + timedelta(days=5), format="DD/MM/YYYY")
    st.caption(f"🗓️ {pretty_date(start_date)}  →  {pretty_date(end_date)}")
    travelers = st.number_input("Travelers", min_value=1, max_value=10, value=2)
    budget_cap = st.number_input("Budget cap (INR, optional)", min_value=0, value=0, step=5000)
    plan_btn = st.button("Research my trip ✨", type="primary", use_container_width=True)

if plan_btn:
    if end_date <= start_date:
        st.sidebar.error("End date must be after start date.")
    else:
        with st.spinner("Trip Manager Agent is coordinating all agents..."):
            initial: TripState = {
                "origin": origin.strip(), "destination": destination.strip(),
                "start_date": str(start_date), "end_date": str(end_date),
                "travelers": int(travelers), "budget_cap": int(budget_cap) or None, "log": [],
            }
            st.session_state.trip_state = build_initial_graph().invoke(initial)
            st.session_state.chat_history = []

state = st.session_state.trip_state
if state is None:
    st.info("Fill in the trip details in the sidebar and click **Research My Trip** to begin.")
    st.stop()

st.markdown(
    f"<div class='card'><b>{html.escape(str(state.get('origin', 'Origin')))} → "
    f"{html.escape(str(state.get('destination', 'Destination')))}</b><br>"
    f"<span class='source'>🗓️ {pretty_date(state.get('start_date'))} — {pretty_date(state.get('end_date'))} · "
    f"{state.get('travelers', 1)} traveler(s)</span></div>",
    unsafe_allow_html=True,
)

with st.expander("Agent run log"):
    for line in state.get("log", []):
        st.text(line)

tabs = st.tabs(["✨ Overview", "🌦️ Weather", "✈️ Flights", "🏨 Stays", "🍜 Food", "📍 Things to do", "💰 Budget"])


def money(value):
    if value is None or value == "":
        return "Price unavailable"
    try:
        cleaned = str(value).replace(",", "").replace("₹", "").replace("Rs.", "").strip()
        return f"₹{float(cleaned):,.0f}"
    except (TypeError, ValueError):
        return "Price unavailable"


def render_list(data: dict, key: str, line_fn, empty_label: str, limit: int = 10):
    if data.get("ok") and data.get(key):
        for item in data[key][:limit]:
            st.markdown(f"<div class='card'>{line_fn(item)}</div>", unsafe_allow_html=True)
        st.markdown(f"<p class='source'>Live source: {html.escape(str(data['source']))}</p>", unsafe_allow_html=True)
    else:
        st.error(f"{empty_label}: {data.get('error', 'unavailable')}")


def render_place_card(place: dict, fallback: str):
    """Show real SerpApi imagery when supplied, without making UI rendering fragile."""
    image, content = st.columns([1, 3], gap="medium")
    with image:
        if isinstance(place.get("image_url"), str) and place["image_url"].startswith(("http://", "https://")):
            st.image(place["image_url"], use_column_width=True)
        else:
            st.markdown(f"<div class='visual-fallback'>{fallback}</div>", unsafe_allow_html=True)
    with content:
        name = html.escape(str(place.get("name", "Untitled")))
        address = html.escape(str(place.get("address") or place.get("location") or "Location details unavailable"))
        tags = [f"★ {place.get('rating', 'New')}"]
        for value in (place.get("price_level"), place.get("type"), place.get("bucket")):
            if value:
                tags.append(str(value))
        st.markdown(f"<div class='card'><b>{name}</b><br><span class='source'>{address}</span><br>" +
                    "".join(f"<span class='tag'>{html.escape(value)}</span>" for value in tags) + "</div>", unsafe_allow_html=True)


with tabs[0]:
    st.markdown("<div class='section-title'>Your curated itinerary</div>", unsafe_allow_html=True)
    st.markdown(state.get("recommendation", "No recommendation generated."))
    if st.button("🔄 Regenerate full recommendation (uses 1 Gemini call)"):
        with st.spinner("Regenerating..."):
            st.session_state.trip_state = recommendation_agent(state)
        st.rerun()

with tabs[1]:
    w = state.get("weather", {})
    if w.get("ok"):
        st.markdown("<div class='section-title'>What to pack for</div>", unsafe_allow_html=True)
        cols = st.columns(min(len(w["daily"]), 5) or 1)
        for col, (day, info) in zip(cols, w["daily"].items()):
            with col:
                st.markdown(f"<div class='card'><b>{html.escape(str(info.get('day_name', day)))}</b><h3>{info.get('high_c', '?')}°C</h3>{html.escape(str(info.get('condition', 'n/a')))}<br><span class='source'>{info.get('low_c', '?')}° low · {info.get('humidity', 'n/a')} humidity</span></div>", unsafe_allow_html=True)
    else:
        st.error(f"Weather unavailable: {w.get('error')}")

with tabs[2]:
    f = state.get("flights", {})
    sel = state.get("selected_flight")
    st.markdown("<div class='section-title'>Flight options</div>", unsafe_allow_html=True)
    if f.get("ok") and f.get("flights"):
        route = f"{state.get('origin', 'Origin')} → {state.get('destination', 'Destination')}"
        for flight in f["flights"][:10]:
            stops = int(flight.get("stops") or 0)
            stop_style = "stop-direct" if stops == 0 else "stop-one" if stops == 1 else "stop-many"
            label = "Non-stop" if stops == 0 else f"{stops} stop{'s' if stops > 1 else ''}"
            duration = flight.get("duration_minutes")
            duration_label = f" · {duration // 60}h {duration % 60:02d}m" if isinstance(duration, int) else ""
            chosen = flight == sel
            st.markdown(
                f"<div class='flight-card'><div class='flight-route'>{'⭐ ' if chosen else '✈️ '}"
                f"{html.escape(str(flight.get('airline', 'Unknown airline')))} <span class='source'>· {html.escape(route)}</span></div>"
                f"<div class='flight-meta'><b>{html.escape(str(flight.get('departure_time', '—')))}</b> &nbsp; ━━━━━━━✈━━━━━━━ &nbsp; "
                f"<b>{html.escape(str(flight.get('arrival_time', '—')))}</b></div>"
                f"<span class='{stop_style}'>{label}{duration_label}</span><br>"
                f"<span class='fare'>{money(flight.get('price_inr'))}</span>"
                f"{' <span class=\"tag selected\">Best value</span>' if chosen else ''}</div>",
                unsafe_allow_html=True,
            )
        st.markdown(f"<p class='source'>Live source: {html.escape(str(f.get('source', 'SerpApi')))}</p>", unsafe_allow_html=True)
    else:
        st.error(f"Flights unavailable: {f.get('error', 'unavailable')}")


with tabs[3]:
    h = state.get("hotels", {})
    sel_h = state.get("selected_hotel")

    def format_hotel_price(price):
        if price is None or price == "":
            return "price n/a"

        try:
            cleaned = str(price).replace(",", "").replace("₹", "").strip()
            return f"Rs.{float(cleaned):,.0f}/night"
        except (ValueError, TypeError):
            return "price n/a"

    st.markdown("<div class='section-title'>Places to stay</div>", unsafe_allow_html=True)
    if h.get("ok") and h.get("hotels"):
        for hotel in h["hotels"][:10]:
            hotel = {**hotel, "type": format_hotel_price(hotel.get("price_inr")),
                     "bucket": "Top pick" if hotel == sel_h else None}
            render_place_card(hotel, "🏨")
        st.markdown(f"<p class='source'>Live source: {html.escape(str(h['source']))}</p>", unsafe_allow_html=True)
    else:
        st.error(f"Hotels unavailable: {h.get('error', 'unavailable')}")


with tabs[4]:
    r = state.get("restaurants", {})
    st.markdown("<div class='section-title'>Taste the destination</div>", unsafe_allow_html=True)
    if r.get("ok") and r.get("places"):
        for place in r["places"][:10]:
            render_place_card(place, "🍜")
        st.markdown(f"<p class='source'>Live source: {html.escape(str(r['source']))}</p>", unsafe_allow_html=True)
    else:
        st.error(f"Restaurants unavailable: {r.get('error', 'unavailable')}")

with tabs[5]:
    a = state.get("attractions", {})
    st.markdown("<div class='section-title'>Make time for these</div>", unsafe_allow_html=True)
    if a.get("ok") and a.get("places"):
        for place in a["places"][:16]:
            render_place_card(place, "📍")
        st.markdown(f"<p class='source'>Live source: {html.escape(str(a['source']))}</p>", unsafe_allow_html=True)
    else:
        st.error(f"Attractions unavailable: {a.get('error', 'unavailable')}")

with tabs[6]:
    b = state.get("budget", {})
    if b:
        total = b.get("estimated_total_inr", 0)
        cap = b.get("budget_cap_inr")
        status = "✅ Within your budget" if cap and b.get("within_budget") else "⚠️ Above budget" if cap else "Your trip estimate"
        st.markdown(f"<div class='budget-hero'><div class='eyebrow'>{status}</div><div class='total'>{money(total)}</div>"
                    f"<div>{b.get('nights', '—')} nights · {state.get('travelers', 1)} traveler(s)"
                    f"{' · budget cap ' + money(cap) if cap else ''}</div></div>", unsafe_allow_html=True)
        live, estimates = st.columns(2)
        with live:
            st.markdown("<div class='section-title'>Live prices</div>", unsafe_allow_html=True)
            for key, value in b.get("actual_retrieved", {}).items():
                label = key.replace("_inr", "").replace("_", " ").title()
                st.markdown(f"<div class='card'><span class='source'>{label}</span><br><b>{money(value)}</b></div>", unsafe_allow_html=True)
        with estimates:
            st.markdown("<div class='section-title'>Trip estimates</div>", unsafe_allow_html=True)
            for key, value in b.get("ai_estimated", {}).items():
                label = key.replace("_inr", "").replace("_", " ").title()
                st.markdown(f"<div class='card'><span class='source'>{label}</span><br><b>{money(value)}</b></div>", unsafe_allow_html=True)

st.divider()
st.markdown("<div class='section-title'>Refine your trip</div>", unsafe_allow_html=True)
st.caption('Try: "find a cheaper hotel but keep the flight" or "I don\'t want to spend more than ₹80,000"')

for role, msg in st.session_state.chat_history:
    with st.chat_message(role):
        st.markdown(msg)

entry, action = st.columns([5, 1])
with entry:
    user_msg = st.text_input("💬 What should we change?", placeholder="Cheaper hotel, direct flight, food near the stay…", label_visibility="collapsed")
with action:
    update_plan = st.button("✈️ Update", type="primary", use_container_width=True)

if update_plan and user_msg.strip():
    st.session_state.chat_history.append(("user", user_msg))
    with st.spinner("Trip Manager Agent is re-planning..."):
        updated = run_replan(state, user_msg)
        st.session_state.trip_state = updated
        reran = updated.get("rerun", [])
        reply = (f"Re-ran: {', '.join(reran)}. {summarize_changes(updated)}"
                 if reran else "No agents needed to re-run for that.")
        st.session_state.chat_history.append(("assistant", reply))
    st.rerun()
