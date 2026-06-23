import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", str(BASE_DIR / "uploads"))
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 16 * 1024 * 1024))

    DEFAULT_MODEL_API_URL = os.getenv(
        "MODEL_API_URL",
        "http://127.0.0.1:8000/v1/chat/completions",
    )
    DEFAULT_MODEL_NAME = os.getenv("MODEL_NAME", "local-model")
    MODEL_PRESETS = [
        {
            "label": "Ollama - Qwen2.5 7B",
            "api_url": "http://127.0.0.1:11434/v1/chat/completions",
            "model": "qwen2.5:7b",
        },
        {
            "label": "Ollama - Llama 3.1 8B",
            "api_url": "http://127.0.0.1:11434/v1/chat/completions",
            "model": "llama3.1:8b",
        },
        {
            "label": "vLLM - OpenAI Compatible",
            "api_url": "http://127.0.0.1:8000/v1/chat/completions",
            "model": "local-model",
        },
        {
            "label": "LM Studio - Local Server",
            "api_url": "http://127.0.0.1:1234/v1/chat/completions",
            "model": "local-model",
        },
    ]
    MODEL_API_TIMEOUT = float(os.getenv("MODEL_API_TIMEOUT", "60"))
    APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT = int(os.getenv("PORT", "5001"))
