"""
Chat REST API: sending messages, retrieving/clearing history, exporting
conversations, submitting feedback, and regenerating responses.
"""
import io
import json
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, session, send_file
from flask_login import current_user

from models import db
from models.conversation import Conversation, Message
from models.feedback import Feedback
from models.analytics import UsageLog
from services.ai_service import generate_response, generate_title, generate_suggested_questions, AIProviderError
from utils.helpers import sanitize_text_input
from utils.logger import get_logger

logger = get_logger(__name__)
chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")


def _current_user_role() -> str:
    if current_user.is_authenticated:
        return current_user.role
    return session.get("guest_role", "guest")


def _current_user_id():
    return current_user.id if current_user.is_authenticated else None


def _get_or_create_conversation(session_id: str, provider: str) -> Conversation:
    convo = Conversation.query.filter_by(session_id=session_id).first()
    if convo:
        return convo
    convo = Conversation(
        session_id=session_id,
        user_id=_current_user_id(),
        ai_provider=provider,
        user_role=_current_user_role(),
    )
    db.session.add(convo)
    db.session.commit()
    return convo


@chat_bp.route("/send", methods=["POST"])
def send_message():
    """Send a user message and receive an AI-generated, RAG-grounded response."""
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    provider = (data.get("provider") or "claude").lower()

    if provider == "chatgpt":
        provider = "openai"

    message_text = sanitize_text_input(data.get("message", ""))

    if not session_id:
        return jsonify({"success": False, "error": "session_id is required."}), 400
    if not message_text:
        return jsonify({"success": False, "error": "Message cannot be empty."}), 400
    if provider not in ("claude", "openai", "groq"):
        return jsonify({"success": False, "error": "Invalid AI provider selected."}), 400

    convo = _get_or_create_conversation(session_id, provider)
    convo.ai_provider = provider  # allow switching mid-conversation

    history = [m.to_dict() for m in convo.messages]
    is_first_message = len(history) == 0

    user_msg = Message(conversation_id=convo.id, role="user", content=message_text)
    db.session.add(user_msg)
    db.session.commit()

    try:
        result = generate_response(
            provider=provider,
            question=message_text,
            history=[{"role": h["role"], "content": h["content"]} for h in history],
            user_role=convo.user_role,
            use_rag=True,
        )
    except AIProviderError as exc:
        db.session.add(UsageLog(event_type="chat_message", ai_provider=provider,
                                 success=False, details=str(exc)))
        db.session.commit()
        logger.error("Chat generation error: %s", exc)
        return jsonify({
            "success": False,
            "error": f"The AI provider could not process your request: {exc}",
        }), 502

    assistant_msg = Message(
        conversation_id=convo.id,
        role="assistant",
        content=result["answer"],
        ai_provider=result["provider"],
        latency_ms=result["latency_ms"],
        sources=json.dumps(result["sources"]),
    )
    db.session.add(assistant_msg)

    if is_first_message:
        convo.title = generate_title(provider, message_text)

    db.session.add(UsageLog(event_type="chat_message", ai_provider=provider,
                             latency_ms=result["latency_ms"], success=True))
    db.session.commit()

    suggested = generate_suggested_questions(provider, result["answer"], convo.user_role)

    return jsonify({
        "success": True,
        "message": assistant_msg.to_dict(),
        "conversation": convo.to_dict(),
        "suggested_questions": suggested,
    })


@chat_bp.route("/history/<session_id>", methods=["GET"])
def get_history(session_id):
    convo = Conversation.query.filter_by(session_id=session_id).first()
    if not convo:
        return jsonify({"success": True, "conversation": None, "messages": []})
    return jsonify({"success": True, "conversation": convo.to_dict(), "messages": [m.to_dict() for m in convo.messages]})


@chat_bp.route("/conversations", methods=["GET"])
def list_conversations():
    """List conversations for sidebar chat history (current user or guest)."""
    query = Conversation.query.filter_by(is_archived=False)
    if current_user.is_authenticated:
        query = query.filter_by(user_id=current_user.id)
    else:
        # Guests only see conversations created in their own browser session via session_ids stored client-side.
        session_ids = request.args.get("session_ids", "")
        ids = [s for s in session_ids.split(",") if s]
        if not ids:
            return jsonify({"success": True, "conversations": []})
        query = query.filter(Conversation.session_id.in_(ids))

    conversations = query.order_by(Conversation.updated_at.desc()).limit(50).all()
    return jsonify({"success": True, "conversations": [c.to_dict() for c in conversations]})


@chat_bp.route("/conversations/<session_id>", methods=["DELETE"])
def clear_conversation(session_id):
    convo = Conversation.query.filter_by(session_id=session_id).first()
    if not convo:
        return jsonify({"success": False, "error": "Conversation not found."}), 404
    db.session.delete(convo)
    db.session.commit()
    return jsonify({"success": True})


