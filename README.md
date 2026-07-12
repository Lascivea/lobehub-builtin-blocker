# lobehub-builtin-blocker

> **Status Update / 状态更新 (2025-07)**
>
> LobeHub 官方 canary 已经提供 **per-agent 禁用内置工具** 的能力，因此大多数用户**不再需要**这个全局补丁项目。
>
> 本仓库现在主要保留两样有价值的内容：
> 1. **推荐关闭哪些内置工具**（见下表，注意：**记忆不要关**）。
> 2. 在官方 canary Docker 镜像尚未包含该功能、或 MCP session 官方修复未合并前的过渡补丁。
>
> 如果你运行的是最新 `lobehub/lobehub:canary`，建议优先使用官方 per-agent 方案。

---

## TL;DR: 现在推荐怎么做

1. **升级**到最新 `lobehub/lobehub:canary`。
2. **在每个助手 / Agent 的设置里**，把下面"推荐禁用"的工具加入 per-agent 禁用列表（`disabledBuiltinToolIds` / `disabledPluginIds`）。
3. **保留 `memory` 开启**——自动记忆很有用，不建议关闭。
4. 如果 HTTP MCP 工具在服务端重启后仍然失效，说明官方 session retry 还没合并到 canary，此时再启用本仓库的 MCP patch。

---

## 推荐关闭的内置工具（per-agent 黑名单）

这些工具会注入污染性 systemRole 提示词，且过去无法通过 UI 可靠关闭。**现在可以用官方 per-agent 禁用列表关闭它们。**

| Identifier | UI Name | 污染表现 |
|---|---|---|
| `lobe-web-browsing` | Web Browsing | 强制脚注、搜索强迫症 |
| `lobe-task` | Task Tools | 小问题也建任务清单 |
| `lobe-delivery-checker` | Delivery Check Verifier | 回答前先整验收标准 |
| `agent-signal-review` | Agent Signal Nightly Review | 每晚自省 |
| `agent-signal-reflection` | Agent Signal Self-Reflection | 回合后自省 |
| `agent-signal-feedback-intent` | Agent Signal Self-Feedback Intent | 自我反馈意图 |
| `agent-signal-skill-management` | Agent Signal Skill Management | 反馈固化 |
| `lobe-self-iteration` | Self Feedback Intent | 元 agent 自我迭代 |
| `lobehub` | LobeHub | 平台身份劫持 |

### 哪些工具**不要**关？

| Identifier | 原因 |
|---|---|
| `memory` | 自动记忆是 LobeHub 核心体验，**不建议关闭**。 |
| `knowledge-base` | 只有启用知识库时才工作，污染很低。 |
| `cloud-sandbox` | 仅在 cloud 运行时启用。 |
| `calculator`, `message` | 无 systemRole 污染。 |

---

## 官方方案 vs 本补丁

### 官方已经解决的

| 问题 | 官方状态 | 说明 |
|---|---|---|
| 内置工具污染 | ✅ canary 已支持 per-agent 禁用 | 官方在 canary 中增加了 `disabledBuiltinToolIds` / `disabledPluginIds`，可按助手单独禁用。 |
| `lobe-web-browsing` 默认关闭 | ✅ 可用 `DEFAULT_AGENT_CONFIG` | 设置 `DEFAULT_AGENT_CONFIG=chatConfig.searchMode=off` 可让新建/未显式配置的助手默认不联网。 |
| MCP session 复用 bug | 🔄 官方修复存在但未合并 | `fix/mcp-session-retry` 分支实现了 `withSessionRetry()`；Docker Hub canary 镜像目前仍需要本补丁。 |

### 本补丁的剩余价值

- 你的 canary 镜像比较旧，还没有 per-agent 禁用功能。
- 你想要**全局强制**禁用某些工具（但 per-agent 通常已经够用）。
- 你还在等 MCP session 官方修复合并。

---

## How LobeHub Decides Which Tools Are Enabled / LobeHub 工具启用机制

LobeHub's tool enablement is **not** simply "user toggles UI checkbox". It uses a **three-layer model** where later layers can override earlier ones:

LobeHub 的工具启用**不是**简单的"用户勾选 UI"。它使用**三层模型**，后面的层可以覆盖前面的：

```
Layer 1: defaultToolIds     — 12 tools always loaded into candidate pool
Layer 2: rules              — decides which candidates are actually enabled:
         ├─ alwaysOnToolIds (4 tools, forced on)
         ├─ runtimeManagedToolIds (7 tools, decided by system state)
         ├─ user plugins (respects UI toggle)
         └─ allowExplicitActivation (can bypass all rules above)
Layer 3: UI display         — hidden/discoverable affects what user sees
```

