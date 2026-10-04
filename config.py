"""Shared configuration for Lab 18."""

import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# --- API Keys ---
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").strip().lower()
if LLM_PROVIDER not in ("openai", "openrouter"):
    raise ValueError("LLM_PROVIDER must be openai or openrouter")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
# Compatibility name used by existing modules; always selects the provider's key.
OPENAI_API_KEY = (OPENROUTER_API_KEY if LLM_PROVIDER == "openrouter"
                  else os.getenv("OPENAI_API_KEY", "").strip())
LLM_BASE_URL = (os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
                if LLM_PROVIDER == "openrouter"
                else os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-4o-mini" if LLM_PROVIDER == "openrouter" else "gpt-4o-mini")
RAGAS_MODEL = os.getenv("RAGAS_MODEL", LLM_MODEL)
RAGAS_EMBEDDING_MODEL = os.getenv("RAGAS_EMBEDDING_MODEL",
    "openai/text-embedding-3-small" if LLM_PROVIDER == "openrouter" else "text-embedding-3-small")

# --- Qdrant ---
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
COLLECTION_NAME = "lab18_production"
NAIVE_COLLECTION = "lab18_naive"

# --- Embedding ---
EMBEDDING_MODEL = "BAAI/bge-m3"
EMBEDDING_DIM = 1024

# --- Chunking ---
HIERARCHICAL_PARENT_SIZE = 2048
HIERARCHICAL_CHILD_SIZE = 256
SEMANTIC_THRESHOLD = 0.85

# --- Search ---
BM25_TOP_K = 20
DENSE_TOP_K = 20
HYBRID_TOP_K = 20
RERANK_TOP_K = 3

# --- Paths ---
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
TEST_SET_PATH = os.path.join(os.path.dirname(__file__), "test_set.json")
