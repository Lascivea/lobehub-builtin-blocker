# 为什么关掉没用？

> 你在 UI 上取消勾选某些工具，但它们仍然出现在对话中。这是 LobeHub 的设计"特性"，不是你的操作失误。

---

## 问题现象

你做了这些操作：
1. 进入 `设置 → 助手 → 工具`
2. 取消勾选了 `Web Browsing`、`Memory`、`Knowledge Base` 等工具
3. 但这些工具仍然：
   - 出现在系统提示词中
   - 影响对话风格
   - 被模型调用

**为什么关掉没用？**

---

## 三个根本原因

### 1. `alwaysOnToolIds` — 系统强制启用，用户无法控制

**4 个工具**:
```
lobe-agent, lobe-activator, lobe-skills, skill-store
```

这 4 个是 LobeHub 的**核心基础设施**：
- `lobe-agent`: AI agent 执行引擎（plan/todo 管理、子 agent 调度）
- `lobe-activator`: 工具自动激活引擎
- `lobe-skills`: 技能管理引擎
- `skill-store`: 技能发现引擎

**机制** (源码位置：`packages/builtin-tools/src/index.ts:72-77`)
```typescript
export const alwaysOnToolIds = [
  LobeAgentManifest.identifier,      // line 73
  LobeActivatorManifest.identifier,  // line 74
  SkillsManifest.identifier,         // line 75
  SkillStoreManifest.identifier,     // line 76
];
```

**启用规则构建** (源码位置：`src/server/modules/Mecha/AgentToolsEngine/index.ts:242-246`)
```typescript
// alwaysOnToolIds 强制启用，覆盖用户设置
for (const pluginId of alwaysOnToolIds) {
  rules[pluginId] = true;  // ← 这里直接设为 true，忽略用户勾选
}
```

**结果**: 
- 这 4 个工具在 UI 上**完全隐藏**（`hidden: true`，`discoverable: false`）
- 你甚至看不到它们的存在
- 但在 Agent 模式下，它们**始终启用**，它们的 `systemRole` 始终注入到系统提示词

---

### 2. `runtimeManagedToolIds` — 运行时条件决定，与用户勾选无关

**7 个工具**:
```
cloud-sandbox, knowledge-base, local-system, memory, remote-device, lobe-agent, web-browsing
```

这些工具的启用状态由**运行时条件**决定，而不是你的 UI 勾选。

**运行时条件** (源码位置：`src/server/modules/Mecha/AgentToolsEngine/index.ts:248-298`)
```typescript
// runtimeManagedToolIds 由运行时条件决定
for (const pluginId of runtimeManagedToolIds) {
  const condition = runtimeConditions[pluginId];
  
  if (pluginId === 'cloud-sandbox') {
    rules[pluginId] = hasCloudSandboxAccess();  // ← 检查云端沙箱权限
  } else if (pluginId === 'knowledge-base') {
    rules[pluginId] = hasKnowledgeBases();       // ← 检查是否有知识库
  } else if (pluginId === 'local-system') {
    rules[pluginId] = isDesktop();               // ← 检查是否桌面版
  } else if (pluginId === 'memory') {
    rules[pluginId] = globalMemoryEnabled();     // ← 检查全局 memory 设置
  } else if (pluginId === 'remote-device') {
    rules[pluginId] = hasConnectedDevices();     // ← 检查是否有远程设备
  } else if (pluginId === 'web-browsing') {
    rules[pluginId] = globalWebBrowsingEnabled();// ← 检查全局 web-browsing 设置
  }
}
```

**关键问题**:
- 这些工具在 UI 上**可能显示**（如 cloud-sandbox, knowledge-base）
- 但 UI 勾选框是**装饰性的**，你的勾选不会影响实际启用状态
- 即使你取消勾选，只要运行时条件满足，工具仍然启用

**举例**:
- `web-browsing`: 如果全局 web-browsing 设置开启（`globalWebBrowsingEnabled()` 返回 true），即使你在 UI 上取消勾选，工具仍然启用
- `memory`: 如果全局 memory 设置开启，即使你取消勾选，工具仍然启用
- `knowledge-base`: 如果你创建过知识库，即使你取消勾选，工具仍然启用

**LobeHub 源码注释** (line 133-140):
> 聊天输入工具弹出窗口在工具列表中**故意隐藏**这些工具 — 这样用户就不会看到实际上无法影响的切换。

**翻译**: LobeHub 的开发者知道这些工具的 UI 勾选是无效的，所以故意隐藏它们，避免用户困惑。

---

### 3. `hidden` 或 `discoverable: false` — 工具在 UI 上不可见，但仍可能启用

**20 个工具**具有 `hidden: true` 或 `discoverable: false` 属性：

