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

"""Case file service for the Test Case Center (fork extension).

Pure standard library: reads .xlsx / .csv case workbooks (Excel-compatible
sheet produced from the template in the repo) and writes result workbooks.
No third-party spreadsheet dependency is introduced on purpose, so the fork
keeps the upstream dependency surface untouched.

Expected columns (header row, CN or EN aliases, any order):
    用例编号 / case id | 用例标题 / title | 所属模块 / module | 前置条件 /
    precondition | 用例步骤 / steps | 预期结果 / expected | 优先级 / priority |
    备注 / notes
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from xml.etree import ElementTree as ET

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

_HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "case_id": ("用例编号", "用例id", "编号", "caseid", "case id", "id"),
    "title": ("用例标题", "标题", "用例名称", "title", "case title"),
    "module": ("所属模块", "模块", "module"),
    "precondition": ("前置条件", "precondition", "preconditions"),
    "steps": ("用例步骤", "操作步骤", "步骤", "steps", "case steps"),
    "expected": ("预期结果", "预期", "expected", "expected result"),
    "priority": ("优先级", "priority"),
    "notes": ("备注", "notes", "remark"),
}


def _norm(value) -> str:
    return re.sub(r"[\s_]", "", str(value or "")).lower()


def _split_lines(cell) -> list[str]:
    """Split a cell into clean numbered-free lines."""
    out: list[str] = []
    for raw in str(cell or "").splitlines():
        line = re.sub(r"^\s*(?:[0-9]+[\.、)）]|[-*•])\s*", "", raw.strip())
        if line:
            out.append(line)
    return out


def _parse_col_letter(ref: str) -> int:
    """A1-style column letters -> 0-based index (A=0, Z=25, AA=26)."""
    idx = 0
    for ch in ref:
        if ch.isalpha():
            idx = idx * 26 + (ord(ch.upper()) - ord("A") + 1)
        else:
            break
    return idx - 1 if idx else 0


def _col_name(idx: int) -> str:
    name = ""
    idx += 1
    while idx:
        idx, rem = divmod(idx - 1, 26)
        name = chr(65 + rem) + name
    return name


def _read_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    try:
        data = zf.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(data)
    strings: list[str] = []
    for si in root.findall(f"{NS}si"):
        parts = [t.text or "" for t in si.iter(f"{NS}t")]
        strings.append("".join(parts))
    return strings


def _first_sheet_path(zf: zipfile.ZipFile) -> str | None:
    candidates = sorted(n for n in zf.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml", n))
    return candidates[0] if candidates else None


def _read_xlsx_grid(content: bytes) -> list[list[str]]:
    zf = zipfile.ZipFile(io.BytesIO(content))
    shared = _read_shared_strings(zf)
    sheet_path = _first_sheet_path(zf)
    if sheet_path is None:
        raise ValueError("no worksheet found in xlsx file")
    root = ET.fromstring(zf.read(sheet_path))
    grid: list[list[str]] = []
    for row_el in root.iter(f"{NS}row"):
        cells: dict[int, str] = {}
        for c in row_el.findall(f"{NS}c"):
            ref = c.get("r") or ""
            idx = _parse_col_letter(ref) if ref else len(cells)
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


def _read_csv_grid(content: bytes) -> list[list[str]]:
    text = content.decode("utf-8-sig", errors="replace")
    rows: list[list[str]] = []
    for row in csv.reader(io.StringIO(text)):
        if any(cell.strip() for cell in row):
            rows.append([cell.strip() for cell in row])
    return rows


def _map_header(header_row: list[str]) -> dict[int, str]:
    mapping: dict[int, str] = {}
    for idx, raw in enumerate(header_row):
        key = _norm(raw)
        for field, aliases in _HEADER_ALIASES.items():
            if key in {_norm(a) for a in aliases}:
                mapping[idx] = field
                break
    return mapping


def _cell(grid_row: list[str] | None, idx: int) -> str:
    if not grid_row or idx >= len(grid_row):
        return ""
    return str(grid_row[idx] or "").strip()


def parse_case_file(filename: str, content: bytes) -> dict:
    """Parse an xlsx/csv workbook into normalized case dicts."""
    lowered = (filename or "").lower()
    if lowered.endswith(".csv") or not content[:4]:
        grid = _read_csv_grid(content)
    else:
        grid = _read_xlsx_grid(content)
    if not grid:
        raise ValueError("workbook is empty")

    header_idx = None
    for i, row in enumerate(grid[:10]):
        if len(_map_header(row)) >= 2:
            header_idx = i
            break
    if header_idx is None:
        raise ValueError(
            "header row with at least two known columns not found; "
            "use the template (模板 button) for the expected layout"
        )
    mapping = _map_header(grid[header_idx])
    if "steps" not in mapping.values() or "expected" not in mapping.values():
        raise ValueError("workbook must contain 用例步骤/steps and 预期结果/expected columns")

    cases: list[dict] = []
    warnings: list[str] = []
    for offset, row in enumerate(grid[header_idx + 1:]):
        values = {field: _cell(row, idx) for idx, field in mapping.items()}
        title = values.get("title", "")
        steps = _split_lines(values.get("steps", ""))
        expected = _split_lines(values.get("expected", ""))
        if not title and not steps:
            continue
        if not title:
            warnings.append(f"row {header_idx + 2 + offset}: 用例标题为空，已用步骤首行代替")
            title = steps[0] if steps else f"CASE-00{len(cases) + 1}"
        case_id = values.get("case_id", "") or f"CASE-{len(cases) + 1:03d}"
        cases.append(
            {
                "case_id": case_id,
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
        raise ValueError("no case rows found below the header")
    return {"cases": cases, "warnings": warnings}


def render_case_goal(case: dict, index: int, total: int) -> str:
    """Render one case into the structured goal text dispatched to the agent.

    Template (see docs/case-center.md):
        【用例 {id}】{title}
        [前置条件] ...
        [操作步骤] numbered lines
        [预期结果] verify:/assert: lines
    """
    lines: list[str] = []
    header = f"【用例 {case['case_id']}】{case['title']}"
    if total > 1:
        header += f"（批次 {index + 1}/{total}）"
    lines.append(header)
    precond = str(case.get("precondition") or "").strip()
    if precond:
        lines.append(f"[前置条件] {precond}")
        lines.append("（执行前先确认该状态成立；若不成立，记录 BLOCKED 并停止，不要继续后续步骤）")
    else:
        lines.append("[前置条件] 无")
    lines.append("[操作步骤]")
    for i, step in enumerate(case.get("steps") or [], start=1):
        lines.append(f"{i}. {step}")
    lines.append("[预期结果]")
    expected = case.get("expected") or []
    if not expected:
        lines.append("verify: 操作完成后系统无报错，界面状态符合用例标题描述")
    for exp in expected:
        if exp.lower().startswith(("assert:", "verify:")):
            lines.append(exp)
        else:
            lines.append(f"verify: {exp}")
    lines.append(
        "完成后在最终答复中明确给出结论：全部预期满足则 PASS，否则 FAIL 并逐条列出未满足的预期项。"
    )
    return "\n".join(lines)


def write_results_xlsx(rows: list[list[str]], sheet_name: str = "results") -> bytes:
    """Minimal Excel-compatible writer (inline strings, single sheet)."""

    def esc(text) -> str:
        return (
            str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    def cell_xml(col: int, row_no: int, value) -> str:
        ref = f"{_col_name(col)}{row_no}"
        return (
            f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{esc(value)}</t></is></c>'
        )

    sheet_rows = []
    for r, row in enumerate(rows, start=1):
        cells = "".join(cell_xml(c, r, v) for c, v in enumerate(row))
        sheet_rows.append(f'<row r="{r}">{cells}</row>')

    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(sheet_rows)}</sheetData></worksheet>'
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets><sheet name="{esc(sheet_name)}" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    wb_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheets" '
        'Target="worksheets/sheet1.xml"/></Relationships>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
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


TEMPLATE_ROWS: list[list[str]] = [
    ["用例编号", "用例标题", "所属模块", "前置条件", "用例步骤", "预期结果", "优先级", "备注"],
    [
        "TC-001",
        "示例：打开设置查看电量",
        "系统设置",
        "设备已解锁并在主屏幕",
        "1. 打开应用\n2. 进入设置\n3. 进入电池页面",
        "verify: 电池页面显示电量百分比",
        "P0",
        "示例行，导入前请删除",
    ],
]
