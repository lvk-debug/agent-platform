# 移动端开发文档（React Native / Expo）

> 适用范围：`mobile/`（Android / iOS 客户端）与后端为它新增的定时任务、推送能力。

## 1. 概述

移动端让用户在手机上随时与 AI 助手对话：

- **聊天**：完整还原设计稿的对话界面（顶部栏 / 消息流 / 快捷指令 / 语音与图片输入）
- **多模态输入**：按住麦克风说话（系统原生 ASR）、拍照或从相册选图上传
- **定时任务**：创建按「单次 / 每天 / 每周 / 自定义 cron」触发的任务，由**服务端调度**执行，结果通过推送下发

## 2. 技术栈

| 领域 | 选型 | 说明 |
|---|---|---|
| 基座 | Expo SDK 50（Managed）+ TypeScript 严格模式 | EAS 云端构建 iOS，无需 Mac |
| 导航 | React Navigation 6（Drawer + Native Stack） | 汉堡菜单打开会话抽屉 |
| 状态 | Zustand | 与 Web 端一致；流式文本用模块级缓冲 + 节流 |
| 网络 | axios + `react-native-sse` | RN 原生 `fetch` 会缓冲响应体，**不能**用于流式读取 |
| 安全存储 | `expo-secure-store` | JWT / 服务端地址存 Keychain / Keystore |
| 语音 | `@react-native-voice/voice` | 系统原生识别（含原生代码，需 development build） |
| 图片 | `expo-image-picker` + `expo-image-manipulator` | 选图拍照 + 压缩（长边 ≤1600px，质量 0.8） |
| 通知 | `expo-notifications` | 接收定时任务执行结果 |

后端新增：`apscheduler`（调度）、`httpx` 直连 Expo Push API（不引第三方 SDK）。

## 3. 目录结构

```
mobile/
├── App.tsx                     # 入口（手势根视图 + 安全区 + 状态栏）
├── app.config.js               # Expo 配置（extra.apiBaseUrl、权限、插件）
├── eas.json                    # EAS Build 配置
└── src/
    ├── navigation/
    │   ├── RootNavigator.tsx   # Stack(Login | Main(Drawer) | 任务列表 | 任务编辑 | 应用选择 | 设置)
    │   └── types.ts            # 路由参数类型
    ├── screens/                # 6 个页面
    │   ├── LoginScreen.tsx
    │   ├── ChatScreen.tsx              # 聊天主页
    │   ├── ScheduledTaskListScreen.tsx
    │   ├── ScheduledTaskEditScreen.tsx
    │   ├── AppPickerScreen.tsx
    │   └── SettingsScreen.tsx
    ├── components/             # ChatHeader / MessageList / MessageBubble /
    │                           # QuickPromptBar / ChatInputBar / VoiceRecordOverlay /
    │                           # AttachmentActionSheet / EmptyChatState / SessionsDrawerContent
    ├── hooks/
    │   ├── useVoiceInput.ts        # 原生 ASR 封装
    │   └── useAttachmentUpload.ts  # 选图压缩 + multipart 上传
    ├── services/               # http(axios) / auth / hermes(SSE) / apps /
    │                           # scheduledTask / notifications / storage
    ├── stores/                 # authStore / chatStore / taskStore
    ├── theme/                  # 设计令牌（深色 + 毛玻璃 + 渐变）
    └── types/                  # 共享类型 + voice 模块声明
```

## 4. 环境准备与启动

### 4.1 后端

```bash
cd backend
# ⚠️ 定时任务依赖，需先安装（本项目不自动执行 pip）
D:/AI/Miniconda3/envs/python311/python.exe -m pip install "apscheduler>=3.10.4"

# 建表（development 下由 create_all 自动完成；生产用迁移）
alembic upgrade head

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4.2 移动端

```bash
cd mobile
npm install

