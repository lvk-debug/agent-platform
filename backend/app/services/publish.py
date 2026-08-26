import json
import secrets
import string
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.app import App
from app.models.publish_config import PublishConfig

# 所有支持的发布渠道
ALL_CHANNELS = ["api", "mcp", "embed", "wechat", "h5"]


def _generate_api_key() -> str:
    """生成随机 API Key"""
    alphabet = string.ascii_letters + string.digits
    prefix = "ak-"
    key = "".join(secrets.choice(alphabet) for _ in range(40))
    return prefix + key


def _generate_mcp_config(app: App, base_url: str) -> Dict[str, Any]:
    """生成 MCP Server 配置"""
    return {
        "mcpServers": {
            app.name: {
                "url": f"{base_url}/api/v1/apps/{app.id}/mcp",
                "headers": {"Authorization": "Bearer <your-api-key>"},
            }
        }
    }


def _generate_embed_code(app_id: int, base_url: str) -> str:
    """生成 iframe 嵌入代码"""
    return (
        f"<iframe\n"
        f'  src="{base_url}/api/v1/apps/{app_id}/embed"\n'
        f'  width="400"\n'
        f'  height="600"\n'
        f'  frameborder="0"\n'
        f'  style="border: 1px solid #e5e7eb; border-radius: 12px;"\n'
        f"></iframe>"
    )


def _generate_wechat_guide(app_id: int, webhook_url: str) -> List[Dict[str, str]]:
    """生成微信公众号对接指引"""
    return [
        {
            "step": "1",
            "title": "创建公众号自定义菜单",
            "description": "在公众号后台 → 自定义菜单 → 添加菜单项",
        },
        {
            "step": "2",
            "title": "配置服务器地址",
            "description": f"将服务器 URL 设置为: {webhook_url}",
        },
        {
            "step": "3",
            "title": "设置 Token",
            "description": "在公众号后台 → 基本配置 → 服务器配置，填写 Token",
        },
        {
            "step": "4",
            "title": "提交验证",
            "description": "点击提交，系统将自动验证并启用",
        },
    ]


def _generate_h5_url(app_id: int, base_url: str) -> Dict[str, str]:
    """生成 H5 页面链接"""
    h5_url = f"{base_url}/api/v1/apps/{app_id}/h5"
    return {
        "url": h5_url,
        "title": "H5 页面访问链接",
    }


