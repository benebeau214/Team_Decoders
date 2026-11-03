```markdown


### 1. 팀원 1인당 최소 1개 함수, 사이클 6단계 완주 
payback.py의 calc_payback_months(), simulate_payback()

### 2. 함수당 테스트 3개 이상(정상·경계·예외), pytest 전체통과 
tests/test_payback.py로 테스트 (7개: simulate_payback 정상·경계·예외·입력 키 누락 회귀 4개, calc_payback_months 정상·경계·예외 3개),
통과 로그(7 passed)는 tests/payback_pytest_result.txt에 기록

### 3. prompt_log.md: 프롬프트 원문 + 발견 결함+ 수정 내역+ 커밋 해시 
prompt_log.md의 [payback] simulate_payback · calc_payback_months — 2026-11-02

### 4. 함수당 2 커밋 이상, 의미있는 커밋 메시지 
테스트 먼저 작성 커밋: 15743907690085bea0483589c1a6e3594cb92412 (feat: payback.py의 테스트 파일인 test_payback.py add)
원본 코드 커밋: f1c0f1589e620ed5bea3b68dacc4403749d1aeac (feat: payback.py 코파일럿으로 생성한 수정 전 원본 코드)
simulate_payback() 수정 커밋: 5c0ae2617c8a2aea3287f931c46c8329d33c6539(fix: simulate_payback 함수 코드 리딩 후 수정)
테스트 결과 커밋: 7d65e19825bc13bc8e74cfaecf67d730ea775d75 (test: payback.py pytest 결과)

### 5. .gitignore(.env, .venv/, __pycache__/) 및 보안 체크리스트 포함 
.gitignore 포함, 보안 체크리스트는 보안_체크리스트/week9_보안_체크리스트

### 6. LLM 의존기능의 Mock 격리 및 [MOCK] 표시(해당시) 
해당 없음 (payback.py는 LLM·네트워크·파일에 의존하지 않는 순수 계산 모듈)

### 7. 저장소에 PII·실데이터·API 키가 없음을 전원 교차 확인 
확인함 (payback 테스트 입력은 가상 값)


```

