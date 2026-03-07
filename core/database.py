"""
User & Prediction Database
==========================
Async PostgreSQL via asyncpg. Scalable and robust for prod.

Tables:
  users          — account records
  refresh_tokens — stored refresh tokens (enables revocation)
  predictions    — prediction history for accuracy tracking

All queries use parameterized statements — no SQL injection possible.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from uuid import uuid4

import asyncpg

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# SCHEMA
# ─────────────────────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            UUID PRIMARY KEY,
    email         TEXT UNIQUE NOT NULL,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'user',
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL,
    last_login    TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    jti        TEXT PRIMARY KEY,          -- JWT token ID (from the 'jti' claim)
    user_id    UUID NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS predictions (
    id              UUID PRIMARY KEY,
    symbol          TEXT NOT NULL,
    asset_type      TEXT NOT NULL,  -- 'stock' or 'crypto'
    predicted_price DECIMAL(20,8) NOT NULL,
    target_price    DECIMAL(20,8),
    confidence      INTEGER,  -- percentage 0-100
    timeframe       TEXT,     -- e.g. '1 week', '1 month'
    created_at      TIMESTAMPTZ NOT NULL,
    actual_price    DECIMAL(20,8),  -- filled later for accuracy calc
    accuracy_pct    DECIMAL(5,2)    -- calculated as |pred - actual| / pred * 100
);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_predictions_symbol ON predictions(symbol);
CREATE INDEX IF NOT EXISTS idx_predictions_created_at ON predictions(created_at);
"""


# ─────────────────────────────────────────────────────────────────────────────
# INIT
# ─────────────────────────────────────────────────────────────────────────────

async def init_db(database_url: str) -> None:
    """Create tables if they don't exist. Call once at app startup."""
    conn = await asyncpg.connect(database_url)
    try:
        await conn.execute(_SCHEMA)
        logger.info(f"[DB] Initialized at {database_url}")
    finally:
        await conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# USER CRUD
# ─────────────────────────────────────────────────────────────────────────────

async def create_user(
    email: str,
    username: str,
    password_hash: str,
    role: str = "user",
    database_url: str = None,
) -> dict:
    """
    Insert a new user. Raises ValueError on duplicate email/username.
    Returns the created user record (without password_hash).
    """
    from core.config import settings
    db_url = database_url or settings.database_url
    if not db_url:
        raise RuntimeError("Database URL not configured")

    user_id = uuid4()
    now = datetime.now(timezone.utc)

    conn = await asyncpg.connect(db_url)
    try:
        await conn.execute(
            """
            INSERT INTO users (id, email, username, password_hash, role, is_active, created_at)
            VALUES ($1, $2, $3, $4, $5, TRUE, $6)
            """,
            user_id, email.lower().strip(), username.strip(), password_hash, role, now,
        )
        user = {
            "user_id": str(user_id),
            "email": email.lower().strip(),
            "username": username.strip(),
            "role": role,
            "is_active": True,
            "created_at": now.isoformat(),
            "last_login": None,
        }
        logger.info(f"[DB] Created user {user_id} ({username})")
        return user
    except asyncpg.UniqueViolationError as e:
        if "email" in str(e):
            raise ValueError(f"Email '{email}' is already registered.")
        elif "username" in str(e):
            raise ValueError(f"Username '{username}' is already taken.")
        raise
    finally:
        await conn.close()


async def get_user_by_email(email: str, database_url: str = None) -> Optional[dict]:
    """Fetch a user by email. Returns None if not found."""
    from core.config import settings
    db_url = database_url or settings.database_url
    if not db_url:
        raise RuntimeError("Database URL not configured")

    conn = await asyncpg.connect(db_url)
    try:
        row = await conn.fetchrow(
            "SELECT id, email, username, password_hash, role, is_active, created_at, last_login FROM users WHERE email = $1 AND is_active = TRUE",
            email.lower().strip(),
        )
        return dict(row) if row else None
    finally:
        await conn.close()


async def get_user_by_id(user_id: str, database_url: str = None) -> Optional[dict]:
    """Fetch a user by ID. Returns None if not found."""
    from core.config import settings
    db_url = database_url or settings.database_url
    if not db_url:
        raise RuntimeError("Database URL not configured")

    conn = await asyncpg.connect(db_url)
    try:
        row = await conn.fetchrow(
            "SELECT id, email, username, password_hash, role, is_active, created_at, last_login FROM users WHERE id = $1",
            user_id,
        )
        return dict(row) if row else None
    finally:
        await conn.close()


