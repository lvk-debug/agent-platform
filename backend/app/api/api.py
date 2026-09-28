from fastapi import APIRouter

from app.api.endpoints import (
    agent,
    app_chat,
    apps,
    chatbot,
    devices,
    evaluation,
    hermes,
    knowledge,
    learning,
    models,
    paper_agent,
    publish,
    scheduled_tasks,
    support,
    tools,
    users,
    workflow,
)

api_router = APIRouter()

# 包含各个模块的路由
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(apps.router, prefix="/apps", tags=["apps"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])
api_router.include_router(learning.router, prefix="/learning", tags=["learning"])
api_router.include_router(support.router, prefix="/support", tags=["support"])
api_router.include_router(models.router, prefix="/models", tags=["models"])
api_router.include_router(paper_agent.router, prefix="/paper-agent", tags=["paper-agent"])
api_router.include_router(tools.router, prefix="/tools", tags=["tools"])
api_router.include_router(chatbot.router, prefix="/chatbot", tags=["chatbot"])
api_router.include_router(workflow.router, prefix="/workflow", tags=["workflow"])
api_router.include_router(agent.router, prefix="/agent", tags=["agent"])
api_router.include_router(app_chat.router, prefix="/apps", tags=["app-api"])
api_router.include_router(
    publish.router, prefix="/apps/{app_id}/publish", tags=["publish"]
)
api_router.include_router(evaluation.router, prefix="/evaluation", tags=["evaluation"])
api_router.include_router(hermes.router, prefix="/hermes", tags=["hermes"])
api_router.include_router(
    scheduled_tasks.router, prefix="/scheduled-tasks", tags=["scheduled-tasks"]
)
api_router.include_router(devices.router, prefix="/devices", tags=["devices"])
