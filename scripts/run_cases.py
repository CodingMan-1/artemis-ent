#!/usr/bin/env python3
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

"""CI runner for the Test Case Center (fork extension).

Runs an Excel/CSV case workbook against a live Artemis host via the
artemis-client SDK, one case per session (sequential), and exports a
result xlsx. Exit code 1 when any case is FAIL/ERROR (CI-friendly).

Usage:
    uv run python scripts/run_cases.py cases.xlsx \
        --base-url http://127.0.0.1:8000 --profile pro \
        --verification-level strict --output results.xlsx
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import io
import json
import os
import re
import sys
import time
import zipfile
from xml.etree import ElementTree as ET

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


# ---------------------------------------------------------------- xlsx read
def _norm(value) -> str:
    return re.sub(r"[\s_]", "", str(value or "")).lower()


def _split_lines(cell) -> list[str]:
    out = []
    for raw in str(cell or "").splitlines():
        line = re.sub(r"^\s*(?:[0-9]+[\.、)）]|[-*•])\s*", "", raw.strip())
        if line:
            out.append(line)
    return out


def _read_xlsx_grid(content: bytes) -> list[list[str]]:
    zf = zipfile.ZipFile(io.BytesIO(content))
    try:
        shared_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    except KeyError:
        shared_root = None
    shared = [
        "".join(t.text or "" for t in si.iter(f"{NS}t"))
        for si in shared_root.findall(f"{NS}si")
    ] if shared_root is not None else []
    sheet = sorted(n for n in zf.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml", n))
    if not sheet:
        raise ValueError("no worksheet found")
    root = ET.fromstring(zf.read(sheet[0]))
    grid: list[list[str]] = []
    for row_el in root.iter(f"{NS}row"):
        cells: dict[int, str] = {}
        for c in row_el.findall(f"{NS}c"):
            ref = c.get("r") or ""
            idx = 0
            for ch in ref:
                if ch.isalpha():
                    idx = idx * 26 + (ord(ch.upper()) - ord("A") + 1)
                else:
                    break
            idx = (idx - 1) if idx else len(cells)
            ctype = c.get("t")
            value = ""
            if ctype == "inlineStr":
                is_el = c.find(f"{NS}is")
                if is_el is not None:
                    value = "".join(t.text or "" for t in is_el.iter(f"{NS}t"))
            else:
                v_el = c.find(f"{NS}v")
                if v_el is not None and v_el.text is not None:
                    value = v_el.text
                    if ctype == "s":
                        try:
                            value = shared[int(value)]
                        except (ValueError, IndexError):
                            value = ""
            cells[idx] = value
        if cells:
            width = max(cells) + 1
            grid.append([cells.get(i, "") for i in range(width)])
    return grid


def _read_grid(filename: str, content: bytes) -> list[list[str]]:
    if filename.lower().endswith(".csv"):
        text = content.decode("utf-8-sig", errors="replace")
        rows = []
        for row in csv.reader(io.StringIO(text)):
            if any(cell.strip() for cell in row):
                rows.append([cell.strip() for cell in row])
        return rows
    return _read_xlsx_grid(content)


ALIASES: dict[str, tuple[str, ...]] = {
    "case_id": ("用例编号", "用例id", "编号", "caseid", "case id", "id"),
    "title": ("用例标题", "标题", "用例名称", "title", "case title"),
    "module": ("所属模块", "模块", "module"),
    "precondition": ("前置条件", "precondition", "preconditions"),
    "steps": ("用例步骤", "操作步骤", "步骤", "steps", "case steps"),
    "expected": ("预期结果", "预期", "expected", "expected result"),
    "priority": ("优先级", "priority"),
    "notes": ("备注", "notes", "remark"),
}


def load_cases(filename: str) -> list[dict]:
    with open(filename, "rb") as fh:
        grid = _read_grid(filename, fh.read())
    if not grid:
        raise SystemExit("workbook is empty")
    header_idx = None
    for i, row in enumerate(grid[:10]):
        mapping = {}
        for idx, raw in enumerate(row):
            key = _norm(raw)
            for field, aliases in ALIASES.items():
                if key in {_norm(a) for a in aliases}:
                    mapping[idx] = field
                    break
        if len(mapping) >= 2:
            header_idx = i
            break
    if header_idx is None:
        raise SystemExit("header row not found; use the template layout")
    mapping = {}
    for idx, raw in enumerate(grid[header_idx]):
        key = _norm(raw)
        for field, aliases in ALIASES.items():
            if key in {_norm(a) for a in aliases}:
                mapping[idx] = field
                break
    cases = []
    for row in grid[header_idx + 1:]:
        values = {f: (row[i] if i < len(row) else "").strip() for i, f in mapping.items()}
        title = values.get("title", "")
        steps = _split_lines(values.get("steps", ""))
        expected = _split_lines(values.get("expected", ""))
        if not title and not steps:
            continue
        if not title:
            title = steps[0] if steps else f"CASE-{len(cases) + 1:03d}"
        cases.append(
            {
                "case_id": values.get("case_id", "") or f"CASE-{len(cases) + 1:03d}",
                "title": title,
                "module": values.get("module", ""),
                "precondition": values.get("precondition", ""),
                "steps": steps,
                "expected": expected,
                "priority": values.get("priority", ""),
                "notes": values.get("notes", ""),
                "expected_text": "\n".join(expected),
            }
        )
    if not cases:
        raise SystemExit("no case rows found")
    return cases


# ---------------------------------------------------------------- goal text
def render_case_goal(case: dict, index: int, total: int) -> str:
    lines = [f"【用例 {case['case_id']}】{case['title']}" + (f"（批次 {index + 1}/{total}）" if total > 1 else "")]
    precond = (case.get("precondition") or "").strip()
    if precond:
        lines.append(f"[前置条件] {precond}")
        lines.append("（执行前先确认该状态成立；若不成立，记录 BLOCKED 并停止，不要继续后续步骤）")
    else:
        lines.append("[前置条件] 无")
    lines.append("[操作步骤]")
    for i, step in enumerate(case.get("steps") or [], start=1):
        lines.append(f"{i}. {step}")
    lines.append("[预期结果]")
    if not case.get("expected"):
        lines.append("verify: 操作完成后系统无报错，界面状态符合用例标题描述")
    for exp in case.get("expected") or []:
        lines.append(exp if exp.lower().startswith(("assert:", "verify:")) else f"verify: {exp}")
    lines.append("完成后在最终答复中明确给出结论：全部预期满足则 PASS，否则 FAIL 并逐条列出未满足的预期项。")
    return "\n".join(lines)


def verdict_from(result) -> tuple[str, str]:
    """(verdict, note) from an artemis-client TaskResult."""
    status = (result.status or "").lower()
    if status in ("queued", "pending"):
        return "QUEUED", ""
    if status == "running":
        return "RUNNING", ""
    if status in ("rejected", "cancelled", "error"):
        return "ERROR", result.error or status
    output = result.output
    tests = {}
    if isinstance(output, dict):
        tests = (output.get("test_summary") or {}).get("tests") or {}
        if not tests:
            tests = output.get("test_summary") or {}
    failed = int(tests.get("failed") or 0)
    unchecked = int(tests.get("unchecked") or 0)
    inconclusive = int(tests.get("inconclusive") or 0)
    if status == "completed":
        if failed > 0:
            return "FAIL", f"{failed} 条预期未满足"
        if unchecked > 0 or inconclusive > 0:
            return "INCONCLUSIVE", f"unchecked={unchecked} inconclusive={inconclusive}"
        return "PASS", ""
    return "FAIL", result.error or status


# ---------------------------------------------------------------- xlsx out
def _col_name(idx: int) -> str:
    name = ""
    idx += 1
    while idx:
        idx, rem = divmod(idx - 1, 26)
        name = chr(65 + rem) + name
    return name


def write_results_xlsx(rows: list[list[str]]) -> bytes:
    def esc(text) -> str:
        return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

    sheet_rows = []
    for r, row in enumerate(rows, start=1):
        cells = "".join(
            f'<c r="{_col_name(c)}{r}" t="inlineStr"><is><t xml:space="preserve">{esc(v)}</t></is></c>'
            for c, v in enumerate(row)
        )
        sheet_rows.append(f'<row r="{r}">{cells}</row>')
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(sheet_rows)}</sheetData></worksheet>'
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="results" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    wb_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheets" '
        'Target="worksheets/sheet1.xml"/></Relationships>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/></Relationships>'
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", root_rels)
        zf.writestr("xl/workbook.xml", workbook)
        zf.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        zf.writestr("xl/worksheets/sheet1.xml", sheet)
    return buf.getvalue()


# ---------------------------------------------------------------- main
async def run_case(client, case: dict, index: int, total: int, profile: str,
                   verification_level: str | None, poll: float, timeout: float):
    goal = render_case_goal(case, index, total)
    started = time.time()
    handle = await client.submit(
        goal,
        profile=profile,
        expected_output=case.get("expected_text") or None,
        verification_level=verification_level,
    )
    deadline = time.time() + timeout
    result = None
    while time.time() < deadline:
        result = await client.get_task(handle.task_id)
        if result.done:
            break
        await asyncio.sleep(poll)
    if result is None or not result.done:
        return "ERROR", f"timeout after {timeout:.0f}s", started
    verdict, note = verdict_from(result)
    return verdict, note, started


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run an Excel/CSV case workbook against Artemis.")
    parser.add_argument("workbook", help="path to .xlsx / .csv case file")
    parser.add_argument("--base-url", default=os.environ.get("ARTEMIS_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--profile", default="pro", choices=["flash", "pro"])
    parser.add_argument("--verification-level", default="strict",
                        choices=["off", "final", "checkpoints", "strict"],
                        help="Pro-profile checker preset (ignored for flash)")
    parser.add_argument("--cases", default="", help="comma separated case ids to run (default: all)")
    parser.add_argument("--poll", type=float, default=10.0, help="poll interval seconds")
    parser.add_argument("--timeout", type=float, default=1800.0, help="per-case timeout seconds")
    parser.add_argument("--output", default="case-results.xlsx")
    args = parser.parse_args()

    try:
        from artemis_client import ArtemisClient
    except ImportError:
        print("artemis-client is not installed; run inside the artemis venv (uv run python ...)", file=sys.stderr)
        return 2

    cases = load_cases(args.workbook)
    if args.cases:
        wanted = {c.strip() for c in args.cases.split(",") if c.strip()}
        cases = [c for c in cases if c["case_id"] in wanted]
    print(f"loaded {len(cases)} case(s) from {args.workbook}")

    client = ArtemisClient(base_url=args.base_url)
    results: list[dict] = []
    total = len(cases)
    for index, case in enumerate(cases, start=1):
        print(f"[{index}/{total}] {case['case_id']} {case['title']} ...", flush=True)
        try:
            verdict, note, started = await run_case(
                client, case, index, total, args.profile, args.verification_level, args.poll, args.timeout
            )
        except Exception as exc:  # noqa: BLE001
            verdict, note, started = "ERROR", str(exc), time.time()
        elapsed = round(time.time() - started, 1)
        results.append({"case": case, "verdict": verdict, "note": note, "elapsed": elapsed})
        print(f"    -> {verdict} ({elapsed}s) {note}", flush=True)

    rows = [["用例编号", "用例标题", "所属模块", "判定", "说明", "耗时(秒)"]]
    for r in results:
        c = r["case"]
        rows.append([c["case_id"], c["title"], c.get("module", ""), r["verdict"], r["note"], r["elapsed"]])
    with open(args.output, "wb") as fh:
        fh.write(write_results_xlsx(rows))
    failed = [r for r in results if r["verdict"] in ("FAIL", "ERROR")]
    print(f"summary: pass={sum(1 for r in results if r['verdict'] == 'PASS')} "
          f"fail={sum(1 for r in results if r['verdict'] == 'FAIL')} "
          f"inconclusive={sum(1 for r in results if r['verdict'] == 'INCONCLUSIVE')} "
          f"error={sum(1 for r in results if r['verdict'] == 'ERROR')}")
    print(f"results written to {args.output}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
