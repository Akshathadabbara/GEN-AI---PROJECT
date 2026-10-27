import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.getenv("DATABASE_PATH", os.path.join(BASE_DIR, "lost_found.db"))

# Matching thresholds
SIMILARITY_THRESHOLD = float(os.getenv("MATCH_THRESHOLD", "0.28"))
STRONG_MATCH_THRESHOLD = float(os.getenv("STRONG_MATCH_THRESHOLD", "0.65"))
POSSIBLE_MATCH_THRESHOLD = float(os.getenv("POSSIBLE_MATCH_THRESHOLD", "0.40"))

# LLM Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")  # or "none" / "mock"
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-1.5-flash")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "8"))

# Admin / Security
ADMIN_KEY = os.getenv("ADMIN_KEY", "campus_admin_secret_2026")
DEBUG = os.getenv("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")
