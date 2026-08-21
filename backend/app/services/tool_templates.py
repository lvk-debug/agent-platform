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
]

# 工具分类
TOOL_CATEGORIES = [
    {"id": "all", "name": "全部", "icon": "📋"},
    {"id": "search", "name": "搜索", "icon": "🔍"},
    {"id": "weather", "name": "天气", "icon": "🌤️"},
    {"id": "web", "name": "网页", "icon": "🌐"},
    {"id": "file", "name": "文件", "icon": "📄"},
    {"id": "database", "name": "数据库", "icon": "🗃️"},
    {"id": "code", "name": "代码", "icon": "🐍"},
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
