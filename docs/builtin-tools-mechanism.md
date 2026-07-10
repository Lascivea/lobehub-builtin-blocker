# LobeHub 内置工具启用机制详解

> 基于 `lobehub/lobehub` canary 分支源码分析。理解这个机制,才能判断哪些工具"关掉有用"、哪些"关掉没用"。

---

## 一、什么是内置工具 (Builtin Tools)?

LobeHub 有两类扩展:
- **MCP 工具**: 通过 MCP server 接入的外部工具
- **内置工具 (Builtin Tools)**: LobeHub 自带的工具包,在 `packages/builtin-tool-*` 目录下

每个内置工具包含:
- `manifest.ts`: 工具定义(API schema、`systemRole`、metadata)
- `systemRole.ts` 或 `content.ts`: 注入到系统提示词中的角色指令
- `executor/`: 工具执行逻辑

**关键问题**: 工具的 `systemRole` 会在启用时自动注入到系统提示词,即使模型从未调用该工具。这是"对话风格变奇怪"的根本原因。

---

## 二、三层控制模型

LobeHub 用三层机制决定哪些工具最终可用:

```
第一层:候选集 (Candidate Set)
    ↓ defaultToolIds 加入,用户无法移除
第二层:启用检查器 (Enable Checker)
    ↓ alwaysOnToolIds 强制启用,运行时条件覆盖
第三层:UI 展示 (UI Display)
    ↓ hidden/discoverable 决定显示方式
```

---

## 三、五个关键列表

源码位置: `packages/builtin-tools/src/index.ts:40-89`

### 1. `defaultToolIds` (line 42-55)

**12 个工具**: activator, skills, skill-store, web-browsing, knowledge-base, memory, local-system, cloud-sandbox, topic-reference, agent-documents, task, lobe-agent

**作用**: 这些工具**始终加入候选集**,每次请求都会加载。用户**无法从候选集中移除**它们。

**影响**: 如果你的工具在 `defaultToolIds` 里,即使 UI 上取消勾选,它仍然会被加载到候选集中(但不一定启用,见第二层)。

---

### 2. `alwaysOnToolIds` (line 72-77)

**4 个工具**: lobe-agent, lobe-activator, lobe-skills, skill-store

**作用**: 这些是**核心系统工具**,在 Agent 模式下**强制启用**,用户勾选无效。

**机制** (在 `enableCheckerFactory.ts:38`):
```typescript
if (alwaysOnToolIds.includes(toolId)) {
  return true;  // 强制启用,跳过所有规则检查
}
```

**影响**:
- **Agent 模式**: 始终启用,用户无法关闭
- **Chat 模式**: 完全移除(line 63-66 注释)
- **Manual 模式**: lobe-activator 和 skill-store 可能被移除(由 `manualModeExcludeToolIds` 决定)

**注释说明** (line 61-66):
> `lobe-agent` 提供内置能力(plan + todo 管理、子 agent 调度、媒体回退),每次 agent 模式都可用,不受显式注入限制。
> 注意:这些规则仅在 agent 模式下生效 — chat 模式会**完全丢弃** `alwaysOnToolIds`。

---

### 3. `chatModeAllowedToolIds` (line 101-105)

**3 个工具**: knowledge-base, memory, web-browsing

**作用**: Chat 模式(Chat 模式下 `enableAgentMode === false`)下,只允许这 3 个工具。

**机制**:
- 移除 `alwaysOnToolIds`
- 移除所有用户插件
- 只保留这 3 个(且需满足运行时条件)
- **禁用** `allowExplicitActivation`(防止工具偷偷激活)

**影响**: Chat 模式下,即使 UI 显示某个工具已启用,实际也不可用。

---

### 4. `runtimeManagedToolIds` (line 142-150)

**7 个工具**: cloud-sandbox, knowledge-base, local-system, memory, remote-device, lobe-agent, web-browsing

**作用**: 这些工具的启用/禁用状态由**运行时条件**决定,不由用户勾选控制。

**运行时条件**:
| 工具 | 条件 |
|------|------|
| cloud-sandbox | `hasCloudSandboxAccess()` 为 true |
| knowledge-base | 存在已启用的知识库(`hasKnowledgeBases`) |
| local-system | 桌面版客户端 |
| memory | 全局 memory 设置开启 |
| remote-device | 有已连接的远程设备 |
| lobe-agent | 始终 true |
| web-browsing | 全局 web-browsing 设置开启 |

**机制** (在 `createEnableChecker` 中):
```typescript
if (runtimeManagedToolIds.includes(toolId)) {
  // 检查运行时条件,直接返回结果,跳过用户勾选
  return checkRuntimeCondition(toolId);
}
```

