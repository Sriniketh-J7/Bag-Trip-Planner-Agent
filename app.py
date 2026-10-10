import streamlit as st
from datetime import date, timedelta
from config import MISSING_KEYS
from agents import build_initial_graph, run_replan, recommendation_agent, TripState, summarize_changes

st.set_page_config(page_title="BagTrip Planner", page_icon="🎒", layout="wide")
st.title("🎒 BagTrip Planner")
st.caption("Multi-agent AI trip planning - Weather, Flights, Hotels, Food, Attractions & Budget")

if MISSING_KEYS:
    st.warning(f"Missing keys in .env: {', '.join(MISSING_KEYS)}. Affected agents will report "
               "unavailable data instead of crashing. See README.md.")

st.session_state.setdefault("trip_state", None)
st.session_state.setdefault("chat_history", [])

with st.sidebar:
    st.header("Plan a new trip")
    origin = st.text_input("Flying from (city or airport code)", value="HYD")
    destination = st.text_input("Destination (city or airport code)", value="Chennai")
    c1, c2 = st.columns(2)
    start_date = c1.date_input("Start date", value=date.today() + timedelta(days=2))
    end_date = c2.date_input("End date", value=date.today() + timedelta(days=5))
    travelers = st.number_input("Travelers", min_value=1, max_value=10, value=2)
    budget_cap = st.number_input("Budget cap (INR, optional)", min_value=0, value=0, step=5000)
    plan_btn = st.button("Research My Trip", type="primary", use_container_width=True)

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

with st.expander("Agent run log"):
    for line in state.get("log", []):
        st.text(line)

tabs = st.tabs(["🧠 Recommendation", "🌦️ Weather", "✈️ Flights", "🏨 Hotels", "🍜 Food", "📍 Attractions", "💰 Budget"])


def render_list(data: dict, key: str, line_fn, empty_label: str, limit: int = 10):
    if data.get("ok") and data.get(key):
        for item in data[key][:limit]:
            st.markdown(line_fn(item))
        st.caption(f"Source: {data['source']}")
    else:
        st.error(f"{empty_label}: {data.get('error', 'unavailable')}")


with tabs[0]:
    st.markdown(state.get("recommendation", "No recommendation generated."))
    if st.button("🔄 Regenerate full recommendation (uses 1 Gemini call)"):
        with st.spinner("Regenerating..."):
            st.session_state.trip_state = recommendation_agent(state)
        st.rerun()

with tabs[1]:
    w = state.get("weather", {})
    if w.get("ok"):
        for day, info in w["daily"].items():
            st.markdown(f"**{day}** ({info.get('day_name', '')}) - {info.get('condition', 'n/a')}, "
                        f"{info.get('low_c', '?')}-{info.get('high_c', '?')}°C, humidity {info.get('humidity', 'n/a')}")
    else:
        st.error(f"Weather unavailable: {w.get('error')}")

with tabs[2]:
    f = state.get("flights", {})
    sel = state.get("selected_flight")
    render_list(f, "flights", lambda fl: f"{'⭐ ' if fl == sel else ''}**{fl['airline']}** | "
                f"Rs.{fl['price_inr']:,} | {fl['departure_time']} to {fl['arrival_time']} | {fl['stops']} stop(s)",
                "Flights unavailable")


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

    render_list(
        h,
        "hotels",
        lambda ht: (
            f"{'⭐ ' if ht == sel_h else ''}**{ht['name']}** | "
            f"{format_hotel_price(ht.get('price_inr'))} | "
            f"rating {ht.get('rating', 'n/a')} "
            f"({ht.get('reviews_count', 0)} reviews)"
        ),
        "Hotels unavailable"
    )


with tabs[4]:
    r = state.get("restaurants", {})
    render_list(r, "places", lambda p: f"**{p['name']}** | {p.get('type', '')} | rating {p.get('rating', 'n/a')} "
                f"({p.get('reviews_count', 0)} reviews) | {p.get('price_level', '')}", "Restaurants unavailable")

with tabs[5]:
    a = state.get("attractions", {})
    render_list(a, "places", lambda p: f"**{p['name']}** _({p.get('bucket')})_ | rating {p.get('rating', 'n/a')}",
                "Attractions unavailable", limit=16)

with tabs[6]:
    b = state.get("budget", {})
    if b:
        st.subheader("Actual retrieved prices")
        for k, v in b["actual_retrieved"].items():
            label = k.replace("_inr", "").replace("_", " ").title()
            st.markdown(f"- {label}: {'Rs.' + format(v, ',.0f') if v else 'unavailable'}")
        st.subheader("AI-estimated costs")
        for k, v in b["ai_estimated"].items():
            st.markdown(f"- {k.replace('_inr', '').replace('_', ' ').title()}: Rs.{v:,.0f}")
        st.metric("Estimated Total", f"Rs.{b['estimated_total_inr']:,.0f}")
        if b.get("budget_cap_inr"):
            status = "✅ Within budget" if b["within_budget"] else "⚠️ Over budget"
            st.markdown(f"**{status}** (cap: Rs.{b['budget_cap_inr']:,})")

st.divider()
st.subheader("💬 Refine your trip")
st.caption('Try: "find a cheaper hotel but keep the flight" or "I don\'t want to spend more than ₹80,000"')
st.caption("Replies here are free (rule-based routing) - use the Regenerate button above only when you want "
           "the full narrative rewritten.")

for role, msg in st.session_state.chat_history:
    with st.chat_message(role):
        st.markdown(msg)

user_msg = st.chat_input("Add a constraint or ask for changes...")
if user_msg:
    st.session_state.chat_history.append(("user", user_msg))
    with st.spinner("Trip Manager Agent is re-planning..."):
        updated = run_replan(state, user_msg)
        st.session_state.trip_state = updated
        reran = updated.get("rerun", [])
        reply = (f"Re-ran: {', '.join(reran)}. {summarize_changes(updated)}"
                 if reran else "No agents needed to re-run for that.")
        st.session_state.chat_history.append(("assistant", reply))
    st.rerun()
