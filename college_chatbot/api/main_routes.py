"""Main frontend page routes (chat UI)."""
from flask import Blueprint, render_template
from config import config

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    return render_template("index.html", college_name=config.COLLEGE_NAME)
