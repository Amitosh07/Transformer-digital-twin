"""A PostgreSQL session lease enforces one stateful runtime owner per database.

This is a deployment guard, not horizontal synchronization of ML objects.
The dedicated connection remains open until application shutdown.
"""
from sqlalchemy import text
from app.db.session import get_engine


class RuntimeLease:
    def __init__(self):
        self.connection = None

    def acquire(self):
        connection = get_engine().connect()
        try:
            if not connection.scalar(text('SELECT pg_try_advisory_lock(19002, 110)')):
                raise RuntimeError('One Python ML runtime worker per database is supported')
            self.connection = connection
        except Exception:
            connection.close()
            raise

    def close(self):
        if self.connection is not None:
            try:
                self.connection.execute(text('SELECT pg_advisory_unlock(19002, 110)'))
            finally:
                self.connection.close()
                self.connection = None
