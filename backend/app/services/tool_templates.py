"""
预置工具模板
提供常用外部工具的预配置模板，用户可一键安装到工具库
"""

from typing import Any, Dict, List, Optional


TOOL_TEMPLATES: List[Dict[str, Any]] = [
    # ============ 搜索 ============
    {
        "id": "tavily_search",
        "name": "Tavily Search",
        "description": "AI 优化的网页搜索工具，返回结构化搜索结果，适合 LLM 使用",
        "category": "search",
        "icon": "🔍",
        "tool_type": "builtin",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索查询关键词"
                },
                "max_results": {
                    "type": "integer",
                    "description": "返回结果数量，默认 5",
                    "default": 5
                },
                "search_depth": {
                    "type": "string",
                    "enum": ["basic", "advanced"],
                    "description": "搜索深度：basic 或 advanced",
                    "default": "basic"
                }
            },
            "required": ["query"]
        },
        "return_schema": {
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "url": {"type": "string"},
                            "content": {"type": "string"},
                            "score": {"type": "number"}
                        }
                    }
                }
            }
        },
        "endpoint": "https://api.tavily.com/search",
        "auth_config": {"api_key": ""},
    },
    {
        "id": "duckduckgo_search",
        "name": "DuckDuckGo Search",
        "description": "隐私友好的搜索引擎，无需 API Key",
        "category": "search",
        "icon": "🦆",
        "tool_type": "builtin",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索查询关键词"
                },
                "max_results": {
                    "type": "integer",
                    "description": "返回结果数量，默认 5",
                    "default": 5
                }
            },
            "required": ["query"]
        },
        "return_schema": {
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "url": {"type": "string"},
                            "snippet": {"type": "string"}
                        }
                    }
                }
            }
        },
        "endpoint": None,
        "auth_config": None,
    },

    # ============ 天气 ============
    {
        "id": "openweather",
        "name": "OpenWeatherMap",
        "description": "全球天气查询，支持实时天气、预报、空气质量",
        "category": "weather",
        "icon": "🌤️",
        "tool_type": "plugin",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "城市名称，如 Beijing、Shanghai"
                },
                "units": {
                    "type": "string",
                    "enum": ["metric", "imperial"],
                    "description": "温度单位：metric(摄氏) 或 imperial(华氏)",
                    "default": "metric"
                },
                "lang": {
                    "type": "string",
                    "description": "语言代码，如 zh_cn、en",
                    "default": "zh_cn"
                }
            },
            "required": ["city"]
        },
        "return_schema": {
            "type": "object",
            "properties": {
                "temperature": {"type": "number"},
                "description": {"type": "string"},
                "humidity": {"type": "integer"},
                "wind_speed": {"type": "number"}
            }
        },
        "endpoint": "https://api.openweathermap.org/data/2.5/weather",
        "auth_config": {"api_key": ""},
    },
    {
        "id": "qweather",
        "name": "和风天气",
        "description": "国内天气查询服务，支持实时天气、7天预报、生活指数",
        "category": "weather",
        "icon": "🌬️",
        "tool_type": "plugin",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "城市名称或城市 ID"
                },
                "type": {
                    "type": "string",
                    "enum": ["realtime", "forecast", "lifestyle"],
                    "description": "查询类型：realtime(实时)、forecast(预报)、lifestyle(生活指数)",
                    "default": "realtime"
                }
            },
            "required": ["city"]
        },
        "return_schema": {
            "type": "object",
            "properties": {
                "temp": {"type": "string"},
                "text": {"type": "string"},
                "humidity": {"type": "string"},
                "windDir": {"type": "string"}
            }
        },
        "endpoint": "https://devapi.qweather.com/v7/weather/now",
        "auth_config": {"api_key": ""},
    },

    # ============ 网页 ============
    {
        "id": "web_scraper",
        "name": "Web Scraper",
        "description": "抓取网页内容并提取文本，支持 JavaScript 渲染",
        "category": "web",
        "icon": "🌐",
        "tool_type": "builtin",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "要抓取的网页 URL"
                },
                "selector": {
                    "type": "string",
                    "description": "CSS 选择器，提取指定元素（可选）"
                }
            },
            "required": ["url"]
        },
        "return_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
                "html": {"type": "string"}
            }
        },
        "endpoint": None,
        "auth_config": None,
    },
    {
        "id": "html_to_markdown",
        "name": "HTML to Markdown",
        "description": "将 HTML 内容转换为 Markdown 格式",
        "category": "web",
        "icon": "📝",
        "tool_type": "builtin",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "html": {
                    "type": "string",
                    "description": "要转换的 HTML 内容"
                },
                "url": {
                    "type": "string",
                    "description": "或提供 URL，自动抓取并转换"
                }
            }
        },
        "return_schema": {
            "type": "object",
            "properties": {
                "markdown": {"type": "string"}
            }
        },
        "endpoint": None,
        "auth_config": None,
    },

    # ============ 文件 ============
    {
        "id": "pdf_reader",
        "name": "PDF Reader",
        "description": "读取 PDF 文件内容，提取文本和元数据",
        "category": "file",
        "icon": "📄",
        "tool_type": "builtin",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "PDF 文件路径或 URL"
                },
                "pages": {
                    "type": "string",
                    "description": "页码范围，如 1-5 或 1,3,5（可选）"
                }
            },
            "required": ["file_path"]
        },
        "return_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "page_count": {"type": "integer"},
                "metadata": {"type": "object"}
            }
        },
        "endpoint": None,
        "auth_config": None,
    },
    {
        "id": "csv_parser",
        "name": "CSV Parser",
        "description": "解析 CSV 文件，支持筛选、排序、聚合",
        "category": "file",
        "icon": "📊",
        "tool_type": "builtin",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "CSV 文件路径或 URL"
                },
                "query": {
                    "type": "string",
                    "description": "自然语言查询，如 '列出所有销售额大于1000的记录'"
                }
            },
            "required": ["file_path"]
        },
        "return_schema": {
            "type": "object",
            "properties": {
                "data": {"type": "array"},
                "columns": {"type": "array"},
                "row_count": {"type": "integer"}
            }
        },
        "endpoint": None,
        "auth_config": None,
    },

    # ============ 数据库 ============
    {
        "id": "sql_query",
        "name": "SQL Query",
        "description": "执行 SQL 查询并返回结果，支持 MySQL、PostgreSQL、SQLite",
        "category": "database",
        "icon": "🗃️",
        "tool_type": "plugin",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "connection_string": {
                    "type": "string",
                    "description": "数据库连接字符串"
                },
                "query": {
                    "type": "string",
                    "description": "SQL 查询语句"
                }
            },
            "required": ["connection_string", "query"]
        },
        "return_schema": {
            "type": "object",
            "properties": {
                "columns": {"type": "array"},
                "rows": {"type": "array"},
                "row_count": {"type": "integer"}
            }
        },
        "endpoint": None,
        "auth_config": None,
    },

    # ============ 代码 ============
    {
        "id": "code_executor",
        "name": "Code Executor",
        "description": "安全执行 Python 代码片段，支持数据处理和计算",
        "category": "code",
        "icon": "🐍",
        "tool_type": "builtin",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "要执行的 Python 代码"
                },
                "timeout": {
                    "type": "integer",
                    "description": "超时时间（秒），默认 30",
                    "default": 30
                }
            },
            "required": ["code"]
        },
        "return_schema": {
            "type": "object",
            "properties": {
                "output": {"type": "string"},
                "error": {"type": "string"},
                "exit_code": {"type": "integer"}
            }
        },
        "endpoint": None,
        "auth_config": None,
    },

    # ============ 搜索 (扩展) ============
    {
        "id": "serpapi_search",
        "name": "SerpAPI Search",
        "description": "Google/Bing 搜索结果 API，返回结构化 SERP 数据",
        "category": "search",
        "icon": "🔎",
        "tool_type": "plugin",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索查询关键词"
                },
                "engine": {
                    "type": "string",
                    "enum": ["google", "bing", "baidu"],
                    "description": "搜索引擎",
                    "default": "google"
                },
                "num": {
                    "type": "integer",
                    "description": "返回结果数量",
                    "default": 10
                }
            },
            "required": ["query"]
        },
        "return_schema": {
            "type": "object",
            "properties": {
                "organic_results": {"type": "array"},
                "answer_box": {"type": "object"}
            }
        },
        "endpoint": "https://serpapi.com/search",
        "auth_config": {"api_key": ""},
    },
    {
        "id": "google_search",
        "name": "Google Custom Search",
        "description": "Google 自定义搜索 API，适合精确网页检索",
        "category": "search",
        "icon": "🔍",
        "tool_type": "plugin",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索查询"
                },
                "num": {
                    "type": "integer",
                    "description": "结果数量，最多 10",
                    "default": 10
                },
                "language": {
                    "type": "string",
                    "description": "结果语言，如 lang_zh-CN",
                    "default": "lang_zh-CN"
                }
            },
            "required": ["query"]
        },
        "return_schema": {
            "type": "object",
            "properties": {
                "items": {"type": "array"}
            }
        },
        "endpoint": "https://www.googleapis.com/customsearch/v1",
        "auth_config": {"api_key": "", "cx": ""},
    },

    # ============ 翻译 ============
    {
        "id": "google_translate",
        "name": "Google Translate",
        "description": "Google 翻译 API，支持 100+ 语言互译",
        "category": "translate",
        "icon": "🌐",
        "tool_type": "plugin",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "要翻译的文本"
                },
                "source": {
                    "type": "string",
                    "description": "源语言代码，如 zh、en、ja（可选，自动检测）"
                },
                "target": {
                    "type": "string",
                    "description": "目标语言代码，如 en、zh、ja",
                    "default": "en"
                }
            },
            "required": ["text", "target"]
        },
        "return_schema": {
            "type": "object",
            "properties": {
                "translatedText": {"type": "string"},
                "detectedSourceLanguage": {"type": "string"}
            }
        },
        "endpoint": "https://translation.googleapis.com/language/translate/v2",
        "auth_config": {"api_key": ""},
    },
    {
        "id": "deepl_translate",
        "name": "DeepL Translate",
        "description": "DeepL 高质量翻译，尤其中英互译效果出色",
        "category": "translate",
        "icon": "🔤",
        "tool_type": "plugin",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "要翻译的文本"
                },
                "target_lang": {
                    "type": "string",
                    "description": "目标语言代码，如 EN、ZH、JA、DE、FR",
                    "default": "EN"
                },
                "source_lang": {
                    "type": "string",
                    "description": "源语言代码（可选，自动检测）"
                }
            },
            "required": ["text", "target_lang"]
        },
        "return_schema": {
            "type": "object",
            "properties": {
                "translations": {"type": "array"}
            }
        },
        "endpoint": "https://api-free.deepl.com/v2/translate",
        "auth_config": {"api_key": ""},
    },

    # ============ 通知 ============
    {
        "id": "send_email",
        "name": "Send Email (SMTP)",
        "description": "通过 SMTP 发送电子邮件，支持 HTML 内容和附件",
        "category": "notification",
        "icon": "📧",
        "tool_type": "plugin",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "to": {
                    "type": "string",
                    "description": "收件人邮箱地址"
                },
                "subject": {
                    "type": "string",
                    "description": "邮件主题"
                },
                "body": {
                    "type": "string",
                    "description": "邮件正文（支持 HTML）"
                },
                "cc": {
                    "type": "string",
                    "description": "抄送邮箱地址（可选）"
                }
            },
            "required": ["to", "subject", "body"]
        },
        "return_schema": {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "message_id": {"type": "string"}
            }
        },
        "endpoint": None,
        "auth_config": {"smtp_host": "", "smtp_port": "587", "username": "", "password": ""},
    },
    {
        "id": "slack_webhook",
        "name": "Slack Webhook",
        "description": "通过 Slack Incoming Webhook 发送消息到频道",
        "category": "notification",
        "icon": "💬",
        "tool_type": "plugin",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "消息内容，支持 Markdown 格式"
                },
                "channel": {
                    "type": "string",
                    "description": "频道名称（可选，覆盖 Webhook 默认频道）"
                },
                "username": {
                    "type": "string",
                    "description": "机器人显示名称",
                    "default": "Agent Bot"
                }
            },
            "required": ["text"]
        },
        "return_schema": {
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"}
            }
        },
        "endpoint": None,
        "auth_config": {"webhook_url": ""},
    },
    {
        "id": "dingtalk_webhook",
        "name": "钉钉 Webhook",
        "description": "通过钉钉自定义机器人发送群消息",
        "category": "notification",
        "icon": "🔔",
        "tool_type": "plugin",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "消息内容"
                },
                "title": {
                    "type": "string",
                    "description": "消息标题（Markdown 类型时必填）"
                },
                "msgtype": {
                    "type": "string",
                    "enum": ["text", "markdown"],
                    "description": "消息类型",
                    "default": "text"
                }
            },
            "required": ["text"]
        },
        "return_schema": {
            "type": "object",
            "properties": {
                "errcode": {"type": "integer"},
                "errmsg": {"type": "string"}
            }
        },
        "endpoint": None,
        "auth_config": {"webhook_url": "", "secret": ""},
    },

    # ============ AI / 多媒体 ============
    {
        "id": "image_generation",
        "name": "DALL·E Image Generation",
        "description": "OpenAI DALL·E 文生图，根据文字描述生成图片",
        "category": "ai",
        "icon": "🎨",
        "tool_type": "plugin",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "图片描述，越详细效果越好"
                },
                "size": {
                    "type": "string",
                    "enum": ["256x256", "512x512", "1024x1024"],
                    "description": "图片尺寸",
                    "default": "1024x1024"
                },
                "n": {
                    "type": "integer",
                    "description": "生成图片数量",
                    "default": 1
                }
            },
            "required": ["prompt"]
        },
        "return_schema": {
            "type": "object",
            "properties": {
                "images": {"type": "array", "items": {"type": "object", "properties": {"url": {"type": "string"}}}}
            }
        },
        "endpoint": "https://api.openai.com/v1/images/generations",
        "auth_config": {"api_key": ""},
    },
    {
        "id": "speech_to_text",
        "name": "Whisper Speech-to-Text",
        "description": "OpenAI Whisper 语音转文字，支持多语言音频识别",
        "category": "ai",
        "icon": "🎤",
        "tool_type": "plugin",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "audio_url": {
                    "type": "string",
                    "description": "音频文件 URL 或路径"
                },
                "language": {
                    "type": "string",
                    "description": "语言代码，如 zh、en（可选，自动检测）"
                },
                "response_format": {
                    "type": "string",
                    "enum": ["json", "text", "srt", "verbose_json"],
                    "description": "输出格式",
                    "default": "json"
                }
            },
            "required": ["audio_url"]
        },
        "return_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "language": {"type": "string"},
                "duration": {"type": "number"}
            }
        },
        "endpoint": "https://api.openai.com/v1/audio/transcriptions",
        "auth_config": {"api_key": ""},
    },
    {
        "id": "text_to_speech",
        "name": "Text-to-Speech",
        "description": "OpenAI TTS 文字转语音，支持多种音色",
        "category": "ai",
        "icon": "🔊",
        "tool_type": "plugin",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "input": {
                    "type": "string",
                    "description": "要转换的文本"
                },
                "voice": {
                    "type": "string",
                    "enum": ["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
                    "description": "音色选择",
                    "default": "alloy"
                },
                "speed": {
                    "type": "number",
                    "description": "语速，0.25-4.0",
                    "default": 1.0
                }
            },
            "required": ["input"]
        },
        "return_schema": {
            "type": "object",
            "properties": {
                "audio_url": {"type": "string"},
                "duration": {"type": "number"}
            }
        },
        "endpoint": "https://api.openai.com/v1/audio/speech",
        "auth_config": {"api_key": ""},
    },

    # ============ 数据处理 ============
    {
        "id": "json_processor",
        "name": "JSON Processor",
        "description": "JSON 数据处理工具，支持查询、过滤、转换",
        "category": "data",
        "icon": "📋",
        "tool_type": "builtin",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "data": {
                    "type": "string",
                    "description": "JSON 字符串或 URL"
                },
                "jq_query": {
                    "type": "string",
                    "description": "jq 风格查询表达式，如 .items[0].name"
                },
                "operation": {
                    "type": "string",
                    "enum": ["query", "flatten", "merge", "validate"],
                    "description": "操作类型",
                    "default": "query"
                }
            },
            "required": ["data"]
        },
        "return_schema": {
            "type": "object",
            "properties": {
                "result": {},
                "valid": {"type": "boolean"}
            }
        },
        "endpoint": None,
        "auth_config": None,
    },
    {
        "id": "xml_parser",
        "name": "XML Parser",
        "description": "XML 数据解析，支持 XPath 查询和 XML→JSON 转换",
        "category": "data",
        "icon": "📑",
        "tool_type": "builtin",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "xml": {
                    "type": "string",
                    "description": "XML 字符串或 URL"
                },
                "xpath": {
                    "type": "string",
                    "description": "XPath 查询表达式（可选）"
                },
                "output_format": {
                    "type": "string",
                    "enum": ["json", "text"],
                    "description": "输出格式",
                    "default": "json"
                }
            },
            "required": ["xml"]
        },
        "return_schema": {
            "type": "object",
            "properties": {
                "result": {},
                "root_tag": {"type": "string"}
            }
        },
        "endpoint": None,
        "auth_config": None,
    },
    {
        "id": "base64_codec",
        "name": "Base64 Encoder/Decoder",
        "description": "Base64 编码解码工具",
        "category": "data",
        "icon": "🔄",
        "tool_type": "builtin",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "input": {
                    "type": "string",
                    "description": "要编码或解码的内容"
                },
                "operation": {
                    "type": "string",
                    "enum": ["encode", "decode"],
                    "description": "操作类型：encode(编码) 或 decode(解码)",
                    "default": "encode"
                }
            },
            "required": ["input"]
        },
        "return_schema": {
            "type": "object",
            "properties": {
                "result": {"type": "string"}
            }
        },
        "endpoint": None,
        "auth_config": None,
    },

    # ============ 实用工具 ============
    {
        "id": "calculator",
        "name": "Calculator",
        "description": "数学计算器，支持复杂表达式、函数、单位转换",
        "category": "utility",
        "icon": "🧮",
        "tool_type": "builtin",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "数学表达式，如 2+3*4、sqrt(16)、sin(pi/2)"
                }
            },
            "required": ["expression"]
        },
        "return_schema": {
            "type": "object",
            "properties": {
                "result": {"type": "number"},
                "expression": {"type": "string"}
            }
        },
        "endpoint": None,
        "auth_config": None,
    },
    {
        "id": "uuid_generator",
        "name": "UUID Generator",
        "description": "生成 UUID/GUID，支持 v4 随机和 v5 命名空间",
        "category": "utility",
        "icon": "🆔",
        "tool_type": "builtin",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "version": {
                    "type": "integer",
                    "enum": [4, 5],
                    "description": "UUID 版本",
                    "default": 4
                },
                "count": {
                    "type": "integer",
                    "description": "生成数量",
                    "default": 1
                },
                "namespace": {
                    "type": "string",
                    "description": "v5 命名空间（可选）"
                },
                "name": {
                    "type": "string",
                    "description": "v5 名称（可选）"
                }
            }
        },
        "return_schema": {
            "type": "object",
            "properties": {
                "uuids": {"type": "array", "items": {"type": "string"}}
            }
        },
        "endpoint": None,
        "auth_config": None,
    },
    {
        "id": "datetime_tool",
        "name": "DateTime Tool",
        "description": "日期时间工具，支持时区转换、格式化、计算",
        "category": "utility",
        "icon": "🕐",
        "tool_type": "builtin",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["now", "convert", "diff", "format", "parse"],
                    "description": "操作类型"
                },
                "datetime_str": {
                    "type": "string",
                    "description": "日期时间字符串（convert/diff/format/parse 时必填）"
                },
                "from_tz": {
                    "type": "string",
                    "description": "源时区，如 Asia/Shanghai、UTC",
                    "default": "UTC"
                },
                "to_tz": {
                    "type": "string",
                    "description": "目标时区",
                    "default": "Asia/Shanghai"
                },
                "format": {
                    "type": "string",
                    "description": "日期格式，如 %Y-%m-%d %H:%M:%S"
                }
            },
            "required": ["operation"]
        },
        "return_schema": {
            "type": "object",
            "properties": {
                "result": {"type": "string"},
                "timestamp": {"type": "number"}
            }
        },
        "endpoint": None,
        "auth_config": None,
    },
    {
        "id": "hash_generator",
        "name": "Hash Generator",
        "description": "哈希/摘要生成工具，支持 MD5、SHA1、SHA256 等",
        "category": "utility",
        "icon": "🔐",
        "tool_type": "builtin",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "input": {
                    "type": "string",
                    "description": "要计算哈希的内容"
                },
                "algorithm": {
                    "type": "string",
                    "enum": ["md5", "sha1", "sha256", "sha512"],
                    "description": "哈希算法",
                    "default": "sha256"
                },
                "encoding": {
                    "type": "string",
                    "enum": ["hex", "base64"],
                    "description": "输出编码",
                    "default": "hex"
                }
            },
            "required": ["input"]
        },
        "return_schema": {
            "type": "object",
            "properties": {
                "hash": {"type": "string"},
                "algorithm": {"type": "string"}
            }
        },
        "endpoint": None,
        "auth_config": None,
    },

    # ============ 网页 (扩展) ============
    {
        "id": "url_shortener",
        "name": "URL Shortener",
        "description": "短链接生成服务，支持多个提供商",
        "category": "web",
        "icon": "🔗",
        "tool_type": "plugin",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "要缩短的长 URL"
                },
                "provider": {
                    "type": "string",
                    "enum": ["tinyurl", "bitly", "rebrandly"],
                    "description": "短链接服务商",
                    "default": "tinyurl"
                }
            },
            "required": ["url"]
        },
        "return_schema": {
            "type": "object",
            "properties": {
                "short_url": {"type": "string"},
                "original_url": {"type": "string"}
            }
        },
        "endpoint": None,
        "auth_config": {"api_key": ""},
    },
    {
        "id": "screenshot_tool",
        "name": "Website Screenshot",
        "description": "网页截图工具，生成网页的 PNG/PDF 快照",
        "category": "web",
        "icon": "📸",
        "tool_type": "plugin",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "要截图的网页 URL"
                },
                "format": {
                    "type": "string",
                    "enum": ["png", "jpeg", "pdf"],
                    "description": "输出格式",
                    "default": "png"
                },
                "full_page": {
                    "type": "boolean",
                    "description": "是否截取完整页面",
                    "default": False
                },
                "width": {
                    "type": "integer",
                    "description": "视口宽度",
                    "default": 1280
                }
            },
            "required": ["url"]
        },
        "return_schema": {
            "type": "object",
            "properties": {
                "image_url": {"type": "string"},
                "width": {"type": "integer"},
                "height": {"type": "integer"}
            }
        },
        "endpoint": None,
        "auth_config": {"api_key": ""},
    },
]

