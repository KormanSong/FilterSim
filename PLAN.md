# MFClab 개발 계획서

> SPEC.md 기반 단계별 구현 계획
> 원칙: **UI는 사용자가 Qt Designer로 직접 편집**, 코드는 .ui의 objectName에 바인딩

---

## 프로젝트 구조 (현재)

```
MFClab/
├── main.py                    ← 엔트리포인트
├── pyproject.toml             ← uv 프로젝트 설정 (Python ≥3.13)
├── mfclab.spec                ← PyInstaller 빌드 설정 (onefile, windowed)
├── SPEC.md                    ← 기능 명세서 v5
├── PLAN.md                    ← 본 문서 (개발 계획 + 이력)
├── README.md                  ← 설치/실행/빌드 안내
├── LICENSES.md                ← 서드파티 라이선스 고지
├── ui/
│   └── mainwindow.ui          ← 유일한 UI 파일 (사용자가 Designer로 편집)
├── src/
│   ├── __init__.py
│   ├── main_window.py         ← UI 로드 + 시그널 연결 + 그래프 셋업
│   ├── csv_loader.py          ← CSV 헤더 읽기, 열 선택 로드, 시간축 검증
│   ├── signal_context.py      ← SignalContext 데이터클래스 (fs, dt, is_uniform, n_total, n_valid)
│   ├── filter_chain.py        ← 필터 체인 파이프라인 엔진
│   ├── param_form.py          ← ParamSpec 기반 폼 자동 생성기
│   ├── chain_card.py          ← 필터 체인 카드 위젯 (접기/펼치기 포함)
│   ├── fft_engine.py          ← FFT 계산 (rfft, window별 가중 DC 제거, coherent gain 보정)
│   ├── resources.py           ← frozen/개발 환경 공용 경로 헬퍼 (resource_path)
│   └── filters/
│       ├── __init__.py        ← FILTER_REGISTRY (필터 1줄 등록)
│       ├── base.py            ← BaseFilter + ParamSpec (frozen dataclass)
│       ├── moving_average.py  ← numpy pad(reflect) + convolve
│       ├── median.py          ← scipy.ndimage.median_filter(mode="reflect")
│       ├── fir.py             ← scipy.signal.firwin + filtfilt (default_params clamp 포함)
│       ├── iir_lpf.py         ← 1차 RC IIR 로우패스 (사용자 추가)
│       └── lead_compensator.py ← Lead Compensator (사용자 추가)
├── tests/
│   ├── __init__.py
│   ├── test_filters.py        ← 필터 단위 테스트 (MA 5, Median 4, FIR 15, IIR 5, Lead 5 = 34개)
│   ├── test_filter_chain.py   ← 체인 파이프라인 테스트 (14개)
│   └── test_fft.py            ← FFT 엔진 테스트 (14개)
├── data/
│   └── rawdata.csv            ← 테스트용 샘플 데이터 (98,444행, ~1kHz)
└── .gitignore                 ← __pycache__, .venv, dist/, build/ 제외
```

---

## 1차: 뼈대 — UI 위젯 배치 + 로드 확인 ✅

### 목표
사용자가 Qt Designer로 레이아웃을 자유롭게 조정할 수 있는 기반 마련

### 작업 내용

1. **mainwindow.ui 설계** — 명세서 레이아웃에 맞춰 위젯 배치
   - 좌측: `graphMain`, `graphFFTRaw`, `graphFFTFiltered` — 빈 QWidget 컨테이너
   - 우측: CSV 영역, 필터 영역, 필터 체인 영역, 상태 표시
   - 모든 위젯에 **objectName 규칙** 확정
   - **그래프는 Designer에서 빈 QWidget 컨테이너만 배치하고, 코드에서 PyQtGraph 위젯을 삽입한다**

2. **main_window.py** — QUiLoader로 ui/mainwindow.ui를 직접 로드, objectName으로 위젯 바인딩, PyQtGraph 위젯 3개를 각 컨테이너에 삽입

3. 실행하면 빈 창 + 빈 그래프 3개 + 비활성 버튼들이 보이는 상태

4. **objectName 규약표** — UI와 코드의 계약

