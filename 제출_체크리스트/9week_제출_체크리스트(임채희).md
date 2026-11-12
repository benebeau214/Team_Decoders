# 4. 제출 체크리스트

### 1. 팀원 1인당 최소 1개 함수, 사이클 6단계 완주

작성 함수: extract_related_party_deals(), extract_unfavorable_clauses(), cross_check_documents()

prompt_log.md에 함수별 사이클 기록

### 2. 함수당 테스트 3개 이상(정상·경계·예외), pytest 전체 통과

tests/test_llm_tasks.py, tests/test_signals.py로 테스트

통과 로그는 tests/llm_tasks_pytest_result.txt, tests/signals_pytest_result.txt에 기록

### 3. prompt_log.md: 프롬프트 원문 + 발견 결함 + 수정 내역 + 커밋 해시

prompt_log.md의 다음 항목에 작성:

- [llm_tasks] extract_related_party_deals — 2026-11-02
- [llm_tasks] extract_unfavorable_clauses — 2026-11-02
- [signals] cross_check_documents — 2026-11-03

### 4. 함수당 2커밋 이상, 의미 있는 커밋 메시지

cross_check_documents() 원본 코드 커밋: de13e59  
cross_check_documents() 수정 커밋: 6a72e73

extract_unfavorable_clauses() 원본 코드 커밋: e11d09f  
extract_unfavorable_clauses() 수정 커밋: f05f64d

extract_related_party_deals() 원본 코드 커밋: b3dc7ad  
extract_related_party_deals() 수정 커밋: e437eea

### 5. .gitignore(.env, .venv/, __pycache__/) 및 보안 체크리스트 포함

.gitignore 포함, 보안 체크리스트 포함 확인

### 6. LLM 의존 기능의 Mock 격리 및 [MOCK] 표시 (해당 시)

llm_client.py에서 Mock 격리 및 [MOCK] 표시 확인

### 7. 저장소에 PII·실데이터·API 키가 없음을 전원 교차 확인

확인함