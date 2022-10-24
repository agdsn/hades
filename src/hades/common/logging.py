"""Common logging utilities"""
import logging


plain_formatter = logging.Formatter("%(message)s")
"""Formatter that produces only the log message"""

stderr_debug_formatter = logging.Formatter(
    "[%(asctime)s] %(levelname)s:%(filename)s:%(lineno)d:%(message)s"
)
"""Formatter for extensive debug output to stderr"""

syslog_debug_formatter = logging.Formatter("%(filename)s:%(lineno)d:%(message)s")
"""Formatter for extensive debug output to syslog"""
