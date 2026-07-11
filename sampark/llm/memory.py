from __future__ import annotations

import json
import sqlite3
import threading
from typing import Any

from sampark.core.models import SamparkRun

_SCHEMA = """
CREATE TABLE IF NOT EXISTS episodic_runs (
    run_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    audit_id          TEXT NOT NULL UNIQUE,
    customer_id       TEXT NOT NULL,
    customer_language TEXT NOT NULL,
    goal              TEXT NOT NULL,
    outcome_status    TEXT NOT NULL,
    step_count        INTEGER NOT NULL,
    blocked_count     INTEGER NOT NULL,
    completed_count   INTEGER NOT NULL,
    skeleton_json     TEXT NOT NULL,
    created_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_episodic_runs_language ON episodic_runs(customer_language);
"""


class EpisodicMemory:
    """SQLite-backed persistence for SamparkRun outcomes -- a drop-in
    replacement for the old in-memory LearningStore. `.record(run)` returns
    the SAME dict shape LearningStore did (runs_recorded,
    completed_or_ready_steps, blocked_steps, language_mix, learning_signal),
    now computed via aggregate SQL over a persisted table instead of an
    in-memory list, so callers and existing tests don't need to change.

    Defaults to an in-memory (":memory:") database when no path is given --
    this reproduces the old per-instance-scoped counting behavior exactly,
    since every existing test constructs a fresh bare SamparkOrchestrator().

    Thread-safety: run_demo.py uses ThreadingHTTPServer, so multiple request
    threads may call .record() concurrently. sqlite3 connections are not
    thread-safe by default; this class opens one connection with
    check_same_thread=False and serializes reads/writes through a
    threading.Lock -- correct and simple at hackathon-demo request volume,
    not a production-scale design.
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def record(self, run: SamparkRun) -> dict[str, Any]:
        skeleton = self._skeletonize(run)
        completed = sum(1 for step in run.steps if step.status != "blocked")
        blocked = sum(1 for step in run.steps if step.status == "blocked")

        with self._lock:
            self._conn.execute(
                "INSERT INTO episodic_runs "
                "(audit_id, customer_id, customer_language, goal, outcome_status, "
                " step_count, blocked_count, completed_count, skeleton_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run.audit_id,
                    run.customer.customer_id,
                    run.customer.language,
                    run.goal,
                    run.outcome["journey_status"],
                    len(run.steps),
                    blocked,
                    completed,
                    json.dumps(skeleton),
                    run.created_at,
                ),
            )
            self._conn.commit()
            (runs_recorded,) = self._conn.execute("SELECT COUNT(*) FROM episodic_runs").fetchone()
            rows = self._conn.execute(
                "SELECT customer_language, COUNT(*) FROM episodic_runs GROUP BY customer_language"
            ).fetchall()

        return {
            "runs_recorded": runs_recorded,
            "completed_or_ready_steps": completed,
            "blocked_steps": blocked,
            "language_mix": dict(rows),
            "learning_signal": "Update next-best-action timing, language, and channel from outcome feedback.",
        }

    def stats(self) -> dict[str, Any]:
        """Aggregate outlet-level performance view, beyond the per-record
        shape .record() returns -- used by /api/health-style diagnostics
        and future analytics, not required by any existing test."""
        with self._lock:
            (total,) = self._conn.execute("SELECT COUNT(*) FROM episodic_runs").fetchone()
            (blocked_total,) = self._conn.execute(
                "SELECT COALESCE(SUM(blocked_count), 0) FROM episodic_runs"
            ).fetchone()
            (completed_total,) = self._conn.execute(
                "SELECT COALESCE(SUM(completed_count), 0) FROM episodic_runs"
            ).fetchone()
        return {
            "runs_recorded": total,
            "total_blocked_steps": blocked_total,
            "total_completed_steps": completed_total,
        }

    def _skeletonize(self, run: SamparkRun) -> dict[str, Any]:
        """Compresses one SamparkRun into a small structured trace -- goal,
        step titles/statuses, verification pass/fail -- NOT the full LLM
        prompt/response text, keeping the persisted footprint small and
        avoiding storing more customer-identifying free text than needed."""
        return {
            "goal": run.goal,
            "steps": [{"title": s.title, "status": s.status, "agent": s.agent} for s in run.steps],
            "verification_passed": run.verification.get("passed"),
        }

    def close(self) -> None:
        self._conn.close()
