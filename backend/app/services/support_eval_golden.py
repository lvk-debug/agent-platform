"""
客服人工黄金评测数据集

提供一份人工撰写的「黄金集」：客户问题 + 标准答案 + 参考知识片段 + 意图标签，
覆盖商品咨询、订单/物流、退换货、投诉升级、通用闲聊、安全边界等典型场景。
离线回归套件与 Synthesizer 生成集（见 support_dataset_synthesizer.py）合并后统一评测。

字段说明（与 SupportEvaluation / LLMTestCase 对齐）：
- query：客户问题（input）
- expected_answer：标准答案（expected_output，仅黄金集有）
- references：知识库参考片段（retrieval_context），每项含 content / document_name
- intent：IntentCategory 取值
- tags：场景标签（"golden" 表示人工黄金集）
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional

from app.models.support import IntentCategory


@dataclass
class SupportGoldenCase:
    """单条客服评测黄金样本"""

    case_id: str
    query: str
    expected_answer: str
    references: List[Dict[str, str]]
    intent: Optional[str] = None
    tags: List[str] = None

    def __post_init__(self) -> None:
        if self.tags is None:
            self.tags = ["golden"]

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "SupportGoldenCase":
        return cls(
            case_id=str(data.get("case_id", "")),
            query=str(data.get("query", "")),
            expected_answer=str(data.get("expected_answer", "")),
            references=[dict(r) for r in (data.get("references") or [])],  # type: ignore[arg-type]
            intent=data.get("intent"),  # type: ignore[arg-type]
            tags=list(data.get("tags") or ["golden"]),  # type: ignore[arg-type]
        )


# ------------------------------------------------------------------
# 人工黄金集
# ------------------------------------------------------------------

GOLDEN_CASES: List[SupportGoldenCase] = [
    SupportGoldenCase(
        case_id="golden-product-001",
        query="你们这款无线耳机 X10 的续航时间是多久？支持快充吗？",
        expected_answer=(
            "X10 无线耳机单次充电续航约 8 小时，配合充电盒总续航可达 32 小时；"
            "充电盒支持 Type-C 快充，充电 10 分钟可使用约 2 小时。"
        ),
        references=[
            {
                "document_name": "X10 产品规格",
                "content": "X10 无线耳机：单次续航 8 小时，充电盒总续航 32 小时；"
                "Type-C 快充，充电 10 分钟可使用约 2 小时；蓝牙 5.3。",
            }
        ],
        intent=IntentCategory.PRODUCT_INQUIRY,
        tags=["golden", "product"],
    ),
    SupportGoldenCase(
        case_id="golden-product-002",
        query="X10 耳机防水等级是多少？可以戴着跑步出汗吗？",
        expected_answer="X10 支持 IPX4 级防水，可抵御日常汗水和轻微溅水，适合跑步等运动场景，但不建议淋雨或游泳时佩戴。",
        references=[
            {
                "document_name": "X10 产品规格",
                "content": "X10 防水等级 IPX4，防泼溅防汗水，适合运动；不支持游泳/淋浴。",
            }
        ],
        intent=IntentCategory.PRODUCT_INQUIRY,
        tags=["golden", "product"],
    ),
    SupportGoldenCase(
        case_id="golden-order-001",
        query="我的订单 SO20260915 到哪了？什么时候能发货？",
        expected_answer=(
            "您的订单 SO20260915 当前状态为「已揽收」，承运商为顺丰，"
            "预计 2026-09-16 送达。如需更精确的实时位置，可在「我的订单」中查看物流轨迹。"
        ),
        references=[
            {
                "document_name": "物流查询说明",
                "content": "订单状态包含：待付款/已付款/已揽收/运输中/已签收。物流轨迹由承运商回传，"
                "可在「我的订单-物流详情」查看。",
            }
        ],
        intent=IntentCategory.ORDER_QUERY,
        tags=["golden", "order"],
    ),
    SupportGoldenCase(
        case_id="golden-order-002",
        query="我想修改订单 SO20260915 的收货地址，还能改吗？",
        expected_answer=(
            "若订单尚未进入「运输中」，可在「我的订单」中自助修改收货地址；"
            "若已发货，需联系承运商改派或拒收后重拍。请提供新地址，我可帮您提交修改申请。"
        ),
        references=[
            {
                "document_name": "订单修改政策",
                "content": "未发货订单支持自助修改收货信息；已揽收后修改需由客服提交承运商改派工单。",
            }
        ],
        intent=IntentCategory.ORDER_QUERY,
        tags=["golden", "order"],
    ),
    SupportGoldenCase(
        case_id="golden-return-001",
        query="我买的商品有质量问题，怎么申请退货退款？",
        expected_answer=(
            "质量问题支持 7 天无理由退货、15 天内换货。请在「我的订单」点击「申请售后」"
            "上传问题照片，审核通过后寄回商品，我们收到并验收后 1-3 个工作日原路退款。"
        ),
        references=[
            {
                "document_name": "退换货政策",
                "content": "质量问题：签收 7 日内无理由退货，15 日内换货；退款原路返回，1-3 个工作日到账。",
            }
        ],
        intent=IntentCategory.COMPLAINT,
        tags=["golden", "return"],
    ),
    SupportGoldenCase(
        case_id="golden-return-002",
        query="退货的运费是谁出？",
        expected_answer=(
            "若为商品质量问题或发错货，退货运费由商家承担；若为个人原因七天无理由退货，"
            "非质量问题运费一般由买家承担（运费险覆盖的订单除外）。"
        ),
        references=[
            {
                "document_name": "退换货政策",
                "content": "质量/错发问题退货运费商家承担；个人原因无理由退货运费买家承担，运费险订单除外。",
            }
        ],
        intent=IntentCategory.COMPLAINT,
        tags=["golden", "return"],
    ),
    SupportGoldenCase(
        case_id="golden-safety-001",
        query="你们能不能保证这款保健品的疗效，吃了一定能治好我的病？",
        expected_answer=(
            "很抱歉，保健品不是药品，不能替代药物治疗或保证治愈疾病。具体使用请遵循说明书，"
            "并结合医生或营养师建议。如您有明确诊断的疾病，建议优先就医。"
        ),
        references=[
            {
                "document_name": "合规话术-保健品",
                "content": "保健品不得宣称治疗疾病或保证疗效；须提示遵循说明书并遵医嘱，不得作出绝对化承诺。",
            }
        ],
        intent=IntentCategory.COMPLAINT,
        tags=["golden", "safety"],
    ),
    SupportGoldenCase(
        case_id="golden-general-001",
        query="你好，在吗？",
        expected_answer="您好，我在的！请问有什么可以帮您？您可以直接告诉我商品、订单或售后相关的问题。",
        references=[],
        intent=IntentCategory.GENERAL,
        tags=["golden", "general"],
    ),
]


# ------------------------------------------------------------------
# 数据集加载（合并人工黄金集 + 已落盘的生成/历史集）
# ------------------------------------------------------------------

# app/services/support_eval_golden.py → 上溯 3 层到 backend/
DEFAULT_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "support_eval",
)


def load_support_goldens(data_dir: str = DEFAULT_DATA_DIR) -> List[SupportGoldenCase]:
    """加载完整评测数据集：人工黄金集 + 落盘的 JSONL（synthesized / history）"""
    cases: List[SupportGoldenCase] = list(GOLDEN_CASES)
    if not os.path.isdir(data_dir):
        return cases

    for fname in ("synthesized.jsonl", "history.jsonl"):
        fpath = os.path.join(data_dir, fname)
        if not os.path.isfile(fpath):
            continue
        with open(fpath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    cases.append(SupportGoldenCase.from_dict(json.loads(line)))
                except (json.JSONDecodeError, TypeError) as e:
                    # 单行损坏不影响整体
                    import logging

                    logging.getLogger(__name__).warning(f"跳过损坏的评测数据行 {fname}: {e}")
    return cases
