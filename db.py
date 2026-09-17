"""Postgres connection + schema helpers, shared by ingestion and retrieval.

Connects to the dedicated lenny_pm_copilot database/role provisioned in
issue #2 -- never the shared VM's other project or the postgres superuser.
"""

import logging

import streamlit as st
import psycopg2
from pgvector.psycopg2 import register_vector

EMBEDDING_DIM = 768  # nomic-embed-text-v1.5 output size (see embeddings.py)

logger = logging.getLogger(__name__)


class DatabaseUnavailableError(Exception):
    """Raised when the Postgres database cannot be reached (network issue,
    VM down, firewall misconfiguration, etc.) -- callers should show the
    user a friendly message rather than an unhandled exception (issue #14).
    """


def get_connection():
    cfg = st.secrets["postgres"]
    try:
        conn = psycopg2.connect(
            host=cfg["host"],
            port=cfg["port"],
            dbname=cfg["dbname"],
            user=cfg["user"],
            password=cfg["password"],
            sslmode=cfg.get("sslmode", "require"),
        )
    except psycopg2.OperationalError as exc:
        logger.exception("could not connect to the database")
        raise DatabaseUnavailableError("could not connect to the database") from exc
    register_vector(conn)
    return conn


def ensure_schema(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                guest TEXT NOT NULL,
                title TEXT NOT NULL,
                youtube_url TEXT NOT NULL,
                video_id TEXT NOT NULL,
                publish_date DATE,
                start_timestamp INTEGER NOT NULL,
                chunk_text TEXT NOT NULL,
                embedding VECTOR({EMBEDDING_DIM}) NOT NULL
            );
            """
        )
    conn.commit()