| objectName | 위젯 타입 | 용도 |
|---|---|---|
| `btnOpenCSV` | QPushButton | CSV 파일 열기 |
| `comboTimeCol` | QComboBox | Time 열 선택 |
| `comboDataCol` | QComboBox | Data 열 선택 |
| `btnLoadData` | QPushButton | 선택한 열 로드 |
| `comboFilterType` | QComboBox | 필터 종류 선택 |
| `btnAddFilter` | QPushButton | 필터 체인에 추가 |
| `filterChainArea` | QScrollArea | 필터 카드 목록 영역 |
| `filterChainVLayout` | QVBoxLayout | 카드 배치 레이아웃 |
| `btnClearChain` | QPushButton | 필터 체인 전체 초기화 |
| `comboFFTWindow` | QComboBox | FFT window 선택 |
| `labelStatus` | QLabel | 상태 표시 (N건 / fs) |
| `graphMain` | QWidget | 메인 그래프 컨테이너 |
| `graphFFTRaw` | QWidget | FFT Raw 그래프 컨테이너 |
| `graphFFTFiltered` | QWidget | FFT Filtered 그래프 컨테이너 |

---

## 2차: CSV 로드 + 시간축 검증 + 메인 그래프 ✅

### 목표
CSV를 열고 Raw 데이터를 그래프에 표시

### 작업 내용

1. **csv_loader.py** 구현
   - `read_headers(path) → list[str]` : nrows=0으로 열 이름만 읽기
   - `load_columns(path, time_col, data_col) → (time_arr, data_arr, n_total, n_valid)`
   - `validate_time_axis(time_array, n_total, n_valid) → SignalContext`
   - 이중 fs 추정 (전체구간 기반 + 중앙값 기반) → 불일치율로 균일성 판정

2. **main_window.py에 CSV 흐름 연결**
   - btnOpenCSV → QFileDialog → 헤더 읽기 → comboTimeCol/comboDataCol 채우기
   - btnLoadData → 선택 열 로드 → 시간축 검증 → 불균일 시 경고 다이얼로그

---

## 3차: 필터 프레임워크 + 기본 필터 3종 ✅

### 목표
필터 플러그인 구조 확립 + Moving Average, Median, FIR 구현

### 설계 결정
- **BaseFilter** — `name`, `params_spec`, `apply(data, ctx, **params)`, `validate_params(ctx, **params)`, `default_params(ctx)`
- **ParamSpec** — frozen dataclass: name, label, type, default, min, max, step, unit, constraint, choices, visible_if
- **FILTER_REGISTRY** — `dict[str, type[BaseFilter]]`, 새 필터 = 파일 1개 + 1줄 등록
- **SignalContext** — 별도 dataclass (fs, dt, is_uniform, n_total, n_valid)

### 필터별 구현 상세
- **Moving Average**: numpy `np.pad(reflect)` + `np.convolve(valid)`
- **Median**: `scipy.ndimage.median_filter(mode="reflect")`
- **FIR**: `scipy.signal.firwin` + `filtfilt(padtype="odd")`, 짧은 데이터는 numtaps 자동 축소 또는 원본 복사
  - `default_params(ctx)` override: cutoff 기본값이 nyquist 초과 시 clamp
  - `get_params_spec(ctx)` override: fs에 따라 visible_if로 불필요한 cutoff 숨김

### 사용자 추가 필터
- **IIR Lowpass** (`iir_lpf.py`): 1차 RC IIR 로우패스 — `y[n] = y[n-1] + alpha * (x[n] - y[n-1])`, R/C 파라미터
- **Lead Compensator** (`lead_compensator.py`): 위상 진상 보상기 — R/C/gain 파라미터

---

## 4차: 필터 UI 연결 — 자동 폼 생성 + 필터 체인 카드 ✅