async def update_last_login(user_id: str, database_url: str = None) -> None:
    """Update the last_login timestamp after a successful login."""
    from core.config import settings
    db_url = database_url or settings.database_url
    if not db_url:
        raise RuntimeError("Database URL not configured")

    now = datetime.now(timezone.utc)
    conn = await asyncpg.connect(db_url)
    try:
        await conn.execute(
            "UPDATE users SET last_login = $1 WHERE id = $2", now, user_id
        )
    finally:
        await conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# REFRESH TOKEN CRUD
# ─────────────────────────────────────────────────────────────────────────────

async def store_refresh_token(
    jti: str,
    user_id: str,
    expires_at: datetime,
    database_url: str = None,
) -> None:
    """
    Store a refresh token in the DB. Used for revocation and cleanup.
    """
    from core.config import settings
    db_url = database_url or settings.database_url
    if not db_url:
        raise RuntimeError("Database URL not configured")

    now = datetime.now(timezone.utc)
    conn = await asyncpg.connect(db_url)
    try:
        await conn.execute(
            """
            INSERT INTO refresh_tokens (jti, user_id, expires_at, created_at)
            VALUES ($1, $2, $3, $4)
            """,
            jti, user_id, expires_at, now,
        )
    finally:
        await conn.close()


async def is_refresh_token_valid(jti: str, database_url: str = None) -> bool:
    """
    Return True only if the refresh token exists, is not revoked,
    and has not expired.
    """
    from core.config import settings
    db_url = database_url or settings.database_url
    if not db_url:
        raise RuntimeError("Database URL not configured")

    now = datetime.now(timezone.utc)
    conn = await asyncpg.connect(db_url)
    try:
        row = await conn.fetchrow(
            """
            SELECT 1 FROM refresh_tokens
            WHERE jti = $1 AND revoked = FALSE AND expires_at > $2
            """,
            jti, now,
        )
        return row is not None
    finally:
        await conn.close()


async def revoke_refresh_token(jti: str, database_url: str = None) -> None:
    """Revoke a specific refresh token (used during rotation and logout)."""
    from core.config import settings
    db_url = database_url or settings.database_url
    if not db_url:
        raise RuntimeError("Database URL not configured")

    conn = await asyncpg.connect(db_url)
    try:
        await conn.execute(
            "UPDATE refresh_tokens SET revoked = TRUE WHERE jti = $1", jti
        )
    finally:
        await conn.close()


async def revoke_all_user_tokens(user_id: str, database_url: str = None) -> int:
    """
    Revoke ALL refresh tokens for a user.
    Use for: password change, account compromise, force-logout-everywhere.
    Returns the number of tokens revoked.
    """
    from core.config import settings
    db_url = database_url or settings.database_url
    if not db_url:
        raise RuntimeError("Database URL not configured")

    conn = await asyncpg.connect(db_url)
    try:
        result = await conn.execute(
            "UPDATE refresh_tokens SET revoked = TRUE WHERE user_id = $1 AND revoked = FALSE",
            user_id,
        )
        count = int(result.split()[-1])  # asyncpg returns "UPDATE X" string
        logger.info(f"[DB] Revoked {count} refresh token(s) for user {user_id}")
        return count
    finally:
        await conn.close()


async def cleanup_expired_tokens(database_url: str = None) -> int:
    """
    Delete expired refresh tokens from the DB.
    Run this periodically (e.g. daily) to keep the table small.
    Returns the number of rows deleted.
    """
    from core.config import settings
    db_url = database_url or settings.database_url
    if not db_url:
        raise RuntimeError("Database URL not configured")

    now = datetime.now(timezone.utc)
    conn = await asyncpg.connect(db_url)
    try:
        result = await conn.execute(
            "DELETE FROM refresh_tokens WHERE expires_at < $1", now
        )
        count = int(result.split()[-1])
        return count
    finally:
        await conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# PREDICTION CRUD
# ─────────────────────────────────────────────────────────────────────────────

