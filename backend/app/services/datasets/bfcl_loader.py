"""
BFCL 数据集加载器

支持从 HuggingFace 或内置示例加载 BFCL 测试数据集
"""

import json
from typing import Any, Dict, List, Optional

import httpx

from app.utils.logger import logger


class BFCLDatasetLoader:
    """
    BFCL 数据集加载器

    BFCL 包含 5 个评估维度：
    - simple: 简单函数调用
    - multiple: 多函数调用
    - parallel: 并行函数调用
    - parallel_multiple: 并行多函数调用
    - relevance: 相关性检测（何时不调用）
    """

    BFCL_CATEGORIES = [
        "simple",
        "multiple",
        "parallel",
        "parallel_multiple",
        "relevance",
    ]

    async def load_from_source(
        self,
        source: str = "builtin",
        categories: Optional[List[str]] = None,
        max_cases: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        从源头加载 BFCL 数据集

        Args:
            source: 数据源，支持 "builtin"、"huggingface"
            categories: 要加载的类别，None 表示全部
            max_cases: 最大加载数量

        Returns:
            测试用例列表
        """
        target_categories = categories or self.BFCL_CATEGORIES

        if source == "huggingface":
            try:
                return await self._load_from_huggingface(target_categories, max_cases)
            except Exception as e:
                logger.warning(f"HuggingFace 加载失败，回退到内置数据: {e}")

        # 使用内置示例数据
        return self._load_builtin_samples(target_categories, max_cases)

    def _load_builtin_samples(
        self,
        categories: List[str],
        max_cases: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """加载内置示例数据"""
        all_samples = self._get_builtin_samples()
        test_cases = []

        for category in categories:
            if category not in self.BFCL_CATEGORIES:
                logger.warning(f"跳过无效类别: {category}")
                continue

            samples = all_samples.get(category, [])
            for item in samples:
                test_case = self._parse_test_case(item, category)
                if test_case:
                    test_cases.append(test_case)

            logger.info(f"加载类别 {category}: {len(samples)} 个测试用例")

        if max_cases and len(test_cases) > max_cases:
            test_cases = test_cases[:max_cases]

        logger.info(f"总共加载 {len(test_cases)} 个 BFCL 测试用例")
        return test_cases

    async def _load_from_huggingface(
        self,
        categories: List[str],
        max_cases: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """从 HuggingFace 加载"""
        try:
            from datasets import load_dataset

            dataset = load_dataset(
                "gorilla-llm/Berkeley-Function-Calling-Leaderboard",
                split="test",
            )

            test_cases = []
            for item in dataset:
                category = item.get("category", "")
                if category not in categories:
                    continue

                test_case = self._parse_test_case(item, category)
                if test_case:
                    test_cases.append(test_case)

                if max_cases and len(test_cases) >= max_cases:
                    break

            logger.info(f"从 HuggingFace 加载 {len(test_cases)} 个 BFCL 测试用例")
            return test_cases

        except ImportError:
            logger.warning("datasets 库未安装")
            raise
        except Exception as e:
            logger.error(f"从 HuggingFace 加载失败: {e}")
            raise

    def _parse_test_case(
        self,
        item: Dict[str, Any],
        category: str,
    ) -> Optional[Dict[str, Any]]:
        """解析测试用例"""
        try:
            question = item.get("question", item.get("prompt", item.get("input_query", "")))
            if not question:
                return None

            functions = item.get("functions", item.get("tools", item.get("context", {}).get("functions", [])))

            expected_calls = item.get("expected_calls", item.get("ground_truth", item.get("expected_output", {}).get("tool_calls", [])))
            expected_tools = []
            for call in expected_calls:
                if isinstance(call, dict):
                    tool_name = call.get("name", call.get("function", {}).get("name", ""))
                    if tool_name:
                        expected_tools.append(tool_name)

            expected_answer = item.get("expected_answer", item.get("answer", ""))
            case_id = item.get("id", item.get("case_id", f"bfcl_{category}_{hash(question) % 10000:04d}"))

            return {
                "case_id": case_id,
                "category": category,
                "difficulty": self._infer_difficulty(category),
                "input_query": question,
                "context": {
                    "functions": functions,
                    "tools": functions,
                },
                "expected_output": {
                    "tool_calls": expected_calls,
                },
                "expected_tools": expected_tools,
                "expected_answer": expected_answer,
                "evaluation_criteria": {
                    "mode": "bfcl",
                    "check_ast": True,
                    "check_executability": True,
                },
            }

        except Exception as e:
            logger.warning(f"解析测试用例失败: {e}")
            return None

    def _infer_difficulty(self, category: str) -> str:
        """推断难度级别"""
        difficulty_map = {
            "simple": "easy",
            "multiple": "medium",
            "parallel": "medium",
            "parallel_multiple": "hard",
            "relevance": "medium",
        }
        return difficulty_map.get(category, "medium")

    def _get_builtin_samples(self) -> Dict[str, List[Dict[str, Any]]]:
        """获取内置示例数据"""
        return {
            "simple": [
                {
                    "id": "simple_001",
                    "question": "What's the weather like in San Francisco?",
                    "functions": [
                        {
                            "name": "get_weather",
                            "description": "Get the current weather for a location",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "location": {"type": "string", "description": "City name"},
                                    "unit": {"type": "string", "enum": ["celsius", "fahrenheit"], "default": "celsius"}
                                },
                                "required": ["location"]
                            }
                        }
                    ],
                    "expected_calls": [
                        {"name": "get_weather", "arguments": {"location": "San Francisco"}}
                    ]
                },
                {
                    "id": "simple_002",
                    "question": "Convert 100 USD to EUR",
                    "functions": [
                        {
                            "name": "convert_currency",
                            "description": "Convert currency from one type to another",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "amount": {"type": "number", "description": "Amount to convert"},
                                    "from_currency": {"type": "string", "description": "Source currency code"},
                                    "to_currency": {"type": "string", "description": "Target currency code"}
                                },
                                "required": ["amount", "from_currency", "to_currency"]
                            }
                        }
                    ],
                    "expected_calls": [
                        {"name": "convert_currency", "arguments": {"amount": 100, "from_currency": "USD", "to_currency": "EUR"}}
                    ]
                },
                {
                    "id": "simple_003",
                    "question": "Search for restaurants near Central Park",
                    "functions": [
                        {
                            "name": "search_restaurants",
                            "description": "Search for restaurants near a location",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "location": {"type": "string", "description": "Location to search near"},
                                    "cuisine": {"type": "string", "description": "Type of cuisine"},
                                    "price_range": {"type": "string", "enum": ["low", "medium", "high"]}
                                },
                                "required": ["location"]
                            }
                        }
                    ],
                    "expected_calls": [
                        {"name": "search_restaurants", "arguments": {"location": "Central Park"}}
                    ]
                },
                {
                    "id": "simple_004",
                    "question": "Calculate the tip for a $85.50 meal at 18%",
                    "functions": [
                        {
                            "name": "calculate_tip",
                            "description": "Calculate tip amount for a bill",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "bill_amount": {"type": "number", "description": "Total bill amount"},
                                    "tip_percentage": {"type": "number", "description": "Tip percentage"}
                                },
                                "required": ["bill_amount", "tip_percentage"]
                            }
                        }
                    ],
                    "expected_calls": [
                        {"name": "calculate_tip", "arguments": {"bill_amount": 85.50, "tip_percentage": 18}}
                    ]
                },
                {
                    "id": "simple_005",
                    "question": "What's the stock price of Apple?",
                    "functions": [
                        {
                            "name": "get_stock_price",
                            "description": "Get current stock price for a company",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "symbol": {"type": "string", "description": "Stock ticker symbol"},
                                    "exchange": {"type": "string", "description": "Stock exchange"}
                                },
                                "required": ["symbol"]
                            }
                        }
                    ],
                    "expected_calls": [
                        {"name": "get_stock_price", "arguments": {"symbol": "AAPL"}}
                    ]
                },
            ],
            "multiple": [
                {
                    "id": "multiple_001",
                    "question": "Find flights from New York to London on December 25th and book a hotel in London for 3 nights",
                    "functions": [
                        {
                            "name": "search_flights",
                            "description": "Search for available flights",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "origin": {"type": "string"},
                                    "destination": {"type": "string"},
                                    "date": {"type": "string"}
                                },
                                "required": ["origin", "destination", "date"]
                            }
                        },
                        {
                            "name": "book_hotel",
                            "description": "Book a hotel room",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "location": {"type": "string"},
                                    "check_in": {"type": "string"},
                                    "nights": {"type": "integer"}
                                },
                                "required": ["location", "check_in", "nights"]
                            }
                        }
                    ],
                    "expected_calls": [
                        {"name": "search_flights", "arguments": {"origin": "New York", "destination": "London", "date": "2024-12-25"}},
                        {"name": "book_hotel", "arguments": {"location": "London", "check_in": "2024-12-25", "nights": 3}}
                    ]
                },
                {
                    "id": "multiple_002",
                    "question": "Look up the population of Tokyo and calculate what percentage it is of Japan's total population",
                    "functions": [
                        {
                            "name": "get_city_population",
                            "description": "Get population of a city",
                            "parameters": {
                                "type": "object",
                                "properties": {"city": {"type": "string"}},
                                "required": ["city"]
                            }
                        },
                        {
                            "name": "get_country_population",
                            "description": "Get total population of a country",
                            "parameters": {
                                "type": "object",
                                "properties": {"country": {"type": "string"}},
                                "required": ["country"]
                            }
                        },
                        {
                            "name": "calculate_percentage",
                            "description": "Calculate percentage of a value",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "part": {"type": "number"},
                                    "whole": {"type": "number"}
                                },
                                "required": ["part", "whole"]
                            }
                        }
                    ],
                    "expected_calls": [
                        {"name": "get_city_population", "arguments": {"city": "Tokyo"}},
                        {"name": "get_country_population", "arguments": {"country": "Japan"}}
                    ]
                },
                {
                    "id": "multiple_003",
                    "question": "Send an email to John about the meeting tomorrow and add it to my calendar",
                    "functions": [
                        {
                            "name": "send_email",
                            "description": "Send an email to a recipient",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "to": {"type": "string"},
                                    "subject": {"type": "string"},
                                    "body": {"type": "string"}
                                },
                                "required": ["to", "subject", "body"]
                            }
                        },
                        {
                            "name": "add_calendar_event",
                            "description": "Add an event to calendar",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "date": {"type": "string"},
                                    "time": {"type": "string"},
                                    "duration": {"type": "integer"}
                                },
                                "required": ["title", "date"]
                            }
                        }
                    ],
                    "expected_calls": [
                        {"name": "send_email", "arguments": {"to": "John", "subject": "Meeting Tomorrow", "body": "Reminder about our meeting tomorrow"}},
                        {"name": "add_calendar_event", "arguments": {"title": "Meeting with John", "date": "tomorrow"}}
                    ]
                },
            ],
            "parallel": [
                {
                    "id": "parallel_001",
                    "question": "Get the weather in both New York and Los Angeles",
                    "functions": [
                        {
                            "name": "get_weather",
                            "description": "Get weather for a location",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "location": {"type": "string"}
                                },
                                "required": ["location"]
                            }
                        }
                    ],
                    "expected_calls": [
                        {"name": "get_weather", "arguments": {"location": "New York"}},
                        {"name": "get_weather", "arguments": {"location": "Los Angeles"}}
                    ]
                },
                {
                    "id": "parallel_002",
                    "question": "Check the stock prices of Google, Microsoft, and Amazon",
                    "functions": [
                        {
                            "name": "get_stock_price",
                            "description": "Get stock price for a symbol",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "symbol": {"type": "string"}
                                },
                                "required": ["symbol"]
                            }
                        }
                    ],
                    "expected_calls": [
                        {"name": "get_stock_price", "arguments": {"symbol": "GOOGL"}},
                        {"name": "get_stock_price", "arguments": {"symbol": "MSFT"}},
                        {"name": "get_stock_price", "arguments": {"symbol": "AMZN"}}
                    ]
                },
                {
                    "id": "parallel_003",
                    "question": "Translate 'hello' to Spanish, French, and German",
                    "functions": [
                        {
                            "name": "translate_text",
                            "description": "Translate text to a target language",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "text": {"type": "string"},
                                    "target_language": {"type": "string"}
                                },
                                "required": ["text", "target_language"]
                            }
                        }
                    ],
                    "expected_calls": [
                        {"name": "translate_text", "arguments": {"text": "hello", "target_language": "Spanish"}},
                        {"name": "translate_text", "arguments": {"text": "hello", "target_language": "French"}},
                        {"name": "translate_text", "arguments": {"text": "hello", "target_language": "German"}}
                    ]
                },
            ],
            "parallel_multiple": [
                {
                    "id": "parallel_multiple_001",
                    "question": "Book a flight from SF to NYC on Jan 15 and a hotel in NYC for 3 nights, also get weather forecast for NYC",
                    "functions": [
                        {
                            "name": "book_flight",
                            "description": "Book a flight",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "origin": {"type": "string"},
                                    "destination": {"type": "string"},
                                    "date": {"type": "string"}
                                },
                                "required": ["origin", "destination", "date"]
                            }
                        },
                        {
                            "name": "book_hotel",
                            "description": "Book a hotel",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "location": {"type": "string"},
                                    "check_in": {"type": "string"},
                                    "nights": {"type": "integer"}
                                },
                                "required": ["location", "check_in", "nights"]
                            }
                        },
                        {
                            "name": "get_weather_forecast",
                            "description": "Get weather forecast",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "location": {"type": "string"},
                                    "days": {"type": "integer"}
                                },
                                "required": ["location"]
                            }
                        }
                    ],
                    "expected_calls": [
                        {"name": "book_flight", "arguments": {"origin": "SF", "destination": "NYC", "date": "2025-01-15"}},
                        {"name": "book_hotel", "arguments": {"location": "NYC", "check_in": "2025-01-15", "nights": 3}},
                        {"name": "get_weather_forecast", "arguments": {"location": "NYC", "days": 3}}
                    ]
                },
                {
                    "id": "parallel_multiple_002",
                    "question": "Order pizza for dinner and check if the grocery store is open, also set a reminder for tomorrow's meeting",
                    "functions": [
                        {
                            "name": "order_food",
                            "description": "Order food delivery",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "restaurant": {"type": "string"},
                                    "items": {"type": "array", "items": {"type": "string"}},
                                    "delivery_address": {"type": "string"}
                                },
                                "required": ["restaurant", "items"]
                            }
                        },
                        {
                            "name": "check_store_hours",
                            "description": "Check store operating hours",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "store_name": {"type": "string"},
                                    "location": {"type": "string"}
                                },
                                "required": ["store_name"]
                            }
                        },
                        {
                            "name": "set_reminder",
                            "description": "Set a reminder",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "datetime": {"type": "string"}
                                },
                                "required": ["title", "datetime"]
                            }
                        }
                    ],
                    "expected_calls": [
                        {"name": "order_food", "arguments": {"restaurant": "pizza", "items": ["pizza"]}},
                        {"name": "check_store_hours", "arguments": {"store_name": "grocery store"}},
                        {"name": "set_reminder", "arguments": {"title": "meeting", "datetime": "tomorrow"}}
                    ]
                },
            ],
            "relevance": [
                {
                    "id": "relevance_001",
                    "question": "What's the meaning of life?",
                    "functions": [
                        {
                            "name": "search_definition",
                            "description": "Search for word definitions",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "word": {"type": "string"}
                                },
                                "required": ["word"]
                            }
                        },
                        {
                            "name": "get_philosophical_quote",
                            "description": "Get a philosophical quote",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "topic": {"type": "string"}
                                },
                                "required": ["topic"]
                            }
                        }
                    ],
                    "expected_calls": []
                },
                {
                    "id": "relevance_002",
                    "question": "Tell me a joke",
                    "functions": [
                        {
                            "name": "get_joke",
                            "description": "Get a random joke",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "category": {"type": "string"}
                                },
                                "required": []
                            }
                        }
                    ],
                    "expected_calls": []
                },
                {
                    "id": "relevance_003",
                    "question": "Can you help me with my homework?",
                    "functions": [
                        {
                            "name": "solve_math_problem",
                            "description": "Solve a math problem",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "problem": {"type": "string"}
                                },
                                "required": ["problem"]
                            }
                        },
                        {
                            "name": "search_wikipedia",
                            "description": "Search Wikipedia for information",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "query": {"type": "string"}
                                },
                                "required": ["query"]
                            }
                        }
                    ],
                    "expected_calls": []
                },
                {
                    "id": "relevance_004",
                    "question": "I'm feeling sad today",
                    "functions": [
                        {
                            "name": "get_mood_music",
                            "description": "Get music recommendations based on mood",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "mood": {"type": "string"}
                                },
                                "required": ["mood"]
                            }
                        },
                        {
                            "name": "find_therapist",
                            "description": "Find a therapist nearby",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "location": {"type": "string"},
                                    "specialty": {"type": "string"}
                                },
                                "required": ["location"]
                            }
                        }
                    ],
                    "expected_calls": []
                },
            ],
        }

    def get_category_info(self) -> List[Dict[str, str]]:
        """获取类别信息"""
        return [
            {
                "id": "simple",
                "name": "简单函数调用",
                "description": "单个函数调用，基础能力测试",
                "difficulty": "easy",
            },
            {
                "id": "multiple",
                "name": "多函数调用",
                "description": "需要调用多个函数完成任务",
                "difficulty": "medium",
            },
            {
                "id": "parallel",
                "name": "并行函数调用",
                "description": "多个独立的函数调用",
                "difficulty": "medium",
            },
            {
                "id": "parallel_multiple",
                "name": "并行多函数调用",
                "description": "复杂的并行函数调用场景",
                "difficulty": "hard",
            },
            {
                "id": "relevance",
                "name": "相关性检测",
                "description": "判断何时应该/不应该调用函数",
                "difficulty": "medium",
            },
        ]