For full source-level analysis, see [`docs/builtin-tools-mechanism.md`](docs/builtin-tools-mechanism.md).

详细源码分析见 [`docs/builtin-tools-mechanism.md`](docs/builtin-tools-mechanism.md)。

---

## Tool Classification / 工具分类

### Category 1: System Infrastructure — Always Enabled / 系统基础设施 — 始终启用

These are in `alwaysOnToolIds`. They are **forced on in agent mode** regardless of UI toggles. They have no `systemRole` pollution, so disabling them is **not** a goal — they make LobeHub function.

这些工具在 `alwaysOnToolIds` 中，Agent 模式下**强制启用**，UI 勾选无效。它们没有 `systemRole` 污染，**不需要**禁用 — 它们是 LobeHub 正常运行的基础。

| Identifier | UI Name | Role / 作用 |
|---|---|---|
| `lobe-activator` | Tools Activator | Dynamically activates tools when needed / 按需激活工具 |
| `lobe-skills` | Skills | Skill activation engine / 技能激活引擎 |
| `skill-store` | Skill Store | Skill discovery / 技能发现 |
| `skill-maintainer` | Skill Maintainer | Skill management / 技能管理 |

### Category 2: UI Toggle Partially Works / UI 勾选部分有效

These tools behave differently based on whether they are in `defaultToolIds`:

这些工具的行为取决于是否在 `defaultToolIds` 中：

#### 2a. In `defaultToolIds` — Uncheck = Less Pollution (NOT Full Disable)
#### 2a. 在 `defaultToolIds` 中 — 取消勾选 = 减少污染（非完全禁用）

**Mechanism / 机制**:
- **Checked (fixed enable)**: systemRole injected into **every** system prompt
- **Unchecked (auto enable)**: systemRole NOT in system prompt, but model can still call `activateTools` to activate it on demand
- **Result**: Less token usage & less bias in most conversations, but tool can still appear when model thinks it's relevant

**勾选（固定启用）**: systemRole 注入到**每次**系统提示
**取消勾选（自动启用）**: systemRole 不注入系统提示，但模型可调用 `activateTools` 按需激活
**结果**: 大多数对话占用更少 token & 减少倾向偏差，但模型认为相关时仍可能激活

| Identifier | UI Name | Notes / 备注 |
|---|---|---|
| `agent-documents` | Documents | Document management / 文档管理 |
| `topic-reference` | Topic Reference | Topic references / 话题引用 |
| `task` | Task Tools | Task management, verbose systemRole / 任务管理，冗长 systemRole |
| `web-browsing` | Web Browsing | Forced footnotes / 强制脚注 (also runtime managed) |
| `knowledge-base` | Knowledge Base | KB queries / 知识库查询 (also runtime managed) |
| `memory` | Memory | Auto-memory / 自动记忆 (also runtime managed) **不要关** |
| `cloud-sandbox` | Cloud Sandbox | Code execution / 代码执行 (also runtime managed) |
| `local-system` | Local System | Desktop / 桌面端 (also runtime managed) |
| `lobe-agent` | Lobe Agent | Plan/todo/sub-agent / 计划/子 agent (also alwaysOn) |

**Key insight**: `task` is a special case — it's in `defaultToolIds` but NOT in `alwaysOnToolIds` or `runtimeManagedToolIds`. So unchecking it genuinely reduces pollution (its systemRole prompt is ~30 lines), but the tool can still be activated via `activateTools`. Most of the time unchecking is enough; add to blacklist only if model keeps activating it.

**关键洞察**：`task` 是特殊情况 — 它在 `defaultToolIds` 但不在 `alwaysOnToolIds` 或 `runtimeManagedToolIds` 中。所以取消勾选确实减少污染（它的 systemRole ~30 行），但工具仍可通过 `activateTools` 激活。大多数时候取消勾选就够了；只有模型一直激活它时才需要加入黑名单。

#### 2b. NOT in `defaultToolIds` — UI Uncheck = Fully Disabled
#### 2b. 不在 `defaultToolIds` 中 — UI 取消勾选 = 完全禁用

