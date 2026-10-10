# 🎒 BagTrip

## Intelligent trip research and planning

BagTrip is a travel-planning workspace that turns a route, travel dates, and budget into a clear, live-data trip board. It researches flights, stays, local food, activities, weather, and total cost in one workflow—then lets travelers refine the result in natural language.

The product is designed to be transparent: live supplier data is labelled, estimated costs are separate from retrieved prices, and unavailable information is shown as unavailable rather than invented.

## Product capabilities

- Live flight, hotel, restaurant, attraction, and weather research
- Dark travel dashboard with visual cards, source labels, and SerpApi-supplied imagery when available
- Lowest-price-first flight and hotel selection, plus affordable local-food discovery
- Clear budget view separating live prices from trip estimates
- Natural-language refinements such as “find a cheaper hotel” or “keep the flight under ₹20,000 total”
- Graceful handling for missing API keys, unavailable routes, and provider errors

---

## Technology stack

| Layer | Technology | Role |
|---|---|---|
| Product UI | Streamlit | Responsive trip workspace and refinement controls |
| Workflow orchestration | LangGraph | Runs specialist agents in a predictable sequence |
| AI | Google Gemini(gemini-3.8-flash) via LangChain | Writes the itinerary narrative and interprets ambiguous refinements |
| Live travel data | SerpApi | Google Flights, Google Hotels, Google Maps, and Google Search results |
| Configuration | python-dotenv | Loads local secrets from `.env` |

## Quick start

### 1. Prerequisites

Make sure you have:

- **Python 3.12** installed
- **Git** installed
- A **SerpApi API key**
- A **Google Gemini API key**

> **Recommended Python version: 3.12**
>
> This project uses a LangChain/LangGraph dependency stack tested with Python 3.12.

Check your Python version:

```bash
python --version
```

You should see:

```text
Python 3.12.x
```

---

### 2. Get the code

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd bagtrip
```

---

### 3. Create a virtual environment

#### Windows PowerShell

```powershell
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then activate again:

```powershell
.\venv\Scripts\Activate.ps1
```

After activation, verify:

```bash
python --version
```

---

### 4. Install dependencies

Upgrade pip:

```bash
python -m pip install --upgrade pip
```

Install the project's dependencies:

```bash
pip install -r requirements.txt
```

---

### 5. Configure API keys

Create a `.env` file in the project root.

```text
bagtrip/
├── app.py
├── agents.py
├── serpapi_tools.py
├── weather_tool.py
├── config.py
├── requirements.txt
├── .env
└── README.md
```

Add:

```env
SERPAPI_KEY=your_serpapi_api_key
GOOGLE_API_KEY=your_gemini_api_key
```

### Getting the API Keys

| Key | Where | Usage |
|---|---|---|
| `SERPAPI_KEY` | https://serpapi.com/users/sign_up | Flights, Hotels, Maps, Weather |
| `GOOGLE_API_KEY` | https://aistudio.google.com/app/apikey | Gemini AI |


Make sure `.gitignore` contains:

```gitignore
.env
venv/
__pycache__/
*.pyc
.streamlit/secrets.toml
```

## Data providers and SerpApi usage

BagTrip uses SerpApi as the live-travel-data gateway. A single `SERPAPI_KEY` enables the following Google engines:

| SerpApi engine | Used for | What BagTrip shows |
|---|---|---|
| `google_flights` | Flight search | Airlines, departure/arrival times, stops, duration, and live price |
| `google_hotels` | Accommodation search | Nightly price, rating, address, amenities, and property imagery when returned |
| `google_maps` | Local discovery | Affordable restaurants, attractions, ratings, addresses, category, and imagery when returned |
| `google` | Weather lookup | Google weather answer-box forecast for the destination |

The UI never manufactures supplier data. Provider results may be incomplete, change between requests, or be unavailable for a route or date.

## How to use BagTrip

