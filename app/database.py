from __future__ import annotations
from datetime import datetime, timezone
import json
import sqlite3
import uuid
from supabase import create_client, Client
from .config import settings


class DatabaseClient:
    _instance: "DatabaseClient | None" = None
    _client: Client | None = None
    _sqlite_initialized: bool = False

    @classmethod
    def get(cls) -> "DatabaseClient":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def client(self) -> Client:
        if settings.database_type == "sqlite":
            raise RuntimeError("Cannot access Supabase client when database_type is set to 'sqlite'")
        if self._client is None:
            self._client = create_client(
                settings.supabase_url,
                settings.supabase_service_role_key,
            )
        return self._client

    def __init__(self):
        if settings.database_type == "sqlite" and not DatabaseClient._sqlite_initialized:
            self._init_sqlite()
            DatabaseClient._sqlite_initialized = True

    def _init_sqlite(self):
        conn = sqlite3.connect(settings.sqlite_db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id          TEXT PRIMARY KEY,
                title       TEXT NOT NULL DEFAULT 'New Session',
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL,
                metadata    TEXT NOT NULL DEFAULT '{}'
            );
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id           TEXT PRIMARY KEY,
                session_id   TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                user_input   TEXT NOT NULL,
                status       TEXT NOT NULL DEFAULT 'pending',
                result       TEXT,
                error        TEXT,
                created_at   TEXT NOT NULL,
                completed_at TEXT
            );
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_runs (
                id              TEXT PRIMARY KEY,
                task_id         TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                ant_type        TEXT NOT NULL,
                input_summary   TEXT NOT NULL,
                output_summary  TEXT,
                status          TEXT NOT NULL DEFAULT 'pending',
                tokens_used     INTEGER NOT NULL DEFAULT 0,
                started_at      TEXT NOT NULL,
                completed_at    TEXT
            );
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id          TEXT PRIMARY KEY,
                session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                task_id     TEXT REFERENCES tasks(id) ON DELETE SET NULL,
                role        TEXT NOT NULL,
                content     TEXT NOT NULL,
                ant_type    TEXT,
                created_at  TEXT NOT NULL
            );
            """)
            conn.commit()
        finally:
            conn.close()

    def _conn(self):
        conn = sqlite3.connect(settings.sqlite_db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _row_to_dict(self, row, table_name):
        if row is None:
            return None
        d = dict(row)
        if table_name == "sessions" and "metadata" in d:
            try:
                d["metadata"] = json.loads(d["metadata"])
            except Exception:
                d["metadata"] = {}
        return d

    # ── Sessions ──────────────────────────────────────────────────────────────

    def create_session(self, session_id: str, title: str) -> dict:
        if settings.database_type != "sqlite":
            result = self.client.table("sessions").insert(
                {"id": session_id, "title": title}
            ).execute()
            return result.data[0]

        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO sessions (id, title, created_at, updated_at, metadata) VALUES (?, ?, ?, ?, ?)",
                (session_id, title, now, now, "{}"),
            )
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
            return self._row_to_dict(row, "sessions")

    def get_session(self, session_id: str) -> dict | None:
        if settings.database_type != "sqlite":
            result = self.client.table("sessions").select("*").eq("id", session_id).execute()
            return result.data[0] if result.data else None

        with self._conn() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
            return self._row_to_dict(row, "sessions")

    def list_sessions(self, limit: int = 20) -> list[dict]:
        if settings.database_type != "sqlite":
            result = (
                self.client.table("sessions")
                .select("*")
                .order("updated_at", desc=True)
                .limit(limit)
                .execute()
            )
            return result.data

        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [self._row_to_dict(r, "sessions") for r in rows]

    def update_session(self, session_id: str, updates: dict) -> dict:
        if settings.database_type != "sqlite":
            result = (
                self.client.table("sessions")
                .update(updates)
                .eq("id", session_id)
                .execute()
            )
            return result.data[0]

        now = datetime.now(timezone.utc).isoformat()
        local_updates = dict(updates)
        local_updates["updated_at"] = now

        fields = []
        values = []
        for k, v in local_updates.items():
            fields.append(f"{k} = ?")
            if k == "metadata":
                values.append(json.dumps(v))
            else:
                values.append(v)
        values.append(session_id)

        query = f"UPDATE sessions SET {', '.join(fields)} WHERE id = ?"
        with self._conn() as conn:
            conn.execute(query, values)
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
            return self._row_to_dict(row, "sessions")

    # ── Tasks ─────────────────────────────────────────────────────────────────

    def create_task(self, task: dict) -> dict:
        if settings.database_type != "sqlite":
            result = self.client.table("tasks").insert(task).execute()
            return result.data[0]

        now = datetime.now(timezone.utc).isoformat()
        task_id = task.get("id") or str(uuid.uuid4())
        session_id = task.get("session_id")
        user_input = task.get("user_input")
        status = task.get("status") or "pending"
        result_val = task.get("result")
        error = task.get("error")
        created_at = task.get("created_at") or now
        completed_at = task.get("completed_at")

        with self._conn() as conn:
            conn.execute(
                """INSERT INTO tasks (id, session_id, user_input, status, result, error, created_at, completed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (task_id, session_id, user_input, status, result_val, error, created_at, completed_at),
            )
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            return self._row_to_dict(row, "tasks")

    def update_task(self, task_id: str, updates: dict) -> dict:
        if settings.database_type != "sqlite":
            result = (
                self.client.table("tasks")
                .update(updates)
                .eq("id", task_id)
                .execute()
            )
            return result.data[0]

        fields = []
        values = []
        for k, v in updates.items():
            fields.append(f"{k} = ?")
            values.append(v)
        values.append(task_id)

        query = f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?"
        with self._conn() as conn:
            conn.execute(query, values)
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            return self._row_to_dict(row, "tasks")

    def get_tasks_for_session(self, session_id: str) -> list[dict]:
        if settings.database_type != "sqlite":
            result = (
                self.client.table("tasks")
                .select("*")
                .eq("session_id", session_id)
                .order("created_at")
                .execute()
            )
            return result.data

        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE session_id = ? ORDER BY created_at", (session_id,)
            ).fetchall()
            return [self._row_to_dict(r, "tasks") for r in rows]

    def get_task(self, task_id: str) -> dict | None:
        if settings.database_type != "sqlite":
            result = self.client.table("tasks").select("*").eq("id", task_id).execute()
            return result.data[0] if result.data else None

        with self._conn() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            return self._row_to_dict(row, "tasks")

    # ── Agent runs ────────────────────────────────────────────────────────────

    def create_agent_run(self, run: dict) -> dict:
        if settings.database_type != "sqlite":
            result = self.client.table("agent_runs").insert(run).execute()
            return result.data[0]

        now = datetime.now(timezone.utc).isoformat()
        run_id = run.get("id") or str(uuid.uuid4())
        task_id = run.get("task_id")
        ant_type = run.get("ant_type")
        input_summary = run.get("input_summary")
        output_summary = run.get("output_summary")
        status = run.get("status") or "pending"
        tokens_used = run.get("tokens_used") or 0
        started_at = run.get("started_at") or now
        completed_at = run.get("completed_at")

        with self._conn() as conn:
            conn.execute(
                """INSERT INTO agent_runs (id, task_id, ant_type, input_summary, output_summary, status, tokens_used, started_at, completed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (run_id, task_id, ant_type, input_summary, output_summary, status, tokens_used, started_at, completed_at),
            )
            row = conn.execute("SELECT * FROM agent_runs WHERE id = ?", (run_id,)).fetchone()
            return self._row_to_dict(row, "agent_runs")

    def update_agent_run(self, run_id: str, updates: dict) -> dict:
        if settings.database_type != "sqlite":
            result = (
                self.client.table("agent_runs")
                .update(updates)
                .eq("id", run_id)
                .execute()
            )
            return result.data[0]

        fields = []
        values = []
        for k, v in updates.items():
            fields.append(f"{k} = ?")
            values.append(v)
        values.append(run_id)

        query = f"UPDATE agent_runs SET {', '.join(fields)} WHERE id = ?"
        with self._conn() as conn:
            conn.execute(query, values)
            row = conn.execute("SELECT * FROM agent_runs WHERE id = ?", (run_id,)).fetchone()
            return self._row_to_dict(row, "agent_runs")

    def get_runs_for_task(self, task_id: str) -> list[dict]:
        if settings.database_type != "sqlite":
            result = (
                self.client.table("agent_runs")
                .select("*")
                .eq("task_id", task_id)
                .order("started_at")
                .execute()
            )
            return result.data

        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM agent_runs WHERE task_id = ? ORDER BY started_at", (task_id,)
            ).fetchall()
            return [self._row_to_dict(r, "agent_runs") for r in rows]

    # ── Messages ──────────────────────────────────────────────────────────────

    def append_message(self, message: dict) -> dict:
        if settings.database_type != "sqlite":
            result = self.client.table("messages").insert(message).execute()
            return result.data[0]

        now = datetime.now(timezone.utc).isoformat()
        msg_id = message.get("id") or str(uuid.uuid4())
        session_id = message.get("session_id")
        task_id = message.get("task_id")
        role = message.get("role")
        content = message.get("content")
        ant_type = message.get("ant_type")
        created_at = message.get("created_at") or now

        with self._conn() as conn:
            conn.execute(
                """INSERT INTO messages (id, session_id, task_id, role, content, ant_type, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (msg_id, session_id, task_id, role, content, ant_type, created_at),
            )
            row = conn.execute("SELECT * FROM messages WHERE id = ?", (msg_id,)).fetchone()
            return self._row_to_dict(row, "messages")

    def get_messages_for_session(self, session_id: str) -> list[dict]:
        if settings.database_type != "sqlite":
            result = (
                self.client.table("messages")
                .select("*")
                .eq("session_id", session_id)
                .order("created_at")
                .execute()
            )
            return result.data

        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at", (session_id,)
            ).fetchall()
            return [self._row_to_dict(r, "messages") for r in rows]
