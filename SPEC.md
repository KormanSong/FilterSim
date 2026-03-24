# 유량 센서 Raw Data 분석 프로그램 - 개발 명세서

## 개요

느린 유량 센서의 raw data를 대상으로, 지연과 노이즈 사이의 균형을 보며 필터 조합을 실험하고
시간영역과 주파수영역에서 결과를 비교하는 Windows 데스크톱 분석 도구다.

현재 사용자에게 노출된 핵심 워크플로는 다음과 같다.

1. CSV를 연다.
2. Time/Data 열을 고른다.
3. 시간축을 검증한다.
4. 필터 체인을 구성한다.
5. Time domain, FFT, 메트릭으로 결과를 비교한다.

## 기술 스택

- Python 3.13+
- PySide6
- PyQtGraph
- pandas
- numpy
- scipy

## 설계 원칙

- **Causal-first**: 현재 앱에 포함된 실시간용 필터는 미래 샘플을 보지 않는 방향을 우선한다.
- **펌웨어 일치성 존중**: MCU로 옮기기 쉬운 수식과 상태 모델을 선호한다.
- **플러그인 구조 유지**: 신규 필터는 `BaseFilter` 상속 + 레지스트리 등록으로 확장한다.
- **시간축 신뢰성 우선**: 잘못된 시간축으로 잘못된 `fs`를 만들어 분석 전체를 왜곡하지 않도록, 시간축 검증을 신중하게 적용한다.

## 기능 요구사항

### 1. CSV 열기

- CSV 로드 UI는 별도 다이얼로그에서 처리한다.
- 첫 단계에서는 헤더만 읽어 Time/Data 열 후보를 보여준다.
- 실제 데이터 로드 시에는 선택된 두 열만 읽는다.
- 숫자로 변환되지 않는 값은 `NaN`으로 처리한 뒤 pairwise drop 한다.

### 2. 시간축 검증

- Time 열은 **monotonically non-decreasing**이어야 한다.
- duplicate timestamp(`dt == 0`)는 logging artifact로 보고 허용한다.
- 역순 timestamp(`dt < 0`)는 허용하지 않는다.
- duplicate timestamp가 있으면 로드 시 경고를 띄우고, 상태 표시에도 duplicate 개수를 남긴다.
- 양의 dt들의 상대 표준편차가 충분히 작으면, 모든 샘플이 균일한 Hz라고 가정하고 대표 dt(중앙값)에서 운영용 `fs`를 정한다.
- 간격 분산이 크면 불균일 시간축으로 간주하고 경고를 띄운다.
- 불균일 시간축은 경고 후 사용자가 계속 진행할지 결정하게 한다.

### 3. 필터 체인

- 필터는 순서대로 직렬 적용한다.
- 각 필터는 on/off, 삭제, 순서 변경이 가능해야 한다.
- 같은 종류의 필터를 다른 파라미터로 중복 적용할 수 있어야 한다.

### 4. 필터 프레임워크

- 모든 필터는 `BaseFilter`를 상속한다.
- `apply(data, ctx, **params)` 형식으로 동작한다.
- 파라미터 정의는 `ParamSpec`으로 통일한다.
- 필터별로 `estimated_delay_samples()`를 제공할 수 있다.
- UI 폼은 `ParamSpec`을 바탕으로 자동 생성한다.

### 5. 현재 필터 구현

#### 이동평균 (MA)

- 과거와 현재 샘플만 사용하는 causal moving average
- 시작 구간은 실제 누적 개수로 나누어 warm-up 한다

#### Median

- `scipy.ndimage.median_filter`를 사용한다
- `origin=kernel_size // 2`와 `mode="nearest"`를 이용해 causal median 형태로 동작한다

#### FIR

- `scipy.signal.firwin`으로 계수를 설계한다
- 적용은 `scipy.signal.lfilter` 기반의 single-pass causal FIR로 수행한다
- `filtfilt`는 사용하지 않는다
- 데이터가 너무 짧으면 필터를 무리하게 적용하지 않고 원본 복사 또는 안전한 tap 축소를 사용한다

#### IIR LPF

- 1차 RC low-pass
- 식: `y[n] = y[n-1] + alpha * (x[n] - y[n-1])`

#### IIR LPF (2차)

- 동일한 1차 EMA 두 단을 직렬로 연결한 critically damped low-pass

#### Bessel LPF (2nd)

- 2차 Bessel low-pass biquad
- 리드 보상 후 overshoot를 최소화하는 후단 smoothing 용도로 사용한다

#### 미분 필터

- 리드 보상기 기반 필터
- 원신호와 차분 상태를 이용해 빠른 응답을 보강한다

### 6. 그래프

- 메인 그래프: Raw / Filtered time-domain overlay
- FFT Raw: 원본 데이터의 one-sided magnitude spectrum
- FFT Filtered: 필터 결과의 one-sided magnitude spectrum
- 지원 window: None, Hann, Hamming, Blackman
- FFT 엔진은 window별 DC 제거와 coherent gain 보정을 수행한다

### 7. 메트릭

- Settled noise std
- High-frequency RMS
- 예상 delay

HF RMS는 시간영역 1차 IIR high-pass equivalent 잔차 기반으로 계산한다.
cutoff가 Nyquist 이상이면 통과 가능한 고주파 대역이 없다고 보고 `0.0`으로 처리한다.

### 8. 상태 표시

- 총 row 수
- 유효 row 수
- 운영용 `fs`
- 체인 delay 추정치
- 필터 오류 시 에러 메시지

## UI 요구사항

- 그래프는 `.ui`에서 빈 컨테이너를 두고 코드에서 PyQtGraph를 삽입한다.
- CSV 로드는 메뉴 액션 `actionOpenCSV`에서 시작한다.
- 필터 추가/삭제/순서 변경/토글이 한 화면에서 가능해야 한다.
- 메트릭 영역은 HF cutoff와 분석 구간 표시 토글을 제공해야 한다.

## 테스트 요구사항

- 필터 개별 테스트
- 필터 체인 테스트
- FFT 엔진 테스트
- 메트릭 엔진 테스트
- CSV 로더와 시간축 검증 회귀 테스트

## 배포

- PyInstaller 기반 단일 실행 파일 빌드를 기준 경로로 사용한다.
- UI `.ui` 파일은 빌드 산출물에 포함되어야 한다.

## 향후 확장

- 도메인 분석 모드(raw-model-residual)
- CSV export
- 필터 체인 preset 저장/불러오기
- 그래프 이미지 export
- 대용량 CSV 비동기 로드
- 다중 채널 비교
