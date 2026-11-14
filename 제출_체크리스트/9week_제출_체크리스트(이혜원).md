### 1. 팀원 1인당 최소 1개 함수, 사이클 6단계 완주
llm_tasks.py의 write_report()

### 2. 함수당 테스트 3개 이상(정상·경계·예외), pytest 전체통과
tests/test_llm_tasks.py로 테스트,
통과 로그는 llm_tasks_pytest_result.txt에 기록

### 3. prompt_log.md: 프롬프트 원문 + 발견 결함+ 수정 내역+ 커밋 해시
prompt_log.md의 [llm_report]  — 2026-11-03

### 4. 함수당 2 커밋 이상, 의미있는 커밋 메시지
원본 코드 커밋: 2f2f8bec35fc7d1307fec0abf1a7c651bdc91926
수정 커밋: ae263b1cc2c13c0d0793bef166a5594c13638f8d
(테스트 코드 수정 커밋: 17f5de6e89180e794f648a2303784051bf419e6b)

### 5. .gitignore(.env, .venv/, __pycache__/) 및 보안 체크리스트 포함
.gitignore 포함, 보안 체크리스트는 보안_체크리스트/9week_보안_체크리스트

### 6. LLM 의존기능의 Mock 격리 및 [MOCK] 표시(해당시)
확인함

### 7. 저장소에 PII·실데이터·API 키가 없음을 전원 교차 확인
확인함