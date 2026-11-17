# 파이프라인 입출력 스키마

`franchise_checkup/pipeline.py`의 진입 함수 `run_checkup`이 받는 입력과 돌려주는 결과의 구조를 정리한 문서입니다.
화면(`app.py`)과 통합 테스트(`tests/test_pipeline.py`)는 모두 이 함수를 호출합니다.

## 1. 전체 흐름

```
사용자 입력 + CSV 5종
  → 공통 기준연도 선택 (본사 재무 ∩ 정보공개서)
  → 재무 비율·계약 해지율 계산 → 위험 신호 판정        (signals.py)
  → 자료 최신성 경고
  → 문서 검토: LLM 추출 + 교차 점검                    (llm_tasks.py, signals.py)
  → 투자 회수 기간 시뮬레이션                          (data_loader.py, payback.py)
  → 비전문가용 리포트 작성 (LLM)                       (llm_tasks.py)
  → 결과 dict 반환
```

## 2. 함수 시그니처

```python
def run_checkup(
    user_input: dict[str, Any],
    tables: dict[str, pd.DataFrame],
    call_llm: Callable[[str], str] | None = None,
) -> dict[str, Any]
```

## 3. 입력

### 3-1. `user_input`

`data_loader.validate_user_input`으로 검증을 마친 값을 넣습니다. 키가 하나라도 없으면 `PipelineError`가 발생합니다.

| 키 | 타입 | 설명 |
|---|---|---|
| `brand` | str | 브랜드명 |
| `region` | str | 지역명 (지역 평균 매출 선택에 사용) |
| `deposit` | float | 보증금 (만원) |
| `key_money` | float | 권리금 (만원) |
| `loan_amount` | float | 대출금 (만원) |
| `loan_rate` | float | 대출 금리(%) |
| `user_type` | str | `"예비"` 또는 `"기존"` (리포트 관점) |

### 3-2. `tables`

`load_tables(root)` 또는 `load_tables_from_uploads(uploaded_files)`(7절)의 반환값이며, 형식은 `{CSV 파일명: DataFrame}`입니다. 필수 컬럼이 빠지면 `PipelineError`가 발생합니다.
필수 파일 목록(`CSV_NAMES`)과 필수 컬럼(`REQUIRED_COLUMNS`)은 `data_loader.py`에 정의된 값을 기준으로 합니다.

| 파일 | 필수 컬럼 |
|---|---|
| `hq_financials.csv` | brand, year, total_liabilities, total_equity, capital_stock, revenue, operating_income |
| `franchise_disclosure.csv` | brand, year, startup_cost, avg_annual_sales, stores_begin, contract_terminated, contract_ended, related_party, relationship, transaction_type, amount |
| `region_sales.csv` | brand, year, region, avg_annual_sales |
| `audit_notes.csv` | brand, year, note_text |
| `disclosure_clauses.csv` | brand, year, clause_text |

### 3-3. `call_llm`

`prompt(str) → response(str)` 형태의 함수입니다. 생략하면 `llm_client.llm_call`을 씁니다.
환경변수 `USE_MOCK`이 `true`(기본값)이면 실제 API를 부르지 않고, `[MOCK]` 표시가 붙은 고정 응답을 돌려줍니다.

## 4. 출력 (반환 dict)

| 키 | 타입 | 설명 |
|---|---|---|
| `user_input` | dict | 입력값 사본 |
| `year` | int | 선택된 공통 기준연도 |
| `year_summary` | dict | `financial_latest`, `disclosure_latest`, `selected` (각각 int 또는 None) |
| `fin_row` | dict | 기준연도의 본사 재무 행 |
| `disc_row` | dict | 기준연도의 정보공개서 행 |
| `ratios` | dict | `debt_ratio`, `op_margin` (float 또는 None), `capital_status` (`"정상"`, `"부분잠식"`, `"완전잠식"`, `"NA"`) |
| `termination_rate` | float \| None | 계약 해지율(%) |
| `signals` | list[dict] | 위험 신호. 각 항목은 `item`, `value`, `level`, `reason` |
| `freshness` | list[str] | 자료 최신성 경고 문장 |
| `review_flags` | list[dict] | 사용자가 확인해야 할 항목. 각 항목은 `issue`, `evidence` (불리한 조항에는 `quote`도 있음) |
| `audit_text` | str \| None | 감사보고서 주석 원문 |
| `clause_text` | str \| None | 계약 조항 원문 |
| `avg_sales_info` | dict \| None | `value`(평균 매출), `basis`(지역명 또는 `"전국"`) |
| `payback_df` | DataFrame \| None | 컬럼: `scenario`, `monthly_net_profit`, `payback_months`, `uncertain` |
| `report` | dict \| None | `summary`(str), `checklist`(list[str]) |
| `warnings` | list[str] | 자료 누락·중복 등 진행 중 수집된 경고 |

