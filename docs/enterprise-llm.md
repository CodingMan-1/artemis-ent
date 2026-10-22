# 企业自建 LLM 接入指南（Qwen3.8-27B 多模态，单端点）

> 分支基线：google/artemis main（2026-10 快照）
> 本 fork 的 `config/artemis.jsonc` 已切换为**企业单端点配置**：所有 agent 节点
> （感知执行环 + 分析校验环）统一指向同一个 OpenAI 兼容端点。
> 总方案与用例中心改造方案见交付文档 `artemis-plan/00-方案-企业自建LLM与Excel用例适配.md`。

## 1. 服务端部署（企业侧）

用 vLLM 或 SGLang 起 OpenAI 兼容服务。**必须开启多模态通道**（模型支持图片 ≠ 服务端开了图片通道）：

```bash
vllm serve <qwen3.8-27B路径> --port 8001 \
    --served-model-name qwen3.8-27b \
    --max-model-len 32768 \
    --limit-mm-per-prompt image=4 \
    --enable-auto-tool-choice --tool-call-parser hermes
# 建议同型号再挂一个实例 qwen3.8-27b-bak 作 fallback（熔断回退用）
```

- 多实例/多租户：企业网关（One-API/Kong）层路由限流，ARTEMIS 只认一个 base_url。
- ARTEMIS 侧 `ModelEndpoint.is_multimodal` 默认 true，端点就绪后无需再改配置。

## 2. ARTEMIS 侧配置

| 文件 | 内容 |
|---|---|
| `config/artemis.jsonc` | `default.provider="openai"`、`default.model="qwen3.8-27b"`；`object_detector: null`（见 §4 基准确认后再开）；节点级 Gemini 专属参数（thinking_level / include_thoughts / enable_grounding）已移除（router 的 GOOGLE 分支以外不生效） |
| `.env` | `OPENAI_API_KEY=sk-local-enterprise`、`OPENAI_BASE_URL=http://<vllm>:8001/v1`（`.env.example` 已有注释段） |

单一网关 → 无需修改任何 Python 代码。若 27B 与 VL 旗舰分属两个独立端点，
才需要给 `third_party/mobile_use/config/llm.py` 的 `LLM` 加 `api_base/api_key` 透传（~10 行）。

## 3. 多模态探活（验收第 1 步）

对端点发一条 OpenAI vision 格式请求，确认图片链路：

```bash
curl -s http://<vllm>:8001/v1/chat/completions -H "Content-Type: application/json" -d '{
  "model": "qwen3.8-27b",
  "messages": [{"role":"user","content":[
    {"type":"image_url","image_url":{"url":"data:image/png;base64,<截图base64>"}},
    {"type":"text","text":"描述当前屏幕上的可点击元素"}
  ]}]
}'
```

返回合理的屏幕元素描述即通过。随后 `artemis doctor` 验证 ADB/设备/模型连通；
`ARTEMIS_FAKE_LLM=1` 可离线自测整条图（不依赖真模型）。

## 4. 坐标精度小基准（决定 object_detector 开关）

本 fork 默认 `object_detector: null`（上游把该节点锁死在 Gemini Robotics-ER 模型，
通用多模态模型的亚像素定位精度需先验证）。元素索引优先路径（无障碍树）已覆盖原生 UI。

基准做法：
1. 准备 20~30 个已知元素（以原生 UI 为主，含 1 个自绘页）；
2. 让模型对同一截图预测每个元素的点击坐标；
3. 用 `artemis/utils/element_hit_test.py` 对元素 bounds 统计命中率；
4. 命中率 ≥95% → 可在 `config/artemis.jsonc` 把 `object_detector` 改回
   `{"provider":"openai","model":"qwen3.8-27b"}` 开启；
   不达标 → 保持关闭，自绘页场景用 `pro.explorer.mode=ultra` 提升感知档位。

## 5. 冒烟与回归

```bash
uv run artemis run "打开设置，进入电池，告诉我电量" --profile flash
uv run artemis run "打开设置，进入电池，verify 显示电量百分比" --profile pro --verification-level final
# 节点抽查：log_analyzer 分析一段 Logcat 崩溃栈；checker 对已知失败断言判 FAIL
```

AndroidWorld 子集回归：抽 10 条任务对比 Gemini 默认配置基线，量化 gap。

## 6. 回退项：XML 文本模式

若图片路径的坐标精度/token 成本不达预期，可切"感知=无障碍树文本+OCR"的
XML 文本模式（改动清单：`artemis/agents/flash/runner.py`、`artemis/graph/perception.py`、
`artemis/agents/operator/prompts.py`、`flash/flash_runner.md`、`artemis/utils/ocr_api.py`，
详见总方案文档 §2.4）。当前路线未启用。

## 7. 测试用例中心（规划中）

Web UI 增加"用例中心"页：Excel（前置条件/步骤/预期结果）→ goal 模板
（verify/assert 检查项）→ `POST /api/run` 批量派发 → 结果表（PASS/FAIL/INCONCLUSIVE/ERROR）
→ 导出 xlsx。接口与前端骨架见 `artemis-plan/examples/` 与总方案文档 §3。
