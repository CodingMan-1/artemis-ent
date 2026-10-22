# 用例中心（Test Case Center）

> fork 扩展：Web UI 侧边栏新增"用例中心"区，把 Excel/CSV 测试用例
> （前置条件 / 用例步骤 / 预期结果）批量派发到 ARTEMIS，自动判定
> PASS / FAIL / INCONCLUSIVE / ERROR 并导出结果 xlsx。
> CI 侧提供等价的 `scripts/run_cases.py`（artemis-client SDK）。

## 1. 用例文件

列（表头支持中英文别名，顺序任意；模板点侧边栏"模板"按钮直接下载）：

| 用例编号 | 用例标题 | 所属模块 | 前置条件 | 用例步骤 | 预期结果 | 优先级 | 备注 |
|---|---|---|---|---|---|---|---|
| TC-001 | 打开设置查看电量 | 系统设置 | 设备已解锁在主屏幕 | 多行或 `1. 2. 3.` 编号 | 每行一条预期 | P0 | |

- 步骤/预期支持单元格内换行，自动去掉 `1.` / `1、` / `-` 编号前缀。
- 编号为空时自动按 `CASE-001` 递增。

## 2. Web UI 用法（admin console，默认 http://127.0.0.1:8000）

1. 侧边栏 **用例中心** → 导入 xlsx/csv → 表格显示解析结果（含警告）。
2. 选档位：**Pro · 严格校验**（默认，verification_level=strict）或 **Flash · 快速**。
3. **▶ 批量执行**：每条用例渲染成结构化 goal（见下）后进入既有任务队列，
   一条用例 = 一个 session，顺序执行；进度 5 秒轮询，判定列实时刷新。
4. 全部完成后 **导出结果** 下载 xlsx（编号/标题/模块/判定/会话ID/时间/耗时/预期/错误）。

goal 模板（`case_file_service.render_case_goal`）：

```
【用例 TC-001】打开设置查看电量（批次 1/3）
[前置条件] 设备已解锁在主屏幕
（执行前先确认该状态成立；若不成立，记录 BLOCKED 并停止，不要继续后续步骤）
[操作步骤]
1. 打开应用
2. 进入设置
[预期结果]
verify: 电池页面显示电量百分比
完成后在最终答复中明确给出结论：全部预期满足则 PASS，否则 FAIL 并逐条列出未满足的预期项。
```

## 3. 判定规则（与方案文档 §2.5 一致）

以 session 状态 + 退出结算 `run_outcome.json`（tests: passed/failed/inconclusive/unchecked）：

| 判定 | 条件 |
|---|---|
| PASS | status=completed 且 failed=0 且 unchecked=0 且 inconclusive=0 |
| FAIL | status=completed 且 failed>0；或 session failed/rejected |
| INCONCLUSIVE | completed 且 unchecked>0 或 inconclusive>0 |
| ERROR | rejected / error / cancelled |
| QUEUED / RUNNING | 尚未结束 |

## 4. API

```
POST /api/cases/import      {filename, content_b64} | {filename, text}
GET  /api/cases/workbook    当前已导入工作簿
GET  /api/cases/template   下载用例模板 xlsx
POST /api/cases/run        {case_ids?, profile, verification_level?, device_serial?}
GET  /api/cases/batches    全部批次（含实时判定）
GET  /api/cases/batches/{id}
GET  /api/cases/export?batch_id=   结果 xlsx
```

批次元数据存于进程内存（MVP）；判定与状态读自会话库与 traces 目录，
console 重启后 UI 自动恢复展示（工作簿需重新导入）。

## 5. CI 用法

```bash
uv run python scripts/run_cases.py cases.xlsx --profile pro --verification-level strict --output results.xlsx
# 有 FAIL/ERROR 时退出码 1（可直接挂 CI 门禁）
```

## 6. 已知限制（MVP）

- 工作簿按"第一个 worksheet"解析；多 sheet 请合并到一张表。
- 日期型单元格按数值字符串处理（模板均为文本列，不影响用例）。
- 批量执行共用同一设备串行；多设备并行需按 device_serial 拆批。
