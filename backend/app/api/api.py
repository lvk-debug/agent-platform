from fastapi import APIRouter

from app.api.endpoints import users, apps, knowledge, models, tools, chatbot, workflow, publish

api_router = APIRouter()

# 包含各个模块的路由
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(apps.router, prefix="/apps", tags=["apps"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])
api_router.include_router(models.router, prefix="/models", tags=["models"])
api_router.include_router(tools.router, prefix="/tools", tags=["tools"])
api_router.include_router(chatbot.router, prefix="/chatbot", tags=["chatbot"])
api_router.include_router(workflow.router, prefix="/workflow", tags=["workflow"])
api_router.include_router(publish.router, prefix="/apps/{app_id}/publish", tags=["publish"])
