"""Shared helper/utility functions used across the application."""
import os
import re
import uuid
from werkzeug.utils import secure_filename
from config import config


def allowed_file(filename: str) -> bool:
    """Check whether the uploaded file has an allowed extension."""
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in config.ALLOWED_EXTENSIONS
    )


def make_safe_filename(original_filename: str) -> str:
    """Generate a collision-free, filesystem-safe filename while preserving extension."""
    safe = secure_filename(original_filename)
    ext = safe.rsplit(".", 1)[1].lower() if "." in safe else "txt"
    unique_id = uuid.uuid4().hex[:12]
    return f"{unique_id}_{safe}" if safe else f"{unique_id}.{ext}"


def sanitize_text_input(text: str, max_length: int = 4000) -> str:
    """Basic sanitation of user-provided text: strip control chars, cap length."""
    if not text:
        return ""
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    return cleaned.strip()[:max_length]


def format_bytes(num_bytes: int) -> str:
    """Human-readable file size."""
    for unit in ["B", "KB", "MB", "GB"]:
        if num_bytes < 1024:
            return f"{num_bytes:.1f}{unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f}TB"


def paginate_query(query, page: int, per_page: int = 20):
    """Return a paginated SQLAlchemy result."""
    return query.paginate(page=page, per_page=per_page, error_out=False)