| Identifier | UI Name | SystemRole Pollution |
|---|---|---|
| `calculator` | Calculator | 无 / None |
| `message` | Message | 无 / None |
| `delivery-checker` | Delivery Check | ⚠️ Medium / 中 |
| `user-interaction` | User Interaction | 无 / None |
| `brief` | Brief Tools | 无 / None |
| `web-onboarding` | Web Onboarding | 无 / None |
| `agent-builder` | Agent Builder | 无 / None |
| `agent-management` | Agent Management | 无 / None |

**Mechanism / 机制**: These are not in any always-on or auto-load list. UI uncheck puts them in `uninstalledBuiltinTools`, which filters them out of the manifest map entirely. They don't even appear in model's tool list.

**机制**: 这些工具不在任何 always-on 或 auto-load 列表中。UI 取消勾选把它们放入 `uninstalledBuiltinTools`，会被从 manifest map 完全过滤。它们甚至不出现在模型的工具列表里。

**Result**: Fully disabled. Uncheck in UI is enough — no env var needed.

**结果**: 完全禁用。UI 取消勾选即可 — 无需环境变量。

### Category 3: Runtime Managed — UI Checkbox Is Decorative / 运行时管理 — UI 勾选框是装饰

These are in `runtimeManagedToolIds`. Enablement is decided by **runtime/system conditions**, not user toggles. UI checkboxes (when visible) are **decorative only**. They have systemRole and may pollute:

这些在 `runtimeManagedToolIds` 中。启用状态由**运行时/系统条件**决定，非用户勾选控制。UI 勾选框（如果可见）**仅为装饰**。它们有 systemRole 可能污染：

| Identifier | UI Name | Enable Condition / 启用条件 | Has systemRole? |
|---|---|---|---|
| `cloud-sandbox` | Cloud Sandbox | `runtimeMode === 'cloud'` | Low / 低 |
| `knowledge-base` | Knowledge Base | Has enabled KB / 有启用的知识库 | Low / 低 |
| `memory` | Memory | Global memory on / 全局记忆开启 | Medium / 中 |
| `remote-device` | Remote Device | Device connected / 设备已连接 | Low / 低 |
| `local-system` | Local System | Desktop + device online / 桌面端+设备在线 | Low / 低 |
| `web-browsing` | Web Browsing | `searchMode !== 'off'` / 搜索未关 | **High (footnotes!) / 高（强制脚注）** |

**Key insight**: `web-browsing` appears in both `runtimeManagedToolIds` AND `defaultToolIds`. Even when `searchMode` is off, `allowExplicitActivation` can still make the Activator enable it. **This is why UI toggle is useless for it.**

**关键问题**：`web-browsing` 同时在 `runtimeManagedToolIds` 和 `defaultToolIds` 中。即使 `searchMode` 关闭，`allowExplicitActivation` 仍可以让 Activator 启用它。**这就是为什么 UI 勾选对它无效。**

### Category 4: Hidden Tools — Invisible But Active / 隐藏工具 — 不可见但已激活

These have `discoverable: false` or `hidden: true`. They don't appear in any UI tool list, but are active and inject systemRole. **You cannot see them, let alone uncheck them.** They exist in 4 subcategories:

这些有 `discoverable: false` 或 `hidden: true`。它们不出现在任何 UI 工具列表中，但已激活并注入 systemRole。**你看不到它们，更别说取消勾选了。** 它们分 4 个子类：

#### 4a. Self-Reflection / 自我反思类

These are the worst polluters. Their systemRole gives the model "self-reflection" tendencies.

这些是最严重的污染源。它们的 systemRole 让模型有"自我反思"倾向。

| Identifier | systemRole Effect / systemRole 效果 |
|---|---|
| `agent-signal-review` | "Review the conversation" / "回顾对话" |
| `agent-signal-reflection` | "Reflect on your response" / "反思你的回应" |
| `agent-signal-feedback-intent` | "Seek feedback" / "寻求反馈" |
| `agent-signal-skill-management` | "Manage skills" / "管理技能" |
| `self-feedback-intent` | "Self-iteration" / "自我迭代" |

#### 4b. Other Hidden Tools / 其他隐藏工具

| Identifier | Notes / 备注 |
|---|---|
| `verify-tool` | Delivery verification / 交付验证 |
| `page-agent` | Page-level agent / 页面级 agent |
| `agent-builder` | Agent builder helper / Agent 构建辅助 |
| `agent-management` | Agent management / Agent 管理 (no systemRole) |
| `group-agent-builder` | Group agent builder / 群组 agent 构建 (no systemRole) |
| `group-management` | Group management / 群组管理 (no systemRole) |
| `brief` | Task briefs / 任务简报 |
| `user-interaction` | User interaction helper / 用户交互辅助 |
| `web-onboarding` | Onboarding guide / 新手引导 |