# 工具分类
TOOL_CATEGORIES = [
    {"id": "all", "name": "全部", "icon": "📋"},
    {"id": "search", "name": "搜索", "icon": "🔍"},
    {"id": "weather", "name": "天气", "icon": "🌤️"},
    {"id": "web", "name": "网页", "icon": "🌐"},
    {"id": "translate", "name": "翻译", "icon": "🌐"},
    {"id": "notification", "name": "通知", "icon": "🔔"},
    {"id": "ai", "name": "AI", "icon": "🤖"},
    {"id": "data", "name": "数据", "icon": "📊"},
    {"id": "file", "name": "文件", "icon": "📄"},
    {"id": "database", "name": "数据库", "icon": "🗃️"},
    {"id": "code", "name": "代码", "icon": "🐍"},
    {"id": "utility", "name": "实用工具", "icon": "🧮"},
]


def get_all_templates() -> List[Dict[str, Any]]:
    """获取所有工具模板"""
    return TOOL_TEMPLATES


def get_template_by_id(template_id: str) -> Optional[Dict[str, Any]]:
    """根据 ID 获取工具模板"""
    for template in TOOL_TEMPLATES:
        if template["id"] == template_id:
            return template
    return None


def get_templates_by_category(category: str) -> List[Dict[str, Any]]:
    """根据分类获取工具模板"""
    if category == "all":
        return TOOL_TEMPLATES
    return [t for t in TOOL_TEMPLATES if t["category"] == category]


def get_categories() -> List[Dict[str, str]]:
    """获取所有分类"""
    return TOOL_CATEGORIES
