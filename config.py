import os
from dotenv import load_dotenv

load_dotenv()

SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = "gemini-1.5-flash"

MISSING_KEYS = [n for n, v in [("SERPAPI_KEY", SERPAPI_KEY), ("GOOGLE_API_KEY", GOOGLE_API_KEY)] if not v]
