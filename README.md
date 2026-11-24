## 테스트 결과


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

(3)-2 signals.py  cross_check_documents 관련 (담당자: 임채희(lch419955-git))

pytest를 사용하여 signals.py의 문서 교차 검증 함수(cross_check_documents)의 정상·경계·예외 테스트를 검증했습니다. 두 문서의 거래 정보가 일치하는 경우, 감사보고서 거래가 없는 경우, 거래 목록에 잘못된 자료형이 전달된 경우의 반환 결과와 예외 처리를 확인했으며, 총 3개 테스트가 모두 통과했습니다.

- 테스트 실행 명령어: `python -m pytest tests/test_signals.py -v`
- 실행 결과: tests/signals_pytest_result.txt  

(4)-1 llm_tasks.py write_report 관련 (담당자: 이혜원(hyeonwlee))

pytest를 사용하여 llm_tasks.py의 보고서 생성 함수(write_report)와 보조 함수(_json_safe, _analysis_prompt, _fallback_report)의 정상·경계·예외 테스트 및 공통 LLM mock 연동 테스트를 검증했습니다.

- 테스트 실행 명령어: `python -m pytest tests/test_llm_tasks.py -v`
- 테스트 범위:
    - write_report: 반환 형식, 사용자 유형별 프롬프트 차이, LLM 호출 및 응답 오류 처리, 공통 mock 연동
    - _json_safe: 중첩 자료형 및 DataFrame의 JSON 변환, 빈 DataFrame과 결측값 처리
    - _analysis_prompt: 분석 결과 직렬화, 사용자 유형별 설명 초점, 빈 입력과 결측 입력의 구분
    - _fallback_report: 사용자 유형별 체크리스트, 면책 문구 및 예외 상황 처리
- 실행 결과: tests/llm_tasks_pytest_result.txt

(4)-2  llm_tasks.py extract_unfavorable_clauses, extract_related_party_deals 관련(담당자: 임채희 (lch419955-git))

pytest를 사용하여 llm_tasks.py의 추출 함수 2개(extract_unfavorable_clauses, extract_related_party_deals)의 정상·경계·예외 테스트를 검증했습니다. 불리한 조항의 유형·원문 인용 추출, 특수관계자 거래의 필드 추출, 추출 결과가 없는 경우의 정상 처리, 빈 입력 시 LLM 호출 생략, 잘못된 JSON 응답의 오류 처리, 원문에 없는 조항 인용의 제외 여부를 확인했습니다.

- 테스트 실행 명령어: `python -m pytest tests/test_llm_tasks.py -v`
- 실행 결과: tests/llm_tasks_pytest_result.txt

## 실행 방법

저장소 루트에서 아래 명령을 실행합니다.

```powershell
python -m pip install -r requirements.txt
python -m franchise_checkup.pipeline
python -m streamlit run franchise_checkup/app.py
python -m pytest tests/ -q
```

두 번째 명령은 명령줄에서 파이프라인을 실행하고, 세 번째 명령은 웹 화면을 실행합니다. 입출력 구조는 [스키마 문서](docs/schema.md)를 참고하세요.

## 교차 리뷰 반영 내역

| # | 리뷰어 | 대상 | 판단 | 이유 | 커밋 | 근거 |
|---|---|---|---|---|---|---|
| A | 강민규 | `llm_tasks.py`의 JSON 파싱 로직 3곳 | 수용 | 파싱 로직을 공통화해 수정 시 동작이 어긋날 위험을 줄임 | `eba07d8` | [오채윤 AI 로그](ai_log/오채윤.md) |
| B | 신동훈 | `signals.py`의 `cross_check_documents()`에 `deals_status` 추가 제안 | 보류 | 호출부에서 정상 추출 0건과 추출 실패를 이미 구분함. 일부 성공 시에는 확보한 거래가 있을 때만 호출하며, 이 조건을 docstring에 명시함 | `86d5728` |  [임채희 AI 로그](ai_log/임채희.md) |
| C | 이다현 | `signals.py`의 `value_for` 중복 정의 | 수용 | 두 함수가 공유하는 숫자 검증 규칙을 한곳에서 관리하도록 정리함 | `6b9e13c` | [최영효 AI 로그](ai_log/최영효.md) |


### 10주차 통합 테스트 (담당자 김리나)

- 통합 테스트 파일은 [tests/test_pipeline.py](tests/test_pipeline.py)입니다.
- `python -m pytest tests/ -v`로 전체 테스트 122개가 통과했습니다.
- [최종 테스트 결과](tests/pytest_result_week10.txt)
- [파이프라인 fixture(시연용 data/ CSV) 실행 로그](tests/pipeline_run_week10.txt)

---

## 11주차 
### 설치 및 실행

저장소 루트에서 아래 명령을 실행합니다.

```bash
pip install -r requirements.txt
python -m streamlit run franchise_checkup/app.py
```

강의자료의 `app.py`는 팀 저장소의 `franchise_checkup/app.py`(Streamlit 화면)에, `backend.py`는 `data_loader.py`, `payback.py`, `signals.py` 등 팀의 데이터 처리·분석 모듈에 해당합니다.

### CSV 업로드
CSV 업로드 기능을 검증하기 위한 데이터셋 3종
`cp949_normal,missing_column,utf8_normal`  

앱의 각 업로드 항목에 대응하는 CSV를 넣습니다. 샘플 CSV는 저장소의 `sample_data/` 아래 `cp949_normal,missing_column,utf8_normal` 폴더에서 확인할 수 있습니다.

| CSV 목록 |
| --- |
| `hq_financials.csv` | 
|`franchise_disclosure.csv` |
| `region_sales.csv` |
| `audit_notes.csv` |
| `disclosure_clauses.csv` |

 검증용 데이터셋 관련 자세한 사항은 [README](sample_data/README.md) 참고

### `st.session_state` 사용 이유

Streamlit은 위젯의 값이 변경될 때마다 앱을 다시 실행하므로, 업로드한 데이터와 분석 결과가 불필요하게 초기화되거나 반복 처리되지 않도록 `st.session_state`를 활용했습니다. 업로드 파일의 식별값과 DataFrame을 세션에 저장하여 동일한 파일을 다시 읽는 것을 방지하고, 분석 결과와 마지막 입력 조건을 함께 관리합니다. 새로운 파일이 업로드되면 기존 데이터를 초기화하고, 입력 조건이 변경되거나 재분석 버튼을 누르면 분석 결과를 갱신하도록 구현했습니다.  

### 11주차 수동 검증

[수동 검증 결과 및 실행 화면](docs/manual_test.md)에서 정상 CSV, CP949 인코딩 CSV, 필수 컬럼이 누락된 CSV의 실행 결과와 관찰 내용을 확인할 수 있습니다.

