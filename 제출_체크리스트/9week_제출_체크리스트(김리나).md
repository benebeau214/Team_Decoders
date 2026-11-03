### 1. 팀원 1인당 최소 1개 함수, 사이클 6단계 완주
data_loader.py의  load_csv_table(), validate_user_input(), select_avg_sales()

### 2. 함수당 테스트 3개 이상(정상·경계·예외), pytest 전체통과
tests/test_data_loader.py로 테스트,
통과 로그는 data_loader_pytest_result.txt에 기록

### 3. prompt_log.md: 프롬프트 원문 + 발견 결함 + 수정 내역 + 커밋 해시
prompt_log.md의 [data_loader] load_csv_table — 2026-11-02, [data_loader] validate_user_input — 2026-11-02, [data_loader] select_avg_sales — 2026-11-02

### 4. 함수당 2 커밋 이상, 의미있는 커밋 메시지
원본 코드 커밋: cac935c025c9a05b44bd584059e2b7aa4ee05767

load_csv_table() 수정 커밋: 15a37da90e3019105552326a475bd4e6d7a14b55

validate_user_input() 수정 커밋: a30ac418e88105cd61c7a846905fe19a9033019f

select_avg_sales() 수정 커밋: 9ddf190854c84fe925d57614f9ef7a6d60505448

### 5. .gitignore(.env, .venv/, __pycache__/) 및 보안 체크리스트 포함
.gitignore 포함, 보안 체크리스트는 보안_체크리스트/9week_보안_체크리스트

### 6. LLM 의존기능의 Mock 격리 및 [MOCK] 표시(해당시)

확인함

### 7. 저장소에 PII·실데이터·API 키가 없음을 전원 교차 확인

확인함