"""Runtime configuration, loaded once from .env at the repository root."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

HINDSIGHT_BASE_URL = os.environ.get("HINDSIGHT_BASE_URL", "https://api.hindsight.vectorize.io")
HINDSIGHT_API_KEY = os.environ.get("HINDSIGHT_API_KEY", "")
BANK_ID = os.environ.get("HINDSIGHT_BANK_ID", "why-org-decisions")

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1")
LLM_API_KEY = os.environ.get("LLM_API_KEY") or os.environ.get("GROQ_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "openai/gpt-oss-120b")
LLM_RPM = float(os.environ.get("LLM_RPM", "0"))  # client-side pacing (requests/minute); 0 = off

DATA = ROOT / "data"
CORPUS = DATA / "corpus"
HOLDBACK = DATA / "holdback"
EXTRACTED = DATA / "extracted"
DB_PATH = DATA / "store.db"

# Retrieval parameters (see methodology §6)
K0 = 1                # reciprocal-rank offset
K2 = 3                # evidence items per assumption
AMBIGUITY_MARGIN = 0.2
TRIPWIRE_M = 5
