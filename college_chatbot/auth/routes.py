"""Authentication routes: admin/faculty login, logout, guest access, role selection."""
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, flash
from flask_login import login_user, logout_user, login_required, current_user

from models import db
from models.user import User
from models.analytics import UsageLog
from utils.helpers import sanitize_text_input
from utils.logger import get_logger

logger = get_logger(__name__)
auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

ALLOWED_ROLES = {"student", "faculty", "parent", "guest"}


@auth_bp.route("/login", methods=["GET"])
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))
    return render_template("login.html")


@auth_bp.route("/login", methods=["POST"])
def login():
    """Authenticate an admin/faculty user with hashed password verification."""
    data = request.get_json(silent=True) or request.form
    username = sanitize_text_input(data.get("username", ""), 80)
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"success": False, "error": "Username and password are required."}), 400

    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        UsageLog.query  # noop to keep import used
        db.session.add(UsageLog(event_type="login", success=False,
                                 details=f"Failed login attempt for '{username}'"))
        db.session.commit()
        return jsonify({"success": False, "error": "Invalid username or password."}), 401

    if not user.is_active_flag:
        return jsonify({"success": False, "error": "This account has been deactivated."}), 403

    from datetime import datetime, timezone
    login_user(user)
    user.last_login = datetime.now(timezone.utc)
    db.session.add(UsageLog(event_type="login", success=True,
                             details=f"User '{username}' logged in"))
    db.session.commit()

    return jsonify({"success": True, "user": user.to_dict(),
                     "redirect": url_for("admin.dashboard") if user.is_admin() else url_for("main.index")})


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.index"))


@auth_bp.route("/guest-session", methods=["POST"])
def guest_session():
    """Establish a lightweight guest session with a self-declared role (no password)."""
    data = request.get_json(silent=True) or {}
    role = data.get("role", "guest")
    if role not in ALLOWED_ROLES:
        role = "guest"

    if "guest_id" not in session:
        session["guest_id"] = str(uuid.uuid4())
    session["guest_role"] = role

    return jsonify({"success": True, "guest_id": session["guest_id"], "role": role})


@auth_bp.route("/whoami")
def whoami():
    """Return current identity info (authenticated admin/faculty or guest role)."""
    if current_user.is_authenticated:
        return jsonify({"authenticated": True, **current_user.to_dict()})
    return jsonify({
        "authenticated": False,
        "guest_id": session.get("guest_id"),
        "role": session.get("guest_role", "guest"),
    })
