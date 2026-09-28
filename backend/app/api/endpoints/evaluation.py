"""
评估系统 API 端点 (v2)

支持：
- 数据集管理
- 测试用例管理
- 评估器管理
- 评估任务管理
- 评估结果查询
- 执行轨迹查询
- 分析统计
"""

import asyncio
from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.evaluation import (
    Evaluation,
    EvaluationDataset,
    EvaluationResult,
    Evaluator,
    TestCase,
    Trace,
)
from app.models.user import User
from app.schemas.evaluation import (
    AnalyticsOverview,
    CategoryScore,
    ComparisonResult,
    DatasetCreate,
    DatasetDetailResponse,
    DatasetImportRequest,
    DatasetImportResponse,
    DatasetResponse,
    DatasetUpdate,
    DimensionScore,
    EvaluationCreate,
    EvaluationDetailResponse,
    EvaluationListResponse,
    EvaluationReport,
    EvaluationResponse,
    EvaluationResultDetailResponse,
    EvaluationResultListResponse,
    EvaluationResultResponse,
    EvaluatorCreate,
    EvaluatorListResponse,
    EvaluatorResponse,
    EvaluatorUpdate,
    TestCaseCreate,
    TestCaseListResponse,
    TestCaseResponse,
    TraceCreate,
    TraceListResponse,
    TraceResponse,
)
from app.utils.deps import get_current_user

router = APIRouter()


# ============================================================
# 评估数据集 API
# ============================================================


