import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.getenv("DATABASE_PATH", os.path.join(BASE_DIR, "lost_found.db"))

# Matching thresholds
SIMILARITY_THRESHOLD = float(os.getenv("MATCH_THRESHOLD", "0.28"))
STRONG_MATCH_THRESHOLD = float(os.getenv("STRONG_MATCH_THRESHOLD", "0.65"))
POSSIBLE_MATCH_THRESHOLD = float(os.getenv("POSSIBLE_MATCH_THRESHOLD", "0.40"))

# Vector Store (ChromaDB) Configuration
CHROMA_PATH = os.getenv("CHROMA_PATH", os.path.join(BASE_DIR, "chroma_data"))
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "items_rag")

# LLM Configuration (OpenAI primary, Gemini optional)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_TIMEOUT = int(os.getenv("OPENAI_TIMEOUT", "10"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")  # "openai", "gemini", or "none"
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "10"))

# Admin / Security
ADMIN_KEY = os.getenv("ADMIN_KEY", "campus_admin_secret_2026")
DEBUG = os.getenv("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")
