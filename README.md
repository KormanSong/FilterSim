# MFClab

유량 센서 Raw Data 분석기 — CSV 시계열 데이터의 필터링과 FFT 스펙트럼 비교.

## Features

- CSV 파일 로드 (시간축 자동 검증, 불균일 시간축 경고)
- 실시간 필터 체인: Moving Average, Median, FIR, IIR Lowpass, Lead Compensator
- 필터 추가/삭제/순서변경/토글/파라미터 편집, 카드 접기/펼치기
- Time domain: Raw (gray) + Filtered (blue) 비교
- FFT: Raw / Filtered 스펙트럼 비교 (Hann, Hamming, Blackman window)
- Window별 가중평균 DC 제거, Coherent gain 보정
- PyInstaller 단일 .exe 빌드 지원

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

현재 62개 테스트 (필터 34 + 체인 14 + FFT 14)

## Build (PyInstaller)

```bash
uv run pyinstaller mfclab.spec --noconfirm
```

산출물: `dist/MFClab.exe` (단일 실행 파일, ~103 MB)

> pyside6-deploy는 uv 환경(pip 미설치)에서 동작하지 않아 PyInstaller를 사용합니다.

## Project Structure

```
MFClab/
├── main.py                 # Entry point
├── mfclab.spec             # PyInstaller build config
├── ui/mainwindow.ui        # Qt Designer UI (objectName 계약)
├── src/
│   ├── main_window.py      # UI 로드 + 시그널 연결 + 그래프
│   ├── csv_loader.py       # CSV 헤더/열 로드 + 시간축 검증
│   ├── signal_context.py   # SignalContext (fs, dt, is_uniform)
│   ├── filter_chain.py     # 필터 파이프라인 엔진
│   ├── fft_engine.py       # FFT 계산 (rfft, window별 DC 제거)
│   ├── param_form.py       # ParamSpec 기반 폼 자동 생성
│   ├── chain_card.py       # 필터 체인 카드 위젯 (접기/펼치기)
│   ├── resources.py        # Frozen/개발 환경 경로 헬퍼
│   └── filters/            # 필터 플러그인
│       ├── base.py         # BaseFilter + ParamSpec
│       ├── moving_average.py
│       ├── median.py
│       ├── fir.py
│       ├── iir_lpf.py
│       └── lead_compensator.py
├── tests/                  # pytest 단위 테스트 (62개)
└── data/rawdata.csv        # 샘플 데이터 (98,444행)
```

## License

See [LICENSES.md](LICENSES.md) for third-party library licenses.
