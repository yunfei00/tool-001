from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable


class RunStatus(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    STOPPED = "stopped"


class ComboResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"


@dataclass(frozen=True)
class TestContext:
    project_name: str
    band: str
    frequency: str


@dataclass(frozen=True)
class TestRun:
    run_id: int
    context: TestContext
    power: float
    param_schema_hash: str
    status: RunStatus
    started_at: str
    finished_at: str | None


@dataclass(frozen=True)
class PlanDetails:
    current_set: set[str]
    inherited_set: set[str]
    new_set: set[str]
    plan_set: set[str]
    base_run: TestRun | None


class AutoTestRepository:
    """SQLite storage for incremental auto-test planning and run history."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS test_run (
                    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_name TEXT NOT NULL,
                    band TEXT NOT NULL,
                    frequency TEXT NOT NULL,
                    power REAL NOT NULL,
                    param_schema_hash TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    status TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_test_run_context_power
                ON test_run(project_name, band, frequency, power);

                CREATE TABLE IF NOT EXISTS combo_catalog (
                    project_name TEXT NOT NULL,
                    band TEXT NOT NULL,
                    frequency TEXT NOT NULL,
                    combo_id TEXT NOT NULL,
                    combo_json TEXT NOT NULL,
                    created_in_run_id INTEGER NOT NULL,
                    PRIMARY KEY (project_name, band, frequency, combo_id),
                    FOREIGN KEY(created_in_run_id) REFERENCES test_run(run_id)
                );

                CREATE INDEX IF NOT EXISTS idx_combo_catalog_context_combo
                ON combo_catalog(project_name, band, frequency, combo_id);

                CREATE TABLE IF NOT EXISTS combo_result (
                    run_id INTEGER NOT NULL,
                    combo_id TEXT NOT NULL,
                    result TEXT NOT NULL,
                    detail TEXT,
                    timestamp TEXT NOT NULL,
                    PRIMARY KEY (run_id, combo_id),
                    FOREIGN KEY(run_id) REFERENCES test_run(run_id)
                );

                CREATE INDEX IF NOT EXISTS idx_combo_result_run_combo
                ON combo_result(run_id, combo_id);
                """
            )

    def create_run(
        self,
        context: TestContext,
        power: float,
        param_schema_hash: str,
        status: RunStatus = RunStatus.RUNNING,
    ) -> int:
        started_at = _now_iso()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO test_run(
                    project_name, band, frequency, power, param_schema_hash,
                    started_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    context.project_name,
                    context.band,
                    context.frequency,
                    power,
                    param_schema_hash,
                    started_at,
                    status.value,
                ),
            )
            return int(cursor.lastrowid)

    def finish_run(self, run_id: int, status: RunStatus) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE test_run SET status = ?, finished_at = ? WHERE run_id = ?",
                (status.value, _now_iso(), run_id),
            )

    def upsert_combo_catalog(
        self,
        context: TestContext,
        combo_id: str,
        combo_payload: dict[str, Any],
        run_id: int,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO combo_catalog(
                    project_name, band, frequency, combo_id, combo_json, created_in_run_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_name, band, frequency, combo_id)
                DO UPDATE SET combo_json = excluded.combo_json
                """,
                (
                    context.project_name,
                    context.band,
                    context.frequency,
                    combo_id,
                    canonical_combo_json(combo_payload),
                    run_id,
                ),
            )

    def record_combo_result(
        self,
        run_id: int,
        combo_id: str,
        result: ComboResult,
        detail: str = "",
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO combo_result(run_id, combo_id, result, detail, timestamp)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(run_id, combo_id)
                DO UPDATE SET
                    result = excluded.result,
                    detail = excluded.detail,
                    timestamp = excluded.timestamp
                """,
                (run_id, combo_id, result.value, detail, _now_iso()),
            )

    def find_latest_base_run(self, context: TestContext, target_power: float) -> TestRun | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM test_run
                WHERE project_name = ?
                  AND band = ?
                  AND frequency = ?
                  AND power < ?
                  AND status IN (?, ?)
                ORDER BY power DESC, run_id DESC
                LIMIT 1
                """,
                (
                    context.project_name,
                    context.band,
                    context.frequency,
                    target_power,
                    RunStatus.SUCCESS.value,
                    RunStatus.PARTIAL.value,
                ),
            ).fetchone()
        return _row_to_test_run(row) if row else None

    def load_pass_set(self, run_id: int) -> set[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT combo_id FROM combo_result WHERE run_id = ? AND result = ?",
                (run_id, ComboResult.PASS.value),
            ).fetchall()
        return {str(row["combo_id"]) for row in rows}

    def load_historical_known_set(self, context: TestContext) -> set[str]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT combo_id FROM combo_catalog
                WHERE project_name = ? AND band = ? AND frequency = ?
                """,
                (context.project_name, context.band, context.frequency),
            ).fetchall()
        return {str(row["combo_id"]) for row in rows}


class AutoTestPlanner:
    """Build executable PlanSet using inherited PASS combinations + newly added combinations."""

    def __init__(self, repository: AutoTestRepository) -> None:
        self._repository = repository

    def build_plan(
        self,
        context: TestContext,
        target_power: float,
        current_combo_ids: Iterable[str],
    ) -> PlanDetails:
        current_set = set(current_combo_ids)
        base_run = self._repository.find_latest_base_run(context, target_power)

        if base_run is None:
            return PlanDetails(
                current_set=current_set,
                inherited_set=set(),
                new_set=current_set,
                plan_set=current_set,
                base_run=None,
            )

        pass_set = self._repository.load_pass_set(base_run.run_id)
        inherited_set = current_set.intersection(pass_set)

        historical_known_set = self._repository.load_historical_known_set(context)
        new_set = current_set.difference(historical_known_set)

        plan_set = inherited_set.union(new_set)
        return PlanDetails(
            current_set=current_set,
            inherited_set=inherited_set,
            new_set=new_set,
            plan_set=plan_set,
            base_run=base_run,
        )


def canonical_combo_json(combo_payload: dict[str, Any]) -> str:
    return json.dumps(combo_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def combo_signature(combo_payload: dict[str, Any]) -> str:
    canonical = canonical_combo_json(combo_payload)
    return hashlib.sha1(canonical.encode("utf-8")).hexdigest()


def schema_signature(param_names: Iterable[str]) -> str:
    canonical = json.dumps(sorted(param_names), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha1(canonical.encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_test_run(row: sqlite3.Row) -> TestRun:
    return TestRun(
        run_id=int(row["run_id"]),
        context=TestContext(
            project_name=str(row["project_name"]),
            band=str(row["band"]),
            frequency=str(row["frequency"]),
        ),
        power=float(row["power"]),
        param_schema_hash=str(row["param_schema_hash"]),
        status=RunStatus(str(row["status"])),
        started_at=str(row["started_at"]),
        finished_at=str(row["finished_at"]) if row["finished_at"] else None,
    )
