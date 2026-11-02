"""A small synchronous API: one database transaction per request."""

import logging
from contextlib import asynccontextmanager
from html import escape

import jwt
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import load_settings
from app.database import Base, get_db, make_database
from app.models import Course, Enrollment, User
from app.schemas import CourseIn, CourseOut, EnrollmentOut, ProfileUpdate, Registration, UserOut
from app.security import DUMMY_HASH, create_token, decode_token, hash_password, verify_password

log = logging.getLogger(__name__)
oauth2 = OAuth2PasswordBearer(tokenUrl="auth/token")


def database(request: Request):
    yield from get_db(request)


def current_user(request: Request, token: str = Depends(oauth2), db: Session = Depends(database)):
    try:
        payload = decode_token(token, request.app.state.settings)
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, ValueError, KeyError, TypeError):
        raise HTTPException(
            401, "Invalid or expired token", headers={"WWW-Authenticate": "Bearer"}
        ) from None
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(401, "Unknown user")
    return user


def admin_user(user: User = Depends(current_user)):
    if user.role != "ADMIN":
        raise HTTPException(403, "ADMIN role required")
    return user


def create_app(settings=None):
    settings = settings or load_settings()
    engine, session_factory = make_database(settings.database_url)

    @asynccontextmanager
    async def lifespan(app):
        # One schema version and one Uvicorn process. create_all is idempotent;
        # it does NOT migrate existing columns. See docs/SCHEMA.md.
        Base.metadata.create_all(engine)
        yield
        engine.dispose()

    # Do not expose traceback pages, even in sandbox. debug is environment metadata.
    app = FastAPI(title="Magic Academy", version="1.0.0", debug=False, lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory

    @app.exception_handler(Exception)
    async def internal_error(request, exc):
        log.error("Unhandled request failure", exc_info=(type(exc), exc, exc.__traceback__))
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    @app.get("/", response_class=HTMLResponse)
    def home():
        return (
            "<h1>Magic Academy</h1><p>Register and enroll in spell courses.</p>"
            '<a href="/docs">Swagger UI</a>'
        )

    @app.get("/health")
    def health(db: Session = Depends(database)):
        db.execute(text("SELECT 1"))
        return {"status": "ok", "environment": settings.app_env}

    @app.post("/auth/register", response_model=UserOut, status_code=201)
    def register(data: Registration, db: Session = Depends(database)):
        user = User(username=data.username, password_hash=hash_password(data.password), role="USER")
        db.add(user)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "Username already registered") from None
        return user

    @app.post("/auth/token")
    def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database)):
        user = db.scalar(select(User).where(User.username == form.username))
        valid = verify_password(form.password, user.password_hash if user else DUMMY_HASH)
        if not valid or user is None:
            raise HTTPException(401, "Invalid credentials", headers={"WWW-Authenticate": "Bearer"})
        return {"access_token": create_token(user.id, settings), "token_type": "bearer"}

    @app.get("/users/me", response_model=UserOut)
    def me(user: User = Depends(current_user)):
        return user

    @app.patch("/users/{user_id}", response_model=UserOut)
    def update_profile(
        user_id: int,
        data: ProfileUpdate,
        user: User = Depends(current_user),
        db: Session = Depends(database),
    ):
        # Even an administrator cannot edit another profile via this endpoint.
        if user_id != user.id:
            raise HTTPException(403, "Cannot modify another user")
        user.display_name = data.display_name
        db.commit()
        return user

    @app.get("/user/home", response_class=HTMLResponse)
    def user_home(user: User = Depends(current_user)):
        return f"<h1>User home</h1><p>Welcome, {escape(user.username)}!</p>"

    @app.get("/admin/home", response_class=HTMLResponse)
    def admin_home(user: User = Depends(admin_user)):
        return f"<h1>Admin home</h1><p>Administrator: {escape(user.username)}</p>"

    @app.post("/admin/courses", response_model=CourseOut, status_code=201)
    def add_course(
        data: CourseIn, admin: User = Depends(admin_user), db: Session = Depends(database)
    ):
        course = Course(**data.model_dump())
        db.add(course)
        db.commit()
        return {**data.model_dump(), "id": course.id, "available_seats": course.capacity}

    @app.get("/courses", response_model=list[CourseOut])
    def courses(db: Session = Depends(database)):
        # One aggregated query, no per-course N+1 count queries.
        rows = db.execute(
            select(Course, func.count(Enrollment.id))
            .outerjoin(Enrollment)
            .group_by(Course.id)
            .order_by(Course.id)
        ).all()
        return [
            {
                "id": c.id,
                "title": c.title,
                "capacity": c.capacity,
                "available_seats": c.capacity - count,
            }
            for c, count in rows
        ]

    @app.post("/courses/{course_id}/enroll", response_model=EnrollmentOut, status_code=201)
    def enroll(course_id: int, user: User = Depends(current_user), db: Session = Depends(database)):
        # The course row is a per-course mutex shared by ALL API processes.
        course = db.scalar(select(Course).where(Course.id == course_id).with_for_update())
        if course is None:
            raise HTTPException(404, "Course not found")
        existing = db.scalar(
            select(Enrollment.id).where(
                Enrollment.course_id == course_id, Enrollment.user_id == user.id
            )
        )
        if existing is not None:
            raise HTTPException(409, "Already enrolled")
        count = db.scalar(
            select(func.count()).select_from(Enrollment).where(Enrollment.course_id == course_id)
        )
        if count >= course.capacity:
            raise HTTPException(409, "Course is full")
        enrollment = Enrollment(user_id=user.id, course_id=course_id)
        db.add(enrollment)
        try:
            db.commit()  # Insert and release lock atomically.
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "Already enrolled") from None
        return enrollment

    @app.get("/enrollments/me", response_model=list[EnrollmentOut])
    def own_enrollments(user: User = Depends(current_user), db: Session = Depends(database)):
        return db.scalars(
            select(Enrollment).where(Enrollment.user_id == user.id).order_by(Enrollment.id)
        ).all()

    @app.get("/enrollments/{enrollment_id}", response_model=EnrollmentOut)
    def read_enrollment(
        enrollment_id: int, user: User = Depends(current_user), db: Session = Depends(database)
    ):
        enrollment = db.get(Enrollment, enrollment_id)
        if enrollment is None:
            raise HTTPException(404, "Enrollment not found")
        if enrollment.user_id != user.id:
            raise HTTPException(403, "Cannot read another user's enrollment")
        return enrollment

    return app
