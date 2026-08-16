from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.model import ModelProvider, Model
from app.schemas.model import (
    ModelCreate,
    ModelUpdate,
    ModelProviderCreate,
    ModelProviderUpdate,
    ModelProviderResponse,
    ModelResponse,
)
from app.utils.deps import get_current_user

router = APIRouter()


@router.get("/providers", response_model=List[ModelProviderResponse])
def read_model_providers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    获取模型供应商列表
    """
    providers = db.query(ModelProvider).filter(
        ModelProvider.is_active == True
    ).all()
    return providers


@router.post("/providers", response_model=ModelProviderResponse)
def create_model_provider(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    provider_in: ModelProviderCreate,
) -> Any:
    """
    创建模型供应商
    """
    provider = ModelProvider(
        name=provider_in.name,
        provider_type=provider_in.provider_type,
        api_endpoint=provider_in.api_endpoint,
        api_key=provider_in.api_key,
        api_config=provider_in.api_config,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return provider


@router.get("/providers/{provider_id}", response_model=ModelProviderResponse)
def read_model_provider(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    provider_id: int,
) -> Any:
    """
    获取模型供应商详情
    """
    provider = db.query(ModelProvider).filter(
        ModelProvider.id == provider_id
    ).first()
    if not provider:
        raise HTTPException(
            status_code=404,
            detail="模型供应商不存在",
        )
    return provider


@router.delete("/providers/{provider_id}")
def delete_model_provider(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    provider_id: int,
) -> Any:
    """
    删除模型供应商
    """
    provider = db.query(ModelProvider).filter(
        ModelProvider.id == provider_id
    ).first()
    if not provider:
        raise HTTPException(
            status_code=404,
            detail="模型供应商不存在",
        )

    # 删除供应商下的所有模型
    db.query(Model).filter(Model.provider_id == provider_id).delete()

    # 删除供应商
    db.delete(provider)
    db.commit()
    return {"message": "删除成功"}


@router.put("/providers/{provider_id}", response_model=ModelProviderResponse)
def update_model_provider(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    provider_id: int,
    provider_in: ModelProviderUpdate,
) -> Any:
    """
    更新模型供应商
    """
    provider = db.query(ModelProvider).filter(
        ModelProvider.id == provider_id
    ).first()
    if not provider:
        raise HTTPException(
            status_code=404,
            detail="模型供应商不存在",
        )

    # 更新供应商信息
    if provider_in.name is not None:
        provider.name = provider_in.name
    if provider_in.api_endpoint is not None:
        provider.api_endpoint = provider_in.api_endpoint
    if provider_in.api_key is not None:
        provider.api_key = provider_in.api_key
    if provider_in.api_config is not None:
        provider.api_config = provider_in.api_config
    if provider_in.is_active is not None:
        provider.is_active = provider_in.is_active

    db.commit()
    db.refresh(provider)
    return provider


@router.get("/providers/{provider_id}/models", response_model=List[ModelResponse])
def read_models(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    provider_id: int,
) -> Any:
    """
    获取供应商下的模型列表
    """
    # 检查供应商是否存在
    provider = db.query(ModelProvider).filter(
        ModelProvider.id == provider_id
    ).first()
    if not provider:
        raise HTTPException(
            status_code=404,
            detail="模型供应商不存在",
        )

    models = db.query(Model).filter(
        Model.provider_id == provider_id,
        Model.is_active == True,
    ).all()
    return models


@router.post("/providers/{provider_id}/models", response_model=ModelResponse)
def create_model(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    provider_id: int,
    model_in: ModelCreate,
) -> Any:
    """
    创建模型
    """
    # 检查供应商是否存在
    provider = db.query(ModelProvider).filter(
        ModelProvider.id == provider_id
    ).first()
    if not provider:
        raise HTTPException(
            status_code=404,
            detail="模型供应商不存在",
        )

    model = Model(
        provider_id=provider_id,
        name=model_in.name,
        model_id=model_in.model_id,
        description=model_in.description,
        max_tokens=model_in.max_tokens,
        supports_streaming=model_in.supports_streaming,
        supports_function_calling=model_in.supports_function_calling,
        default_temperature=model_in.default_temperature,
        default_max_tokens=model_in.default_max_tokens,
        is_active=model_in.is_active,
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


@router.put("/providers/{provider_id}/models/{model_id}", response_model=ModelResponse)
def update_model(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    provider_id: int,
    model_id: int,
    model_in: ModelUpdate,
) -> Any:
    """
    更新模型
    """
    model = db.query(Model).filter(
        Model.id == model_id,
        Model.provider_id == provider_id,
    ).first()
    if not model:
        raise HTTPException(
            status_code=404,
            detail="模型不存在",
        )

    if model_in.name is not None:
        model.name = model_in.name
    if model_in.model_id is not None:
        model.model_id = model_in.model_id
    if model_in.description is not None:
        model.description = model_in.description
    if model_in.max_tokens is not None:
        model.max_tokens = model_in.max_tokens
    if model_in.supports_streaming is not None:
        model.supports_streaming = model_in.supports_streaming
    if model_in.supports_function_calling is not None:
        model.supports_function_calling = model_in.supports_function_calling
    if model_in.default_temperature is not None:
        model.default_temperature = model_in.default_temperature
    if model_in.default_max_tokens is not None:
        model.default_max_tokens = model_in.default_max_tokens
    if model_in.is_active is not None:
        model.is_active = model_in.is_active

    db.commit()
    db.refresh(model)
    return model


@router.delete("/providers/{provider_id}/models/{model_id}")
def delete_model(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    provider_id: int,
    model_id: int,
) -> Any:
    """
    删除模型
    """
    model = db.query(Model).filter(
        Model.id == model_id,
        Model.provider_id == provider_id,
    ).first()
    if not model:
        raise HTTPException(
            status_code=404,
            detail="模型不存在",
        )

    db.delete(model)
    db.commit()
    return {"message": "删除成功"}


@router.get("/", response_model=List[ModelResponse])
def read_all_models(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    获取所有可用模型
    """
    models = db.query(Model).filter(
        Model.is_active == True
    ).all()
    return models
