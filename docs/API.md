# API 接口文档

> 后端基于 FastAPI，自动生成交互式文档：
> - Swagger UI：http://localhost:8000/docs
> - ReDoc：http://localhost:8000/redoc
> - OpenAPI Schema：http://localhost:8000/api/v1/openapi.json

---

## 目录

- [1. 通用约定](#1-通用约定)
- [2. 认证](#2-认证)
- [3. 用户 `/users`](#3-用户-users)
- [4. 应用 `/apps`](#4-应用-apps)
- [5. 应用运行时对话 `/apps`（app-api）](#5-应用运行时对话-appsapp-api)
- [6. 发布配置 `/apps/{app_id}/publish`](#6-发布配置-appsapp_idpublish)
- [7. 聊天助手 `/chatbot`](#7-聊天助手-chatbot)
- [8. 工作流 `/workflow`](#8-工作流-workflow)
- [9. 智能体 `/agent`](#9-智能体-agent)
- [10. 知识库 `/knowledge`](#10-知识库-knowledge)
- [11. 模型 `/models`](#11-模型-models)
- [12. 工具 `/tools`](#12-工具-tools)
- [13. 评估 `/evaluation`](#13-评估-evaluation)
- [14. 工作助理 `/hermes`](#14-工作助理-hermes)
- [15. 未挂载模块](#15-未挂载模块)

---

## 1. 通用约定

### 1.1 基础信息

| 项 | 值 |
|---|---|
| 统一前缀 | `/api/v1` |
| 请求/响应格式 | `application/json`（除文件上传） |
| 字符编码 | UTF-8 |
| 鉴权方式 | `Authorization: Bearer <access_token>` |
| 路由重定向 | 关闭（`redirect_slashes=False`） |

### 1.2 根路径与健康检查

| 方法 | 路径 | 鉴权 | 说明 |
|---|---|---|---|
| GET | `/` | 否 | 返回平台名称、版本、文档地址 |
| GET | `/health` | 否 | 返回 `{"status": "healthy"}` |

### 1.3 状态码

| 码 | 含义 | 常见场景 |
|---|---|---|
| 200 | 成功 | |
| 400 | 请求错误 | 参数校验失败、账号已禁用 |
| 401 | 未认证 | Token 缺失/过期/无效、用户不存在 |
| 403 | 无权限 | 非超级管理员访问管理员接口 |
| 404 | 不存在 | 资源 ID 未找到 |
| 422 | 校验失败 | Pydantic Schema 校验不通过 |
| 500 | 服务端错误 | LLM 调用失败、内部异常 |

### 1.4 分页

项目使用**两套分页机制**，调用时需区分：

| 类型 | 响应模型 | 请求参数 | 适用模块 |
|---|---|---|---|
| 游标分页 | `CursorResponse[T]` | `cursor`（可选）、`limit` | `apps`、`knowledge` |
| 页码分页 | `XxxListResponse` | `page`（≥1）、`page_size`（1–100） | `evaluation` |

`CursorResponse[T]` 典型结构：

```jsonc
{
  "items": [...],
  "next_cursor": "eyJpZCI6MTB9",   // null 表示无下一页
  "has_more": true
}
```

---

## 2. 认证

除注册/登录外，所有接口均需在请求头携带：

```
Authorization: Bearer <access_token>
```

Token 由 `/api/v1/users/login` 返回，有效期默认 **8 天**（`ACCESS_TOKEN_EXPIRE_MINUTES = 60*24*8`），算法 `HS256`。

前端 axios 响应拦截器在收到 **401** 时会自动清除本地认证状态并跳转 `/login`。

---

## 3. 用户 `/users`

| 方法 | 路径 | 说明 | 响应模型 |
|---|---|---|---|
| POST | `/register` | 用户注册 | `UserResponse` |
| POST | `/login` | 登录（OAuth2 表单），返回 `access_token` | `Token` |
| GET | `/me` | 获取当前用户信息 | `UserResponse` |
| PUT | `/me` | 更新当前用户信息 | `UserResponse` |

---

## 4. 应用 `/apps`

| 方法 | 路径 | 说明 | 响应模型 |
|---|---|---|---|
| GET | `/` | 应用列表（游标分页） | `CursorResponse[AppResponse]` |
| POST | `/` | 创建应用 | `AppResponse` |
| GET | `/{app_id}` | 应用详情 | `AppResponse` |
| PUT | `/{app_id}` | 更新应用 | `AppResponse` |
| DELETE | `/{app_id}` | 删除应用 | 消息 |
| POST | `/{app_id}/publish` | 发布应用 | `AppResponse` |
| GET | `/{app_id}/conversations` | 会话列表（游标分页） | `CursorResponse` |
| GET | `/{app_id}/conversations/{conversation_id}/messages` | 会话消息列表 | — |

---

## 5. 应用运行时对话 `/apps`（app-api）

面向外部集成的运行时接口，由 `app_chat.py` 提供。

| 方法 | 路径 | 说明 | 响应模型 |
|---|---|---|---|
| POST | `/{app_id}/api/chat` | 聊天助手/工作流类型应用对话 | `ChatResponse` |
| POST | `/{app_id}/api/agent/chat` | Agent 类型应用对话 | `AgentChatResponse` |

---

## 6. 发布配置 `/apps/{app_id}/publish`

支持 5 个渠道：`api` · `mcp` · `embed` · `wechat` · `h5`

| 方法 | 路径 | 说明 | 响应模型 |
|---|---|---|---|
| GET | `` 或 `/` | 列出该应用所有渠道配置 | `PublishConfigListResponse` |
| GET | `/{channel}` | 获取单个渠道配置 | `PublishConfigResponse` |
| PUT | `/{channel}` | 更新渠道配置 | `PublishConfigResponse` |
| POST | `/{channel}/enable` | 启用渠道（自动生成密钥/代码） | `PublishConfigResponse` |
| POST | `/{channel}/disable` | 禁用渠道（配置保留） | `PublishConfigResponse` |

---

## 7. 聊天助手 `/chatbot`

| 方法 | 路径 | 说明 | 响应模型 |
|---|---|---|---|
| GET | `/{app_id}/config` | 获取配置 | `ChatbotConfig` |
| PUT | `/{app_id}/config` | 保存配置 | dict |
| POST | `/{app_id}/chat` | 对话（非流式） | `ChatResponse` |
| POST | `/{app_id}/chat/stream` | 对话（SSE 流式） | SSE |
| GET | `/{app_id}/conversations` | 会话列表 | `List[ConversationResponse]` |
| GET | `/{app_id}/conversations/{conversation_id}/messages` | 会话消息（`limit` 默认 50） | `List[MessageResponse]` |
| DELETE | `/{app_id}/conversations/{conversation_id}` | 删除会话 | — |

---

## 8. 工作流 `/workflow`

| 方法 | 路径 | 说明 | 响应模型 |
|---|---|---|---|
| GET | `/{app_id}/config` | 获取图配置 | `WorkflowConfig` |
| PUT | `/{app_id}/config` | 保存图配置（version 自增） | dict |
| POST | `/{app_id}/run` | 执行工作流（非流式） | dict |
| POST | `/{app_id}/run/stream` | 执行工作流（SSE 流式） | SSE |
| POST | `/{app_id}/llm-run` | 单节点调试：仅执行某个 LLM 节点 | `LLMNodeRunResponse` |
| GET | `/{app_id}/runs` | 运行记录列表 | `List[WorkflowRunResponse]` |
| GET | `/{app_id}/runs/{run_id}` | 运行记录详情 | `WorkflowRunResponse` |
| POST | `/{app_id}/dsl/export` | 导出 DSL | `DSLExportResponse` |
| POST | `/{app_id}/dsl/import` | 导入 DSL | dict |

### 8.1 执行请求体

```jsonc
POST /api/v1/workflow/{app_id}/run
{
  "inputs": { "query": "用户问题", "var1": "value1" },
  "thread_id": "optional-thread-id"    // 用于 checkpoint 复用
}
```

### 8.2 执行响应

```jsonc
{
  "run_id": 123,
  "status": "completed",
  "outputs": { "answer": "..." },
  "node_runs": { "node-1": {...}, "node-2": {...} },
  "execution_log": [ { "node_id": "node-1", "type": "llm", ... } ]
}
```

### 8.3 流式事件（SSE）

| 事件 | data 内容 | 说明 |
|---|---|---|
| `node_start` | `{ node_id, type }` | 节点开始执行 |
| `node_log` | execution log 条目 | 节点执行日志 |
| `llm_token` | `{ node_id, token }` | LLM 增量 token |
| `done` | `{ outputs, execution_log }` | 执行完成 |
| `error` | `{ message }` | 执行失败 |

---

## 9. 智能体 `/agent`

| 方法 | 路径 | 说明 | 响应模型 |
|---|---|---|---|
| GET | `/{app_id}/config` | 获取配置 | `AgentConfigResponse` |
| GET | `/{app_id}/debug/config` | 调试用配置（含更多内部信息） | — |
| PUT | `/{app_id}/config` | 保存配置 | — |
| POST | `/{app_id}/chat` | 对话（非流式） | `AgentChatResponse` |
| POST | `/{app_id}/chat/stream` | 对话（SSE 流式） | SSE |
| GET | `/{app_id}/debug/model` | 查看当前调试模型 | — |

---

## 10. 知识库 `/knowledge`

| 方法 | 路径 | 说明 | 响应模型 |
|---|---|---|---|
| GET | `/` | 知识库列表（游标分页） | `CursorResponse[KnowledgeBaseResponse]` |
| POST | `/` | 创建知识库 | `KnowledgeBaseResponse` |
| GET | `/{kb_id}` | 知识库详情 | `KnowledgeBaseResponse` |
| PUT | `/{kb_id}` | 更新知识库 | `KnowledgeBaseResponse` |
| DELETE | `/{kb_id}` | 删除知识库 | 消息 |
| POST | `/{kb_id}/documents` | 上传文档（multipart） | `DocumentResponse` |
| GET | `/{kb_id}/documents` | 文档列表（游标分页） | `CursorResponse[DocumentResponse]` |
| DELETE | `/{kb_id}/documents/{doc_id}` | 删除文档 | 消息 |
| GET | `/{kb_id}/documents/{doc_id}/segments` | 分片列表（游标分页） | `CursorResponse[DocumentSegmentResponse]` |
| POST | `/{kb_id}/documents/{doc_id}/retry` | 重试处理失败的文档 | — |
| GET | `/{kb_id}/documents/{doc_id}/content` | 获取文档解析后全文 | — |
| POST | `/{kb_id}/documents/{doc_id}/chunks/preview` | **分片预览**（调参用，不落库） | `ChunkPreviewResponse` |
| POST | `/{kb_id}/documents/{doc_id}/process` | 执行解析 + 分片 + 向量化 | — |
| POST | `/{kb_id}/search` | 检索测试 | `SearchResponse` |
| POST | `/{kb_id}/crawl` | URL 爬取入库 | `CrawlResponse` |

### 10.1 支持的文件类型

| 扩展名 | 映射 `file_type` |
|---|---|
| `.pdf` | `pdf` |
| `.xlsx` / `.xls` | `excel` |
| `.md` | `markdown` |
| `.docx` | `docx` |
| `.html` | `html` |
| `.txt` | `txt` |
| `.epub` | `epub` |

### 10.2 检索请求

```jsonc
POST /api/v1/knowledge/{kb_id}/search
{
  "query": "检索词",
  "top_k": 5,
  "score_threshold": 0.5,     // 可选，默认取 RAG_SCORE_THRESHOLD
  "enable_hyde": false,       // 假设性文档嵌入
  "enable_query_expansion": false
}
```

---

## 11. 模型 `/models`

| 方法 | 路径 | 说明 | 响应模型 |
|---|---|---|---|
| GET | `/providers` | 供应商列表 | `List[ModelProviderResponse]` |
| POST | `/providers` | 创建供应商 | `ModelProviderResponse` |
| GET | `/providers/{provider_id}` | 供应商详情 | `ModelProviderResponse` |
| PUT | `/providers/{provider_id}` | 更新供应商 | `ModelProviderResponse` |
| DELETE | `/providers/{provider_id}` | 删除供应商 | — |
| GET | `/providers/{provider_id}/models` | 该供应商下的模型列表 | `List[ModelResponse]` |
| POST | `/providers/{provider_id}/models` | 新增模型 | `ModelResponse` |
| PUT | `/providers/{provider_id}/models/{model_id}` | 更新模型 | `ModelResponse` |
| DELETE | `/providers/{provider_id}/models/{model_id}` | 删除模型 | — |
| GET | `/` | 全部模型列表（扁平） | `List[ModelResponse]` |

---

## 12. 工具 `/tools`

| 方法 | 路径 | 说明 | 响应模型 |
|---|---|---|---|
| GET | `/` | 工具列表 | `List[ToolResponse]` |
| POST | `/` | 创建工具 | `ToolResponse` |
| GET | `/templates` | 内置模板市场 | `List[ToolTemplateResponse]` |
| GET | `/templates/categories` | 模板分类 | — |
| POST | `/install/{template_id}` | 一键安装模板 | `ToolResponse` |
| POST | `/import/mcp` | 从 MCP Server URL 导入工具 | `List[ToolResponse]` |
| GET | `/{tool_id}` | 工具详情 | `ToolResponse` |
| PUT | `/{tool_id}` | 更新工具 | `ToolResponse` |
| DELETE | `/{tool_id}` | 删除工具 | — |
| POST | `/{tool_id}/test` | 测试工具调用 | `ToolTestResponse` |

---

## 13. 评估 `/evaluation`

### 13.1 数据集

| 方法 | 路径 | 响应模型 |
|---|---|---|
| POST | `/datasets` | `DatasetResponse` |
| GET | `/datasets` | `List[DatasetResponse]` |
| GET | `/datasets/{dataset_id}` | `DatasetDetailResponse` |
| PUT | `/datasets/{dataset_id}` | `DatasetResponse` |
| DELETE | `/datasets/{dataset_id}` | — |
| POST | `/datasets/{dataset_id}/test-cases` | `TestCaseResponse` |
| GET | `/datasets/{dataset_id}/test-cases` | `TestCaseListResponse` |
| POST | `/datasets/{dataset_id}/import` | `DatasetImportResponse` |

支持导入的数据集类型：`bfcl`（Berkeley Function Calling Leaderboard）、`gaia`、自定义 JSON。

### 13.2 评估器

| 方法 | 路径 | 响应模型 |
|---|---|---|
| POST | `/evaluators` | `EvaluatorResponse` |
| GET | `/evaluators` | `EvaluatorListResponse` |
| GET | `/evaluators/{evaluator_id}` | `EvaluatorResponse` |
| PUT | `/evaluators/{evaluator_id}` | `EvaluatorResponse` |
| DELETE | `/evaluators/{evaluator_id}` | — |
| POST | `/evaluators/init-builtin` | 初始化内置评估器 |

### 13.3 评估任务（Experiment）

| 方法 | 路径 | 响应模型 |
|---|---|---|
| POST | `/evaluations` | `EvaluationResponse` |
| GET | `/evaluations` | `EvaluationListResponse` |
| GET | `/evaluations/{eval_id}` | `EvaluationDetailResponse` |
| POST | `/evaluations/{eval_id}/start` | 启动评估 |
| POST | `/evaluations/{eval_id}/cancel` | 取消评估 |
| DELETE | `/evaluations/{eval_id}` | — |
| GET | `/evaluations/{eval_id}/results` | `EvaluationResultListResponse` |
| GET | `/evaluations/{eval_id}/results/{result_id}` | `EvaluationResultDetailResponse` |
| GET | `/evaluations/{eval_id}/report` | `EvaluationReport` |

`/results` 支持筛选参数：`page`、`page_size`、`passed`、`evaluator_id`、`category`

### 13.4 执行轨迹

| 方法 | 路径 | 响应模型 |
|---|---|---|
| GET | `/traces` | `TraceListResponse` |
| GET | `/traces/{trace_id}` | `TraceResponse` |

### 13.5 分析看板

| 方法 | 路径 | 响应模型 |
|---|---|---|
| GET | `/analytics/overview` | `AnalyticsOverview` |
| GET | `/analytics/comparison` | `ComparisonResult` |

---

## 14. 工作助理 `/hermes`

| 方法 | 路径 | 说明 | 响应模型 |
|---|---|---|---|
| GET | `/sessions` | 会话列表 | `List[SessionResponse]` |
| POST | `/sessions` | 创建会话 | `SessionResponse` |
| DELETE | `/sessions/{session_id}` | 删除会话 | — |
| GET | `/sessions/{session_id}/messages` | 会话消息 | `List[MessageResponse]` |
| POST | `/sessions/{session_id}/chat` | 对话（非流式） | — |
| POST | `/sessions/{session_id}/stream` | 对话（**SSE 流式**，推荐） | SSE |
| GET | `/attachments` | 某会话下全部附件（`?session_id=`，需本人） | `List[AttachmentResponse]` |
| POST | `/attachments` | 上传附件（multipart） | `AttachmentResponse` |
| GET | `/attachments/{id}/preview` | 预览/下载（归属校验） | 文件流 |
| DELETE | `/attachments/{id}` | 删除附件 | — |
| GET | `/quick-prompts` | 可用提示词（内置 + 本人） | `List[QuickPromptResponse]` |
| POST | `/quick-prompts` | 新建提示词 | `QuickPromptResponse` |
| PUT | `/quick-prompts/{id}` | 修改本人提示词 | `QuickPromptResponse` |
| DELETE | `/quick-prompts/{id}` | 删除本人提示词（内置不可删） | — |
| POST | `/quick-prompts/init-builtin` | 初始化内置默认集（幂等） | `{"added","total_builtin"}` |
| GET | `/health` | 检查 Hermes 服务连通性 | `HealthResponse` |

### 14.1 SSE 事件

| 事件 | 说明 |
|---|---|
| `message_start` | 开始接收 |
| `content_delta` | 内容增量 |
| `tool_start` | 工具开始执行 |
| `tool_result` | 工具执行完成 |
| `message_end` | 消息结束（含 usage） |
| `error` | 发生错误 |

### 14.2 附件与快捷提示词

**附件上传（两步式）**：`POST /attachments` 先 `multipart` 上传落盘并（文档）同步解析，返回 `id`；随后 `POST /sessions/{id}/stream` 请求体携带 `attachment_ids: number[]` 引用。

- `attachment_ids` 经 `HermesService.build_history` 转为 content 数组：图片 → `image_url`(base64 data URI)，文档 → `文件名 + parsed_text`；历史图片仅最近 `HERMES_HISTORY_IMAGE_TURNS` 轮保留，更早降级为文本占位。
- 类型白名单：图片 `png/jpg/jpeg/gif/webp`（单图 ≤ `ATTACHMENT_MAX_IMAGE_MB`）；文档 `pdf/docx/xlsx/xls/md/txt/html/epub`（≤ `ATTACHMENT_MAX_DOC_MB`）。落盘用 UUID 命名杜绝路径穿越。
- `GET /attachments/{id}/preview` 与 `DELETE /attachments/{id}` 均校验 `user_id` 归属。

**快捷提示词**：`GET /quick-prompts` 返回「内置 ∪ 本人自建」；`POST/PUT/DELETE` 仅限本人自建，`is_builtin=True` 的内置项不可删改。`init-builtin` 按标题幂等写入默认 8 条。

---

## 15. 未挂载模块

以下模块代码已实现但**未注册到路由**，当前不可访问：

| 模块文件 | 预期前缀 | 状态 |
|---|---|---|
| `api/endpoints/openclaw.py` | `/openclaw` | 未在 `api/api.py` 中 include |

详见 [ARCHITECTURE.md §11](./ARCHITECTURE.md#11-已知问题与技术债)。