**UI 影响** (line 133-140 注释):
> 聊天输入工具弹出窗口在工具列表中**故意隐藏**这些工具 — 即使在手动技能激活模式下 — 这样用户就不会看到实际上无法影响的切换。

**影响**: 如果你的工具在 `runtimeManagedToolIds` 里,UI 上可能显示勾选框,但**勾选无效**,实际启用状态由运行时条件决定。

---

### 5. `manualModeExcludeToolIds` (line 84-87)

**2 个工具**: lobe-activator, skill-store

**作用**: 手动技能激活模式(Manual Mode)下,从默认工具列表中排除这些工具。

**背景**: Manual 模式下,用户希望精确控制每个技能,不想让系统自动激活工具。

**影响**: Manual 模式下,即使 `alwaysOnToolIds` 包含了 lobe-activator 和 skill-store,它们也可能被移除。

---

## 四、四个模式对比

| 模式 | 候选集 | allowExplicitActivation | alwaysOnToolIds | runtimeManagedToolIds | 用户插件 |
|------|--------|------------------------|-----------------|----------------------|----------|
| **Agent** | `defaultToolIds` | ✓ true | 强制启用 | 由运行时条件决定 | ✓ 启用 |
| **Chat** | `chatModeAllowedToolIds` | ✗ false | 完全移除 | 由运行时条件决定 | 完全移除 |
| **Custom** | agent plugins | ✗ false | 完全移除 | 由运行时条件决定 | agent plugins |
| **Manual** | `defaultToolIds` minus `manualModeExcludeToolIds` | ✓ true | 强制启用(可能有例外) | 由运行时条件决定 | ✓ 启用 |

---

## 五、UI 显示与实际启用的差异

这是最容易混淆的部分:**UI 显示的工具 ≠ 实际启用的工具**。

### 1. `hidden` 属性

**含义**: `hidden: true` 的工具**不会显示在 UI 工具列表中**(`selectors.ts:103-126`),但仍可能被启用。

**当前 hidden 工具**:
```
memory, lobe-web-browsing, lobe-agent, lobe-activator, lobe-skills, skill-store,
skill-maintainer, self-feedback-intent, agent-signal-review, agent-signal-reflection,
agent-signal-feedback-intent, agent-signal-skill-management, cloud-sandbox, page-agent,
locale-system, calculator, topic-reference, web-onboarding, user-interaction, brief
```

**影响**: 你**看不到**这些工具,但它们可能已经启用了。

### 2. `discoverable` 属性

**含义**: `discoverable: false` 的工具**永远不会出现在用户界面**中,即使启用也不会显示。

**当前 discoverable:false 工具**:
```
lobe-activator, lobe-skills
```

**影响**: 你完全不知道这些工具存在,但它们可能在后台强制运行。

### 3. `alwaysOnToolIds` 工具

**4 个工具**: lobe-agent, lobe-activator, lobe-skills, skill-store

**UI 显示**: 这 4 个工具都有 `hidden: true`,所以**不会显示在工具列表中**。

**实际启用**: 在 Agent 模式下**强制启用**,用户无法关闭。

**影响**: 你无法控制这 4 个工具,它们的 `systemRole` 会始终注入。

### 4. `runtimeManagedToolIds` 工具

**7 个工具**: cloud-sandbox, knowledge-base, local-system, memory, remote-device, lobe-agent, web-browsing

**UI 显示**: 这些工具的显示逻辑复杂:
- 有些是 `hidden: true`(如 memory, web-browsing, lobe-agent)
- 有些不是(如 cloud-sandbox, knowledge-base)
- 但 UI 会**根据运行时条件**决定是否显示勾选框(可能显示但灰色)

**实际启用**: 由运行时条件决定,**不受 UI 勾选影响**。

**影响**: 即使你在 UI 上取消勾选,如果运行时条件满足,工具仍会启用。

---

## 六、为什么"关掉没用"?

结合以上分析,有 **13 个工具**的用户控制是**无效的**:

### 第一类:始终启用,无法关闭 (4 个)
```
lobe-agent, lobe-activator, lobe-skills, skill-store
```
- 在 `alwaysOnToolIds` 中
- Agent 模式下强制启用
- 用户勾选无效

### 第二类:运行时条件决定,UI 勾选无效 (9 个)
```
cloud-sandbox, knowledge-base, local-system, memory, remote-device,
lobe-agent (双重), web-browsing
```
- 在 `runtimeManagedToolIds` 中
- 启用状态由运行时条件决定
- UI 勾选无效(即使显示)

**关键代码位置**: `src/server/modules/Mecha/AgentToolsEngine/index.ts:231-300`

