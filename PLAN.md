# MFClab 개발 계획서

이 문서는 과거 차수 기록보다 "현재 코드베이스를 안전하게 이어받기 위한 기준 문서"를 목표로 합니다.
다음 작업자가 이 문서만 읽고도 현재 아키텍처, UI 계약, 테스트 경계, 향후 작업 후보를 이해할 수 있어야 합니다.

## 현재 상태 요약

- 앱 종류: PySide6 + PyQtGraph 기반 데스크톱 분석 도구
- 주 워크플로: CSV 선택 → 시간축 검증 → 필터 체인 적용 → Time/FFT/메트릭 비교
- 현재 노출 모드: 필터 모드
- 표준 실행: `uv run python main.py`
- 표준 테스트: `uv run python -m pytest`
- 표준 빌드: `uv run pyinstaller mfclab.spec --noconfirm`

## 현재 아키텍처

### 1. CSV 입력 흐름

- 진입점은 메뉴 액션 `actionOpenCSV`이다.
- CSV 로드 UI는 `src/csv_dialog.py`의 `CSVOpenDialog`가 담당한다.
- 다이얼로그에서 파일 선택, 헤더 읽기, Time/Data 열 선택까지 마친 뒤 실제 로드는 `src/main_window.py`의 `_load_data()`로 이어진다.

### 2. 시간축 검증 원칙

- `src/csv_loader.py`의 `validate_time_axis()`가 시간축을 검증한다.
- 시간축은 **monotonically non-decreasing**이어야 한다.
- 역순 timestamp(`dt < 0`)는 거부한다.
- duplicate timestamp(`dt == 0`)는 logging artifact로 보고 허용한다.
- duplicate timestamp가 있으면 로드 시 경고를 띄우고, 상태 표시에도 duplicate 개수를 남긴다.
- 양의 dt들의 상대 표준편차가 충분히 작으면 균일 샘플링으로 간주하고, 대표 dt(중앙값)에서 운영용 `fs`를 정한다.
- 시간축이 대체로 일정하지 않으면 앱은 경고를 띄우고 사용자가 계속 진행할지 선택한다.

### 3. 필터 체인

- `src/filter_chain.py`가 체인 상태와 실행을 담당한다.
- 각 필터는 `src/filters/base.py`의 `BaseFilter`를 상속한다.
- 필터 추가 시 필요한 최소 작업은 "필터 파일 추가 + `src/filters/__init__.py` 등록"이다.
- 현재 등록된 필터는 다음과 같다.
  - 이동평균 (MA)
  - Median
  - FIR
  - IIR LPF
  - IIR LPF (2차)
  - Bessel LPF (2nd)
  - 미분 필터

### 4. 그래프와 메트릭

- `src/main_window.py`가 그래프 구성과 UI 이벤트를 관리한다.
- `src/fft_engine.py`는 one-sided FFT magnitude 계산을 담당한다.
- `src/metrics_engine.py`는 Settled std와 HF RMS를 계산한다.
- HF RMS cutoff가 Nyquist 이상이면 통과 가능한 고주파 대역이 없다고 보고 `0.0`을 반환한다.

### 5. 빌드와 실행

- 엔트리포인트는 `main.py`이다.
- SciPy 관련 초기 import 비용은 `src/scipy_preload.py`가 완화한다.
- 리소스 경로는 `src/resources.py`의 `resource_path()`로 통합 관리한다.
- 실행 파일 빌드는 `mfclab.spec`를 사용한다.

## UI objectName 계약

현재 코드가 직접 참조하는 핵심 objectName은 아래와 같다.

| objectName | 타입 | 역할 |
|---|---|---|
| `actionOpenCSV` | QAction | CSV 열기 메뉴 액션 |
| `graphMain` | QWidget | 메인 Time domain 그래프 컨테이너 |
| `graphFFTRaw` | QWidget | Raw FFT 그래프 컨테이너 |
| `graphFFTFiltered` | QWidget | Filtered FFT 그래프 컨테이너 |
| `comboFilterType` | QComboBox | 필터 종류 선택 |
| `btnAddFilter` | QPushButton | 필터 체인에 추가 |
| `filterChainArea` | QScrollArea | 필터 카드 스크롤 영역 |
| `filterChainVLayout` | QVBoxLayout | 필터 카드 레이아웃 |
| `btnClearChain` | QPushButton | 체인 전체 초기화 |
| `labelSettledStd` | QLabel | Settled std 결과 표시 |
| `labelHFRMS` | QLabel | HF RMS 결과 표시 |
| `spinHFCutoff` | QDoubleSpinBox | HF RMS cutoff 입력 |
| `checkShowRegion` | QCheckBox | 분석 구간 표시 토글 |
| `comboFFTWindow` | QComboBox | FFT window 선택 |
| `labelStatus` | QLabel | 상태 표시 |

> UI 수정 시 이름을 바꾸지 않는 한 배치와 스타일은 자유롭게 바꿀 수 있다.
> 반대로 objectName을 바꾸면 `main_window.py`가 깨질 수 있다.

## 디렉터리 구조

```text
src/
├── main_window.py            # UI 로드, 그래프, 이벤트, 메트릭
├── csv_dialog.py             # CSV 선택/열 선택 다이얼로그
├── csv_loader.py             # CSV 읽기, 숫자 변환, 시간축 검증
├── signal_context.py         # fs, dt, uniformity, row counts
├── filter_chain.py           # 체인 상태와 순차 실행
├── fft_engine.py             # FFT magnitude 계산
├── metrics_engine.py         # Settled std, HF RMS
├── param_form.py             # ParamSpec -> QWidget 폼 생성
├── chain_card.py             # 체인 카드 위젯
├── resources.py              # frozen/dev 경로 헬퍼
├── scipy_preload.py          # SciPy preload
└── filters/                  # 개별 필터 구현
```

## 테스트 전략

현재 테스트는 다음 영역을 커버한다.

- 필터 개별 동작
- 필터 체인 조합
- FFT 엔진
- 메트릭 엔진
- CSV 로더와 시간축 검증 회귀

아직 전용 UI 자동화 테스트는 없다. 따라서 `main_window.py`와 `.ui` 변경 시에는 최소한 앱 초기화 스모크 체크를 함께 수행하는 것을 권장한다.

## 최근 정리된 이슈

- duplicate timestamp 때문에 CSV 로드가 막히지 않도록 조건을 완화하고, 대신 경고와 상태 표시로 드러나게 정리했다.
- HF RMS가 Nyquist 경계에서 전체 신호 RMS로 뒤집히던 문제를 수정했다.
- `README.md`, `PLAN.md`, `SPEC.md`를 현재 코드 구조와 동작에 맞게 다시 정리했다.

## 다음 작업 후보

- 분석 모드(도메인 분석 모드) UI 노출 여부 결정 및 실제 구현
- CSV 내보내기
- 필터 체인 preset 저장/불러오기
- 그래프 이미지 export
- 대용량 CSV의 worker thread 로드
