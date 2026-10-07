from logging.config import fileConfig

from alembic import context

from app.config import Settings
from app.db.models import Base
from app.db.session import database

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
url = config.attributes.get("database_url") or Settings().database_url

if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()
else:
    engine, _ = database(url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