class PublishService:
    """发布服务"""

    def __init__(self, db: Session):
        self.db = db

    def _get_or_create_config(self, app_id: int, channel: str) -> PublishConfig:
        """获取或创建渠道配置"""
        config = (
            self.db.query(PublishConfig)
            .filter(PublishConfig.app_id == app_id, PublishConfig.channel == channel)
            .first()
        )
        if not config:
            config = PublishConfig(
                app_id=app_id, channel=channel, enabled=False, config="{}"
            )
            self.db.add(config)
            self.db.commit()
            self.db.refresh(config)
        return config

    def _get_app(self, app_id: int) -> Optional[App]:
        """获取应用"""
        return self.db.query(App).filter(App.id == app_id).first()

    def _get_base_url(self) -> str:
        """获取基础 URL（生产环境应从配置读取）"""
        return "http://localhost:3000"

    def get_all_configs(self, app_id: int) -> List[Dict[str, Any]]:
        """获取应用所有渠道配置"""
        app = self._get_app(app_id)
        if not app:
            return []

        base_url = self._get_base_url()
        result = []

        for channel in ALL_CHANNELS:
            config = self._get_or_create_config(app_id, channel)
            channel_data = self._build_channel_response(config, app, base_url)
            result.append(channel_data)

        return result

    def get_config(self, app_id: int, channel: str) -> Optional[Dict[str, Any]]:
        """获取单个渠道配置"""
        app = self._get_app(app_id)
        if not app:
            return None

        config = self._get_or_create_config(app_id, channel)
        base_url = self._get_base_url()
        return self._build_channel_response(config, app, base_url)

    def update_config(
        self, app_id: int, channel: str, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """更新渠道配置"""
        app = self._get_app(app_id)
        if not app:
            return None

        config = self._get_or_create_config(app_id, channel)

        if "enabled" in data:
            config.enabled = data["enabled"]
        if "config" in data:
            config.config = json.dumps(data["config"])

        self.db.commit()
        self.db.refresh(config)

        base_url = self._get_base_url()
        return self._build_channel_response(config, app, base_url)

    def enable_channel(self, app_id: int, channel: str) -> Optional[Dict[str, Any]]:
        """启用渠道"""
        app = self._get_app(app_id)
        if not app:
            return None

        config = self._get_or_create_config(app_id, channel)
        existing_config = json.loads(config.config) if config.config else {}

        # 根据渠道生成产出物
        base_url = self._get_base_url()
        if channel == "api" and "api_key" not in existing_config:
            existing_config["api_key"] = _generate_api_key()
            existing_config["api_endpoint"] = (
                f"{base_url}/api/v1/apps/{app_id}/api/chat"
            )
        elif channel == "mcp" and "mcp_config" not in existing_config:
            existing_config["mcp_config"] = _generate_mcp_config(app, base_url)
            existing_config["mcp_command"] = (
                f"npx mcp-remote {base_url}/api/v1/apps/{app_id}/mcp"
            )
        elif channel == "embed" and "embed_code" not in existing_config:
            existing_config["embed_code"] = _generate_embed_code(app_id, base_url)
            existing_config["embed_url"] = f"{base_url}/api/v1/apps/{app_id}/embed"
        elif channel == "wechat" and "webhook_url" not in existing_config:
            existing_config["webhook_url"] = (
                f"{base_url}/api/v1/apps/{app_id}/wechat/webhook"
            )
            existing_config["guide"] = _generate_wechat_guide(
                app_id, existing_config["webhook_url"]
            )
        elif channel == "h5" and "h5_url" not in existing_config:
            h5_data = _generate_h5_url(app_id, base_url)
            existing_config["h5_url"] = h5_data["url"]

        config.config = json.dumps(existing_config)
        config.enabled = True

        self.db.commit()
        self.db.refresh(config)

        base_url = self._get_base_url()
        return self._build_channel_response(config, app, base_url)

    def disable_channel(self, app_id: int, channel: str) -> Optional[Dict[str, Any]]:
        """禁用渠道"""
        config = (
            self.db.query(PublishConfig)
            .filter(PublishConfig.app_id == app_id, PublishConfig.channel == channel)
            .first()
        )
        if not config:
            return None

        config.enabled = False
        self.db.commit()
        self.db.refresh(config)

        app = self._get_app(app_id)
        base_url = self._get_base_url()
        return self._build_channel_response(config, app, base_url)

    def _build_channel_response(
        self, config: PublishConfig, app: App, base_url: str
    ) -> Dict[str, Any]:
        """构建渠道响应数据"""
        channel_config = json.loads(config.config) if config.config else {}

        response: Dict[str, Any] = {
            "channel": config.channel,
            "enabled": config.enabled,
            "config": channel_config,
            "created_at": config.created_at.isoformat() if config.created_at else None,
            "updated_at": config.updated_at.isoformat() if config.updated_at else None,
        }

        # 根据渠道添加产出物
        if config.channel == "api":
            response["api_key"] = channel_config.get("api_key")
            response["api_endpoint"] = channel_config.get("api_endpoint")
        elif config.channel == "mcp":
            response["mcp_config"] = channel_config.get("mcp_config")
            response["mcp_command"] = channel_config.get("mcp_command")
        elif config.channel == "embed":
            response["embed_code"] = channel_config.get("embed_code")
            response["embed_url"] = channel_config.get("embed_url")
        elif config.channel == "wechat":
            response["wechat_webhook_url"] = channel_config.get("webhook_url")
            response["wechat_guide"] = channel_config.get("guide")
        elif config.channel == "h5":
            response["h5_url"] = channel_config.get("h5_url")

        return response


def get_publish_service(db: Session) -> PublishService:
    """获取发布服务实例"""
    return PublishService(db)