@router.post("/datasets", response_model=DatasetResponse)
def create_dataset(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    dataset_in: DatasetCreate,
) -> Any:
    """创建评估数据集"""
    dataset = EvaluationDataset(
        name=dataset_in.name,
        description=dataset_in.description,
        dataset_type=dataset_in.dataset_type,
        version=dataset_in.version,
        metadata_=dataset_in.metadata,
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return dataset


@router.get("/datasets", response_model=List[DatasetResponse])
def list_datasets(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    dataset_type: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Any:
    """获取数据集列表"""
    query = db.query(EvaluationDataset)

    if dataset_type:
        query = query.filter(EvaluationDataset.dataset_type == dataset_type)
    if is_active is not None:
        query = query.filter(EvaluationDataset.is_active == is_active)

    datasets = query.order_by(EvaluationDataset.created_at.desc()).all()
    return datasets


@router.get("/datasets/{dataset_id}", response_model=DatasetDetailResponse)
def get_dataset(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    dataset_id: int,
) -> Any:
    """获取数据集详情"""
    dataset = db.query(EvaluationDataset).filter(EvaluationDataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")

    test_cases_count = db.query(TestCase).filter(TestCase.dataset_id == dataset_id).count()
    evaluations_count = db.query(Evaluation).filter(Evaluation.dataset_id == dataset_id).count()

    result = DatasetDetailResponse(
        **dataset.__dict__,
        test_cases_count=test_cases_count,
        evaluations_count=evaluations_count,
    )
    return result


@router.put("/datasets/{dataset_id}", response_model=DatasetResponse)
def update_dataset(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    dataset_id: int,
    dataset_in: DatasetUpdate,
) -> Any:
    """更新数据集"""
    dataset = db.query(EvaluationDataset).filter(EvaluationDataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")

    update_data = dataset_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(dataset, field, value)

    db.commit()
    db.refresh(dataset)
    return dataset


@router.delete("/datasets/{dataset_id}")
def delete_dataset(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    dataset_id: int,
) -> Any:
    """删除数据集"""
    dataset = db.query(EvaluationDataset).filter(EvaluationDataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")

    db.delete(dataset)
    db.commit()
    return {"message": "数据集已删除"}


# ============================================================
# 测试用例 API
# ============================================================


@router.post("/datasets/{dataset_id}/test-cases", response_model=TestCaseResponse)
def create_test_case(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    dataset_id: int,
    test_case_in: TestCaseCreate,
) -> Any:
    """创建测试用例"""
    dataset = db.query(EvaluationDataset).filter(EvaluationDataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")

    test_case = TestCase(
        dataset_id=dataset_id,
        case_id=test_case_in.case_id,
        category=test_case_in.category,
        difficulty=test_case_in.difficulty,
        input_query=test_case_in.input_query,
        input_context=test_case_in.input_context,
        input_tools=test_case_in.input_tools,
        expected_answer=test_case_in.expected_answer,
        expected_trajectory=test_case_in.expected_trajectory,
        expected_tools=test_case_in.expected_tools,
        tags=test_case_in.tags,
        metadata_=test_case_in.metadata,
    )
    db.add(test_case)

    dataset.total_cases = db.query(TestCase).filter(TestCase.dataset_id == dataset_id).count() + 1

    db.commit()
    db.refresh(test_case)
    return test_case


@router.get("/datasets/{dataset_id}/test-cases", response_model=TestCaseListResponse)
def list_test_cases(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    dataset_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
) -> Any:
    """获取测试用例列表"""
    query = db.query(TestCase).filter(TestCase.dataset_id == dataset_id)

    if category:
        query = query.filter(TestCase.category == category)
    if difficulty:
        query = query.filter(TestCase.difficulty == difficulty)

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return TestCaseListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/datasets/{dataset_id}/import", response_model=DatasetImportResponse)
async def import_test_cases(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    dataset_id: int,
    import_in: DatasetImportRequest,
) -> Any:
    """导入测试用例（从 BFCL 数据源）"""
    dataset = db.query(EvaluationDataset).filter(EvaluationDataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")

    try:
        if import_in.source in ["builtin", "huggingface"]:
            from app.services.datasets.bfcl_loader import BFCLDatasetLoader

            loader = BFCLDatasetLoader()
            test_cases_data = await loader.load_from_source(import_in.source)

            if import_in.categories:
                test_cases_data = [
                    tc for tc in test_cases_data if tc.get("category") in import_in.categories
                ]

            if import_in.max_cases:
                test_cases_data = test_cases_data[: import_in.max_cases]

            imported_count = 0
            skipped_count = 0
            error_count = 0

            for tc_data in test_cases_data:
                try:
                    existing = (
                        db.query(TestCase)
                        .filter(
                            TestCase.dataset_id == dataset_id,
                            TestCase.case_id == tc_data["case_id"],
                        )
                        .first()
                    )
                    if existing:
                        skipped_count += 1
                        continue

                    test_case = TestCase(
                        dataset_id=dataset_id,
                        case_id=tc_data["case_id"],
                        category=tc_data.get("category"),
                        difficulty=tc_data.get("difficulty", "medium"),
                        input_query=tc_data["input_query"],
                        input_context=tc_data.get("context"),
                        input_tools=tc_data.get("functions"),
                        expected_answer=tc_data.get("expected_answer"),
                        expected_tools=tc_data.get("expected_calls"),
                    )
                    db.add(test_case)
                    imported_count += 1
                except Exception as e:
                    error_count += 1
                    continue

            dataset.total_cases = (
                db.query(TestCase).filter(TestCase.dataset_id == dataset_id).count()
                + imported_count
            )
            db.commit()

            return DatasetImportResponse(
                dataset_id=dataset_id,
                imported_count=imported_count,
                skipped_count=skipped_count,
                error_count=error_count,
                message=f"成功导入 {imported_count} 个测试用例",
            )
        else:
            raise HTTPException(status_code=400, detail=f"不支持的数据源: {import_in.source}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


# ============================================================
# 评估器 API
# ============================================================


@router.post("/evaluators", response_model=EvaluatorResponse)
def create_evaluator(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    evaluator_in: EvaluatorCreate,
) -> Any:
    """创建评估器"""
    evaluator = Evaluator(
        name=evaluator_in.name,
        description=evaluator_in.description,
        evaluator_type=evaluator_in.evaluator_type,
        config=evaluator_in.config,
        judge_model=evaluator_in.judge_model,
        judge_prompt=evaluator_in.judge_prompt,
        metric_type=evaluator_in.metric_type,
        script_content=evaluator_in.script_content,
    )
    db.add(evaluator)
    db.commit()
    db.refresh(evaluator)
    return evaluator


@router.get("/evaluators", response_model=EvaluatorListResponse)
def list_evaluators(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    evaluator_type: Optional[str] = None,
    is_builtin: Optional[bool] = None,
    is_active: Optional[bool] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> Any:
    """获取评估器列表"""
    query = db.query(Evaluator)

    if evaluator_type:
        query = query.filter(Evaluator.evaluator_type == evaluator_type)
    if is_builtin is not None:
        query = query.filter(Evaluator.is_builtin == is_builtin)
    if is_active is not None:
        query = query.filter(Evaluator.is_active == is_active)

    total = query.count()
    items = query.order_by(Evaluator.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return EvaluatorListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/evaluators/{evaluator_id}", response_model=EvaluatorResponse)
def get_evaluator(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    evaluator_id: int,
) -> Any:
    """获取评估器详情"""
    evaluator = db.query(Evaluator).filter(Evaluator.id == evaluator_id).first()
    if not evaluator:
        raise HTTPException(status_code=404, detail="评估器不存在")
    return evaluator


@router.put("/evaluators/{evaluator_id}", response_model=EvaluatorResponse)
def update_evaluator(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    evaluator_id: int,
    evaluator_in: EvaluatorUpdate,
) -> Any:
    """更新评估器"""
    evaluator = db.query(Evaluator).filter(Evaluator.id == evaluator_id).first()
    if not evaluator:
        raise HTTPException(status_code=404, detail="评估器不存在")

    update_data = evaluator_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(evaluator, field, value)

    db.commit()
    db.refresh(evaluator)
    return evaluator


@router.delete("/evaluators/{evaluator_id}")
def delete_evaluator(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    evaluator_id: int,
) -> Any:
    """删除评估器"""
    evaluator = db.query(Evaluator).filter(Evaluator.id == evaluator_id).first()
    if not evaluator:
        raise HTTPException(status_code=404, detail="评估器不存在")

    if evaluator.is_builtin:
        raise HTTPException(status_code=400, detail="无法删除内置评估器")

    db.delete(evaluator)
    db.commit()
    return {"message": "评估器已删除"}


@router.post("/evaluators/init-builtin")
def init_builtin_evaluators(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """初始化内置评估器"""
    from app.services.evaluators import EvaluatorEngine

    engine = EvaluatorEngine(db)
    evaluators = engine.create_builtin_evaluators()
    return {"message": f"已初始化 {len(evaluators)} 个内置评估器"}


# ============================================================
# 评估任务 API
# ============================================================


@router.post("/evaluations", response_model=EvaluationResponse)
def create_evaluation(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    eval_in: EvaluationCreate,
) -> Any:
    """创建评估任务"""
    from app.models.app import App

    app = db.query(App).filter(App.id == eval_in.app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="应用不存在")

    dataset = (
        db.query(EvaluationDataset).filter(EvaluationDataset.id == eval_in.dataset_id).first()
    )
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")

    # 验证评估器存在
    evaluators = db.query(Evaluator).filter(Evaluator.id.in_(eval_in.evaluator_ids)).all()
    if len(evaluators) != len(eval_in.evaluator_ids):
        raise HTTPException(status_code=400, detail="部分评估器不存在")

    evaluation = Evaluation(
        name=eval_in.name,
        description=eval_in.description,
        app_id=eval_in.app_id,
        dataset_id=eval_in.dataset_id,
        user_id=current_user.id,
        evaluator_ids=eval_in.evaluator_ids,
        config=eval_in.config or {},
        total_cases=dataset.total_cases,
    )
    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)
    return evaluation


@router.get("/evaluations", response_model=EvaluationListResponse)
def list_evaluations(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    app_id: Optional[int] = None,
    status: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Any:
    """获取评估任务列表"""
    query = db.query(Evaluation).filter(Evaluation.user_id == current_user.id)

    if app_id:
        query = query.filter(Evaluation.app_id == app_id)
    if status:
        query = query.filter(Evaluation.status == status)

    total = query.count()
    items = (
        query.order_by(Evaluation.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return EvaluationListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/evaluations/{eval_id}", response_model=EvaluationDetailResponse)
def get_evaluation(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    eval_id: int,
) -> Any:
    """获取评估任务详情"""
    evaluation = db.query(Evaluation).filter(Evaluation.id == eval_id).first()
    if not evaluation:
        raise HTTPException(status_code=404, detail="评估任务不存在")

    from app.models.app import App

    app = db.query(App).filter(App.id == evaluation.app_id).first()
    dataset = (
        db.query(EvaluationDataset)
        .filter(EvaluationDataset.id == evaluation.dataset_id)
        .first()
    )

    # 获取评估器信息
    evaluator_ids = evaluation.evaluator_ids or []
    evaluators = db.query(Evaluator).filter(Evaluator.id.in_(evaluator_ids)).all()

    # 统计结果摘要
    results = (
        db.query(EvaluationResult).filter(EvaluationResult.evaluation_id == eval_id).all()
    )
    results_summary = {
        "total": len(results),
        "passed": sum(1 for r in results if r.passed),
        "avg_score": sum(r.score or 0 for r in results) / len(results) if results else 0,
        "avg_time": (
            sum(r.execution_time or 0 for r in results) / len(results) if results else 0
        ),
    }

    return EvaluationDetailResponse(
        **evaluation.__dict__,
        dataset_name=dataset.name if dataset else None,
        app_name=app.name if app else None,
        evaluators=evaluators,
        results_summary=results_summary,
    )


@router.post("/evaluations/{eval_id}/start")
async def start_evaluation(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    eval_id: int,
    background_tasks: BackgroundTasks,
) -> Any:
    """启动评估任务"""
    evaluation = db.query(Evaluation).filter(Evaluation.id == eval_id).first()
    if not evaluation:
        raise HTTPException(status_code=404, detail="评估任务不存在")

    if evaluation.status == "running":
        raise HTTPException(status_code=400, detail="评估任务正在运行中")

    evaluation.status = "running"
    evaluation.started_at = datetime.utcnow()
    evaluation.progress = 0
    db.commit()

    # 后台执行评估任务
    from app.services.evaluation import EvaluationEngine

    engine = EvaluationEngine(db)
    background_tasks.add_task(engine.run_evaluation, eval_id)

    return {"message": "评估任务已启动", "evaluation_id": eval_id}


@router.post("/evaluations/{eval_id}/cancel")
def cancel_evaluation(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    eval_id: int,
) -> Any:
    """取消评估任务"""
    evaluation = db.query(Evaluation).filter(Evaluation.id == eval_id).first()
    if not evaluation:
        raise HTTPException(status_code=404, detail="评估任务不存在")

    if evaluation.status != "running":
        raise HTTPException(status_code=400, detail="评估任务未在运行中")

    evaluation.status = "failed"
    evaluation.completed_at = datetime.utcnow()
    db.commit()

    return {"message": "评估任务已取消"}


@router.delete("/evaluations/{eval_id}")
def delete_evaluation(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    eval_id: int,
) -> Any:
    """删除评估任务"""
    evaluation = db.query(Evaluation).filter(Evaluation.id == eval_id).first()
    if not evaluation:
        raise HTTPException(status_code=404, detail="评估任务不存在")

    if evaluation.status == "running":
        raise HTTPException(status_code=400, detail="无法删除运行中的评估任务")

    db.delete(evaluation)
    db.commit()
    return {"message": "评估任务已删除"}


# ============================================================
# 评估结果 API
# ============================================================


@router.get(
    "/evaluations/{eval_id}/results", response_model=EvaluationResultListResponse
)
def list_evaluation_results(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    eval_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    passed: Optional[bool] = None,
    evaluator_id: Optional[int] = None,
    category: Optional[str] = None,
) -> Any:
    """获取评估结果列表"""
    evaluation = db.query(Evaluation).filter(Evaluation.id == eval_id).first()
    if not evaluation:
        raise HTTPException(status_code=404, detail="评估任务不存在")

    query = db.query(EvaluationResult).filter(EvaluationResult.evaluation_id == eval_id)

    if passed is not None:
        query = query.filter(EvaluationResult.passed == passed)
    if evaluator_id:
        query = query.filter(EvaluationResult.evaluator_id == evaluator_id)
    if category:
        query = query.join(TestCase).filter(TestCase.category == category)

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return EvaluationResultListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/evaluations/{eval_id}/results/{result_id}",
    response_model=EvaluationResultDetailResponse,
)
def get_evaluation_result(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    eval_id: int,
    result_id: int,
) -> Any:
    """获取评估结果详情"""
    result = (
        db.query(EvaluationResult)
        .filter(
            EvaluationResult.id == result_id,
            EvaluationResult.evaluation_id == eval_id,
        )
        .first()
    )
    if not result:
        raise HTTPException(status_code=404, detail="评估结果不存在")

    test_case = db.query(TestCase).filter(TestCase.id == result.test_case_id).first()
    evaluator = db.query(Evaluator).filter(Evaluator.id == result.evaluator_id).first() if result.evaluator_id else None

    return EvaluationResultDetailResponse(
        **result.__dict__,
        test_case=test_case,
        evaluator=evaluator,
    )


# ============================================================
# 执行轨迹 API
# ============================================================


@router.get("/traces", response_model=TraceListResponse)
def list_traces(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    app_id: Optional[int] = None,
    trace_type: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Any:
    """获取轨迹列表"""
    query = db.query(Trace)

    if app_id:
        query = query.filter(Trace.app_id == app_id)
    if trace_type:
        query = query.filter(Trace.trace_type == trace_type)
    if status:
        query = query.filter(Trace.status == status)

    total = query.count()
    items = query.order_by(Trace.started_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return TraceListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/traces/{trace_id}", response_model=TraceResponse)
def get_trace(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    trace_id: int,
) -> Any:
    """获取轨迹详情"""
    trace = db.query(Trace).filter(Trace.id == trace_id).first()
    if not trace:
        raise HTTPException(status_code=404, detail="轨迹不存在")
    return trace


# ============================================================
# 评估报告 API
# ============================================================


@router.get("/evaluations/{eval_id}/report", response_model=EvaluationReport)
def get_evaluation_report(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    eval_id: int,
) -> Any:
    """获取评估报告"""
    evaluation = db.query(Evaluation).filter(Evaluation.id == eval_id).first()
    if not evaluation:
        raise HTTPException(status_code=404, detail="评估任务不存在")

    from app.models.app import App

    app = db.query(App).filter(App.id == evaluation.app_id).first()
    dataset = (
        db.query(EvaluationDataset)
        .filter(EvaluationDataset.id == evaluation.dataset_id)
        .first()
    )

    results = (
        db.query(EvaluationResult).filter(EvaluationResult.evaluation_id == eval_id).all()
    )

    # 按评估器分组统计
    evaluator_scores = {}
    for result in results:
        if result.evaluator_id:
            if result.evaluator_id not in evaluator_scores:
                evaluator_scores[result.evaluator_id] = {"scores": [], "passed": 0, "total": 0}
            evaluator_scores[result.evaluator_id]["scores"].append(result.score or 0)
            evaluator_scores[result.evaluator_id]["total"] += 1
            if result.passed:
                evaluator_scores[result.evaluator_id]["passed"] += 1

    evaluator_scores_list = []
    for eid, data in evaluator_scores.items():
        evaluator = db.query(Evaluator).filter(Evaluator.id == eid).first()
        evaluator_scores_list.append({
            "evaluator_id": eid,
            "evaluator_name": evaluator.name if evaluator else "Unknown",
            "avg_score": sum(data["scores"]) / len(data["scores"]) if data["scores"] else 0,
            "pass_rate": data["passed"] / data["total"] if data["total"] > 0 else 0,
            "total": data["total"],
        })

    # 计算分类得分
    category_scores = {}
    for result in results:
        test_case = db.query(TestCase).filter(TestCase.id == result.test_case_id).first()
        if test_case:
            category = test_case.category or "unknown"
            if category not in category_scores:
                category_scores[category] = {"scores": [], "passed": 0, "total": 0}
            category_scores[category]["scores"].append(result.score or 0)
            category_scores[category]["total"] += 1
            if result.passed:
                category_scores[category]["passed"] += 1

    category_scores_list = [
        CategoryScore(
            category=cat,
            score=sum(data["scores"]) / len(data["scores"]) if data["scores"] else 0,
            total=data["total"],
            passed=data["passed"],
        )
        for cat, data in category_scores.items()
    ]

    # 错误分析
    error_analysis = {
        "total_errors": sum(1 for r in results if r.error_message),
        "error_types": {},
        "low_score_cases": [],
    }
    for result in results:
        if result.error_message:
            error_type = result.error_message[:50]
            error_analysis["error_types"][error_type] = (
                error_analysis["error_types"].get(error_type, 0) + 1
            )
        if result.score is not None and result.score < 0.5:
            error_analysis["low_score_cases"].append(result.id)

    duration = None
    if evaluation.started_at and evaluation.completed_at:
        delta = evaluation.completed_at - evaluation.started_at
        duration = f"{delta.total_seconds():.1f}秒"

    return EvaluationReport(
        evaluation=evaluation,
        dataset_name=dataset.name if dataset else "未知",
        app_name=app.name if app else "未知",
        total_cases=evaluation.total_cases,
        completed_cases=evaluation.completed_cases,
        success_cases=evaluation.success_cases,
        overall_score=evaluation.overall_score or 0,
        duration=duration,
        evaluator_scores=evaluator_scores_list,
        category_scores=category_scores_list,
        error_analysis=error_analysis,
    )


# ============================================================
# 分析统计 API
# ============================================================


@router.get("/analytics/overview", response_model=AnalyticsOverview)
def get_analytics_overview(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    app_id: Optional[int] = None,
) -> Any:
    """获取分析概览"""
    eval_query = db.query(Evaluation).filter(Evaluation.user_id == current_user.id)
    if app_id:
        eval_query = eval_query.filter(Evaluation.app_id == app_id)

    total_evaluations = eval_query.count()
    completed_evaluations = eval_query.filter(Evaluation.status == "completed").count()
    total_datasets = db.query(EvaluationDataset).count()
    total_evaluators = db.query(Evaluator).filter(Evaluator.is_active == True).count()

    completed_evals = eval_query.filter(
        Evaluation.status == "completed", Evaluation.overall_score.isnot(None)
    ).all()
    avg_score = (
        sum(e.overall_score for e in completed_evals) / len(completed_evals)
        if completed_evals
        else 0
    )

    results_query = db.query(EvaluationResult).join(Evaluation).filter(
        Evaluation.user_id == current_user.id
    )
    if app_id:
        results_query = results_query.filter(Evaluation.app_id == app_id)

    all_results = results_query.all()
    tool_accuracy = 0
    if all_results:
        passed_count = sum(1 for r in all_results if r.passed)
        tool_accuracy = passed_count / len(all_results) * 100

    completion_rate = (
        completed_evaluations / total_evaluations * 100 if total_evaluations > 0 else 0
    )

    return AnalyticsOverview(
        total_evaluations=total_evaluations,
        total_datasets=total_datasets,
        total_evaluators=total_evaluators,
        avg_score=round(avg_score, 2),
        tool_accuracy=round(tool_accuracy, 2),
        completion_rate=round(completion_rate, 2),
    )


@router.get("/analytics/comparison", response_model=ComparisonResult)
def compare_evaluations(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    eval_ids: str = Query(..., description="逗号分隔的评估 ID 列表"),
) -> Any:
    """对比多个评估结果"""
    try:
        ids = [int(id.strip()) for id in eval_ids.split(",")]
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的评估 ID 格式")

    evaluations = db.query(Evaluation).filter(Evaluation.id.in_(ids)).all()
    if not evaluations:
        raise HTTPException(status_code=404, detail="未找到评估任务")

    # 评估器对比
    evaluator_comparison = []
    for evaluation in evaluations:
        results = (
            db.query(EvaluationResult)
            .filter(EvaluationResult.evaluation_id == evaluation.id)
            .all()
        )

        eval_scores = {}
        for result in results:
            if result.evaluator_id:
                if result.evaluator_id not in eval_scores:
                    eval_scores[result.evaluator_id] = []
                eval_scores[result.evaluator_id].append(result.score or 0)

        evaluator_comparison.append({
            "evaluation_id": evaluation.id,
            "evaluation_name": evaluation.name,
            "evaluator_scores": {
                eid: sum(scores) / len(scores) if scores else 0
                for eid, scores in eval_scores.items()
            },
        })

    # 分类对比
    category_comparison = []
    for evaluation in evaluations:
        results = (
            db.query(EvaluationResult)
            .filter(EvaluationResult.evaluation_id == evaluation.id)
            .all()
        )

        cats = {}
        for result in results:
            test_case = db.query(TestCase).filter(TestCase.id == result.test_case_id).first()
            if test_case:
                cat = test_case.category or "unknown"
                if cat not in cats:
                    cats[cat] = {"scores": [], "passed": 0, "total": 0}
                cats[cat]["scores"].append(result.score or 0)
                cats[cat]["total"] += 1
                if result.passed:
                    cats[cat]["passed"] += 1

        cat_stats = {
            cat: {
                "avg_score": sum(data["scores"]) / len(data["scores"]) if data["scores"] else 0,
                "pass_rate": data["passed"] / data["total"] if data["total"] > 0 else 0,
                "total": data["total"],
            }
            for cat, data in cats.items()
        }
        category_comparison.append({
            "evaluation_id": evaluation.id,
            "evaluation_name": evaluation.name,
            "categories": cat_stats,
        })

    summary = {
        "best_overall": max(evaluations, key=lambda e: e.overall_score or 0).__dict__,
        "worst_overall": min(evaluations, key=lambda e: e.overall_score or 0).__dict__,
        "count": len(evaluations),
    }

    return ComparisonResult(
        evaluations=evaluations,
        evaluator_comparison=evaluator_comparison,
        dimension_comparison=[],
        category_comparison=category_comparison,
        summary=summary,
    )
