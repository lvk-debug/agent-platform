"""
Paper Agent API 端点

提供论文综述运行的创建、列表与详情查询。
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.paper_agent import PaperAgentRun
from app.models.user import User
from app.schemas.paper_agent import (
    PaperAgentEvalCaseResponse,
    PaperAgentEvalRequest,
    PaperAgentEvalRunResponse,
    PaperAgentRunDetailResponse,
    PaperAgentRunListResponse,
    PaperAgentRunRequest,
    PaperAgentRunResponse,
)
from app.services.paper_agent.eval_cases import get_cases
from app.services.paper_agent.service import (
    PaperAgentService,
    run_eval_task,
    run_paper_agent_task,
)
from app.utils.deps import get_current_user

router = APIRouter()


def _to_detail(
    service: PaperAgentService, record: PaperAgentRun
) -> PaperAgentRunDetailResponse:
    """把运行记录转换为详情响应（附带综述正文）"""
    data = PaperAgentRunResponse.model_validate(record).model_dump()
    data["review"] = service.read_review(record)
    return PaperAgentRunDetailResponse(**data)


@router.post("/runs", response_model=PaperAgentRunDetailResponse)
def create_run(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: PaperAgentRunRequest,
    background_tasks: BackgroundTasks,
) -> PaperAgentRunDetailResponse:
    """
    创建并后台执行一次综述运行

    流程：规划 → 多源检索 → 排序 → PDF 解析与证据抽取 → 对比 → 综述。
    PDF 解析与证据抽取耗时可达数分钟，因此这里立即返回（status=running），
    通过 GET /runs/{run_id} 轮询状态与综述正文。
    """
    service = PaperAgentService(db)
    try:
        record = service.create_run(
            topic=request.topic,
            model_id=request.model_id,
            user_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    background_tasks.add_task(
        run_paper_agent_task,
        record.run_id,
        topic=request.topic,
        model_id=request.model_id,
        max_papers=request.max_papers,
        year_from=request.year_from,
        year_to=request.year_to,
        source=request.source,
        with_pdf=request.with_pdf,
    )
    return _to_detail(service, record)



@router.get("/runs", response_model=PaperAgentRunListResponse)
def list_runs(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaperAgentRunListResponse:
    """获取当前用户的运行记录列表"""
    query = db.query(PaperAgentRun).filter(PaperAgentRun.user_id == current_user.id)
    total = query.count()
    items = (
        query.order_by(PaperAgentRun.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PaperAgentRunListResponse(
        items=[PaperAgentRunResponse.model_validate(i) for i in items],
        total=total,
    )


@router.get("/runs/{run_id}", response_model=PaperAgentRunDetailResponse)
def get_run(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    run_id: str,
) -> PaperAgentRunDetailResponse:
    """获取运行详情（含 review.md 正文）"""
    service = PaperAgentService(db)
    record = service.get_run(run_id)
    if not record or record.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="运行记录不存在")

    return _to_detail(service, record)


# ============================================================
# 评测 API（里程碑4）
# ============================================================


@router.get("/eval-cases", response_model=list[PaperAgentEvalCaseResponse])
def list_eval_cases(
    *,
    current_user: User = Depends(get_current_user),
    category: str | None = Query(
        None,
        description="类别过滤：topic_search/single_paper/multi_compare/failure/safety",
    ),
) -> list[PaperAgentEvalCaseResponse]:
    """列出内置评测用例（共 20 条）"""
    return [
        PaperAgentEvalCaseResponse(
            case_id=case.case_id,
            category=case.category,
            topic=case.topic,
            notes=case.notes,
        )
        for case in get_cases(category=category)
    ]


@router.post("/evals", response_model=PaperAgentEvalRunResponse)
def create_eval(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: PaperAgentEvalRequest,
    background_tasks: BackgroundTasks,
) -> PaperAgentEvalRunResponse:
    """创建并后台执行评测运行（20 条用例耗时较长，故异步执行）"""
    from app.models.model import Model

    model = db.query(Model).filter(Model.model_id == request.model_id).first()
    if not model:
        raise HTTPException(status_code=400, detail=f"模型不存在: {request.model_id}")

    cases = get_cases(category=request.category, case_ids=request.case_ids)
    if not cases:
        raise HTTPException(status_code=400, detail="没有匹配的评测用例")

    service = PaperAgentService(db)
    record = service.create_eval_record(
        model=model, user_id=current_user.id, case_count=len(cases)
    )
    background_tasks.add_task(
        run_eval_task,
        record.eval_id,
        case_ids=request.case_ids,
        category=request.category,
        with_pdf=request.with_pdf,
        eval_backend=request.eval_backend,
    )
    return PaperAgentEvalRunResponse.model_validate(record)


@router.get("/evals/{eval_id}", response_model=PaperAgentEvalRunResponse)
def get_eval(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    eval_id: str,
) -> PaperAgentEvalRunResponse:
    """查询评测运行状态与汇总指标"""
    service = PaperAgentService(db)
    record = service.get_eval(eval_id)
    if not record:
        raise HTTPException(status_code=404, detail="评测运行不存在")

    return PaperAgentEvalRunResponse.model_validate(record)
