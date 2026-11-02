from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def make_database(url):
    engine = create_engine(url, pool_pre_ping=True, pool_size=10, max_overflow=10)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def get_db(request):
    # Used through the typed dependency in main.py.
    with request.app.state.session_factory() as session:
        yield session
