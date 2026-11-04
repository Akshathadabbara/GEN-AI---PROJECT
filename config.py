import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Database configuration
db_env = os.getenv("DATABASE_PATH")
DATABASE = os.path.abspath(db_env) if db_env else os.path.join(BASE_DIR, "lost_found.db")

# Matching thresholds (0.0 to 1.0)
SIMILARITY_THRESHOLD = float(os.getenv("MATCH_THRESHOLD", "0.28"))
STRONG_MATCH_THRESHOLD = float(os.getenv("STRONG_MATCH_THRESHOLD", "0.65"))
POSSIBLE_MATCH_THRESHOLD = float(os.getenv("POSSIBLE_MATCH_THRESHOLD", "0.40"))

# Vector Store (ChromaDB) Configuration
chroma_env = os.getenv("CHROMA_PATH")
CHROMA_PATH = os.path.abspath(chroma_env) if chroma_env else os.path.join(BASE_DIR, "chroma_data")
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "items_rag")

# LLM Providers Configuration (Gemini, OpenRouter, and OpenAI)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash").strip()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.2-3b-instruct:free").strip()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
OPENAI_TIMEOUT = int(os.getenv("OPENAI_TIMEOUT", "8"))

# Active LLM Provider: "gemini", "openrouter", "openai", "auto", or "none"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "auto").strip().lower()
LLM_MODEL = os.getenv("LLM_MODEL", "").strip()
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "8"))

# Admin / Security
ADMIN_KEY = os.getenv("ADMIN_KEY", "campus_admin_secret_2026")
DEBUG = os.getenv("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")
PORT = int(os.getenv("PORT", 5000))