## 5. 예외와 부분 실패

### 분석을 중단하는 경우 (`PipelineError` 발생)

다음 경우에는 `PipelineError`가 발생합니다. `error.warnings`에는 중단 전까지 모은 경고가 담깁니다.

- 분석 모듈 import 실패
- `user_input`이 dict가 아니거나 키가 누락된 경우
- 테이블 또는 필수 컬럼이 없는 경우
- 선택한 브랜드의 본사 재무 또는 정보공개서 자료가 없는 경우
- 두 자료의 공통 기준연도가 없는 경우
- 기준연도 행이 없거나 여러 개인 경우

### 중단하지 않고 계속 진행하는 경우

| 실패 단계 | 처리 |
|---|---|
| 감사보고서·계약 조항 자료 없음 | `review_flags`에 "자료 누락" 항목 추가 |
| LLM 추출 실패 또는 교차 점검 실패 | `review_flags`에 "확인 필요" 또는 "실패" 항목 추가 |
| 투자 회수 기간 계산 실패 | `payback_df = None`, `review_flags`에 항목 추가 |
| 리포트 생성 실패 | `report = None` |

## 6. 명령줄 실행

```powershell
python -m franchise_checkup.pipeline --brand <브랜드> --region <지역> --user-type 예비
```

인자를 생략하면 공통 브랜드와 지역 중 첫 번째 값을 씁니다.

## 7. CSV 업로드 입력 (11주차, Streamlit 화면용)

화면(`app.py`)은 사용자가 올린 CSV를 `data_loader.load_tables_from_uploads`로 읽어 `tables`를 만든 뒤 `run_checkup`에 넘깁니다.

```python
from franchise_checkup.data_loader import DataLoadError, load_tables_from_uploads

tables = load_tables_from_uploads(uploaded_files)  # → run_checkup(user_input, tables)
```

### 7-1. 입력과 반환

| 항목 | 내용 |
|---|---|
| 입력 | `uploaded_files`: Streamlit `UploadedFile` 목록 (`st.file_uploader(..., accept_multiple_files=True)`의 반환값) |
| 읽는 방식 | 필수 CSV 5종을 UTF-8로 먼저 읽고, 실패하면 `seek(0)`으로 파일 포인터를 처음으로 되돌린 뒤 CP949로 다시 읽음 |
| 반환 | 기존 `load_tables()`와 같은 `dict[str, pandas.DataFrame]` (키는 3-2절의 파일명 5개) |
| 기준 목록 | `data_loader.py`의 `CSV_NAMES`, `REQUIRED_COLUMNS` |

### 7-2. 예외 (`DataLoadError`)

아래 경우는 모두 `DataLoadError`가 발생하며, 오류 메시지에 **파일명과 원인**을 넣습니다. 화면은 이 메시지를 `st.error`로 보여 주고 분석을 멈춥니다.

| 경우 | 메시지 |
|---|---|
| 필수 파일 누락 | `필수 파일이 누락되었습니다: audit_notes.csv, region_sales.csv` (빠진 파일을 한 번에 모두 표시) |
| 같은 파일명 중복 | `hq_financials.csv 파일이 중복 업로드되었습니다.` |
| 빈 파일 | `region_sales.csv 파일이 비어 있습니다.` |
| 디코딩 실패 | `franchise_disclosure.csv 파일을 UTF-8 또는 CP949로 읽을 수 없습니다.` |
| CSV 형식 오류 | `franchise_disclosure.csv CSV 형식이 올바르지 않습니다.` |
| 필수 열 누락 | `hq_financials.csv에 필수 열 'total_liabilities'가 없습니다.` |

메시지는 `data_loader.py`(PR #24) 구현 기준입니다. 파일명 부분은 실제 업로드한 파일 이름으로 바뀝니다.

### 7-3. 검증용 데이터셋

수동 검증 3개 시나리오에 쓰는 데이터셋은 `sample_data/`에 있습니다. 구성과 확인 방법은 `sample_data/README.md`를 참고하세요.