### 설계 결정
- **"추가 후 카드에서 수정" 방식** — 사전 파라미터 폼 없음 (DAW 플러그인 체인 패턴)
- **PlotDataItem.setData()** — clear()+plot() 대신 라인 객체 갱신
- **새 CSV 로드 시 체인 초기화** — 이전 필터 설정이 새 데이터에 유효하지 않을 수 있음
- **전체 카드 재구성** — move/remove 시 인덱스 동기화 문제 회피
- **QSpinBox=editingFinished, QComboBox=currentTextChanged** — 입력 중 과도한 갱신 방지
- **FIR default_params(ctx)** — cutoff 기본값이 nyquist 초과 시 clamp
- **odd 제약** — QSpinBox step=2 + 홀수 최소값

### 작업 내용

1. **param_form.py** — ParamSpec → 위젯 자동 생성 (int→QSpinBox, float→QDoubleSpinBox, str+choices→QComboBox), visible_if 동적 전환
2. **chain_card.py** — QGroupBox 카드, 시그널: remove/move/toggle/params_changed/collapsed_changed
3. **main_window.py** — PlotDataItem 패턴, FilterChain 인스턴스, try/except 에러 처리, 활성 필터 0개 시 Filtered 숨김

---

## 5차: FFT 그래프 + FFT Window ✅

### 설계 결정
- **Window별 가중평균 DC 제거** — 비직사각 window에서 `weighted_mean = sum(w*data)/sum(w)`를 빼서 DC bin이 실제로 0에 수렴하도록 보장 (산술평균만 빼면 window 특성에 의해 DC 재유입됨)
- **Coherent gain 보정** — `magnitudes /= mean(window)`로 peak 진폭 일관성 유지
- **"None" → rectangular** — `scipy.signal.get_window` 미사용, coherent gain = 1.0
- **단일 refresh 사이클** — `_update_graphs`에서 filtered_data를 한 번만 계산, time-domain과 FFT가 재사용
- **에러 경로** — 필터 에러 시 Raw FFT 유지, Filtered FFT 비움, 상태 메시지 유지
- **Magnitude floor는 UI 표시 단계에서만 적용** — `compute_fft`는 원본 magnitude를 반환, `_apply_display_floor()`가 그래프 setData 직전에 `max * 1e-6` 클램프
- **Log-y 스케일** — FFT 그래프에 `setLogMode(y=True)` 적용

### 작업 내용

1. **fft_engine.py** — `compute_fft(data, fs, window_name) → (freqs, magnitudes)`
   - Window별 DC 제거: rectangular=산술평균, 나머지=가중평균
   - rfft + one-sided 정규화 + coherent gain 보정
   - floor 미적용 (엔진은 분석 전용)

2. **main_window.py** — `_apply_display_floor()` 분리, FFT PlotDataItem 4개, comboFFTWindow 연결

3. **tests/test_fft.py** — 14개 테스트
   - 기본: peak frequency, 출력 길이, 주파수 범위, window 보존
   - coherent gain 보정 후 peak 진폭 ±10% 일관성
   - DC 제거: None + 모든 window에서 DC < 0.01 검증
   - DC 제거 후 peak 보존 (window별)
   - floor 미적용 검증: 순수 사인파 DC bin < 1e-10

---

## 6차: 마무리 — 엣지 케이스 + UX 개선 + 빌드 + 배포 ✅

### 설계 결정
- **대용량 CSV**: busy cursor (`QApplication.setOverrideCursor`) + 동기 로드 유지 — 로드 빈도 낮음, 100만 행 1~2초 수준. worker thread는 향후 필요 시 추가
- **frozen 경로**: `src/resources.py`에 `resource_path(relative)` 공용 헬퍼 — `sys._MEIPASS` 분기를 한 곳에서 관리
- **카드 접기/펼치기**: QToolButton(▼/▶) + `param_form.setVisible()` 토글
  - 접힘 상태는 `window._collapsed_states: list[bool]`에서 단일 소스로 관리
  - `collapsed_changed` 시그널로 동기화
  - add/remove/move/clear 시 `_collapsed_states`를 체인과 함께 갱신
  - `_rebuild_chain_ui`는 저장된 상태를 읽어 `collapsed` 인자로 카드에 전달
- **빌드**: pyside6-deploy는 uv 환경에서 pip 부재로 사용 불가 → **PyInstaller 채택**
  - `mfclab.spec`: onefile + windowed + `.ui` 파일 번들
  - pyproject.toml dev 의존성에 `pyinstaller>=6.19.0` 추가
