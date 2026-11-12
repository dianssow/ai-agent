import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "postgres"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
}



if not DB_CONFIG["password"]:
    raise ValueError("DB_PASSWORD is missing. Please set it in your .env file.")

LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:3b")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
DISTANCE_THRESHOLD = float(os.getenv("DISTANCE_THRESHOLD", "0.41"))
