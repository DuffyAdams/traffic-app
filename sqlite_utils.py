"""SQLite connection lifecycle helpers."""

import sqlite3
from contextlib import contextmanager


@contextmanager
def sqlite_connection(database, *, timeout=30, row_factory=None):
    """Yield a connection that always commits/rolls back and then closes."""
    connection = sqlite3.connect(database, timeout=timeout)
    if row_factory is not None:
        connection.row_factory = row_factory
    try:
        yield connection
    except BaseException:
        connection.rollback()
        raise
    else:
        connection.commit()
    finally:
        connection.close()
