import psycopg2
from psycopg2 import pool, extras
from contextlib import contextmanager
import logging
from app.config import settings

logger = logging.getLogger("uvicorn.error")

pool_instance = None

def init_db_pool():
    global pool_instance
    if pool_instance is None or pool_instance.closed:
        target_host = settings.resolved_host
        try:
            pool_instance = pool.ThreadedConnectionPool(
                minconn=2,
                maxconn=20,
                host=target_host,
                port=settings.DB_PORT,
                user=settings.DB_USER,
                password=settings.DB_PASSWORD,
                dbname=settings.DB_NAME,
                connect_timeout=10
            )
            logger.info(f"Supabase PostgreSQL connection pool initialized successfully on host {target_host}.")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase connection pool: {e}")
            raise e

def close_db_pool():
    global pool_instance
    if pool_instance and not pool_instance.closed:
        pool_instance.closeall()
        logger.info("Supabase PostgreSQL connection pool closed.")

@contextmanager
def get_db_connection():
    global pool_instance
    if pool_instance is None or pool_instance.closed:
        init_db_pool()
    conn = pool_instance.getconn()
    try:
        yield conn
    finally:
        if pool_instance and not pool_instance.closed:
            pool_instance.putconn(conn)

@contextmanager
def get_db_cursor(commit_on_success: bool = True):
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
        try:
            yield cursor, conn
            if commit_on_success:
                conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()

def check_db_health():
    with get_db_cursor(commit_on_success=False) as (cur, conn):
        cur.execute("SELECT 1 AS is_alive;")
        res = cur.fetchone()
        cur.execute("SELECT version();")
        ver = cur.fetchone()["version"]
        return {
            "status": "HEALTHY" if res and res["is_alive"] == 1 else "UNHEALTHY",
            "database": "Supabase PostgreSQL",
            "version": ver
        }
