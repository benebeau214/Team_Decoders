## 테스트 결과


(1) data_loader.py (담당자: 김리나)

pytest를 사용하여 data_loader.py의 백엔드 3개 함수의 정상·경계·예외 테스트를 검증했습니다.

- 테스트 실행 명령어: `python -m pytest tests/test_data_loader.py -v`
- 실행 결과: tests/data_loader_pytest_result.txt

(2) payback.py (담당자: 오채윤)

pytest를 사용하여 payback.py의 백엔드 2개 함수(calc_payback_months, simulate_payback)의 정상·경계·예외 테스트와 코드 리딩에서 발견한 결함의 회귀 테스트를 검증했습니다.

- 테스트 실행 명령어: `python -m pytest tests/test_payback.py -v`
- 실행 결과: tests/payback_pytest_result.txt

(3) signals.py

pytest를 사용하여 signals.py의 백엔드 3개 함수(calc_financial_ratios, calc_termination_rate, judge_risk_signals)의 정상·경계·예외 테스트, 계산→판정 연결 테스트, 코드 리딩에서 발견한 결함(NaN이 "정상"으로 판정됨, 숫자가 아닌 값에서 TypeError 발생)의 회귀 테스트를 검증했습니다.

- 테스트 실행 명령어: `python -m pytest tests/test_signals.py -v`
- 실행 결과: tests/signals_pytest_result.txt

(4) llm_tasks.py write_report 관련 (담당자: 이혜원(hyeonwlee))

pytest를 사용하여 llm_tasks.py의 보고서 생성 함수(write_report)와 보조 함수(_json_safe, _analysis_prompt, _fallback_report)의 정상·경계·예외 테스트 및 공통 LLM mock 연동 테스트를 검증했습니다.

- 테스트 실행 명령어: python -m pytest tests/test_llm_tasks.py -v
- 테스트 범위:
    - write_report: 반환 형식, 사용자 유형별 프롬프트 차이, LLM 호출 및 응답 오류 처리, 공통 mock 연동
    - _json_safe: 중첩 자료형 및 DataFrame의 JSON 변환, 빈 DataFrame과 결측값 처리
    - _analysis_prompt: 분석 결과 직렬화, 사용자 유형별 설명 초점, 빈 입력과 결측 입력의 구분
    - _fallback_report: 사용자 유형별 체크리스트, 면책 문구 및 예외 상황 처리
- 실행 결과: tests/llm_tasks_pytest_result.txt
