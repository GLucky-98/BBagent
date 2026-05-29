"""
Environment loader for tests.
Loads variables from .env file in project root.
"""
from dotenv import load_dotenv
from pathlib import Path
import os

def get_env():
    load_dotenv(Path(__file__).parent.parent / ".env")
    return {
        "model": os.getenv("MODEL"),
        "api_key": os.getenv("API_KEY"),
        "base_url": os.getenv("ANTHROPIC_BASE_URL"),
        "openai_base_url": os.getenv("OPENAI_BASE_URL"),
    }