#### 4c. LobeHub Skill (not a tool) / LobeHub 技能（非工具）

`lobehub` is a **builtin skill**, not a tool. It's managed by `SkillEngine`, not `AgentToolsEngine`. Its `content.ts` has a huge Identity table that makes the model identify as "LobeHub platform agent".

`lobehub` 是**内置技能**，非工具。由 `SkillEngine` 管理，非 `AgentToolsEngine`。其 `content.ts` 有巨大的 Identity 表，让模型认同自己是"LobeHub 平台 agent"。

#### 4d. No systemRole Pollution (safe to ignore) / 无 systemRole 污染（可忽略）

| Identifier | Why safe / 为什么安全 |
|---|---|
| `calculator` | Pure computation, no systemRole |
| `message` | Message sending, no systemRole |
| `creds` | Credentials lookup only |
| `topic-reference` | Only `hidden: true`, no `discoverable: false` |

---

## What This Patch Project Does / 本补丁项目做了什么

> **推荐先使用上面的官方方案。** 只有在你必须改 Docker 镜像、或官方功能尚未可用时，才需要看下面这部分。

### Patch 1: MCP Session Fix (5 patch points / 5 个补丁点)

| # | Target | Action |
|---|---|---|
| P1 | `MCPClient.listTools` | Broaden session-expiry error regex |
| P2 | `MCPClient.callTool` | Throw `NoValidSessionId` on session expiry |
| P3 | `MCPClient.listResources` | Same as P2 |
| P4 | `MCPClient.listPrompts` | Same as P2 |
| P5 | `MCPService.callTool` | One-shot retry with fresh client |

**Official fix**: Branch `fix/mcp-session-retry` implements `withSessionRetry()`. This patch will be deprecated once merged into canary/main and available in the Docker image.

**官方修复**: `fix/mcp-session-retry` 分支实现了 `withSessionRetry()` 包装器。待合并到 canary/main 并在 Docker 镜像中可用后，可废弃此补丁。

### Patch 2: Builtin Tool Blacklist (7 patch points / 7 个补丁点)

| # | Target | Action |
|---|---|---|
| P1 | Activator `getToolManifests` | Skip blacklisted IDs at runtime |
| P2 | `toolManifestMap` construction | Skip blacklisted IDs at build time |
| P3 | `SkillEngine` enableChecker | Block blacklisted skills |
| P4 | `injectSelfFeedbackIntentTool` | Block direct injection of lobe-self-iteration |
| P5 | `TaskIdentifier` forced plugin | Block lobe-task forced injection |
| P6 | Post-filter `generateToolsDetailed` | Remove blacklisted from tools + enabledToolIds + manifestMap |
| P7 | `builtinTools` registry | Remove blacklisted tools from `<available_tools>` discovery candidates |

**Result**: Disabled tools are removed from the LLM's function list, cannot be activated, and their systemRole text is stripped from the context. The model never sees them.

**效果**: 被禁用的工具从 LLM 的 function 列表中移除，无法被激活，其 systemRole 从上下文中剥离。模型根本看不到这些工具。

---

## Quick Start / 快速开始

### Prerequisites / 前置条件

- Docker + Docker Compose
- Python 3.6+
- Node.js 22+ (for `node --check` syntax validation, any recent Node works)
- Existing LobeHub self-deployed setup with `docker-compose.yml`
- 已部署的 LobeHub Docker 实例

### 1. Copy files to server / 复制文件到服务器

The production deployment on `hkhe` keeps the official compose file unchanged and uses two explicit override layers:

```
/opt/lobehub/
├── docker-compose.yml                    # Official (unchanged)
├── docker-compose.mcpfix.yml             # Intermediate image override
├── docker-compose.antipollute.yml        # Final image override
├── .env                                  # Official runtime config
├── .env.antipollute                      # DISABLED_BUILTIN_TOOLS
├── mcpfix/                               # MCP session patch script
└── antipollute/                          # Builtin blacklist patch script
```

### 2. Configure / 配置

Copy `.env.example` to `.env.antipollute` in the same directory as `docker-compose.yml`:

```bash
cp .env.example .env.antipollute
# Edit to toggle patches and set blacklist / 按需调整开关和黑名单
```

