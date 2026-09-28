# 文档索引

> 智能体平台（Agent Platform）文档中心。

---

## 新人入门路径

1. [README.md](../README.md) — 项目简介与快速开始
2. **[架构总览](./ARCHITECTURE.md)** — ⭐ 必读，理解整体设计
3. [数据库设计](./DATABASE.md) — 数据模型与表结构
4. [后端模块](./MODULES.md) / [前端架构](./FRONTEND.md) — 按你的工作方向选读
5. [移动端](./MOBILE.md) — React Native (Expo) 客户端与定时任务能力
6. [接口文档](./API.md) — 开发联调时查阅

---

## 核心文档

| 文档 | 内容 | 适用对象 |
|---|---|---|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 项目定位、技术栈、整体架构、分层结构、数据模型总览、API 地图、核心执行流程、配置与部署、设计决策、已知问题 | 所有人 |
| [DATABASE.md](./DATABASE.md) | 20+ 张表字段级说明、ER 图、枚举字典、迁移注意事项 | 后端、数据 |
| [API.md](./API.md) | 12 个路由模块的完整端点清单、分页约定、SSE 事件、错误码 | 前后端联调 |
| [MODULES.md](./MODULES.md) | 后端各 Service 职责、核心类与关键函数、模块依赖图 | 后端 |
| [FRONTEND.md](./FRONTEND.md) | 目录结构、路由表、状态管理、组件分层、工作流编辑器、开发约定 | 前端 |
| [MOBILE.md](./MOBILE.md) | 移动端架构、语音/图片输入、SSE 协议要点、定时任务与推送、构建发布 | 移动端 |

---

## 专题文档（历史）

| 文档 | 内容 | 状态 |
|---|---|---|
| [paper-agent-testing.md](./paper-agent-testing.md) | Paper Agent 测试与评测设计：20 条用例、指标口径、执行架构、降级策略 | 当前实现，随代码同步更新 |
| [hermes-migration-plan .md](./hermes-migration-plan%20.md) | Hermes 迁移实施方案（含 `useChatStream` 参考代码） | 已落地，要点已并入 [ARCHITECTURE.md §7.5](./ARCHITECTURE.md#75-工作助理-sse-中继hermes) |
| [plan.md](./plan.md) | 项目整体开发计划 | 参考 |
| [platform-guide.md](./platform-guide.md) | 平台使用指南 | 参考 |

> ⚠️ 专题文档为开发过程中的设计稿，可能与当前实现存在偏差。**以核心文档为准**；如发现冲突请更新核心文档，而非修改历史设计稿。

> 📌 索引中曾记录的 `hermes-design.md`、`eval-system-redesign.md` 当前已不存在于仓库；其结论已分别并入 [ARCHITECTURE.md §7.5](./ARCHITECTURE.md#75-工作助理-sse-中继hermes) 与 [DATABASE.md §10 评估域](./DATABASE.md#10-评估域)。

---

## 其他入口

| 资源 | 位置 |
|---|---|
| 交互式 API 文档 | 启动后端后访问 http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| 环境变量模板 | `backend/.env.example` |
| AI 协作指引 | [CLAUDE.md](../CLAUDE.md) |

---

## 维护约定

1. **核心文档（上表前 5 篇）为唯一事实来源**，修改实现后同步更新
2. 新增架构级决策时，在 [ARCHITECTURE.md §10 关键设计决策](./ARCHITECTURE.md#10-关键设计决策) 中补充记录（说明决策 + 原因 + 代价）
3. 发现的技术债记录在 [ARCHITECTURE.md §11](./ARCHITECTURE.md#11-已知问题与技术债)
4. 专题设计文档完成后，将其结论并入核心文档，并在索引中标记为"已落地"
