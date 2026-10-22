# 部署拓扑：Ubuntu 服务器 + PC 测试台架（双机方案）

> 网络事实（2026-10）：
> - Ubuntu 服务器 `104.182.x.138`（公网 IP）
> - PC 测试台架 `10.4.181.209`（内网，USB 接安卓设备）
> - 两台机器都能访问企业 Qwen3.8-27B（vLLM/网关端点）
>
> 核心约束：**agent 宿主（跑 artemis 的机器）必须能通过 ADB 看到设备**。
> 设备 USB 插在 PC 上 → 一期直接在 PC 跑；二期把"大脑"挪到服务器，
> PC 降级为"设备桥"。

---

## 一期（MVP，现在就走）：artemis 跑在 PC 测试台架

服务器**不装 artemis**，只做可选入口/CI 宿主。PC 上完成：

### 1) 安装（Windows PC）

```bat
git clone https://github.com/CodingMan-1/artemis-ent.git
cd artemis-ent
git checkout feat/enterprise-llm
:: 依赖（uv 装好后）
uv sync
:: 或直接跑仓库自带启动器
start.bat
```

Linux PC 用 Docker（仓库自带 Dockerfile）或 venv，同样 `uv sync` 后起 console。

### 2) 配置企业模型端点

`.env`（参考 `.env.example` 的企业端点段）：

```
OPENAI_API_KEY=<企业网关key>
OPENAI_BASE_URL=http://<Qwen3.8-27B端点>/v1
```

`config/artemis.jsonc` 已在分支里切好（`provider:openai / qwen3.8-27b`，
`object_detector: null` 待坐标基准）。

### 3) 冒烟（按顺序）

```bash
uv run artemis doctor                 # ADB 设备 + 模型端点连通
uv run artemis run "打开设置，进入电池" --profile flash
uv run python -m apps.admin_console.server --host 127.0.0.1 --port 8000
# 浏览器 http://127.0.0.1:8000 → 侧边栏"用例中心"
# 点"模板"下载 → 填 2~3 条用例 → 导入 → Pro·严格校验 → 批量执行 → 导出结果
# CI 路径（同一台或任意内网机器，能访问 PC:8000 即可）：
uv run python scripts/run_cases.py cases.xlsx --base-url http://10.4.181.209:8000
```

注意：console 默认绑 127.0.0.1。若要**内网其他机器**直连（CI 场景），
启动加 `--host 0.0.0.0` 并**只对内网开放**（console 无登录鉴权，禁止暴露公网）。

### 4) 服务器在一期的角色（可选）

- 远程访问 console：PC 侧 `ssh -R 8080:127.0.0.1:8000 user@104.182.x.138`
  → 从任意处 `ssh -L 8080:127.0.0.1:8080 user@104.182.x.138` → 浏览器开 127.0.0.1:8080。
  （Host 头保持 127.0.0.1，过 SameOrigin 中间件；或上 Tailscale 更省事。）
- 跑 CI：把 `scripts/run_cases.py` 挂到流水线，`--base-url` 指 PC。

**一期验收**：flash 冒烟 + 用例中心 2~3 条用例跑通导出 xlsx +
坐标精度小基准（docs/enterprise-llm.md §4）达标。

---

## 二期（扩展）：大脑上服务器，PC 变设备桥

什么时候升级：需要 7×24 运行、多台台架并行、或 PC 要承担别的事。

### 服务器侧

```bash
# Docker 部署（仓库自带 Dockerfile；8080 只绑 loopback，Dockerfile 注释已写明安全要求）
docker build -t artemis-ent .
docker run -d --name artemis -p 127.0.0.1:8080:8080 \
  -v $(pwd)/.env:/app/.env -v $(pwd)/config:/app/config artemis-ent
# 容器内 ARTEMIS_BASE_URL 等经 .env 注入 Qwen 端点
```

### 设备桥（二选一）

**A. adb over SSH（推荐，服务器不需要能到台架内网）**

台架 PC 保持 adb server 运行（USB 设备自动可见）。服务器上：

```bash
# 常驻隧道（autossh 更稳）：把 PC 的 adb server(5037) 引到本地
autossh -M 0 -f -N -L 127.0.0.1:5037:127.0.0.1:5037 user@10.4.181.209
# artemis 走隧道里的 adb server：
export ADB_SERVER_SOCKET=tcp:127.0.0.1:5037
```

adbutils/uiautomator2 的枚举、forward 都经同一个 adb server，
因此 u2 的 atx 通道也自动走通。

**B. adb over TCP（服务器能直达台架局域网时最简单）**

设备开无线调试（开发者选项），服务器 `adb connect <设备IP>:5555`；
不需要 SSH 隧道，但要求服务器路由得到台架网段。

### 远程访问 console

- Tailscale（服务器+你的笔记本入同一 tailnet）→ 浏览器直接开
  `http://<服务器-tailnet-ip>:8080`；或
- `ssh -R` 反向隧道（一期同款）。
- **红线不变：console 无鉴权，禁止 `-p 8080:8080` 直接出公网。**

### 多台架架扩展

每台台架 = 一个"adb 桥端点"。服务器为每台设备分配
`device_serial`（用例中心 `POST /api/cases/run` 支持 `device_serial` 字段），
即可多机并行；队列/设备锁（DeviceExecutionLock）上游已内置。

---

## 验收与回退

| 步骤 | 一期 | 二期 |
|---|---|---|
| `artemis doctor` 全绿（设备+模型） | ✅ 必过 | ✅ 必过 |
| flash 单条冒烟 | ✅ | ✅ |
| 用例中心 2~3 条导入→执行→导出 | ✅ | ✅ |
| 坐标小基准 ≥95% 命中 | ✅ 决定 object_detector 开关 | 同 |
| 隧道/SSH 断线后任务行为 | — | 观察：设备桥断开会话应落 failed 而非挂死 |

回退：任何二期组件出问题 → 把 artemis 移回 PC 即回一期（设备路径零变化）。
