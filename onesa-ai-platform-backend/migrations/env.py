import os

from alembic import context
from sqlalchemy import create_engine, pool

from app.models import Base

config = context.config
url = os.environ.get("ONESA_DATABASE_URL")
if not url:
    raise RuntimeError("ONESA_DATABASE_URL is required for migrations")
if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    supplied = config.attributes.get("connection")
    engine = None if supplied is not None else create_engine(url, poolclass=pool.NullPool)
    from contextlib import nullcontext

    with nullcontext(supplied) if supplied is not None else engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    if engine is not None:
        engine.dispose()
