"""Shared test helpers."""
import os
import shutil
import tempfile


def create_temp_project(files: dict) -> str:
    """Create a temporary directory with the given files.

    ``files`` maps relative paths (may include subdirectories) to content.
    Returns the temporary directory path.
    """
    tmp = tempfile.mkdtemp(prefix="pharos_test_")
    for rel, content in files.items():
        full = os.path.join(tmp, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(content)
    return tmp


def cleanup_temp_project(path: str) -> None:
    shutil.rmtree(path, ignore_errors=True)


SAMPLE_PYTHON = '''"""Configuration parser module."""
import os
import json


def parseConfig(filename):
    """Parse a configuration file and return settings."""
    with open(filename) as fh:
        return json.load(fh)


class ConfigLoader:
    """Loads configuration from disk."""

    def load_database_settings(self, path):
        settings = parseConfig(path)
        return settings.get("database", {})
'''

SAMPLE_MARKDOWN = """# Project Notes

This document describes the search engine architecture.
The indexer walks directories and builds an inverted index.

## Searching

Users can search for configuration, database settings and parsers.
"""

SAMPLE_CHINESE = "搜索引擎会建立倒排索引，支持中文分词和快速检索。\n用户可以搜索配置文件。\n"