```typescript
// 构建启用检查器规则
const rules: Record<string, boolean> = {};

// 用户插件 (line 235-240)
for (const pluginId of agentConfig.plugins) {
  rules[pluginId] = true;
}

// alwaysOnToolIds 强制启用 (line 242-246)
for (const pluginId of alwaysOnToolIds) {
  rules[pluginId] = true;  // 覆盖用户设置
}

// runtimeManagedToolIds 由运行时条件决定 (line 248-298)
if (runtimeManagedToolIds.includes(pluginId)) {
  rules[pluginId] = checkRuntimeCondition(pluginId);  // 跳过用户设置
}
```

---

## 七、systemRole 注入机制

**位置**: `packages/context-engine/src/providers/ToolSystemRole.ts`

**逻辑**:
```typescript
const tools = enabledTools.filter(tool => tool.manifest?.systemRole);
// ... 将所有启用工具的 systemRole 注入到系统提示词
```

**影响**: 即使你不使用某个工具,只要它被启用,它的 `systemRole` 就会出现在每次对话的系统提示词中。

**当前注入 systemRole 的工具**:
1. lobe-agent (`systemRole.ts`)
2. lobe-task (`systemRole.ts`)
3. agent-signal-review (`systemRole.ts`)
4. agent-signal-reflection (`systemRole.ts`)
5. agent-signal-feedback-intent (`systemRole.ts`)
6. agent-signal-skill-management (`systemRole.ts`)
7. lobe-self-iteration (`systemRole.ts`)
8. lobehub skill (`content.ts`)
9. web-browsing (`systemRole.ts`)
10. memory (`systemRole.ts`)
11. knowledge-base (`systemRole.ts`)
12. local-system (`systemRole.ts`)
13. remote-device (`systemRole.ts`)
14. cloud-sandbox (`systemRole.ts`)
15. topic-reference (`systemRole.ts`)

---

## 八、完整工具列表

基于 `packages/builtin-tools/src/index.ts` 的 `builtinToolRegistry`:

| 工具 ID | hidden | discoverable | defaultToolIds | alwaysOn | runtimeManaged | chatModeAllowed | UI 可关闭? |
|---------|--------|--------------|----------------|----------|----------------|-----------------|-----------|
| **verify-tool** | ✓ | ✗ | - | - | - | - | ❌ 看不到 |
| **lobe-activator** | ✓ | ✗ | ✓ | ✓ | - | - | ❌ 强制启用 |
| **lobe-skills** | ✓ | ✗ | ✓ | ✓ | - | - | ❌ 强制启用 |
| **skill-store** | ✓ | ✓ | ✓ | ✓ | - | - | ❌ 强制启用 |
| **skill-maintainer** | ✓ | ✗ | - | - | - | - | ❌ 看不到 |
| **self-feedback-intent** | ✓ | ✗ | - | - | - | - | ❌ 看不到 |
| **agent-signal-review** | ✓ | ✗ | - | - | - | - | ❌ 看不到 |
| **agent-signal-reflection** | ✓ | ✗ | - | - | - | - | ❌ 看不到 |
| **agent-signal-feedback-intent** | ✓ | ✗ | - | - | - | - | ❌ 看不到 |
| **agent-signal-skill-management** | ✓ | ✗ | - | - | - | - | ❌ 看不到 |
| **locale-system** | ✓ | isDesktop | ✓ | - | ✓ | - | ⚠️ 由运行时决定 |
| **memory** | ✓ | ✓ | ✓ | - | ✓ | ✓ | ⚠️ 由运行时决定 |
| **web-browsing** | ✓ | ✓ | ✓ | - | ✓ | ✓ | ⚠️ 由运行时决定 |
| **cloud-sandbox** | ✓ | ✓ | ✓ | - | ✓ | - | ⚠️ 由运行时决定 |
| **agent-documents** | - | ✓ | ✓ | - | - | - | ✅ 可关闭 |
| **lobe-credentials** | - | ✓ | - | - | - | - | ✅ 可关闭 |
| **knowledge-base** | ✓ | ✓ | ✓ | - | ✓ | ✓ | ⚠️ 由运行时决定 |
| **page-agent** | ✓ | ✗ | - | - | - | - | ❌ 看不到 |
| **agent-builder** | ✓ | ✗ | - | - | - | - | ❌ 看不到 |
| **group-agent-builder** | ✓ | ✗ | - | - | - | - | ❌ 看不到 |
| **group-management** | ✓ | ✗ | - | - | - | - | ❌ 看不到 |
| **agent-management** | ✓ | ✓ | - | - | - | - | ✅ 可关闭 |
| **calculator** | ✓ | ✓ | - | - | - | - | ✅ 可关闭 |
| **message** | ✓ | ✓ | - | - | - | - | ✅ 可关闭 |
| **remote-device** | ✓ | ✓ | - | - | ✓ | - | ⚠️ 由运行时决定 |
| **topic-reference** | ✓ | ✗ | ✓ | - | - | - | ❌ 看不到 |
| **web-onboarding** | ✓ | ✗ | - | - | - | - | ❌ 看不到 |
| **user-interaction** | ✓ | ✗ | - | - | - | - | ❌ 看不到 |
| **task** | - | ✓ | ✓ | - | - | - | ✅ 可关闭 |
| **brief** | ✓ | ✗ | - | - | - | - | ❌ 看不到 |
| **lobe-agent** | ✓ | ✓ | ✓ | ✓ | ✓ | - | ❌ 强制启用 |
| **delivery-checker** | - | ✓ | - | - | - | - | ✅ 可关闭 |

