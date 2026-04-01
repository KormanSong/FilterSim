# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MFClab: 유량 센서 Raw Data 분석기. CSV 시계열 데이터를 불러와 필터 체인을 적용하고, 시간영역/FFT/메트릭으로 비교하는 PySide6 데스크톱 앱. 언어는 한국어 기반.

## Commands

```bash
uv sync                                    # 의존성 설치
uv run python main.py                      # 앱 실행
uv run python -m pytest                    # 전체 테스트
uv run python -m pytest tests/test_filters.py          # 필터 테스트만
uv run python -m pytest tests/test_filters.py -k lead  # 특정 테스트
uv run pyinstaller mfclab.spec --noconfirm             # 빌드 (dist/MFClab.exe)
```

## Architecture

### 데이터 흐름

CSV 파일 → `csv_dialog.py` (열 선택) → `csv_loader.py` (시간축 검증, fs 산출) → `SignalContext` 생성 → `FilterChain.execute()` (직렬 적용) → `main_window.py` (그래프/FFT/메트릭 표시)

### 필터 프레임워크

- 모든 필터는 `src/filters/base.py`의 `BaseFilter`를 상속
- `ParamSpec`으로 파라미터를 선언하면 UI 폼이 자동 생성됨 (`src/param_form.py`)
- 새 필터 추가: 필터 클래스 파일 작성 → `src/filters/__init__.py`의 `FILTER_REGISTRY`에 등록
- `apply(data, ctx, **params)` 시그니처 준수, 동일 길이 배열 반환

### 설계 원칙

- **Causal-first**: 실시간 필터는 미래 샘플을 보지 않음 (`filtfilt` 사용 금지)
- **펌웨어 일치성**: MCU로 옮기기 쉬운 수식과 상태 모델 선호
- **SignalContext**: `fs`, `dt`, 균일성, 행 수를 담는 공유 컨텍스트. 필터와 FFT 엔진 모두 이것에 의존

### UI 계약

`ui/mainwindow.ui`의 objectName은 `src/main_window.py`에서 직접 참조됨. objectName 변경 시 코드도 함께 수정 필요. 상세 목록은 `PLAN.md`의 "UI objectName 계약" 참조.

## Testing

UI 자동화 테스트 없음. `main_window.py`나 `.ui` 변경 시 앱 초기화 스모크 체크 필요.