# 指定后端地址（默认 Android 模拟器 10.0.2.2:8000）
$env:API_BASE_URL="http://192.168.1.10:8000"; npx expo start
```

> 真机调试注意：
> - 后端必须 `--host 0.0.0.0`，并放行防火墙 8000 端口
> - CORS 对移动端无效（非浏览器），无需配置
> - Android 模拟器访问宿主机用 `10.0.2.2`，iOS 模拟器用 `localhost`，真机填局域网 IP
> - 服务端地址也可在 App「设置」页实时覆盖

### 4.3 开发构建（语音模块必需）

`@react-native-voice/voice` 含原生代码，**Expo Go 无法运行**：

```bash
eas build --profile development   # 云端构建，安装到设备/模拟器
# 或本地生成原生工程
npx expo prebuild && npx expo run:android
```

未安装 development build 时，App 会提示「语音不可用」，其余功能不受影响。

## 5. 构建与发布

```bash
eas build --profile preview      # 内测包
eas build --profile production   # 正式包（autoIncrement）
eas update --branch production   # OTA 热更新（JS 层改动）
```

`eas.json` 的 `development` profile 开启 `developmentClient` 与 iOS 模拟器构建。

> 首次使用需把 `app.config.js` 中 `extra.eas.projectId` 与 `updates.url` 换成自己项目的 ID（执行 `eas init` 获取）。

## 6. 后端：定时任务

### 6.1 数据模型

- `scheduled_tasks`：任务定义。含 `locked_at` 用于 **CAS 乐观锁**防重复执行
- `scheduled_task_runs`：每次执行的记录（状态 / 摘要 / 错误 / 耗时）
- `device_push_tokens`：移动端 Expo Push 令牌（token 唯一）

字段级说明见 `docs/DATABASE.md`，迁移脚本 `alembic/versions/scheduled_tasks_001.py`。

### 6.2 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/scheduled-tasks` | 我的任务列表 |
| POST | `/api/v1/scheduled-tasks` | 创建任务 |
| GET/PUT/DELETE | `/api/v1/scheduled-tasks/{id}` | 详情 / 更新 / 删除 |
| POST | `/api/v1/scheduled-tasks/{id}/enable` \| `/disable` | 启停（重新启用会清零失败计数） |
| POST | `/api/v1/scheduled-tasks/{id}/run` | 立即执行（后台异步，返回 202） |
| GET | `/api/v1/scheduled-tasks/{id}/runs` | 执行历史 |
| POST | `/api/v1/devices/register` \| `/unregister` | 登记 / 解绑推送令牌 |

> 与 `/api/v1/hermes/jobs` 的区别：`jobs` 是**代理上游 Hermes 网关**的计划任务（不落本地库、无用户隔离），供 Web 端工作助理使用；`/scheduled-tasks` 是平台自建、落库、按用户隔离的任务。两者互不影响。

### 6.3 周期参数

| schedule_type | 必填 | 说明 |
|---|---|---|
| `once` | `run_at` | 执行一次后自动停用 |
| `daily` | `run_time`（`HH:MM`）或 `cron_expr` | 服务层归一化为 cron 落库 |
| `weekly` | `run_time` + `weekday`（0=周一 … 6=周日） | 同上 |
| `cron` | `cron_expr`（5 段） | 直接使用 |

### 6.4 调度与并发

- 调度器为 **APScheduler 单例**（`services/scheduler.py`），在 `main.py` 的 `lifespan` 中启动，进程启动时由 `bootstrap_scheduled_jobs()` 从数据库重新注册已启用任务
- Job 存内存（`MemoryJobStore`），重启后自动恢复，**不需要**额外的 APScheduler 表
- **多 worker 部署**：只让一个进程设 `SCHEDULER_ENABLED=true`；即便多个进程都开启，执行器的 CAS 乐观锁（`locked_at`）也保证同一任务不会并发执行
- **失败处理**：连续失败达到 `SCHEDULER_MAX_FAILURES`（默认 3）次自动停用并记录错误；重新启用会清零计数
- **推送失败不影响任务结果**：`services/push.py` 中所有异常只记 warning

### 6.5 执行链路

```
到点触发 → execute_task(task_id)
        → CAS 抢锁（失败则跳过）
        → 取/建 HermesSession
        → 消费 HermesService.chat_stream 生成器收集正文
        → 写 ScheduledTaskRun（状态/摘要/耗时）
        → 回写 last_run_at / next_run_at / fail_count，释放锁
        → 查 DevicePushToken → Expo Push 下发
```

## 7. SSE 协议要点（易踩坑）

后端 `services/hermes.py::_sse_event` 输出格式：

```
event: content_delta
data: {"content": "..."}

```

事件名：`message_start` / `content_delta` / `tool_start` / `tool_result` / `message_end` / `error`。

**必须按 `event:` 行分流**。若只解析 `data:` 行并按 OpenAI 协议处理，工具事件会被当成无 `choices` 的空 chunk 静默丢弃（Web 端 2026-09 修复过的同类问题）。

RN 端用 `react-native-sse` 的 `addEventListener('<事件名>')` 分别监听，实现见 `src/services/hermes.ts`。

**流式渲染性能**：禁止每个 token 全量 `setState`。当前实现把文本写入模块级缓冲，每 40ms 节流 flush 一次，只更新当前消息项；消息列表用 inverted `FlatList` + `removeClippedSubviews`。

## 8. 已知限制

1. **`@react-native-voice/voice` 已停止维护**（npm 标记 deprecated，官方建议迁移到 `expo-speech-recognition`）。当前仍可用，如需长期维护建议替换，接口封装已集中在 `src/hooks/useVoiceInput.ts`，替换成本可控。
2. **占位图标**：`mobile/assets/` 下为脚本生成的纯色占位图，正式发布前需替换为真实设计稿。
3. **语音通话**：顶部电话图标为占位，点击提示"开发中"，实际语音交互走麦克风输入。
4. **应用对话**：`AppPickerScreen` 选择的应用目前只作为定时任务的 `app_id` 记录，聊天仍走 Hermes 会话。
5. **`eas.json` projectId**：默认为全零占位值，需 `eas init` 后替换才能构建与推送。
6. 推送在**模拟器上不可用**（Expo Push 需要真机），未授权时 `getPushToken()` 返回 `null` 而非报错。
