"""Usage logging model for the admin analytics dashboard."""
from datetime import datetime, timezone
from models import db


class UsageLog(db.Model):
    __tablename__ = "usage_logs"

    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(50), nullable=False)  # chat_message, doc_upload, login, error
    ai_provider = db.Column(db.String(20), nullable=True)
    latency_ms = db.Column(db.Integer, nullable=True)
    success = db.Column(db.Boolean, default=True)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "event_type": self.event_type,
            "ai_provider": self.ai_provider,
            "latency_ms": self.latency_ms,
            "success": self.success,
            "details": self.details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
