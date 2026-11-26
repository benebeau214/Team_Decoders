# Team Decoders 11주차 제출 체크리스트

| 번호 | 제출 항목 | 확인 | GitHub 근거 |
| --- | --- | --- | --- |
| 1 | CSV 드래그 앤 드롭 업로드 동작 | CSV 5종 업로드 확인 | `docs/manual_test.md` 시나리오 1 |
| 2 | CP949 인코딩 파일 정상 처리 | 확인 | `franchise_checkup/data_loader.py`, `docs/manual_test.md` 시나리오 2 |
| 3 | 가공 로직이 백엔드 모듈에만 존재 | CSV 파싱과 핵심 분석을 백엔드에 위임하는 구조 확인 | `franchise_checkup/app.py`, `franchise_checkup/data_loader.py`, `franchise_checkup/pipeline.py` |
| 4 | 사이드바 필터 1개 이상 및 즉시 반영 | 대출 금리 변경 시 결과 즉시 갱신 확인 | `franchise_checkup/app.py`, `docs/manual_test.md` 시나리오 4-a |
| 5 | metric 2개 이상, 차트 1개 이상, dataframe 표 | 지표 4개, 회수 기간 막대 차트, 원본 데이터 미리보기 표 확인 | `franchise_checkup/app.py`|
| 6 | `session_state` 사용 및 README 설명 | 확인 | `franchise_checkup/app.py`의 업로드 데이터·분석 결과·마지막 입력 조건 저장, `README.md`의 사용 이유 설명 (`94e385a`) |
| 7 | 수동 검증 3개 시나리오 기록 첨부 | 확인 | `docs/manual_test.md` 시나리오 1~3, `docs/screenshots` |
| 8 | AI 프롬프트·수정·검증 과정 기록 아카이브 | 팀원별 11주차 AI 로그 추가·수정 커밋 확인 | `ai_log/김리나.md`, `ai_log/오채윤.md`, `ai_log/이혜원.md`, `ai_log/임채희.md`, `ai_log/최영효.md` |
| 9 | 보안 체크리스트 첨부 및 `.gitignore` 점검 | 확인 | `보안_체크리스트/week11_보안_체크리스트` (`e9af608`) |
| 10 | 팀원 전원의 커밋이 히스토리에 존재 | 팀원 5명의 커밋 확인 | |