async def save_prediction(
    symbol: str,
    asset_type: str,
    predicted_price: float,
    target_price: float = None,
    confidence: int = None,
    timeframe: str = None,
    database_url: str = None,
) -> str:
    """
    Save a prediction to the database.
    Returns the prediction ID.
    """
    from core.config import settings
    db_url = database_url or settings.database_url
    if not db_url:
        raise RuntimeError("Database URL not configured")

    prediction_id = uuid4()
    now = datetime.now(timezone.utc)
    conn = await asyncpg.connect(db_url)
    try:
        await conn.execute(
            """
            INSERT INTO predictions (id, symbol, asset_type, predicted_price, target_price, confidence, timeframe, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            prediction_id, symbol.upper(), asset_type, predicted_price, target_price, confidence, timeframe, now,
        )
        logger.info(f"[DB] Saved prediction {prediction_id} for {symbol}")
        return str(prediction_id)
    finally:
        await conn.close()


async def get_predictions(
    symbol: str = None,
    asset_type: str = None,
    limit: int = 100,
    database_url: str = None,
) -> List[Dict[str, Any]]:
    """
    Get prediction history, optionally filtered by symbol/asset_type.
    """
    from core.config import settings
    db_url = database_url or settings.database_url
    if not db_url:
        raise RuntimeError("Database URL not configured")

    conn = await asyncpg.connect(db_url)
    try:
        query = """
            SELECT id, symbol, asset_type, predicted_price, target_price, confidence, timeframe, created_at, actual_price, accuracy_pct
            FROM predictions
            WHERE ($1::text IS NULL OR symbol = $1)
              AND ($2::text IS NULL OR asset_type = $2)
            ORDER BY created_at DESC
            LIMIT $3
        """
        rows = await conn.fetch(query, symbol.upper() if symbol else None, asset_type, limit)
        return [dict(row) for row in rows]
    finally:
        await conn.close()


async def update_actual_price(
    prediction_id: str,
    actual_price: float,
    database_url: str = None,
) -> None:
    """
    Update the actual price for a prediction and calculate accuracy.
    """
    from core.config import settings
    db_url = database_url or settings.database_url
    if not db_url:
        raise RuntimeError("Database URL not configured")

    conn = await asyncpg.connect(db_url)
    try:
        # Get the predicted price
        row = await conn.fetchrow(
            "SELECT predicted_price FROM predictions WHERE id = $1", prediction_id
        )
        if not row:
            raise ValueError(f"Prediction {prediction_id} not found")

        predicted_price = row['predicted_price']
        accuracy_pct = abs(predicted_price - actual_price) / predicted_price * 100

        await conn.execute(
            """
            UPDATE predictions
            SET actual_price = $1, accuracy_pct = $2
            WHERE id = $3
            """,
            actual_price, accuracy_pct, prediction_id,
        )
        logger.info(f"[DB] Updated prediction {prediction_id} with actual price {actual_price}, accuracy {accuracy_pct:.2f}%")
    finally:
        await conn.close()


async def get_accuracy_stats(
    symbol: str = None,
    asset_type: str = None,
    database_url: str = None,
) -> Dict[str, Any]:
    """
    Calculate accuracy statistics for predictions.
    """
    from core.config import settings
    db_url = database_url or settings.database_url
    if not db_url:
        raise RuntimeError("Database URL not configured")

    conn = await asyncpg.connect(db_url)
    try:
        query = """
            SELECT
                COUNT(*) as total_predictions,
                AVG(accuracy_pct) as avg_accuracy,
                MIN(accuracy_pct) as min_accuracy,
                MAX(accuracy_pct) as max_accuracy,
                COUNT(CASE WHEN accuracy_pct <= 5 THEN 1 END) as excellent_count,
                COUNT(CASE WHEN accuracy_pct > 5 AND accuracy_pct <= 10 THEN 1 END) as good_count,
                COUNT(CASE WHEN accuracy_pct > 10 THEN 1 END) as poor_count
            FROM predictions
            WHERE actual_price IS NOT NULL
              AND ($1::text IS NULL OR symbol = $1)
              AND ($2::text IS NULL OR asset_type = $2)
        """
        row = await conn.fetchrow(query, symbol.upper() if symbol else None, asset_type)
        return dict(row) if row else {}
    finally:
        await conn.close()
