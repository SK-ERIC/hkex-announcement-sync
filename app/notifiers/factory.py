"""
Factory for creating notification backend instances.

通知后端实例的工厂模块。
"""

from app.config import Settings
from app.notifiers.base import NotifierBackend


def create_notifier(settings: Settings | None = None) -> NotifierBackend | None:
    """
    Create a notifier instance based on configuration.

    根据配置创建通知后端实例。

    Returns None if notifications are disabled or no notifier type is configured.

    当通知功能未启用或未配置通知类型时返回 None。

    Args:
    settings: Application settings. Uses defaults if None.
    应用配置。为 None 时使用默认值。

    Returns:
    NotifierBackend | None: Configured notifier instance, or None if disabled.
    已配置的通知后端实例，禁用时返回 None。

    """
    if settings is None:
        from app.config import get_settings

        settings = get_settings()

    if not settings.NOTIFIER_ENABLED or not settings.NOTIFIER_TYPE:
        return None

    match settings.NOTIFIER_TYPE:
        case "feishu":
            from app.notifiers.feishu import FeishuNotifier

            return FeishuNotifier(settings)
        case _:
            return None
