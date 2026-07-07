from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from models.user import User  # noqa: E402,F401
from models.conversation import Conversation, Message  # noqa: E402,F401
from models.document import Document  # noqa: E402,F401
from models.feedback import Feedback  # noqa: E402,F401
from models.analytics import UsageLog  # noqa: E402,F401