1. Enter your origin, destination, travel dates, number of travelers, and an optional total budget.
2. Select **Research my trip** to build the first itinerary from live data.
3. Review each tab: Overview, Weather, Flights, Stays, Food, Things to do, and Budget.
4. Use **Refine your trip** for targeted changes. For example: `find a hotel and flight below 20000 total`, `show direct flights`, or `keep the flight but find cheaper food`.
5. Review the Budget tab after every refinement. If live inventory cannot meet a cap, BagTrip presents the lowest available options and makes that clear.

---

### 6. Run BagTrip

With the virtual environment activated:

```bash
streamlit run app.py
```

The application will normally open at:

```text
http://localhost:8501
```

If it does not open automatically, copy the URL into your browser.

---

## 📦 Requirements

The project intentionally keeps `requirements.txt` limited to the direct dependencies needed by the application.

```text
streamlit==1.38.0
langchain==0.3.7
langchain-google-genai==2.0.4
langgraph==0.2.45
requests==2.32.3
python-dotenv==1.0.1
pydantic==2.9.2
```

Do **not** upload your `venv/` folder or a huge `pip freeze` file to the repository.

If you need to recreate the environment:

```bash
python -m venv venv
pip install -r requirements.txt
```

---

## Specialist agents

BagTrip uses a LangGraph workflow rather than a single all-purpose prompt. Each specialist owns one clear responsibility:

| Agent | Role | Output behavior |
|---|---|---|
| Weather | Retrieves a destination forecast | Maps available forecast days onto the trip window; never guesses beyond provider data |
| Flight | Searches route and dates | Selects the lowest priced returned flight and keeps all options visible |
| Hotel | Searches accommodation | Orders live stays by nightly price and selects the lowest priced returned stay |
| Restaurant | Discovers local food | Searches specifically for affordable local restaurants and prioritizes known lower price tiers |
| Attractions | Finds things to do | Combines well-known attractions with lesser-known destination results |
| Budget | Calculates trip cost | Combines retrieved flight/stay prices with explicit estimates for food, local transport, and activities |
| Recommendation | Creates the overview | Uses Gemini to turn the researched state into a concise itinerary narrative |
| Constraint router | Interprets refinements | Uses free rule-based routing first, then Gemini only for ambiguous requests; re-runs only the relevant agents |

For a total-budget request, BagTrip refreshes flights, stays, food, and the budget calculation. Budget always runs after the new live results have been selected.

## Product boundaries

BagTrip currently uses Google Hotels for accommodation and Google Maps for restaurants and attractions through SerpApi. Partner-only or restricted providers are intentionally not scraped. The provider layer is isolated in `serpapi_tools.py`, so an approved partner integration can be added without changing the agent workflow.

## Weather

Weather runs through SerpApi's Google Search engine using the weather answer
box Google shows for searches such as:

```text
weather in Hyderabad
```

There is no separate weather API key; weather uses the configured SerpApi key.

**Important:** Google's weather answer box only forecasts approximately
10 days from today and does not provide arbitrary historical/future weather
data. The application maps available forecast days onto the trip dates by
position. If the trip falls outside the available forecast window, the
Weather tab reports that honestly instead of guessing.

## Project structure

```text
bagtrip/
├── app.py              # Streamlit UI
├── agents.py           # LangGraph orchestration + all agent node functions
├── serpapi_tools.py    # Google Flights / Hotels / Maps / Search wrappers
├── weather_tool.py     # Weather wrapper
├── config.py           # Environment variable loading
├── requirements.txt    # Python dependencies
├── .gitignore
└── README.md
```

## Architecture

```text
User
  │
  ▼
Sidebar form
  │
  ▼
LangGraph Trip Manager
  │
  ├── Weather Agent
  ├── Flight Agent
  ├── Hotel Agent
  ├── Restaurant Agent
  ├── Attractions Agent
  ├── Budget Agent
  │
  ▼
Recommendation Agent
  │
  ▼
Streamlit UI
```

### Conversational Replanning

```text
User
  │
  ▼
Refinement input
  │
  ▼
Rule-based router (Gemini fallback)
  │
  ├── Decide which agents need new data
  │
  ▼
Relevant live-data agents re-run
  │
  ▼
Budget recalculates from the refreshed selections
```