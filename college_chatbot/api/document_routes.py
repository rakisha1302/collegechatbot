"""Document management API for the admin RAG knowledge base (upload, list, delete)."""
import os
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user

from models import db
from models.document import Document
from models.analytics import UsageLog
from services.rag_service import ingest_document, delete_document_chunks, knowledge_base_stats
from utils.helpers import allowed_file, make_safe_filename, sanitize_text_input
from utils.logger import get_logger

logger = get_logger(__name__)
document_bp = Blueprint("documents", __name__, url_prefix="/api/documents")


def _admin_required():
    return current_user.is_authenticated and current_user.is_admin()


@document_bp.route("/upload", methods=["POST"])
@login_required
def upload_document():
    if not current_user.is_admin():
        return jsonify({"success": False, "error": "Administrator privileges required."}), 403

    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file part in the request."}), 400

    file = request.files["file"]
    category = sanitize_text_input(request.form.get("category", "general"), 50)

    if file.filename == "":
        return jsonify({"success": False, "error": "No file selected."}), 400
    if not allowed_file(file.filename):
        return jsonify({"success": False, "error": "Unsupported file format. Use PDF, DOCX, or TXT."}), 400

    safe_name = make_safe_filename(file.filename)
    save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], safe_name)

    doc = Document(
        filename=safe_name,
        original_filename=file.filename,
        file_type=file.filename.rsplit(".", 1)[1].lower(),
        category=category,
        uploaded_by=current_user.id,
        status="processing",
    )
    db.session.add(doc)
    db.session.commit()

    try:
        file.save(save_path)
        chunk_count = ingest_document(save_path, file.filename, category=category)
        doc.chunk_count = chunk_count
        doc.status = "indexed"
        db.session.add(UsageLog(event_type="doc_upload", success=True,
                                 details=f"Indexed '{file.filename}' ({chunk_count} chunks)"))
    except Exception as exc:
        logger.error("Document ingestion failed for '%s': %s", file.filename, exc)
        doc.status = "failed"
        doc.error_message = str(exc)
        db.session.add(UsageLog(event_type="doc_upload", success=False, details=str(exc)))

    db.session.commit()
    return jsonify({"success": doc.status == "indexed", "document": doc.to_dict()})


@document_bp.route("/", methods=["GET"])
@login_required
def list_documents():
    if not current_user.is_admin():
        return jsonify({"success": False, "error": "Administrator privileges required."}), 403
    docs = Document.query.order_by(Document.uploaded_at.desc()).all()
    return jsonify({"success": True, "documents": [d.to_dict() for d in docs],
                     "vector_store_stats": knowledge_base_stats()})


@document_bp.route("/<int:doc_id>", methods=["DELETE"])
@login_required
def delete_document(doc_id):
    if not current_user.is_admin():
        return jsonify({"success": False, "error": "Administrator privileges required."}), 403

    doc = Document.query.get(doc_id)
    if not doc:
        return jsonify({"success": False, "error": "Document not found."}), 404

    delete_document_chunks(doc.original_filename)

    filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], doc.filename)
    if os.path.exists(filepath):
        os.remove(filepath)

    db.session.delete(doc)
    db.session.commit()
    return jsonify({"success": True})
