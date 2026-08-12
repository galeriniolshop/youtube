"""Local persistence for the YouTube operations console.

Streamlit Cloud's local disk is ephemeral. The database is intentionally kept
behind a small repository so it can later be replaced by Postgres/Supabase
without changing the UI. Refresh tokens are encrypted at rest when
``TOKEN_ENCRYPTION_KEY`` (a Fernet key) is configured in Streamlit secrets.
"""
from __future__ import annotations

import base64
import json
import os
import secrets
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("APP_DATA_DIR", ROOT_DIR / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
PROCESSED_DIR = DATA_DIR / "processed"
DB_PATH = DATA_DIR / "youtube_studio.db"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


class TokenVault:
    """Encrypt channel OAuth tokens with Fernet.

    A key from the environment is preferred. For local development, a key is
    generated in ``data/.token_key`` so the app remains useful without setup.
    On Streamlit Cloud, configure ``TOKEN_ENCRYPTION_KEY`` as a secret to keep
    channels connected after a container restart.
    """

    def __init__(self, key: str | None = None):
        self.key_source = "configured secret"
        raw_key = key or os.getenv("TOKEN_ENCRYPTION_KEY")
        ensure_directories()
        key_file = DATA_DIR / ".token_key"
        if not raw_key and key_file.exists():
            raw_key = key_file.read_text(encoding="utf-8").strip()
            self.key_source = "local data directory"
        if not raw_key:
            raw_key = self._new_key()
            try:
                key_file.write_text(raw_key, encoding="utf-8")
                key_file.chmod(0o600)
                self.key_source = "generated local key"
            except OSError:
                # Ephemeral/container-only fallback. Tokens still do not go
                # into a readable database column, but will not survive a
                # process restart without a configured key.
                self.key_source = "ephemeral key"
        self.key = raw_key
        self._fernet = None
        try:
            from cryptography.fernet import Fernet

            self._fernet = Fernet(raw_key.encode("utf-8"))
        except Exception:
            # The dependency is listed in requirements.txt. This fallback is
            # only for lightweight unit tests before dependencies are installed.
            self._fernet = None

    @staticmethod
    def _new_key() -> str:
        try:
            from cryptography.fernet import Fernet

            return Fernet.generate_key().decode("utf-8")
        except Exception:
            return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")

    def encrypt(self, value: dict[str, Any]) -> str:
        payload = json.dumps(value, separators=(",", ":")).encode("utf-8")
        if self._fernet:
            return self._fernet.encrypt(payload).decode("utf-8")
        return base64.urlsafe_b64encode(payload).decode("ascii")

    def decrypt(self, value: str) -> dict[str, Any]:
        if self._fernet:
            payload = self._fernet.decrypt(value.encode("utf-8"))
        else:
            payload = base64.urlsafe_b64decode(value.encode("ascii"))
        return json.loads(payload.decode("utf-8"))


def _connect() -> sqlite3.Connection:
    ensure_directories()
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS channels (
                id TEXT PRIMARY KEY,
                channel_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                handle TEXT DEFAULT '',
                description TEXT DEFAULT '',
                thumbnail_url TEXT DEFAULT '',
                subscribers INTEGER DEFAULT 0,
                total_views INTEGER DEFAULT 0,
                video_count INTEGER DEFAULT 0,
                token_ciphertext TEXT NOT NULL,
                token_key_source TEXT DEFAULT '',
                status TEXT DEFAULT 'connected',
                created_at TEXT NOT NULL,
                last_used TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS assets (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                original_name TEXT NOT NULL,
                path TEXT NOT NULL,
                size_bytes INTEGER DEFAULT 0,
                width INTEGER DEFAULT 0,
                height INTEGER DEFAULT 0,
                duration_seconds REAL DEFAULT 0,
                source_ratio TEXT DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                asset_id TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                tags_json TEXT DEFAULT '[]',
                keywords_json TEXT DEFAULT '[]',
                category_id TEXT DEFAULT '22',
                privacy_status TEXT DEFAULT 'private',
                made_for_kids INTEGER DEFAULT 0,
                scheduled_at TEXT,
                status TEXT DEFAULT 'queued',
                youtube_video_id TEXT DEFAULT '',
                error_message TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(asset_id) REFERENCES assets(id) ON DELETE CASCADE,
                FOREIGN KEY(channel_id) REFERENCES channels(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS keyword_analyses (
                id TEXT PRIMARY KEY,
                seed TEXT NOT NULL,
                niche TEXT DEFAULT '',
                language TEXT DEFAULT 'Indonesia',
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS activity_logs (
                id TEXT PRIMARY KEY,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                context_json TEXT DEFAULT '{}',
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_jobs_status_schedule
                ON jobs(status, scheduled_at);
            CREATE INDEX IF NOT EXISTS idx_jobs_created
                ON jobs(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_logs_created
                ON activity_logs(created_at DESC);
            """
        )


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def _rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


# ----- Channels ---------------------------------------------------------

def upsert_channel(profile: dict[str, Any], token: dict[str, Any], vault: TokenVault) -> str:
    channel_id = str(profile.get("channel_id") or profile.get("id") or "")
    if not channel_id:
        raise ValueError("Channel ID tidak ditemukan dari respons YouTube.")
    now = utc_now()
    row_id = f"channel_{channel_id}"
    encrypted = vault.encrypt(token)
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO channels
                (id, channel_id, name, handle, description, thumbnail_url,
                 subscribers, total_views, video_count, token_ciphertext,
                 token_key_source, status, created_at, last_used)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'connected', ?, ?)
            ON CONFLICT(channel_id) DO UPDATE SET
                name=excluded.name,
                handle=excluded.handle,
                description=excluded.description,
                thumbnail_url=excluded.thumbnail_url,
                subscribers=excluded.subscribers,
                total_views=excluded.total_views,
                video_count=excluded.video_count,
                token_ciphertext=excluded.token_ciphertext,
                token_key_source=excluded.token_key_source,
                status='connected',
                last_used=excluded.last_used
            """,
            (
                row_id,
                channel_id,
                profile.get("name", "Channel YouTube"),
                profile.get("handle", ""),
                profile.get("description", ""),
                profile.get("thumbnail_url", ""),
                int(profile.get("subscribers") or 0),
                int(profile.get("total_views") or 0),
                int(profile.get("video_count") or 0),
                encrypted,
                vault.key_source,
                now,
                now,
            ),
        )
    return row_id


def list_channels() -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM channels ORDER BY last_used DESC, name ASC").fetchall()
    return _rows_to_dicts(rows)


def get_channel(channel_row_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM channels WHERE id = ?", (channel_row_id,)).fetchone()
    return _row_to_dict(row)


def get_channel_by_youtube_id(channel_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM channels WHERE channel_id = ?", (channel_id,)).fetchone()
    return _row_to_dict(row)


def get_channel_token(channel_row_id: str, vault: TokenVault) -> dict[str, Any]:
    channel = get_channel(channel_row_id)
    if not channel:
        raise ValueError("Channel tidak ditemukan.")
    return vault.decrypt(channel["token_ciphertext"])


def touch_channel(channel_row_id: str) -> None:
    with _connect() as conn:
        conn.execute("UPDATE channels SET last_used = ? WHERE id = ?", (utc_now(), channel_row_id))


def update_channel_profile(channel_row_id: str, profile: dict[str, Any]) -> None:
    with _connect() as conn:
        conn.execute(
            """
            UPDATE channels SET name=?, handle=?, description=?, thumbnail_url=?,
                subscribers=?, total_views=?, video_count=?, last_used=?
            WHERE id=?
            """,
            (
                profile.get("name", "Channel YouTube"),
                profile.get("handle", ""),
                profile.get("description", ""),
                profile.get("thumbnail_url", ""),
                int(profile.get("subscribers") or 0),
                int(profile.get("total_views") or 0),
                int(profile.get("video_count") or 0),
                utc_now(),
                channel_row_id,
            ),
        )


def delete_channel(channel_row_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM channels WHERE id = ?", (channel_row_id,))


# ----- Assets -----------------------------------------------------------

def add_asset(asset: dict[str, Any]) -> str:
    asset_id = asset.get("id") or f"asset_{uuid.uuid4().hex[:12]}"
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO assets
                (id, name, original_name, path, size_bytes, width, height,
                 duration_seconds, source_ratio, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                asset_id,
                asset.get("name") or asset.get("original_name") or "Video",
                asset.get("original_name") or asset.get("name") or "video.mp4",
                asset["path"],
                int(asset.get("size_bytes") or 0),
                int(asset.get("width") or 0),
                int(asset.get("height") or 0),
                float(asset.get("duration_seconds") or 0),
                asset.get("source_ratio", ""),
                asset.get("created_at") or utc_now(),
            ),
        )
    return asset_id


def list_assets() -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM assets ORDER BY created_at DESC").fetchall()
    return _rows_to_dicts(rows)


def get_asset(asset_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
    return _row_to_dict(row)


def delete_asset(asset_id: str) -> None:
    asset = get_asset(asset_id)
    with _connect() as conn:
        conn.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
    if asset:
        try:
            Path(asset["path"]).unlink(missing_ok=True)
        except OSError:
            pass


# ----- Jobs -------------------------------------------------------------

def create_job(job: dict[str, Any]) -> str:
    job_id = job.get("id") or f"job_{uuid.uuid4().hex[:12]}"
    now = utc_now()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO jobs
                (id, asset_id, channel_id, title, description, tags_json,
                 keywords_json, category_id, privacy_status, made_for_kids,
                 scheduled_at, status, youtube_video_id, error_message,
                 created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', '', ?, ?)
            """,
            (
                job_id,
                job["asset_id"],
                job["channel_id"],
                job.get("title", "Untitled video"),
                job.get("description", ""),
                json.dumps(job.get("tags", []), ensure_ascii=False),
                json.dumps(job.get("keywords", []), ensure_ascii=False),
                str(job.get("category_id", "22")),
                job.get("privacy_status", "private"),
                1 if job.get("made_for_kids") else 0,
                job.get("scheduled_at"),
                job.get("status", "queued"),
                now,
                now,
            ),
        )
    return job_id


def _decode_job(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    for field in ("tags_json", "keywords_json"):
        try:
            result[field.replace("_json", "")] = json.loads(result.pop(field) or "[]")
        except (TypeError, json.JSONDecodeError):
            result[field.replace("_json", "")] = []
    result["made_for_kids"] = bool(result.get("made_for_kids"))
    return result


def list_jobs(limit: int = 100, statuses: list[str] | None = None) -> list[dict[str, Any]]:
    with _connect() as conn:
        if statuses:
            placeholders = ",".join("?" for _ in statuses)
            rows = conn.execute(
                f"SELECT j.*, a.name AS asset_name, c.name AS channel_name "
                f"FROM jobs j JOIN assets a ON a.id=j.asset_id JOIN channels c ON c.id=j.channel_id "
                f"WHERE j.status IN ({placeholders}) ORDER BY COALESCE(j.scheduled_at, j.created_at) ASC LIMIT ?",
                (*statuses, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT j.*, a.name AS asset_name, c.name AS channel_name
                FROM jobs j
                JOIN assets a ON a.id=j.asset_id
                JOIN channels c ON c.id=j.channel_id
                ORDER BY COALESCE(j.scheduled_at, j.created_at) DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
    return [_decode_job(row) for row in rows]


def get_job(job_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT j.*, a.name AS asset_name, c.name AS channel_name
            FROM jobs j JOIN assets a ON a.id=j.asset_id JOIN channels c ON c.id=j.channel_id
            WHERE j.id = ?
            """,
            (job_id,),
        ).fetchone()
    return _decode_job(row) if row else None


def due_jobs(now_iso: str | None = None) -> list[dict[str, Any]]:
    now_iso = now_iso or utc_now()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT j.*, a.name AS asset_name, c.name AS channel_name
            FROM jobs j JOIN assets a ON a.id=j.asset_id JOIN channels c ON c.id=j.channel_id
            WHERE j.status='queued' AND (j.scheduled_at IS NULL OR j.scheduled_at <= ?)
            ORDER BY COALESCE(j.scheduled_at, j.created_at) ASC
            """,
            (now_iso,),
        ).fetchall()
    return [_decode_job(row) for row in rows]


def update_job(job_id: str, **fields: Any) -> None:
    allowed = {
        "status",
        "scheduled_at",
        "youtube_video_id",
        "error_message",
        "title",
        "description",
        "tags",
        "keywords",
        "tags_json",
        "keywords_json",
        "privacy_status",
        "category_id",
        "made_for_kids",
    }
    updates: list[str] = []
    values: list[Any] = []
    for key, value in fields.items():
        if key not in allowed:
            continue
        if key in {"tags", "keywords"}:
            key = f"{key}_json"
            value = json.dumps(value, ensure_ascii=False)
        updates.append(f"{key} = ?")
        values.append(value)
    if not updates:
        return
    updates.append("updated_at = ?")
    values.extend([utc_now(), job_id])
    with _connect() as conn:
        conn.execute(f"UPDATE jobs SET {', '.join(updates)} WHERE id = ?", values)


def delete_job(job_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))


def count_jobs(status: str | None = None) -> int:
    with _connect() as conn:
        if status:
            return int(conn.execute("SELECT COUNT(*) FROM jobs WHERE status=?", (status,)).fetchone()[0])
        return int(conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0])


# ----- Keyword history and logs ----------------------------------------

def save_keyword_analysis(seed: str, niche: str, language: str, payload: dict[str, Any]) -> str:
    analysis_id = f"keyword_{uuid.uuid4().hex[:12]}"
    with _connect() as conn:
        conn.execute(
            "INSERT INTO keyword_analyses (id, seed, niche, language, payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (analysis_id, seed, niche, language, json.dumps(payload, ensure_ascii=False), utc_now()),
        )
    return analysis_id


def list_keyword_analyses(limit: int = 20) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM keyword_analyses ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        try:
            item["payload"] = json.loads(item.pop("payload_json"))
        except (TypeError, json.JSONDecodeError):
            item["payload"] = {}
        result.append(item)
    return result


def log_event(level: str, message: str, context: dict[str, Any] | None = None) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO activity_logs (id, level, message, context_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (
                f"log_{uuid.uuid4().hex[:12]}",
                level,
                message,
                json.dumps(context or {}, ensure_ascii=False),
                utc_now(),
            ),
        )


def list_logs(limit: int = 30) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM activity_logs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return _rows_to_dicts(rows)


# Create the local schema as soon as the module is imported. This is quick and
# makes the app resilient when Streamlit reruns the script.
init_db()
