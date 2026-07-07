"""Admin dashboard: page rendering plus analytics/monitoring REST endpoints."""
from datetime import datetime, timedelta, timezone
from collections import Counter

from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy import func

from models import db
from models.conversation import Conversation, Message
from models.document import Document
from models.feedback import Feedback
from models.analytics import UsageLog
from services.langsmith_config import fetch_recent_runs
from config import config

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _require_admin():
    return current_user.is_authenticated and current_user.is_admin()


@admin_bp.route("/dashboard")
@login_required
def dashboard():
    if not current_user.is_admin():
        return render_template("index.html", college_name=config.COLLEGE_NAME)
    return render_template("admin.html", college_name=config.COLLEGE_NAME, user=current_user)


@admin_bp.route("/api/overview", methods=["GET"])
@login_required
def overview():
    if not _require_admin():
        return jsonify({"success": False, "error": "Administrator privileges required."}), 403

    total_conversations = Conversation.query.count()
    total_messages = Message.query.count()
    total_documents = Document.query.filter_by(status="indexed").count()

    provider_counts = dict(
        db.session.query(Message.ai_provider, func.count(Message.id))
        .filter(Message.ai_provider.isnot(None))
        .group_by(Message.ai_provider).all()
    )

    avg_latency = db.session.query(func.avg(Message.latency_ms)).filter(
        Message.latency_ms.isnot(None)
    ).scalar()

    feedback_counts = dict(
        db.session.query(Feedback.rating, func.count(Feedback.id)).group_by(Feedback.rating).all()
    )

    since = datetime.now(timezone.utc) - timedelta(days=7)
    daily_counts = (
        db.session.query(func.date(Message.created_at), func.count(Message.id))
        .filter(Message.created_at >= since, Message.role == "user")
        .group_by(func.date(Message.created_at))
        .all()
    )

    return jsonify({
        "success": True,
        "total_conversations": total_conversations,
        "total_messages": total_messages,
        "total_documents": total_documents,
        "provider_usage": provider_counts,
        "avg_latency_ms": round(avg_latency, 1) if avg_latency else None,
        "feedback": {"up": feedback_counts.get("up", 0), "down": feedback_counts.get("down", 0)},
        "daily_message_counts": [{"date": str(d), "count": c} for d, c in daily_counts],
    })


@admin_bp.route("/api/faq-analysis", methods=["GET"])
@login_required
def faq_analysis():
    """Surface frequently asked questions by clustering common keywords from user messages."""
    if not _require_admin():
        return jsonify({"success": False, "error": "Administrator privileges required."}), 403

    user_messages = db.session.query(Message.content).filter(Message.role == "user").limit(2000).all()
    stopwords = {"the", "a", "an", "is", "are", "what", "how", "do", "does", "i", "my", "to",
                 "of", "for", "in", "on", "can", "you", "please", "and", "it", "me", "about"}

    counter = Counter()
    for (content,) in user_messages:
        words = [w.strip(".,?!").lower() for w in content.split()]
        keywords = [w for w in words if w not in stopwords and len(w) > 3]
        counter.update(keywords)

    top_keywords = counter.most_common(15)
    return jsonify({"success": True, "top_keywords": [{"term": t, "count": c} for t, c in top_keywords]})


@admin_bp.route("/api/chat-review", methods=["GET"])
@login_required
def chat_review():
    """Paginated view of recent conversations for admin review/monitoring."""
    if not _require_admin():
        return jsonify({"success": False, "error": "Administrator privileges required."}), 403

    page = request.args.get("page", 1, type=int)
    pagination = Conversation.query.order_by(Conversation.updated_at.desc()) \
        .paginate(page=page, per_page=20, error_out=False)

    return jsonify({
        "success": True,
        "conversations": [c.to_dict() for c in pagination.items],
        "page": page,
        "total_pages": pagination.pages,
        "total": pagination.total,
    })


@admin_bp.route("/api/langsmith-traces", methods=["GET"])
@login_required
def langsmith_traces():
    """Pull recent LangSmith run traces for debugging and performance comparison."""
    if not _require_admin():
        return jsonify({"success": False, "error": "Administrator privileges required."}), 403

    runs = fetch_recent_runs(limit=50)
    return jsonify({"success": True, "traces": runs, "configured": bool(config.LANGCHAIN_API_KEY)})


@admin_bp.route("/api/logs", methods=["GET"])
@login_required
def usage_logs():
    if not _require_admin():
        return jsonify({"success": False, "error": "Administrator privileges required."}), 403

    logs = UsageLog.query.order_by(UsageLog.created_at.desc()).limit(200).all()
    return jsonify({"success": True, "logs": [log.to_dict() for log in logs]})
