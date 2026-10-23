# Copyright 2026 Artemis-Ent Fork (based on google/artemis)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Test Case Center router (fork extension).

Excel/CSV workbooks (precondition / steps / expected) are parsed into
structured goals, dispatched through the existing task queue (one session
per case), tracked, and exported back to xlsx.

Endpoints:
    POST /api/cases/import            upload + parse a workbook
    GET  /api/cases/workbook          currently loaded workbook
    GET  /api/cases/template          download the case template xlsx
    POST /api/cases/run               dispatch selected cases as a batch
    GET  /api/cases/batches           all known batches with live verdicts
    GET  /api/cases/batches/{id}      one batch
    GET  /api/cases/export?batch_id=  download result xlsx

Batch metadata is kept in process memory (MVP). Session rows and
run_outcome.json in the traces directory are the source of truth for
status and verdicts, so the UI survives console restarts as long as the
traces directory is intact.
"""

from __future__ import annotations

import base64
import itertools
import time
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

try:
    from admin_console.database.repositories.session_repository import session_repo
    from admin_console.services.case_file_service import (
        TEMPLATE_ROWS,
        parse_case_file,
        render_case_goal,
        write_results_xlsx,
    )
    from admin_console.services.task_queue_service import task_queue_service
except ImportError:
    from apps.admin_console.database.repositories.session_repository import session_repo
    from apps.admin_console.services.case_file_service import (
        TEMPLATE_ROWS,
        parse_case_file,
        render_case_goal,
        write_results_xlsx,
    )
    from apps.admin_console.services.task_queue_service import task_queue_service

router = APIRouter(tags=["cases"])

_workbook: list[dict[str, Any]] = []
_batches: dict[str, dict[str, Any]] = {}
_batch_seq = itertools.count(1)


def _read_run_outcome(session_id: str) -> dict[str, Any] | None:
    """Load run_outcome.json (exit settlement) for one session, if present."""
    try:
        from artemis.config import TRACES_PATH

        import json
        import os

        path = os.path.join(TRACES_PATH, str(session_id), "run_outcome.json")
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def _verdict(session: dict[str, Any] | None, outcome: dict[str, Any] | None) -> str:
    """Plan 00 §2.5: completed && failed==0 && unchecked==0 -> PASS; failed>0
    or session failed -> FAIL; inconclusive/unchecked>0 -> INCONCLUSIVE;
    rejected/error -> ERROR; otherwise RUNNING/QUEUED/NOT_RUN."""
    status = str((session or {}).get("status") or "pending").lower()
    if status in ("queued", "pending"):
        return "QUEUED"
    if status in ("running",):
        return "RUNNING"
    if status in ("rejected", "error", "cancelled"):
        return "ERROR"
    tests = (outcome or {}).get("tests") or {}
    failed = int(tests.get("failed") or 0)
    unchecked = int(tests.get("unchecked") or 0)
    inconclusive = int(tests.get("inconclusive") or 0)
    if status == "completed":
        if failed > 0:
            return "FAIL"
        if unchecked > 0 or inconclusive > 0:
            return "INCONCLUSIVE"
        return "PASS"
    return "FAIL"


def _enrich_batch(batch: dict[str, Any]) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    for item in batch["cases"]:
        session_id = item.get("session_id")
        session = session_repo.get_session_by_id(session_id) if session_id else None
        outcome = _read_run_outcome(session_id) if session_id else None
        verdict = _verdict(session, outcome)
        row_status = str((session or {}).get("status") or "not_run")
        start = (session or {}).get("start_time")
        end = (session or {}).get("end_time")
        elapsed = round(float(end) - float(start), 1) if (start and end) else None
        error = (session or {}).get("error")
        cases.append(
            {
                **item,
                "session": row_status,
                "verdict": verdict,
                "elapsed_seconds": elapsed,
                "error": error,
            }
        )
    verdicts = [c["verdict"] for c in cases]
    terminal = {"PASS", "FAIL", "INCONCLUSIVE", "ERROR"}
    batch["summary"] = {
        "total": len(cases),
        "passed": verdicts.count("PASS"),
        "failed": verdicts.count("FAIL"),
        "inconclusive": verdicts.count("INCONCLUSIVE"),
        "error": verdicts.count("ERROR"),
        "running": verdicts.count("RUNNING") + verdicts.count("QUEUED"),
        "not_run": verdicts.count("NOT_RUN"),
        "all_done": all(v in terminal for v in verdicts),
    }
    return batch


@router.get("/api/cases/template")
async def download_template():
    """The Excel-openable case template (same columns as the repo template csv)."""
    data = write_results_xlsx(TEMPLATE_ROWS, sheet_name="cases")
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="test-cases-template.xlsx"'},
    )


@router.post("/api/cases/import")
async def import_cases(payload: dict[str, Any]):
    filename = str(payload.get("filename") or "")
    content_b64 = payload.get("content_b64")
    text = payload.get("text")
    try:
        if content_b64:
            content = base64.b64decode(str(content_b64))
        elif text is not None:
            content = str(text).encode("utf-8")
        else:
            raise HTTPException(status_code=400, detail="content_b64 or text required")
        parsed = parse_case_file(filename, content)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    global _workbook
    _workbook = parsed["cases"]
    return {"count": len(_workbook), "cases": _workbook, "warnings": parsed.get("warnings", [])}


@router.get("/api/cases/workbook")
async def get_workbook():
    return {"count": len(_workbook), "cases": _workbook}


@router.post("/api/cases/run")
async def run_cases(payload: dict[str, Any]):
    if not _workbook:
        raise HTTPException(status_code=400, detail="import a workbook first (POST /api/cases/import)")
    case_ids = payload.get("case_ids")
    selected = [c for c in _workbook if not case_ids or c["case_id"] in case_ids]
    if not selected:
        raise HTTPException(status_code=400, detail="no matching case_ids")
    profile = str(payload.get("profile") or "pro")
    verification_level = payload.get("verification_level") or (
        "strict" if profile == "pro" else None
    )
    device_serial = payload.get("device_serial")

    batch_id = f"BATCH-{uuid.uuid4().hex[:8]}"
    batch = {
        "batch_id": batch_id,
        "seq": next(_batch_seq),
        "profile": profile,
        "verification_level": verification_level,
        "device_serial": device_serial,
        "started_at": time.time(),
        "cases": [],
    }
    total = len(selected)
    for index, case in enumerate(selected, start=1):
        goal = render_case_goal(case, index, total)
        expected = case.get("expected_text") or None
        try:
            result = await task_queue_service.enqueue_tasks(
                [goal],
                profile=profile,
                expected_output=expected,
                verification_level=verification_level,
                device_serial=device_serial,
                ingress="cases",
            )
        except Exception as exc:  # noqa: BLE001 - surface enqueue errors per case
            batch["cases"].append(
                {
                    "case_id": case["case_id"],
                    "title": case["title"],
                    "module": case.get("module", ""),
                    "expected_text": case.get("expected_text", ""),
                    "session_id": None,
                    "enqueue_error": str(exc),
                }
            )
            continue
        enqueued = (result or {}).get("tasks") or []
        session_id = enqueued[0].get("session_id") if enqueued else None
        if result.get("status") == "rejected":
            batch["cases"].append(
                {
                    "case_id": case["case_id"],
                    "title": case["title"],
                    "module": case.get("module", ""),
                    "expected_text": case.get("expected_text", ""),
                    "session_id": None,
                    "enqueue_error": str(result.get("error") or "rejected"),
                }
            )
            continue
        batch["cases"].append(
            {
                "case_id": case["case_id"],
                "title": case["title"],
                "module": case.get("module", ""),
                "expected_text": case.get("expected_text", ""),
                "session_id": session_id,
            }
        )
    _batches[batch_id] = batch
    return _enrich_batch(batch)


@router.get("/api/cases/batches")
async def list_batches():
    return [
        _enrich_batch(b)
        for b in sorted(_batches.values(), key=lambda b: b.get("seq") or 0, reverse=True)
    ]


@router.get("/api/cases/batches/{batch_id}")
async def get_batch(batch_id: str):
    batch = _batches.get(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="unknown batch")
    return _enrich_batch(batch)


@router.get("/api/cases/export")
async def export_batch(batch_id: str = Query(default="")):
    if batch_id:
        batch = _batches.get(batch_id)
        if not batch:
            raise HTTPException(status_code=404, detail="unknown batch")
    else:
        ordered = sorted(_batches.values(), key=lambda b: b.get("seq") or 0, reverse=True)
        if not ordered:
            raise HTTPException(status_code=400, detail="no batch to export yet")
        batch = ordered[0]
    enriched = _enrich_batch(batch)
    rows = [
        [
            "用例编号",
            "用例标题",
            "所属模块",
            "执行判定",
            "会话状态",
            "会话ID",
            "开始时间",
            "结束时间",
            "耗时(秒)",
            "预期结果",
            "错误信息",
        ]
    ]
    def _fmt_ts(value) -> str:
        try:
            return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(value)))
        except (TypeError, ValueError, OSError):
            return ""

    for item in enriched["cases"]:
        session_id = item.get("session_id") or ""
        session = session_repo.get_session_by_id(session_id) if session_id else None
        start = (session or {}).get("start_time")
        end = (session or {}).get("end_time")
        rows.append(
            [
                item.get("case_id", ""),
                item.get("title", ""),
                item.get("module", ""),
                item.get("verdict", ""),
                item.get("session", ""),
                session_id,
                _fmt_ts(start) if start else "",
                _fmt_ts(end) if end else "",
                item.get("elapsed_seconds") or "",
                item.get("expected_text", ""),
                item.get("error") or item.get("enqueue_error") or "",
            ]
        )
    data = write_results_xlsx(rows, sheet_name=enriched["batch_id"][:28] or "results")
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="case-results-{batch_id or "latest"}.xlsx"'},
    )
