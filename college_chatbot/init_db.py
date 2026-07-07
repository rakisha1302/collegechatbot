"""
Standalone database initialization script.

Run this once before first launch (optional - app.py also auto-initializes
the database and default admin on startup):

    python init_db.py

Also ingests the sample documents in data/sample_docs/ into the RAG vector
store so the chatbot has a working knowledge base out of the box.
"""
import os
from app import create_app
from models import db
from models.user import User
from models.document import Document
from services.rag_service import ingest_document
from config import config


def main():
    app = create_app()
    with app.app_context():
        db.create_all()
        print("[OK] Database tables created.")

        if not User.query.filter_by(role="admin").first():
            admin = User(
                username=config.DEFAULT_ADMIN_USERNAME,
                email=config.DEFAULT_ADMIN_EMAIL,
                role="admin",
            )
            admin.set_password(config.DEFAULT_ADMIN_PASSWORD)
            db.session.add(admin)
            db.session.commit()
            print(f"[OK] Default admin created: {config.DEFAULT_ADMIN_USERNAME} / "
                  f"{config.DEFAULT_ADMIN_PASSWORD} (change this password immediately)")
        else:
            print("[SKIP] Admin account already exists.")

        sample_dir = os.path.join(os.path.dirname(__file__), "data", "sample_docs")
        if os.path.isdir(sample_dir):
            for filename in os.listdir(sample_dir):
                if not filename.lower().endswith((".txt", ".pdf", ".docx")):
                    continue
                if Document.query.filter_by(original_filename=filename).first():
                    print(f"[SKIP] '{filename}' already indexed.")
                    continue
                filepath = os.path.join(sample_dir, filename)
                try:
                    chunk_count = ingest_document(filepath, filename, category="general")
                    doc = Document(
                        filename=filename,
                        original_filename=filename,
                        file_type=filename.rsplit(".", 1)[1].lower(),
                        category="general",
                        chunk_count=chunk_count,
                        status="indexed",
                    )
                    db.session.add(doc)
                    db.session.commit()
                    print(f"[OK] Indexed sample document '{filename}' ({chunk_count} chunks).")
                except Exception as exc:
                    print(f"[FAIL] Could not index '{filename}': {exc}")

    print("\nSetup complete. Start the app with: python app.py")


if __name__ == "__main__":
    main()