| 工具 | hidden | discoverable | 可见性 |
|------|--------|--------------|--------|
| memory | ✓ | ✓ | 部分可见（UI 可能灰色显示） |
| web-browsing | ✓ | ✓ | 部分可见（UI 可能灰色显示） |
| lobe-agent | ✓ | ✓ | 部分可见（UI 可能灰色显示） |
| lobe-activator | ✓ | ✗ | **完全不可见** |
| lobe-skills | ✓ | ✗ | **完全不可见** |
| skill-store | ✓ | ✓ | 部分可见（UI 可能灰色显示） |
| skill-maintainer | ✓ | ✗ | **完全不可见** |
| self-feedback-intent | ✓ | ✗ | **完全不可见** |
| agent-signal-review | ✓ | ✗ | **完全不可见** |
| agent-signal-reflection | ✓ | ✗ | **完全不可见** |
| agent-signal-feedback-intent | ✓ | ✗ | **完全不可见** |
| agent-signal-skill-management | ✓ | ✗ | **完全不可见** |
| cloud-sandbox | ✓ | ✓ | 部分可见（UI 可能灰色显示） |
| page-agent | ✓ | ✗ | **完全不可见** |
| local-system | ✓ | isDesktop | 桌面版部分可见 |
| topic-reference | ✓ | ✗ | **完全不可见** |
| web-onboarding | ✓ | ✗ | **完全不可见** |
| user-interaction | ✓ | ✗ | **完全不可见** |
| brief | ✓ | ✗ | **完全不可见** |

**关键问题**:
- 这些工具在 UI 上**看不到**或**显示为灰色不可操作**
- 但其中很多工具**已经启用**，并且它们的 `systemRole` 正在污染你的对话
- 你无法通过 UI 控制它们

**最严重的例子**:
- **Agent Signal 系列** 4 个工具：`agent-signal-review`、`agent-signal-reflection`、`agent-signal-feedback-intent`、`agent-signal-skill-management`
  - 全部 `hidden: true`，`discoverable: false`
  - 在 UI 上**完全不可见**
  - 但**始终启用**，它们的 `systemRole` 会让模型表现出：
    - "自我反思"倾向
    - "夜间回顾"倾向
    - "技能管理"倾向
    - "反馈意图"倾向
  - 这就是为什么你的模型经常说"我需要反思一下"、"让我考虑一下"、"我可以帮你管理技能"等莫名其妙的话

- **Self-feedback-intent**: 
  - `hidden: true`，`discoverable: false`
  - UI 上完全不可见
  - 但始终启用，会让模型产生"自我反馈"的倾向

---

## 实际案例：Web Browsing 为什么关不掉？

**场景**:
1. 你进入 `设置 → 助手 → 工具`
2. 你**找不到** `Web Browsing` 这个工具（因为它 `hidden: true`）
3. 但你的模型仍然表现出：
   - "让我先搜索一下"
   - "我需要联网查询"
   - "让我帮你找找"
   - 自动添加脚注 `[^1]`、`[^2]`

**原因**:
1. `web-browsing` 在 `runtimeManagedToolIds` 中
2. 启用条件是 `globalWebBrowsingEnabled()`
3. 如果全局 web-browsing 设置开启（这可能在其他地方配置），即使你在 UI 上找不到这个工具，它仍然启用
4. 它的 `systemRole` 会注入到系统提示词，影响模型行为

**systemRole 内容** (源码位置：`packages/builtin-tool-web-browsing/src/systemRole.ts`):
```typescript
export const systemRole = `
You have access to a web browsing tool that allows you to search the internet
and visit web pages to find information.

When the user asks you a question, you should proactively search the internet
to find relevant and up-to-date information.

Always cite your sources with footnotes in the format [^1], [^2], etc.

Example:
The capital of France is Paris[^1].

[^1]: https://en.wikipedia.org/wiki/Paris
`;
```

**结果**: 即使你不想让模型搜索，它仍然会搜索，因为 `web-browsing` 的 `systemRole` 命令它"主动搜索互联网"。

---

## 哪些工具可以真正关掉？

**注意**:"真正关掉"有三种程度：

### 🟢 完全有效（完全禁用）— 8 个

这些工具**不在** `defaultToolIds` 中，取消勾选后模型完全看不到它们：
```
calculator          // 数学计算
message             // 消息发送
delivery-checker    // 交付验证
user-interaction    // 用户交互
brief               // 简报
web-onboarding      // 新手引导
agent-builder       // Agent 构建器
agent-management    // Agent 管理
```

**验证方法**：
- UI 上取消勾选
- 工具从工具列表中消失
- 模型无法调用，也不再提到相关功能

---

### 🟡 部分有效（减少 systemRole 污染）— 9 个

这些工具**在** `defaultToolIds` 中，取消勾选 = 从固定启用改为自动启用：
- ✅ `systemRole` 不再每次注入系统提示（**污染减少**）
- ❌ 模型仍可调用 `activateTools` 激活

**典型代表**：
```
task                // 任务管理（~30 行 systemRole）
agent-documents     // 文档管理
topic-reference     // 话题引用
```

