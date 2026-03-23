"""Frozen / 개발 환경 공용 리소스 경로 헬퍼."""

from __future__ import annotations

import sys
from pathlib import Path

# 프로젝트 루트: src/ 의 부모
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def resource_path(relative: str | Path) -> Path:
    """상대 경로를 절대 경로로 변환한다.

    PyInstaller/Nuitka frozen 환경에서는 sys._MEIPASS 또는
    __compiled__ 기반 임시 디렉토리를 사용하고,
    개발 환경에서는 프로젝트 루트를 기준으로 한다.
    """
    # PyInstaller frozen
    base = getattr(sys, "_MEIPASS", None)
    if base is not None:
        return Path(base) / relative

    return _PROJECT_ROOT / relative
