# MFClab

유량 센서 Raw Data 분석기. CSV 시계열 데이터를 불러와 필터 체인을 적용하고,
시간영역 파형, FFT 스펙트럼, 정량 지표를 함께 비교하는 PySide6 데스크톱 앱입니다.

## Features

- CSV 열기 다이얼로그: 파일 선택, 헤더 읽기, Time/Data 열 선택을 한 화면에서 처리
- 시간축 검증: 역순 시간축 거부, duplicate timestamp 허용(경고 및 상태 표시), 간격 분산이 작으면 균일 샘플링으로 간주, 운영용 `fs` 자동 계산
- 필터 체인: 추가, 삭제, 순서 변경, on/off 토글, 카드 접기/펼치기
- 지원 필터: 이동평균 (MA), Median, FIR, IIR LPF, IIR LPF (2차), Bessel LPF (2nd), 미분 필터
- 그래프: Time domain Raw/Filtered 비교 + FFT Raw/Filtered 비교
- 평가 지표: Settled noise std, High-frequency RMS, 예상 delay
- 빌드: PyInstaller 기반 단일 실행 파일 생성

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager

## Setup

```bash
uv sync
```

## Run

```bash
uv run python main.py
```

## Test

```bash
uv run python -m pytest
```

현재 테스트 스위트는 필터, 체인, FFT, 메트릭, CSV 로더/시간축 검증 회귀 테스트를 포함합니다.

## Build

```bash
uv run pyinstaller mfclab.spec --noconfirm
```

산출물은 `dist/MFClab.exe`입니다.

> `pyside6-deploy`는 현재 `uv` 환경 구성과 맞지 않아 사용하지 않고, PyInstaller를 표준 빌드 경로로 사용합니다.

## Project Structure

```text
MFClab/
├── main.py
├── mfclab.spec
├── pyproject.toml
├── README.md
├── SPEC.md
├── PLAN.md
├── LICENSES.md
├── ui/
│   └── mainwindow.ui
├── src/
│   ├── main_window.py
│   ├── csv_dialog.py
│   ├── csv_loader.py
│   ├── signal_context.py
│   ├── filter_chain.py
│   ├── fft_engine.py
│   ├── metrics_engine.py
│   ├── param_form.py
│   ├── chain_card.py
│   ├── resources.py
│   ├── scipy_preload.py
│   └── filters/
│       ├── __init__.py
│       ├── base.py
│       ├── moving_average.py
│       ├── median.py
│       ├── fir.py
│       ├── iir_lpf.py
│       ├── critical_damped_lpf.py
│       ├── biquad_lowpass.py
│       └── lead_compensator.py
├── tests/
│   ├── test_filters.py
│   ├── test_filter_chain.py
│   ├── test_fft.py
│   ├── test_metrics.py
│   └── test_csv_loader.py
└── data/
    └── rawdata.csv
```

## Notes

- 현재 사용자에게 노출된 메인 워크플로는 필터 모드입니다.
- 분석 구간(region)과 메트릭 UI는 필터 모드의 정량 비교를 위한 기능입니다.
- 서드파티 라이선스는 [LICENSES.md](LICENSES.md)를 참고하세요.
