---
title: 快速开始
description: 安装 AgentFlow 并运行你的第一个示例
---

# 快速开始

## 安装

```bash
# 使用 pip
pip install agentflow

# 或使用 uv
uv pip install agentflow
```

## 配置

在项目根目录创建 `.env` 文件，配置你的 API Key：

```bash
OPENAI_API_KEY=sk-your-api-key-here
```

## 运行示例

选择一个模式，运行示例：

```bash
# 反思循环模式
python -m agentflow.patterns.reflection.example

# 辩论模式
python -m agentflow.patterns.debate.example

# MapReduce 模式
python -m agentflow.patterns.map_reduce.example
```

## 下一步

- 浏览所有设计模式：[Pattern Overview](../index.md#patterns)
- 根据场景选择模式：[选型指南](selection.md)