Key options:
```bash
ENABLE_MCPFIX=true        # set false after official fix is merged
ENABLE_ANTIPOLLUTE=true   # set false if official per-agent disable works for you

DISABLED_BUILTIN_TOOLS=lobe-web-browsing,lobe-task,...
```

### 3. Patch image / 打补丁

```bash
chmod +x repatch.sh
bash repatch.sh
```

This will:
1. `docker pull lobehub/lobehub:canary` (get latest / 拉最新版本)
2. Start a temporary container
3. Discover minified chunks by grep
4. Apply patches (mcp 5 points + antipollute 7 points)
5. `node --check` syntax validation on each patched chunk
6. `docker commit` → `lobehub/lobehub:canary-antipollute`
7. Restart the lobehub service via override compose

### 4. Verify / 验证

```bash
# Check patches survived
docker exec lobehub sh -c 'grep -rl serializeParams /app/.next/server/chunks/ | xargs grep -l reinitializing | wc -l'
# Expected: >0 (mcpfix)

docker exec lobehub sh -c 'grep -rl DISABLED_BUILTIN_TOOLS /app/.next/server/chunks/ | wc -l'
# Expected: >0 (antipollute, typically 6-7)

# Check service health
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:3210/
# Expected: 302
```

### 5. Update / 更新

When LobeHub releases a new canary, rebuild the intermediate MCP image first and then the final image:
```bash
bash /opt/lobehub/mcpfix/repatch.sh
bash /opt/lobehub/antipollute/repatch.sh
```

When official fix for MCP merges: set `ENABLE_MCPFIX=false` in `.env.antipollute`, then rebuild the final image.

当官方合并 MCP 修复后：在 `.env.antipollute` 设置 `ENABLE_MCPFIX=false`，运行 `bash repatch.sh`。

---

## Known Limitations / 已知限制

**UI still shows disabled tools** — this is by design:

UI 中仍然显示被禁用的工具 — 这是预期行为：

- The tool list UI is populated from `@lobechat/builtin-tools`, bundled at build time on the client side.
- Server-side patches only affect what the model sees (function list, systemRole, activation).
- Fixing the UI would require patching client-side chunks or modifying the static bundle — high risk, low value since disabled tools simply won't respond.
- If needed, set tools as "uninstalled" from the UI to hide them visually.

- 前端工具列表来自 `@lobechat/builtin-tools` 包，构建时静态打包到客户端 bundle。
- 服务端补丁只影响模型看到的内容（function 列表、systemRole、激活）。
- 修复 UI 需要补丁客户端 chunk 或修改静态 bundle — 风险高、价值低，因为被禁用的工具已经无法响应。

---

## How It Works / 工作原理

Both patches operate on **minified Next.js server chunks** (`.next/server/chunks/*.js`) inside the Docker image. They use precise string replacement — find an anchor string, replace it with a version that includes environment-variable-driven filtering.

Both 补丁都作用于 Docker 镜像内 **编译后的 Next.js server chunk**（`.next/server/chunks/*.js`）。采用精确字符串替换 — 找到锚点字符串，替换为包含环境变量驱动过滤逻辑的版本。

Key design principles / 核心设计原则：
- **Env-driven**: blacklist from `DISABLED_BUILTIN_TOOLS`; changing the blacklist only requires recreating the container, not rebuilding the image
- **Fail-safe**: if anchor strings don't match (version changed), the script exits with error and never produces a broken image
- **Non-destructive**: override compose files, official `docker-compose.yml` and `.env` untouched
- **Reversible**: switch back to official image anytime by dropping the override

- **环境变量驱动**：黑名单、开关全由 env 控制，改配置不需要重新打补丁
- **失败安全**：锚点匹配不到（版本变化），脚本报错退出，不会产出损坏镜像
- **非破坏性**：override compose 叠加，官方文件零改动
- **可逆**：随时可切换回官方镜像

---

## File Reference / 文件说明

| File | Purpose |
|---|---|
| `repatch.sh` | One-shot: pull → patch → commit → restart |
| `mcp_patch.py` | MCP session fix patch logic (5 points) |
| `antipollute_patch.py` | Builtin blacklist patch logic (7 points) |
| `patch-discovery.sh` | Add P7 to an existing final image when the official canary cannot be pulled |
| `docker-compose.antipollute.yml` | Final override pointing to `canary-antipollute` |
| `.env.example` | Configuration template (copy as `.env.antipollute`) |

---

## License / 许可

MIT
