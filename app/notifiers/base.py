"""
Abstract base class for notification backends.

通知后端的抽象基类。
"""

from abc import ABC, abstractmethod
from typing import Any


class NotifierBackend(ABC):
    """
    Abstract base class that all notification backends must implement.

    所有通知后端必须实现的抽象基类。

    Subclasses must implement send_sync_result and send_new_announcements.
    子类必须实现 send_sync_result 和 send_new_announcements。
    """

    @abstractmethod
    def send_sync_result(self, sync_log: Any) -> None:
        """
        Send a notification about a completed sync operation.

        发送同步操作完成的通知。

        Args:
        sync_log: SyncLog ORM instance with status, counts, duration, etc.
        SyncLog ORM 实例，包含状态、计数、耗时等信息。

        """
        ...

    @abstractmethod
    def send_new_announcements(self, announcements: list[Any], stock_code: str) -> None:
        """
        Send a notification about newly synced announcements.

        发送新同步公告的通知。

        Args:
        announcements: List of newly inserted announcement dicts.
        新插入的公告字典列表。
        stock_code: The stock code these announcements belong to.
        这些公告所属的股票代码。

        """
        ...
