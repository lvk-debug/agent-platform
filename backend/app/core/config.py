import os
from typing import List, Union
from pathlib import Path
from pydantic import AnyHttpUrl, validator
from pydantic_settings import BaseSettings

# 获取项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    # 项目配置
    PROJECT_NAME: str = "智能体平台"
    PROJECT_VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"

    # 环境配置
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # 安全配置
    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    ALGORITHM: str = "HS256"
    ADMIN_PASSWORD: str = "admin123"  # 默认管理员密码，生产环境请修改

    # 数据库配置
    DATABASE_URL: str = "sqlite:///./agent_platform.db"
    VECTOR_STORE: str = "sqlite_vector"  # sqlite_vector 或 pgvector
    VECTOR_DB_DIR: str = "./data/vectors"  # SQLiteVec 向量数据库目录

    # Qdrant配置
    QDRANT_URL: str = ""
    QDRANT_API_KEY: str = ""  # 对应 QDRANT__SERVICE__API_KEY，留空表示不鉴权
    QDRANT_COLLECTION: str = "agent_platform"  # 统一 collection 名称
    RAG_SCORE_THRESHOLD: float = 0.5  # minimum cosine similarity to keep
    
    # Redis配置 (可选)
    REDIS_URL: str = "redis://localhost:6379/0"

    # CORS配置
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []
    CORS_ORIGINS: List[AnyHttpUrl] = []

    @validator("BACKEND_CORS_ORIGINS", "CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # 文件存储配置
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 100

    # 会话附件配置（工作助理）
    ATTACHMENT_SUBDIR: str = "hermes"  # UPLOAD_DIR 下的子目录
    ATTACHMENT_MAX_IMAGE_MB: int = 5  # 单图上限（转 base64 后体积膨胀约 33%）
    ATTACHMENT_MAX_DOC_MB: int = 20  # 单个文档上限
    ATTACHMENT_TEXT_LIMIT: int = 30000  # 文档注入上下文的字符上限，超出截断

    # LLM配置
    OPENAI_API_KEY: str = ""
    OPENAI_API_BASE: str = "https://api.openai.com/v1"
    ANTHROPIC_API_KEY: str = ""
    LOCAL_LLM_BASE_URL: str = "http://localhost:11434"
    TAVILY_API_KEY: str = ""

    # 外部知识库配置 (可选)
    EXTERNAL_KB_API_KEY: str = ""
    EXTERNAL_KB_API_URL: str = ""

    # ---------------- Paper Agent（论文研读与综述） ----------------
    PAPER_AGENT_OUTPUT_DIR: str = "./outputs/paper-agent"  # 产物根目录
    PAPER_AGENT_MAX_PAPERS: int = 10                       # 单次运行最多处理论文数
    ARXIV_MAX_RESULTS: int = 20                            # 单源单次检索拉取上限
    ARXIV_REQUEST_TIMEOUT: int = 120                        # 单源检索超时（秒）
    SEMANTIC_SCHOLAR_API_KEY: str = ""                     # 可选，提高 S2 限流配额
    OPENALEX_API_KEY: str = ""                             # 可选
    OPENALEX_MAILTO: str = ""                              # 建议填写，OpenAlex 稳定配额
    # M2：PDF 下载与解析
    PAPER_AGENT_MAX_PDF_PAPERS: int = 2                    # 单次最多下载解析的 PDF 数
    PAPER_AGENT_PDF_MAX_MB: int = 30                       # 单个 PDF 体积上限
    PAPER_AGENT_PDF_TIMEOUT: int = 60                      # PDF 下载超时（秒）
    PAPER_AGENT_MAX_SECTION_CHARS: int = 6000              # 送入 LLM 的正文截断长度
    # M3：引用网络扩展
    PAPER_AGENT_CITATION_DEPTH: int = 1                    # 引用扩展深度（硬上限 2）
    # M4：评测
    PAPER_AGENT_EVAL_DIR: str = "./outputs/paper-agent-evals"
    # 评测后端：auto（装了 deepeval 则 both，否则 builtin）/ builtin / deepeval / both
    PAPER_AGENT_EVAL_BACKEND: str = "auto"
    # 关闭 DeepEval 遥测，不接入 Confident AI 云端
    DEEPEVAL_TELEMETRY_OPT_OUT: bool = True
    # DeepEval 单指标任务超时（秒）；0 表示不覆盖 DeepEval 默认值。
    # 推理模型（如 mimo）响应很慢，超时太小会导致指标被取消并记为 error。
    DEEPEVAL_PER_TASK_TIMEOUT_SECONDS: int = 300

    # 客服自动评测：是否启用 DeepEval 作为唯一自动裁判（替代原自研四维度 LLM 裁判）
    SUPPORT_DEEPEVAL_ENABLED: bool = True

    # 向量数据库配置
    VECTOR_DB_NAME: str = "agent_platform"
    EMBEDDING_MODEL: str = ""
    EMBEDDING_SPARSE_MODEL: str = "Qdrant/bm25"  # fastembed 稀疏模型，用于 Qdrant 混合检索
    EMBEDDING_MODEL_PATH: str = ""
    EMBEDDING_DIMENSION: int = 0  # 0 表示自动检测

    # Hermes Agent 配置
    HERMES_API_URL: str = ""            # Hermes API Server 地址 (如 http://124.221.124.165:8642/v1)
    HERMES_API_KEY: str = ""            # API Server Bearer Key
    HERMES_MODEL: str = "hermes-agent"  # 默认模型名
    HERMES_REQUEST_TIMEOUT: int = 300   # 单次请求超时 (秒)
    HERMES_MAX_HISTORY_MESSAGES: int = 20  # 每次请求携带的最大历史消息数
    HERMES_HISTORY_IMAGE_TURNS: int = 1  # 历史中保留图片的最近轮次数，其余降级为文本占位
    HERMES_CAPABILITY_CACHE_TTL: int = 60  # 能力/模型/健康状态缓存秒数
    HERMES_JOBS_ENABLED: bool = True  # 是否启用 Jobs（后台计划任务）代理
    HERMES_DEFAULT_TOOLS: str = (  # 内置工具清单（逗号分隔 name:label:desc，用于前端展示）
        "terminal:终端:执行 shell 命令、脚本与构建任务,"
        "file:文件:读写与检索本地文件,"
        "web_search:联网搜索:检索实时网络信息,"
        "browser:浏览器:打开网页并提取内容,"
        "image:图像:生成与理解图片,"
        "tts:语音:文本转语音与音频处理"
    )

    # 日志配置
    LOG_LEVEL: str = "INFO"

    # ---------------- 定时任务调度（移动端 / 平台自建） ----------------
    # 多 worker 部署时只让一个进程开启，其余设为 false；执行器另有数据库乐观锁兜底
    SCHEDULER_ENABLED: bool = True
    SCHEDULER_TIMEZONE: str = "Asia/Shanghai"
    SCHEDULER_MAX_WORKERS: int = 8
    # 触发点被错过后仍允许补跑的宽限秒数
    SCHEDULER_MISFIRE_GRACE_SECONDS: int = 300
    # 执行锁有效期：需大于单次任务最长耗时，超时后允许其他进程接管
    SCHEDULER_LOCK_TIMEOUT_SECONDS: int = 1800
    # 连续失败达到该次数后自动停用任务（0 表示不自动停用）
    SCHEDULER_MAX_FAILURES: int = 3

    # ---------------- 移动端推送（Expo Push） ----------------
    EXPO_PUSH_ENABLED: bool = True
    EXPO_PUSH_API_URL: str = "https://exp.host/--/api/v2/push/send"
    EXPO_PUSH_CHANNEL: str = "scheduled-tasks"
    # 可选：Expo 账户 access token，提高推送配额
    EXPO_ACCESS_TOKEN: str = ""

    # ---------------- 学习助手（Learning） ----------------
    LEARNING_UPLOAD_SUBDIR: str = "learning"      # UPLOAD_DIR 下的资源目录
    LEARNING_EXPORT_SUBDIR: str = "exports"       # 画布导出图目录（在 learning 下）
    LEARNING_MAX_DOC_MB: int = 50                 # 单个文档上传上限
    # 抓取出海资源（YouTube）时的可选代理；yt-dlp 反爬策略频繁变更，建议定期升级其版本
    YTDLP_PROXY: str = ""
    # YouTube 播放器客户端标识。抓取被 PO Token / 反爬拦截时可尝试切换：
    # web_safari / tv / android_vr / mweb；留空则使用 yt-dlp 默认客户端
    YTDLP_PLAYER_CLIENT: str = ""
    # JavaScript runtime，用于完成 YouTube 的 PO Token / n-parameter 签名。
    # **缺失时自动字幕将无法下载**（yt-dlp 会提示 No supported JavaScript runtime）。
    # 留空则自动探测 node → deno → bun → quickjs；也可显式指定 `node` 或 `node:可执行文件绝对路径`
    YTDLP_JS_RUNTIME: str = ""
    # 抓取出海视频时是否需要 Cookies（见 .env.example 说明）
    YTDLP_COOKIEFILE: str = ""
    LEARNING_MEDIA_TIMEOUT: int = 120             # 元数据/字幕抓取超时（秒）
    # 心跳间隔超过该秒数判定会话断开，自动结算旧会话并开新会话
    LEARNING_HEARTBEAT_IDLE_SECONDS: int = 300
    LEARNING_EXPORT_MAX_EDGE: int = 1920          # 导出图长边上限
    LEARNING_EXPORT_MAX_MB: int = 5               # 单张导出图上限（超则递归降质）
    LEARNING_MAX_PAGE_CHARS: int = 200000         # 单页返回文本上限，防止超大页打爆响应

    # ---------------- 学习助手 · AI 问答 ----------------
    # 学习资源不建 knowledge_bases 记录，直接用「虚拟 kb_id」操作向量库：
    # vector_store 用 kb_{kb_id}.db 做文件名，故基数取大值避开真实知识库自增 id。
    LEARNING_KB_ID_BASE: int = 1_000_000
    # 索引切片：单片段字符数上限与单资源片段总数上限（防止超长视频/大文档打爆向量库）
    LEARNING_INDEX_CHUNK_CHARS: int = 600
    LEARNING_INDEX_MAX_CHUNKS: int = 2000
    # 视频字幕按时间窗聚合成片段（毫秒），避免逐条字幕太碎
    LEARNING_INDEX_WINDOW_MS: int = 30_000
    # 每次提问检索的片段数
    LEARNING_CHAT_TOP_K: int = 5
    # 上下文总字符预算：检索片段 + 当前位置窗口，超出按优先级截断
    LEARNING_CHAT_CONTEXT_CHARS: int = 6000
    # 用户手动 @ 指定的上下文独立预算：这部分优先保证，不被检索结果挤掉
    LEARNING_CHAT_PINNED_CONTEXT_CHARS: int = 3000
    # 携带的历史消息轮数（一问一答算一轮），控制 prompt 体积
    LEARNING_CHAT_HISTORY_TURNS: int = 4
    # 当前位置窗口：文档取前后页数，视频取前后毫秒
    LEARNING_CHAT_PAGE_WINDOW: int = 1
    LEARNING_CHAT_TRANSCRIPT_WINDOW_MS: int = 30_000
    # 生成参数
    LEARNING_CHAT_TEMPERATURE: float = 0.3
    LEARNING_CHAT_MAX_TOKENS: int = 2048
    # 推荐问题生成超时（秒），超时则回退固定模板
    LEARNING_SUGGEST_TIMEOUT: int = 25
    # 生成摘要/推荐问题时喂给模型的内容字符上限
    LEARNING_SUMMARY_CHARS: int = 3000

    # ---------------- 智能客服（Support） ----------------
    # 单次提问从每个绑定知识库取回的片段数（多库结果合并后再按分数截断）
    SUPPORT_CHAT_TOP_K: int = 5
    # 前端/配置可设的上限，防止一次拉回过多片段打爆 prompt
    SUPPORT_CHAT_MAX_TOP_K: int = 20
    # 上下文总字符预算：所有引用片段拼起来不超过它
    SUPPORT_CHAT_CONTEXT_CHARS: int = 6000
    SUPPORT_CHAT_REFERENCE_CHARS: int = 800   # 单条引用片段的字符上限
    # 携带的历史消息轮数（一问一答算一轮），控制 prompt 体积
    SUPPORT_CHAT_HISTORY_TURNS: int = 6
    # 生成参数：客服回答要稳，temperature 不宜高
    SUPPORT_CHAT_TEMPERATURE: float = 0.4
    SUPPORT_CHAT_MAX_TOKENS: int = 1500
    # 意图识别：一次轻量调用、强制 JSON 输出，超时后降级为关键词规则
    SUPPORT_INTENT_TIMEOUT: int = 15
    # 坐席「AI 建议回复」生成超时（秒）
    SUPPORT_SUGGEST_TIMEOUT: int = 30

    # 多 Agent 编排各环节超时（秒）：任一环节超时即降级，不拖垮整次问答
    SUPPORT_AGENT_INTENT_TIMEOUT: int = 15      # Router 意图识别
    SUPPORT_AGENT_TOOL_TIMEOUT: int = 20       # Tool Agent 工具调用 + 结果汇总
    SUPPORT_AGENT_KNOWLEDGE_TIMEOUT: int = 30   # Knowledge Agent 起草
    SUPPORT_AGENT_ESCALATION_TIMEOUT: int = 30  # Escalation Agent 生成工单
    SUPPORT_AGENT_SUMMARY_TIMEOUT: int = 30     # Summary Agent 汇总最终回复
    # 工具调用最多循环轮数：防止模型反复要求调工具造成死循环
    SUPPORT_AGENT_MAX_TOOL_ROUNDS: int = 2
    # 知识库检索最高分低于该值视为「没把握」，走兜底话术
    SUPPORT_AGENT_LOW_CONFIDENCE: float = 0.35

    model_config = {
        "case_sensitive": True,
        "env_file": (".env.local", ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
