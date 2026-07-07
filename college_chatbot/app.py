"""
College/University AI Chatbot - Application Entry Point.

Run with:  python app.py
Or:        flask run
Or (prod): gunicorn -w 4 -b 0.0.0.0:5000 app:app
"""
import os
from flask import Flask
from flask_cors import CORS
from flask_bcrypt import Bcrypt

from config import config
from models import db

bcrypt = Bcrypt()


def create_app():
    app = Flask(__name__)
    app.config.from_object(config)
    config.init_app(app)

    # Extensions
    db.init_app(app)
    bcrypt.init_app(app)
    CORS(app, supports_credentials=True)

    from auth import login_manager
    login_manager.init_app(app)

    # Blueprints
    from auth import auth_bp
    from api import chat_bp, document_bp, admin_bp, main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(document_bp)
    app.register_blueprint(admin_bp)

    register_error_handlers(app)

    with app.app_context():
        db.create_all()
        _seed_default_admin()

    return app


def register_error_handlers(app):
    from flask import jsonify

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"success": False, "error": "Resource not found."}), 404

    @app.errorhandler(413)
    def too_large(e):
        return jsonify({"success": False, "error": "Uploaded file exceeds the maximum allowed size."}), 413

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"success": False, "error": "An internal server error occurred. Please try again."}), 500


def _seed_default_admin():
    """Create a default admin account on first run if none exists."""
    from models.user import User

    if User.query.filter_by(role="admin").first():
        return

    admin = User(
        username=config.DEFAULT_ADMIN_USERNAME,
        email=config.DEFAULT_ADMIN_EMAIL,
        role="admin",
    )
    admin.set_password(config.DEFAULT_ADMIN_PASSWORD)
    db.session.add(admin)
    db.session.commit()


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=config.DEBUG)
