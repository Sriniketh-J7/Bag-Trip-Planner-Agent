# 🎒 BagTrip Planner

AI multi-agent trip planner built for the **SerpApi India Hackathon 2026**.

Weather, Flights, Hotels, Food, Attractions, and Budget agents are coordinated by a LangGraph Trip Manager, with Gemini powering natural-language replanning and the final recommendation.

---

## 🚀 Installation & Setup

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

### 2. Clone the Repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd bagtrip
```

---

### 3. Create a Virtual Environment

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

### 4. Install Dependencies

Upgrade pip:

```bash
python -m pip install --upgrade pip
```

Install the project's dependencies:

```bash
pip install -r requirements.txt
```

---

### 5. Configure API Keys

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

**Never commit `.env` to GitHub.**

Make sure `.gitignore` contains:

```gitignore
.env
venv/
__pycache__/
*.pyc
.streamlit/secrets.toml
```

---

### 6. Run the Application

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

## What this V1 actually does

- Takes destination, dates, travelers as input
- Runs 6 specialist agents in sequence (LangGraph pipeline): Weather →
  Flight → Hotel → Restaurant → Attractions → Budget → Recommendation
- Every agent calls a real API (SerpApi Google Flights / Google Hotels /
  Google Maps, and Google Search for weather) and clearly labels its data source
- Every agent **fails gracefully**: if a key is missing or an API call
  errors, that section reports "unavailable" instead of crashing the app
  or inventing data
- Conversational replanning: type a follow-up like *"find a cheaper hotel
  but keep the flight"* and Gemini (acting as a router) decides which
  agents to re-run, then only those re-run
- Budget tab clearly separates **actual retrieved prices** (flight, hotel)
  from **AI-estimated costs** (food, local transport, activities)

## What's intentionally out of V1 (and why)

The original brief mentions Airbnb, TripAdvisor, and Yelp APIs. These
don't have accessible free/legitimate public APIs for a project like this
(Airbnb's official API is partner-only; TripAdvisor's API requires a
paid/approved partnership; Yelp's API has very limited non-US coverage).
Scraping them would violate their terms and the hackathon's own rule
against bypassing site protections - so V1 covers accommodation via
**Google Hotels** and food/attractions/reviews via **Google Maps / Google
Local**, both through SerpApi. The code is structured (see
`serpapi_tools.py`) so a legitimate Airbnb/TripAdvisor partner API can be
dropped in as another function later without touching the agent graph.

## Weather

Weather runs through SerpApi's Google Search engine using the weather answer
box Google shows for searches such as:

```text
weather in Hyderabad
```

There is no separate weather API key in V1.

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
├── .env.example        # Environment variable template
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
Chat input
  │
  ▼
Gemini Router
  │
  ├── Decide which agents need new data
  │
  ▼
Only required agents re-run
  │
  ▼
Budget + Recommendation regenerate
```

## Known limitations / honest notes for judges

- Flight/hotel "best pick" selection is a simple heuristic (cheapest
  flight, highest-rated hotel) rather than a separate LLM reasoning step -
  kept deterministic for reliability during a live demo.
- Review deep-dives (`search_place_reviews` in `serpapi_tools.py`) are
  wired up but not called from the main flow by default, to keep SerpApi
  credit usage low during testing. Easy to enable per-place.
- No database (as specified) - trip state lives in Streamlit session state
  for the session only.
- API availability and free-tier quotas depend on the provider.
- Flight and hotel prices are live search results and can change between
  searches.
- Some destinations may not have complete or matching flight/hotel data.
- The application does not invent missing API data; unavailable sections
  are explicitly marked as unavailable.

## 🛡️ Security

Never expose API keys in:

- GitHub commits
- Screenshots
- Streamlit error messages
- README files
- Public demo videos

If an API key is accidentally exposed, **revoke/rotate it immediately** and
replace it with a new key in `.env`.

## 🌐 Streamlit Deployment

For Streamlit Community Cloud:

1. Push the project to GitHub.
2. Create a new Streamlit app.
3. Select the repository and `app.py`.
4. Use **Python 3.12** as the runtime if available.
5. Add your secrets in Streamlit's Secrets settings instead of committing
   `.env`.
6. Deploy the application.

For deployment, do **not** upload:

```text
venv/
.env
__pycache__/
*.pyc
```

The platform installs packages from:

```text
requirements.txt
```

## 🔄 Recreating the Project Environment

If the virtual environment is deleted, nothing important is lost.

Simply recreate it:

```bash
py -3.12 -m venv venv
```

Activate it:

```powershell
.\venv\Scripts\Activate.ps1
```

Then:

```bash
pip install -r requirements.txt
```

Run:

```bash
streamlit run app.py
```

## 🏆 Hackathon Focus

**BagTrip Planner** is designed around a practical multi-agent workflow:

- Real-world travel data
- Specialized AI agents
- LangGraph orchestration
- Gemini-powered natural-language replanning
- Graceful API failure handling
- Transparent distinction between retrieved and estimated costs
- Deterministic recommendations for reliable demos
- No fabricated travel information