**图例**:
- ✓ = 是 / 在列表中
- ✗ = 否 / 不在列表中
- - = 不在该分类中

---

## 九、结论

### 为什么需要服务端补丁?

1. **UI 显示不等于实际控制**: 20+ 个工具要么看不到,要么勾选无效
2. **systemRole 自动注入**: 只要工具启用,其 `systemRole` 就会污染对话
3. **无法通过 UI 关闭**: `alwaysOnToolIds` 和 `runtimeManagedToolIds` 绕过了用户控制
4. **Agent 信号类工具**: 9 个"自我反思"类工具始终注入,严重影响对话风格

### 哪些工具真的可以用 UI 关闭?

**注意**:"UI 勾选有效" 有三种程度:

#### 🟢 完全有效(完全禁用)
这些工具**不在** `defaultToolIds` 中,取消勾选后模型完全看不到它们:
```
calculator
message
delivery-checker
user-interaction
brief
web-onboarding
agent-builder
agent-management
```

#### 🟡 部分有效(减少 systemRole 污染)
这些工具**在** `defaultToolIds` 中,取消勾选 = 从固定启用改为自动启用:
- ✅ `systemRole` 不注入系统提示(**污染减少**)
- ❌ 模型仍可调用 `activateTools` 激活

典型代表:
- `task` — 取消勾选后冗长的任务管理指令不再每次注入
- `agent-documents`, `topic-reference` — 文档/话题管理
- `web-browsing`, `knowledge-base`, `memory`, `cloud-sandbox`, `local-system` — 同时也是 runtimeManaged,UI 勾选本就无法控制

**实际效果**: 取消勾选 `task` 后,大多数对话减少了 ~30 行的 systemRole 污染,模型不会主动想到任务管理。但如果对话中出现相关需求,模型仍可能激活。

#### 🔴 无效(UI 勾选不改变任何行为)
- **alwaysOnToolIds** (4 个): lobe-agent, lobe-activator, lobe-skills, skill-store
- **完全 hidden 的工具** (10 个): agent-signal-review, agent-signal-reflection, agent-signal-feedback-intent, agent-signal-skill-management, self-feedback-intent, agent-management, topic-reference, group-management, group-agent-builder, verify

### 总结:什么时候需要服务端补丁?

只有当工具属于 🔴 无效类别,且其 systemRole 严重影响对话时,才需要服务端补丁。

对于 🟡 部分有效的工具(如 `task`),大多数用户**只需取消 UI 勾选即可**,污染已经大幅减少。只有当模型持续尝试激活这些工具时,才需要加入黑名单。

当前服务端补丁针对的 9 个工具(在 `lobehub-builtin-blocker/README.md` 中),全是 🔴 无效的类别,无法通过 UI 真正关闭。

---

## 十、源码参考位置

| 文件 | 作用 |
|------|------|
| `packages/builtin-tools/src/index.ts:40-89` | 5 个关键列表定义 |
| `packages/builtin-tools/src/index.ts:152+` | 工具注册表(hidden/discoverable 属性) |
| `src/server/modules/Mecha/AgentToolsEngine/index.ts:231-300` | Agent 模式启用规则构建 |
| `src/helpers/toolEngineering/index.ts:280-350` | 前端启用规则构建 |
| `packages/context-engine/src/engine/tools/enableCheckerFactory.ts:35-51` | `createEnableChecker` 核心逻辑 |
| `packages/context-engine/src/providers/ToolSystemRole.ts` | systemRole 注入逻辑 |

---

**文档版本**: 基于 2026-07-10 的 canary 分支源码分析  
**维护说明**: LobeHub 架构可能变化,需定期验证源码是否仍适用
