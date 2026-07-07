"""
Central configuration for the College Chatbot application.
Loads all settings from environment variables (.env file).
"""
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Base configuration shared across environments."""

    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    DEBUG = os.getenv("DEBUG", "True").lower() == "true"

    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'chatbot.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # AI Providers
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

    # LangSmith
    LANGCHAIN_TRACING_V2 = os.getenv("LANGCHAIN_TRACING_V2", "false")
    LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY", "")
    LANGCHAIN_PROJECT = os.getenv("LANGCHAIN_PROJECT", "college-chatbot")
    LANGCHAIN_ENDPOINT = os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")

    # Vector store / RAG
    CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", os.path.join(BASE_DIR, "chroma_db"))
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))
    RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "4"))

    # Uploads
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "data", "uploaded_docs")
    ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_SIZE_MB", "20")) * 1024 * 1024

    # Default admin
    DEFAULT_ADMIN_USERNAME = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
    DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "ChangeMe123!")
    DEFAULT_ADMIN_EMAIL = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@college.edu")

    # Branding
    COLLEGE_NAME = os.getenv("COLLEGE_NAME", "Springfield Institute of Technology")

    @staticmethod
    def init_app(app):
        # Configure LangSmith tracing via environment (LangChain reads these directly)
        os.environ["LANGCHAIN_TRACING_V2"] = Config.LANGCHAIN_TRACING_V2
        os.environ["LANGCHAIN_API_KEY"] = Config.LANGCHAIN_API_KEY
        os.environ["LANGCHAIN_PROJECT"] = Config.LANGCHAIN_PROJECT
        os.environ["LANGCHAIN_ENDPOINT"] = Config.LANGCHAIN_ENDPOINT
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.CHROMA_PERSIST_DIR, exist_ok=True)
        os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)
        os.makedirs(os.path.join(BASE_DIR, "logs"), exist_ok=True)


config = Config()
