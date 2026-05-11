"""
Logging configuration helpers for the application.

应用日志配置辅助模块。
"""

import logging
import sys


def setup_logging(level: str = "INFO"):
    """
    Configure root logger with stdout stream handler.

    配置根日志记录器，使用标准输出流处理器。
    """
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
