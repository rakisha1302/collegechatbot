"""Authentication package: Flask-Login setup and auth blueprint."""
from flask_login import LoginManager

login_manager = LoginManager()
login_manager.login_view = "auth.login_page"
login_manager.login_message = "Please log in to access the admin dashboard."
login_manager.login_message_category = "warning"


@login_manager.user_loader
def load_user(user_id):
    from models.user import User
    return User.query.get(int(user_id))


from auth.routes import auth_bp  # noqa: E402,F401
