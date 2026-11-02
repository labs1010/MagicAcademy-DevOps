from fastapi import FastAPI
from sqlalchemy import text

from app.config import load_settings
from app.database import make_database


def create_app():
    settings = load_settings()
    engine, sessions = make_database(settings.database_url)
    app = FastAPI(title="Magic Academy")

    @app.get("/")
    def home():
        return {"message": "Magic Academy skeleton"}

    @app.get("/health")
    def health():
        with sessions() as db:
            db.execute(text("SELECT 1"))
        return {"status": "ok"}

    return app
