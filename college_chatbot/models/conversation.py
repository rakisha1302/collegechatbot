"""Conversation and Message models for chat history persistence."""
import uuid
from datetime import datetime, timezone
from models import db


class Conversation(db.Model):
    __tablename__ = "conversations"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(64), unique=True, nullable=False,
                            default=lambda: str(uuid.uuid4()), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    title = db.Column(db.String(255), default="New Conversation")
    ai_provider = db.Column(db.String(20), default="claude")  # claude | openai
    user_role = db.Column(db.String(20), default="guest")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                            onupdate=lambda: datetime.now(timezone.utc))
    is_archived = db.Column(db.Boolean, default=False)

    messages = db.relationship("Message", backref="conversation", lazy="dynamic",
                                cascade="all, delete-orphan", order_by="Message.created_at")

    def to_dict(self, include_messages: bool = False) -> dict:
        data = {
            "id": self.id,
            "session_id": self.session_id,
            "title": self.title,
            "ai_provider": self.ai_provider,
            "user_role": self.user_role,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "message_count": self.messages.count(),
        }
        if include_messages:
            data["messages"] = [m.to_dict() for m in self.messages]
        return data


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversations.id"), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # user | assistant
    content = db.Column(db.Text, nullable=False)
    ai_provider = db.Column(db.String(20), nullable=True)
    latency_ms = db.Column(db.Integer, nullable=True)
    sources = db.Column(db.Text, nullable=True)  # JSON string of RAG source references
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    feedback = db.relationship("Feedback", backref="message", lazy="dynamic",
                                cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        import json
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "ai_provider": self.ai_provider,
            "latency_ms": self.latency_ms,
            "sources": json.loads(self.sources) if self.sources else [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
