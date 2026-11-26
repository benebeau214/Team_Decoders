# Team Decoders - 프랜차이즈 본사 재무 건강검진

공시 자료를 바탕으로 프랜차이즈 본사의 재무 상태와 계약 관련 확인 사항을
비전문가도 이해하기 쉽게 보여 주는 Streamlit 대시보드입니다. 예비 가맹점주가
계약 전에 본사의 재무 위험 신호, 예상 투자금 회수 기간, 문서에서 확인해야 할
사항을 한 번에 검토할 수 있도록 돕습니다.

## 배포 앱

[Streamlit 앱 열기](https://teamdecoders-jejavchdn3bbqbfmeazh7y.streamlit.app/)

## 주요 기능

- **본사 재무 신호 진단**: 부채비율, 영업이익률, 자본잠식 여부, 계약 해지율을
  계산하고 정상·주의·위험·확인 필요 단계로 표시합니다.
- **투자금 회수 기간 시뮬레이션**: 보수·평균·낙관 시나리오별 월 순이익과
  원금 회수 예상 기간을 계산합니다.
- **지역 매출 기준 선택**: 선택한 지역의 가맹점 평균매출을 사용하고, 해당
  지역 데이터가 없으면 전국 평균을 사용합니다.
- **문서 확인 목록**: 감사보고서 주석의 특수관계자 거래와 정보공개서의
  불리한 계약 조항을 추출하고, 두 문서의 내용을 교차 점검합니다.
- **비전문가용 리포트**: 분석 결과와 계약 전에 확인할 항목을 요약해 보여
  줍니다.
- **CSV 검증**: UTF-8·CP949 인코딩을 지원하고, 파일별 필수 컬럼 누락을
  안내합니다.

## 처리 흐름

1. 사용자가 5개의 CSV 파일을 업로드합니다.
2. 파일 인코딩과 필수 컬럼을 검증하고 DataFrame으로 읽습니다.
3. 브랜드·지역·투자 조건을 입력합니다.
4. 재무 신호와 계약 해지율을 계산하고 위험 수준을 판정합니다.
5. 시나리오별 투자금 회수 기간과 문서 확인 목록을 생성합니다.
6. 결과 표, 차트, 원문 인용, 요약 리포트를 화면에 표시합니다.

현재 LLM 호출 계층은 데모용 mock 응답을 사용합니다. 따라서 화면의 LLM 기반
추출·리포트 결과에는 mock 응답임을 나타내는 표시가 포함됩니다.

## 저장소 구조

```text
Team_Decoders/
├── franchise_checkup/
│   ├── app.py              # Streamlit 화면과 사용자 입력·결과 표시
│   ├── data_loader.py      # CSV 적재, 인코딩 및 입력값 검증
│   ├── pipeline.py         # 전체 분석 파이프라인 조정
│   ├── signals.py          # 재무·계약 신호 계산과 위험 판정
│   ├── payback.py          # 투자금 회수 기간 시뮬레이션
│   └── llm_tasks.py        # 문서 추출 및 리포트 생성 작업
├── data/                   # 앱에서 사용하는 기본 CSV 데이터
├── sample_data/             # 정상·CP949·필수 컬럼 누락 검증용 데이터
├── prompts/                # LLM 작업별 프롬프트 템플릿
├── tests/                  # 모듈 및 통합 테스트
├── docs/                   # 스키마와 수동 검증 문서·스크린샷
├── llm_client.py           # mock/실제 LLM 호출을 분기하는 계층
├── requirements.txt        # Python 의존성
├── design_doc_v1.md        # 문제 정의와 초기 설계 문서
└── flowchart.png           # 처리 흐름도
```

## 입력 데이터

앱은 다음 5개 CSV를 사용합니다.

| 파일 | 내용 |
|---|---|
| `hq_financials.csv` | 브랜드별 본사 재무 정보 |
| `franchise_disclosure.csv` | 브랜드별 정보공개서와 가맹점 현황 |
| `region_sales.csv` | 시도별 가맹점 평균매출 |
| `audit_notes.csv` | 감사보고서 특수관계자 거래 주석 발췌 |
| `disclosure_clauses.csv` | 정보공개서 계약 조항 발췌 |

저장소의 `data/`에는 기본 실행용 데이터가 있고, `sample_data/`에는 다음 검증
시나리오가 있습니다.

- `utf8_normal/`: 정상적인 UTF-8 CSV
- `cp949_normal/`: CP949 인코딩 CSV
- `missing_column/`: 필수 컬럼이 누락된 CSV

자세한 컬럼 정의는 [docs/schema.md](docs/schema.md)를 참고하세요.

## 설치 및 실행

Python 환경에서 저장소 루트로 이동한 뒤 실행합니다.

```powershell
python -m pip install -r requirements.txt
python -m streamlit run franchise_checkup/app.py
```

앱을 실행하면 브라우저에서 표시되는 업로드 영역에 5개의 CSV 파일을 넣고
브랜드와 분석 조건을 선택합니다. 명령줄 파이프라인은 다음과 같이 실행할 수
있습니다.

```powershell
python -m franchise_checkup.pipeline
```

## 테스트

전체 테스트 실행:

```powershell
python -m pytest tests/ -q
```

주요 모듈만 선택해서 실행:

```powershell
python -m pytest tests/test_data_loader.py tests/test_payback.py tests/test_signals.py -v
```

수동 검증 절차와 실제 화면 결과는
[docs/manual_test.md](docs/manual_test.md)에서 확인할 수 있습니다.

## 문서

- [설계 문서](design_doc_v1.md): 문제 정의, 기능 범위, 모듈 설계
- [데이터 스키마](docs/schema.md): CSV 컬럼과 입출력 구조
- [수동 테스트 기록](docs/manual_test.md): 업로드·오류·화면 검증 결과
- [프롬프트 목록](prompts/prompt_inventory.md): LLM 작업별 프롬프트 설명

## 현재 범위와 제한

- 데이터는 자동으로 DART·공정위에서 수집하지 않고 준비된 CSV를 사용합니다.
- PDF·이미지 업로드와 OCR은 지원하지 않습니다.
- 로그인, 사용자별 결과 저장, 개별 점포 입지 분석은 포함하지 않습니다.
- 현재 LLM 기능은 실제 외부 API가 아닌 mock 응답 기반입니다.
- 분석 결과는 참고용이며 법률·투자 판단을 대신하지 않습니다.

---

## 기존 주차별 개발 기록

### 테스트 결과

(1) data_loader.py (담당자: 김리나)

pytest를 사용하여 data_loader.py의 백엔드 3개 함수의 정상·경계·예외 테스트를 검증했습니다.

- 테스트 실행 명령어: `python -m pytest tests/test_data_loader.py -v`
- 실행 결과: tests/data_loader_pytest_result.txt

(2) payback.py (담당자: 오채윤)

pytest를 사용하여 payback.py의 백엔드 2개 함수(calc_payback_months, simulate_payback)의 정상·경계·예외 테스트와 코드 리딩에서 발견한 결함의 회귀 테스트를 검증했습니다.

- 테스트 실행 명령어: `python -m pytest tests/test_payback.py -v`
- 실행 결과: tests/payback_pytest_result.txt

(3)-1 signals.py (담당자: 최영효 (yhyhoii))

pytest를 사용하여 signals.py의 백엔드 3개 함수(calc_financial_ratios, calc_termination_rate, judge_risk_signals)의 정상·경계·예외 테스트, 계산→판정 연결 테스트, 코드 리딩에서 발견한 결함(NaN이 "정상"으로 판정됨, 숫자가 아닌 값에서 TypeError 발생)의 회귀 테스트를 검증했습니다.

- 테스트 실행 명령어: `python -m pytest tests/test_signals.py -v`
- 실행 결과: tests/signals_pytest_result.txt

(3)-2 signals.py cross_check_documents 관련 (담당자: 임채희 (lch419955-git))

pytest를 사용하여 signals.py의 문서 교차 검증 함수(cross_check_documents)의 정상·경계·예외 테스트를 검증했습니다. 두 문서의 거래 정보가 일치하는 경우, 감사보고서 거래가 없는 경우, 거래 목록에 잘못된 자료형이 전달된 경우의 반환 결과와 예외 처리를 확인했으며, 총 3개 테스트가 모두 통과했습니다.

- 테스트 실행 명령어: `python -m pytest tests/test_signals.py -v`
- 실행 결과: tests/signals_pytest_result.txt

(4)-1 llm_tasks.py write_report 관련 (담당자: 이혜원 (hyeonwlee))

pytest를 사용하여 llm_tasks.py의 보고서 생성 함수(write_report)와 보조 함수(_json_safe, _analysis_prompt, _fallback_report)의 정상·경계·예외 테스트 및 공통 LLM mock 연동 테스트를 검증했습니다.

- 테스트 실행 명령어: `python -m pytest tests/test_llm_tasks.py -v`
- 테스트 범위:
  - write_report: 반환 형식, 사용자 유형별 프롬프트 차이, LLM 호출 및 응답 오류 처리, 공통 mock 연동
  - _json_safe: 중첩 자료형 및 DataFrame의 JSON 변환, 빈 DataFrame과 결측값 처리
  - _analysis_prompt: 분석 결과 직렬화, 사용자 유형별 설명 초점, 빈 입력과 결측 입력의 구분
  - _fallback_report: 사용자 유형별 체크리스트, 면책 문구 및 예외 상황 처리
- 실행 결과: tests/llm_tasks_pytest_result.txt

(4)-2 llm_tasks.py extract_unfavorable_clauses, extract_related_party_deals 관련 (담당자: 임채희 (lch419955-git))

pytest를 사용하여 llm_tasks.py의 추출 함수 2개(extract_unfavorable_clauses, extract_related_party_deals)의 정상·경계·예외 테스트를 검증했습니다. 불리한 조항의 유형·원문 인용 추출, 특수관계자 거래의 필드 추출, 추출 결과가 없는 경우의 정상 처리, 빈 입력 시 LLM 호출 생략, 잘못된 JSON 응답의 오류 처리, 원문에 없는 조항 인용의 제외 여부를 확인했습니다.

- 테스트 실행 명령어: `python -m pytest tests/test_llm_tasks.py -v`
- 실행 결과: tests/llm_tasks_pytest_result.txt

### 교차 리뷰 반영 내역

| # | 리뷰어 | 대상 | 판단 | 이유 | 커밋 | 근거 |
|---|---|---|---|---|---|---|
| A | 강민규 | `llm_tasks.py`의 JSON 파싱 로직 3곳 | 수용 | 파싱 로직을 공통화해 수정 시 동작이 어긋날 위험을 줄임 | `eba07d8` | [오채윤 AI 로그](ai_log/오채윤.md) |
| B | 신동훈 | `signals.py`의 `cross_check_documents()`에 `deals_status` 추가 제안 | 보류 | 호출부에서 정상 추출 0건과 추출 실패를 이미 구분함. 일부 성공 시에는 확보한 거래가 있을 때만 호출하며, 이 조건을 docstring에 명시함 | `86d5728` | [임채희 AI 로그](ai_log/임채희.md) |
| C | 이다현 | `signals.py`의 `value_for` 중복 정의 | 수용 | 두 함수가 공유하는 숫자 검증 규칙을 한곳에서 관리하도록 정리함 | `6b9e13c` | [최영효 AI 로그](ai_log/최영효.md) |

### 10주차 통합 테스트

- 통합 테스트 파일은 [tests/test_pipeline.py](tests/test_pipeline.py)입니다.
- `python -m pytest tests/ -v`로 전체 테스트 122개가 통과했습니다.
- [최종 테스트 결과](tests/pytest_result_week10.txt)
- [파이프라인 fixture 실행 로그](tests/pipeline_run_week10.txt)

---

## 11주차

### 설치 및 실행

저장소 루트에서 아래 명령을 실행합니다.

```bash
pip install -r requirements.txt
python -m streamlit run franchise_checkup/app.py
```

강의자료의 `app.py`는 팀 저장소의 `franchise_checkup/app.py`(Streamlit 화면)에,
`backend.py`는 `data_loader.py`, `payback.py`, `signals.py` 등 팀의 데이터 처리·분석
모듈에 해당합니다.

### CSV 업로드

CSV 업로드 기능을 검증하기 위한 데이터셋 3종은
`cp949_normal`, `missing_column`, `utf8_normal`입니다.

앱의 각 업로드 항목에 대응하는 CSV를 넣습니다. 샘플 CSV는 저장소의
`sample_data/` 아래 각 데이터셋 폴더에서 확인할 수 있습니다.

| CSV 목록 |
|---|
| `hq_financials.csv` |
| `franchise_disclosure.csv` |
| `region_sales.csv` |
| `audit_notes.csv` |
| `disclosure_clauses.csv` |

검증용 데이터셋 관련 자세한 사항은
[sample_data/README.md](sample_data/README.md)를 참고하세요.

### `st.session_state` 사용 이유

Streamlit은 위젯의 값이 변경될 때마다 앱을 다시 실행하므로, 업로드한 데이터와
분석 결과가 불필요하게 초기화되거나 반복 처리되지 않도록 `st.session_state`를
활용했습니다. 업로드 파일의 식별값과 DataFrame을 세션에 저장하여 동일한 파일을
다시 읽는 것을 방지하고, 분석 결과와 마지막 입력 조건을 함께 관리합니다. 새로운
파일이 업로드되면 기존 데이터를 초기화하고, 입력 조건이 변경되거나 재분석 버튼을
누르면 분석 결과를 갱신하도록 구현했습니다.

### 11주차 수동 검증

[수동 검증 결과 및 실행 화면](docs/manual_test.md)에서 정상 CSV, CP949 인코딩 CSV,
필수 컬럼이 누락된 CSV의 실행 결과와 관찰 내용을 확인할 수 있습니다.
