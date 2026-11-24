### 1. 팀원 1인당 최소 1개 함수, 사이클 6단계 완주
signals.py의 judge_risk_signals(), calc_financial_ratios(), calc_termination_rate()

### 2. 함수당 테스트 3개 이상(정상·경계·예외), pytest 전체통과
tests/test_signals.py로 테스트,
통과 로그는 tests/signals_pytest_result.txt에 기록

### 3. prompt_log.md: 프롬프트 원문 + 발견 결함 + 수정 내역 + 커밋 해시
prompt_log.md의 [signals] judge_risk_signals — 2026-10-29 (생성·리딩) / 2026-11-02 (결함 수정), [signals] calc_financial_ratios · calc_termination_rate — 2026-11-03

### 4. 함수당 2 커밋 이상, 의미있는 커밋 메시지
judge_risk_signals()

테스트 커밋: eb2a21eba86bec5091c8828360e9a2592422cc4e

원본 코드 커밋: 81abe11a05aedf5d28ad8ed608dbc46cc4daffe6

회귀 테스트 커밋: 8b7202632d4ba9db1366c733a94bb435ff739239

수정 커밋: d2519b9629a42ef58d797bebcc6afe0d07cd497d

calc_financial_ratios(), calc_termination_rate()

테스트 커밋: 05a7cd167e882e5bc034a380ee43f833a83f3d8d

원본 코드 커밋: dbf396fe3ac1c3fe2f91bb41d83e5500e94a7540

회귀 테스트 커밋: c3625988d9fbd4801ce329a6d09316d46efb466b

수정 커밋: 8ef745acfac12205a2d265f61f6e1e7d01614b29

### 5. .gitignore(.env, .venv/, __pycache__/) 및 보안 체크리스트 포함
.gitignore 포함, 보안 체크리스트는 보안_체크리스트/week9_보안_체크리스트

### 6. LLM 의존기능의 Mock 격리 및 [MOCK] 표시(해당시)

해당 없음 (담당 함수는 LLM을 사용하지 않음)

### 7. 저장소에 PII·실데이터·API 키가 없음을 전원 교차 확인

확인함