- **릴리스 순서**: 모든 검증 통과 → README → LICENSES → git tag (마지막)

### 작업 내용

1. **`src/resources.py`** — `resource_path(relative) → Path`
2. **엣지 케이스 방어 코드**
   | 상황 | 동작 |
   |---|---|
   | 헤더만 있는 CSV (0행) | n_valid < 2 체크 → 경고, 로드 중단 |
   | 전체 NaN 열 | 동일 체크 |
   | CSV 재로드 | 체인 초기화 + _collapsed_states 초기화 + windowTitle 갱신 + 그래프 전체 갱신 |
   | 필터 에러 상태에서 재로드 | 에러 상태 해제 → 정상 갱신 |
   | 대용량 CSV | busy cursor (try/finally 패턴) |

3. **필터 카드 접기/펼치기** — collapsed 상태 보존 (move/remove 시 유실 방지)
4. **Window 타이틀 동적 갱신** — `"MFClab — {filename}"`
5. **PyInstaller 빌드** — `mfclab.spec`, 산출물 `dist/MFClab.exe` (~103 MB)
6. **LICENSES.md** — PySide6(LGPL), NumPy/SciPy/pandas(BSD), PyQtGraph(MIT), PyInstaller(GPL+커스텀 부트로더)
7. **README.md** — 설치/실행/빌드/구조 안내

### 버그 수정 이력
- **필터 이동 시 접힘 상태 유실**: `_rebuild_chain_ui`가 전체 재구성하면서 `_collapsed = False`로 초기화됨 → `window._collapsed_states` 단일 소스 + `collapsed_changed` 시그널로 해결
- **Window별 DC 재유입**: 산술평균 제거 후 비직사각 window를 곱하면 DC bin이 다시 커짐 → window 가중평균으로 수정
- **Floor가 분석값 오염**: `compute_fft` 내부 floor가 DC bin의 실제값을 덮어씀 → floor를 UI 표시 단계(`_apply_display_floor`)로 분리

---

## 현재 상태 요약

| 항목 | 값 |
|---|---|
| 테스트 | **62 passed** (test_filters 34 + test_filter_chain 14 + test_fft 14) |
| 등록 필터 | 5종 (Moving Average, Median, FIR, IIR Lowpass, Lead Compensator) |
| 빌드 | PyInstaller `mfclab.spec` → `dist/MFClab.exe` (~103 MB) |
| Python | ≥3.13, uv 패키지 매니저 |
| 주요 의존성 | PySide6, PyQtGraph, NumPy, SciPy, pandas |

---

## 향후 과제

### 7차 이후 (기능 확장)

- **FFT 전처리 옵션**: UI 콤보박스로 None / DC remove / Linear detrend 선택
  - 현재는 DC remove만 적용됨
  - 유량 센서 step response 분석 시 초저주파 에너지가 FFT를 지배하는 문제 — linear detrend로 완화 가능
  - 장기적으로 Step-model residual 분석은 별도 "도메인 분석 모드"로 추가 검토
- **필터 추가**: Butterworth IIR, Notch, Savitzky-Golay 등
- **데이터 내보내기**: 필터링된 데이터를 CSV로 저장
- **그래프 이미지 저장**: PyQtGraph `exportToImage` 활용
- **다중 채널**: 동시에 여러 Data 열 선택·비교
- **프리셋 저장/로드**: 필터 체인 설정을 JSON으로 저장·복원
- **FFT 표시**: Linear / dB 전환
- **대용량 CSV**: chunksize 읽기 또는 worker thread

---

## 각 차수 진행 방식

```
1. Claude가 코드 작성
2. 사용자가 실행 → 확인
3. (1차 이후) 사용자가 .ui를 Designer에서 자유롭게 조정
4. objectName만 유지되면 코드는 깨지지 않음
5. 다음 차수 진행
```

> **핵심 규칙**: .ui 파일의 objectName은 코드와의 계약이다.
> 이름만 유지하면 위치·크기·스타일은 사용자가 자유롭게 변경 가능.
