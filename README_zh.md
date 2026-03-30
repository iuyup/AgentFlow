# 🔀 AgentFlow

**基于 LangGraph 的多 Agent 协作设计模式实战库**

AgentFlow 是一套经过验证的多 Agent 设计模式合集，基于 [LangGraph](https://github.com/langchain-ai/langgraph) 构建。每个模式都包含完整代码、架构图、适用场景分析和性能对比。

> **不是框架封装，不是教程合集。** 这是多 Agent 系统的 **设计模式参考书**。

## 为什么需要 AgentFlow？

构建多 Agent 系统的难点不在工具，而在 **架构决策**：

- Agent 应该循环还是终止？
- 如何协调 N 个 Agent 而不混乱？
- 什么时候并行优于串行？

AgentFlow 提供 **经过验证的模式**，你可以学习、改造、组合 —— 每个模式都是完整的、可运行的示例。

## 模式索引

| 模式 | 说明 | 核心技术 | 状态 |
|------|------|----------|------|
| [Reflection（反思）](patterns/reflection/) | 通过「写作 → 审阅」循环实现迭代自改进 | 条件循环 | ✅ |
| [Debate（辩论）](patterns/debate/) | 多视角辩论 + 主持人综合裁决 | N 方协调 | ✅ |
| [MapReduce（映射归约）](patterns/map_reduce/) | 并行扇出处理 + 结果聚合 | LangGraph Send API | ✅ |

## 快速开始

### 1. 克隆 & 安装

```bash
git clone https://github.com/YOUR_USERNAME/agentflow.git
cd agentflow
uv sync
```

### 2. 配置 API Key

```bash
cp .env.example .env
# 编辑 .env，填入你的 OpenAI API Key
```

### 3. 运行任意模式

```bash
python patterns/reflection/example.py
python patterns/debate/example.py
python patterns/map_reduce/example.py
```

## 项目结构

```
agentflow/
├── patterns/              # 核心：每个模式一个子目录
│   ├── reflection/        # 写作 → 审阅循环
│   ├── debate/            # N 方辩论 + 主持人
│   └── map_reduce/        # 并行扇出 + 归约
├── docs/                  # 文档模板
└── tasks/                 # 进度追踪
```

## 环境要求

- Python 3.11+
- OpenAI API Key（默认模型：`gpt-4o-mini`）

## 运行测试

```bash
# 单元测试（无需 API Key）
pytest patterns/

# 集成测试（需要 OPENAI_API_KEY）
OPENAI_API_KEY=your-key pytest patterns/ -m "not skipif"
```

## 设计理念

1. **模式参考，不是框架** — 每个模式独立自包含，按需复制。
2. **3 分钟可运行** — 克隆、配置 Key、运行，就这么简单。
3. **双语文档** — 每个模式都有英文和中文 README。
4. **真实 LangGraph** — 不封装 LangGraph，学习原生 API。

## 贡献

请参阅 [docs/PATTERN_TEMPLATE.md](docs/PATTERN_TEMPLATE.md) 了解模式文档模板。

## 许可证

MIT
