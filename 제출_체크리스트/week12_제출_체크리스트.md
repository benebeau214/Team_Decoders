# Team Decoders 12주차 제출 체크리스트

| 번호 | 제출 항목 | 확인 | GitHub 근거 |
| --- | --- | --- | --- |
| 1 | 배포 URL 접속 및 정상 시나리오 완주 가능 | [x] | [배포 앱](https://teamdecoders-jejavchdn3bbqbfmeazh7y.streamlit.app/)에서 정상 CSV 업로드와 분석 화면 동작 확인 |
| 2 | 오입력 시 `st.error`/`st.warning` 안내 2곳 이상 동작 | [x] | [franchise_checkup/app.py](../franchise_checkup/app.py)의 필수 파일 누락, 중복 업로드, 필수 열 누락, 입력 조건 오류 및 mock/분석 경고 안내 |
| 3 | `FEEDBACK_LOG.md`: 반영 7건 이상, 전후 비교 및 해시 포함 | [x] | [docs/FEEDBACK_LOG.md](../docs/FEEDBACK_LOG.md)에 반영 피드백 7건과 미반영 피드백 9건, 수정 전후 화면 및 커밋 해시 기록 |
| 4 | 미반영 피드백의 분류·사유 기록 | [x] | [docs/FEEDBACK_LOG.md](../docs/FEEDBACK_LOG.md)의 `반영하지 않은 피드백` 표에 피드백 ID, 분류, 미반영 사유 기록 |
| 5 | `session_state` 키 정리 표 포함 | [x] | [docs/session_state.md](../docs/session_state.md)에 앱 키, 자료형, 초기화·읽기·쓰기 위치와 상태 정리 표 기록 |
| 6 | 데이터 흐름 구조 1장(mock 위치 점검 포함) | [x] | [docs/session_state_flow.png](../docs/session_state_flow.png), [docs/session_state.md](../docs/session_state.md)에 세션 상태 흐름과 mock 응답 위치 점검 자료 포함 |
| 7 | `requirements.txt` 최적화 및 `.env`/Secrets 미커밋 확인 | [x] | [requirements.txt](../requirements.txt)에 직접 실행 의존성 5개로 정리; `.env`와 비밀 키 파일은 추적 목록에 없고 [.gitignore](../.gitignore)에 `.env` 등록 |
| 8 | AI 사용 시 프롬프트·수정·검증 기록 포함 | [x] | [prompts/prompt_inventory.md](../prompts/prompt_inventory.md), [prompts/](../prompts/) 및 팀원별 [ai_log/](../ai_log/)에 프롬프트와 수정·검증 과정 기록 |
| 9 | GitHub 저장소 링크와 배포 URL 제출 | [x] | GitHub 저장소: https://github.com/benebeau214/Team_Decoders<br>배포 URL: https://teamdecoders-jejavchdn3bbqbfmeazh7y.streamlit.app/ |

