from __future__ import annotations
from datetime import datetime
from supabase import create_client, Client
from .config import settings


class DatabaseClient:
    _instance: "DatabaseClient | None" = None
    _client: Client | None = None

    @classmethod
    def get(cls) -> "DatabaseClient":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def client(self) -> Client:
        if self._client is None:
            self._client = create_client(
                settings.supabase_url,
                settings.supabase_service_role_key,
            )
        return self._client

    # ── Sessions ──────────────────────────────────────────────────────────────

    def create_session(self, session_id: str, title: str) -> dict:
        result = self.client.table("sessions").insert(
            {"id": session_id, "title": title}
        ).execute()
        return result.data[0]

    def get_session(self, session_id: str) -> dict | None:
        result = self.client.table("sessions").select("*").eq("id", session_id).execute()
        return result.data[0] if result.data else None

    def list_sessions(self, limit: int = 20) -> list[dict]:
        result = (
            self.client.table("sessions")
            .select("*")
            .order("updated_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data

    def update_session(self, session_id: str, updates: dict) -> dict:
        result = (
            self.client.table("sessions")
            .update(updates)
            .eq("id", session_id)
            .execute()
        )
        return result.data[0]

    # ── Tasks ─────────────────────────────────────────────────────────────────

    def create_task(self, task: dict) -> dict:
        result = self.client.table("tasks").insert(task).execute()
        return result.data[0]

    def update_task(self, task_id: str, updates: dict) -> dict:
        result = (
            self.client.table("tasks")
            .update(updates)
            .eq("id", task_id)
            .execute()
        )
        return result.data[0]

    def get_tasks_for_session(self, session_id: str) -> list[dict]:
        result = (
            self.client.table("tasks")
            .select("*")
            .eq("session_id", session_id)
            .order("created_at")
            .execute()
        )
        return result.data

    def get_task(self, task_id: str) -> dict | None:
        result = self.client.table("tasks").select("*").eq("id", task_id).execute()
        return result.data[0] if result.data else None

    # ── Agent runs ────────────────────────────────────────────────────────────

    def create_agent_run(self, run: dict) -> dict:
        result = self.client.table("agent_runs").insert(run).execute()
        return result.data[0]

    def update_agent_run(self, run_id: str, updates: dict) -> dict:
        result = (
            self.client.table("agent_runs")
            .update(updates)
            .eq("id", run_id)
            .execute()
        )
        return result.data[0]

    def get_runs_for_task(self, task_id: str) -> list[dict]:
        result = (
            self.client.table("agent_runs")
            .select("*")
            .eq("task_id", task_id)
            .order("started_at")
            .execute()
        )
        return result.data

    # ── Messages ──────────────────────────────────────────────────────────────

    def append_message(self, message: dict) -> dict:
        result = self.client.table("messages").insert(message).execute()
        return result.data[0]

    def get_messages_for_session(self, session_id: str) -> list[dict]:
        result = (
            self.client.table("messages")
            .select("*")
            .eq("session_id", session_id)
            .order("created_at")
            .execute()
        )
        return result.data