@chat_bp.route("/search", methods=["GET"])
def search_history():
    """Full-text-ish search over message content for the searchable chat history feature."""
    q = sanitize_text_input(request.args.get("q", ""), 200)
    if not q:
        return jsonify({"success": True, "results": []})

    query = Message.query.filter(Message.content.ilike(f"%{q}%"))
    matches = query.order_by(Message.created_at.desc()).limit(30).all()

    results = []
    for m in matches:
        convo = m.conversation
        if current_user.is_authenticated and convo.user_id != current_user.id:
            continue
        results.append({
            "conversation_session_id": convo.session_id,
            "conversation_title": convo.title,
            "message_snippet": m.content[:150],
            "role": m.role,
            "created_at": m.created_at.isoformat(),
        })
    return jsonify({"success": True, "results": results})


@chat_bp.route("/regenerate", methods=["POST"])
def regenerate_response():
    """Regenerate the last assistant response, optionally with a different provider."""
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    provider = (data.get("provider") or "claude").lower()
    if provider not in ("claude", "openai", "groq"):
        return jsonify({
          "success": False,
          "error": "Invalid AI provider selected."
    }), 400

    convo = Conversation.query.filter_by(session_id=session_id).first()
    if not convo:
        return jsonify({"success": False, "error": "Conversation not found."}), 404

    messages = list(convo.messages)
    if not messages or messages[-1].role != "assistant":
        return jsonify({"success": False, "error": "No response available to regenerate."}), 400

    last_assistant = messages[-1]
    prior_history = [m.to_dict() for m in messages[:-2]]  # exclude last user+assistant pair
    last_user_msg = messages[-2].content if len(messages) >= 2 else ""

    try:
        result = generate_response(
            provider=provider,
            question=last_user_msg,
            history=[{"role": h["role"], "content": h["content"]} for h in prior_history],
            user_role=convo.user_role,
            use_rag=True,
        )
    except AIProviderError as exc:
        return jsonify({"success": False, "error": str(exc)}), 502

    last_assistant.content = result["answer"]
    last_assistant.ai_provider = result["provider"]
    last_assistant.latency_ms = result["latency_ms"]
    last_assistant.sources = json.dumps(result["sources"])
    convo.ai_provider = provider
    db.session.commit()

    return jsonify({"success": True, "message": last_assistant.to_dict()})


@chat_bp.route("/feedback", methods=["POST"])
def submit_feedback():
    data = request.get_json(silent=True) or {}
    message_id = data.get("message_id")
    rating = data.get("rating")
    comment = sanitize_text_input(data.get("comment", ""), 1000)

    if rating not in ("up", "down"):
        return jsonify({"success": False, "error": "Rating must be 'up' or 'down'."}), 400
    if not Message.query.get(message_id):
        return jsonify({"success": False, "error": "Message not found."}), 404

    fb = Feedback(message_id=message_id, rating=rating, comment=comment or None)
    db.session.add(fb)
    db.session.commit()
    return jsonify({"success": True, "feedback": fb.to_dict()})


@chat_bp.route("/export/<session_id>", methods=["GET"])
def export_conversation(session_id):
    """Export a conversation transcript as TXT or PDF."""
    fmt = request.args.get("format", "txt").lower()
    convo = Conversation.query.filter_by(session_id=session_id).first()
    if not convo:
        return jsonify({"success": False, "error": "Conversation not found."}), 404

    messages = list(convo.messages)
    lines = [f"Conversation: {convo.title}", f"Exported: {datetime.now(timezone.utc).isoformat()}", "-" * 50, ""]
    for m in messages:
        speaker = "You" if m.role == "user" else f"CampusAI ({m.ai_provider or convo.ai_provider})"
        lines.append(f"{speaker}: {m.content}\n")

    if fmt == "pdf":
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import inch

        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=letter)
        width, height = letter
        y = height - inch
        c.setFont("Helvetica", 10)
        for line in "\n".join(lines).split("\n"):
            for wrapped in [line[i:i + 100] for i in range(0, max(len(line), 1), 100)]:
                if y < inch:
                    c.showPage()
                    c.setFont("Helvetica", 10)
                    y = height - inch
                c.drawString(inch, y, wrapped)
                y -= 14
        c.save()
        buf.seek(0)
        return send_file(buf, as_attachment=True, download_name=f"{convo.title}.pdf",
                          mimetype="application/pdf")

    buf = io.BytesIO("\n".join(lines).encode("utf-8"))
    return send_file(buf, as_attachment=True, download_name=f"{convo.title}.txt",
                      mimetype="text/plain")