**实际效果**：
- 你取消了 task 的勾选
- 对话中不再看到冗长的"如何创建/管理 todo"指令
- 对话风格更自然
- 但如果对话中出现任务管理需求，模型仍可能激活

**什么时候需要加入黑名单？**
- 大多数用户：只需取消 UI 勾选即可
- 只有当模型持续尝试激活这些工具时，才需要加入黑名单

---

### 🔴 无效（UI 勾选不改变任何行为）— 14 个

#### 子类别 1: alwaysOnToolIds（4 个）
```
lobe-agent          // AI agent 引擎
lobe-activator      // 工具激活器
lobe-skills         // 技能引擎
skill-store         // 技能发现
```

这 4 个工具在 UI 上**完全隐藏**，你甚至看不到它们。

#### 子类别 2: 完全 hidden 的工具（10 个）
```
agent-signal-review            // 每日自我回顾
agent-signal-reflection        // 每回合反思
agent-signal-feedback-intent   // 反馈意愿
agent-signal-skill-management  // 技能管理
self-feedback-intent           // 自我反馈
verify                         // 交付验证
agent-management               // Agent 管理（虽然名字重复，但这是另一个）
topic-reference                // 话题引用（另一个）
group-management               // 群组管理
group-agent-builder            // Group Agent 构建器
```

这些工具：
- 在 UI 上**完全不可见**（`hidden: true`）
- **始终启用**
- `systemRole` 持续污染系统提示词
- **无法通过 UI 真正关闭**

---

## 总结

**三类工具的控制程度**:

```
🟢 完全有效（8 个）: calculator, message, delivery-checker, user-interaction, 
                     brief, web-onboarding, agent-builder, agent-management

🟡 部分有效（9 个）: task, agent-documents, topic-reference, web-browsing, 
                     knowledge-base, memory, cloud-sandbox, local-system, lobe-agent

🔴 无效（14 个）:   lobe-agent, lobe-activator, lobe-skills, skill-store
                     agent-signal-review, agent-signal-reflection, 
                     agent-signal-feedback-intent, agent-signal-skill-management,
                     self-feedback-intent, verify, agent-management, 
                     topic-reference, group-management, group-agent-builder
```

**关键洞察**:
- 🟢 类工具**: 不在 `defaultToolIds` 中，取消勾选 = 完全禁用
- 🟡 类工具**: 在 `defaultToolIds` 中，取消勾选 = 减少 systemRole 污染，但模型仍可调用 `activateTools`
- 🔴 类工具**: 在 `alwaysOnToolIds` 中，UI 勾选完全无效

---

## solution：服务端补丁

既然 UI 无法控制这些工具，我们只能从**服务端**强行禁用它们。

这就是 `lobehub-builtin-blocker` 项目的目的：通过修改 Docker 镜像中的 minified JS chunk，实现环境变量黑名单过滤。

**原理**:
1. 在工具注册时，检查工具 ID 是否在黑名单中
2. 如果在黑名单中，跳过注册，工具不进入候选集
3. 工具不进入候选集，就不会被启用，其 `systemRole` 也不会注入

**补丁位置**:
- `generateToolsDetailed()`: 过滤黑名单工具
- `toolManifestMap`: 过滤黑名单工具
- `SkillEngine`: 过滤黑名单技能
- `enabledToolIds`: 过滤黑名单工具 ID

**效果**:
- 黑名单工具在 LLM 的请求中**完全消失**
- 模型看不到这些工具，也看不到它们的 `systemRole`
- 对话风格恢复正常

---

## 结论

**为什么关掉没用**？

因为 LobeHub 的设计中，工具启用不是完全由用户 UI 控制的。工具控制有三种程度：

#### 🟢 完全有效（8 个）
`calculator`, `message`, `delivery-checker`, `user-interaction`, `brief`, `web-onboarding`, `agent-builder`, `agent-management`

这些工具不在 `defaultToolIds` 中，取消勾选 = 完全禁用。

#### 🟡 部分有效（9 个）
`task`, `agent-documents`, `topic-reference`, `web-browsing`, `knowledge-base`, `memory`, `cloud-sandbox`, `local-system`, `lobe-agent`

这些工具在 `defaultToolIds` 中：
- ✅ 取消勾选后 `systemRole` 不再注入系统提示（污染减少）
- ❌ 模型仍可调用 `activateTools` 激活

大多数时候取消勾选够用；只有模型持续激活时才需要加入黑名单。

#### 🔴 无效（14 个）
`alwaysOnToolIds` (4 个) + 完全 hidden (10 个)

这些工具的 UI 勾选不改变任何行为，只能通过服务端补丁强制禁用。

**服务端补丁**: 从源头阻止 🔴 类工具加载。

---

## 延伸阅读

- [内置工具启用机制详解](./builtin-tools-mechanism.md) — 完整的源码分析
- [README.md](../README.md) — 服务端补丁使用说明
