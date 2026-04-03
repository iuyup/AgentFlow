---
title: 选型指南
description: 根据场景选择合适的 AgentFlow 设计模式
---

# 选型指南

根据你的业务场景，选择合适的设计模式：

```mermaid
flowchart TD
    Start(["你的场景需要什么？"])
    
    Q1{是否需要人类<br/>介入确认？}
    Q1-- 是 --> Hitl["👤 Human-in-the-Loop<br/>人机协作"]
    Q1-- 否 --> Q2{任务是否<br/>复杂多面？}
    
    Q2-- 简单任务 --> Q3{是否需要<br/>检索增强？}
    Q2-- 复杂任务 --> Q4{是否有安全<br/>合规要求？}
    
    Q3-- 是 --> RAG["📚 RAG-Agent<br/>检索增强"]
    Q3-- 否 --> Q5{是否需要<br/>质量优化？}
    
    Q5-- 是 --> Refl["🔄 Reflection<br/>反思循环"]
    Q5-- 否 --> Q6{是否需要<br/>多专家链式？}
    
    Q6-- 是 --> CoE["🔗 Chain-of-Experts<br/>专家链"]
    Q6-- 否 --> Single["✓ 单 Agent<br/>无需模式"]
    
    Q4-- 是 --> Guard["🛡️ GuardRail<br/>风控守门"]
    Q4-- 否 --> Q7{是否有层级<br/>管理结构？}
    
    Q7-- 是 --> Hier["📊 Hierarchical<br/>层级委派"]
    Q7-- 否 --> Q8{是否需要<br/>并行处理？}
    
    Q8-- 是 --> MR["🗂️ MapReduce<br/>并行处理"]
    Q8-- 否 --> Q9{是否有对立<br/>观点权衡？}
    
    Q9-- 是 --> Deb["⚔️ Debate<br/>辩论模式"]
    Q9-- 否 --> Q10{是否需要<br/>投票决策？}
    
    Q10-- 是 --> Vot["🗳️ Voting<br/>投票决策"]
    Q10-- 否 --> Swarm["🐝 Swarm<br/>群体智能"]
    
    class Start terminal
    class Q1,Q2,Q3,Q4,Q5,Q6,Q7,Q8,Q9,Q10 decision
    class Hitl,RAG,Refl,CoE,Single,Hier,MR,Deb,Vot,Swarm,Guard pattern
    
    click Hitl href "/patterns/human_in_the_loop_zh/"
    click RAG href "/patterns/rag_agent_zh/"
    click Refl href "/patterns/reflection_zh/"
    click CoE href "/patterns/chain_of_experts_zh/"
    click Hier href "/patterns/hierarchical_zh/"
    click MR href "/patterns/map_reduce_zh/"
    click Deb href "/patterns/debate_zh/"
    click Vot href "/patterns/voting_zh/"
    click Swarm href "/patterns/swarm_zh/"
    click Guard href "/patterns/guardrail_zh/"
```

_点击模式名称可跳转到对应中文文档_

| 场景 | 推荐模式 | 原因 |
|------|----------|------|
| 需要迭代优化输出质量 | [反思循环](../patterns/reflection_zh.md) | 自我评审循环，持续改进 |
| 需要多角度分析问题 | [辩论模式](../patterns/debate_zh.md) | 对抗性辩论，全面评估 |
| 需要并行处理大量数据 | [MapReduce](../patterns/map_reduce_zh.md) | 并行扇出，聚合结果 |
| 需要层级管理任务分配 | [层级委派](../patterns/hierarchical_zh.md) | Manager 统筹，Worker 执行 |
| 需要多 Agent 投票决策 | [投票决策](../patterns/voting_zh.md) | 民主决策，少数服从多数 |
| 需要安全内容过滤 | [风控守门](../patterns/guardrail_zh.md) | 检查点拦截，风险控制 |
| 需要知识库检索增强 | [RAG-Agent](../patterns/rag_agent_zh.md) | 动态检索，知识增强 |
| 需要专家依次处理 | [专家链](../patterns/chain_of_experts_zh.md) | 专业化分工，顺序传递 |
| 需要人类介入确认 | [人机协作](../patterns/human_in_the_loop_zh.md) | 关键节点，人工审批 |
| 需要去中心化协作 | [群体智能](../patterns/swarm_zh.md) | 动态协调，自组织 |
