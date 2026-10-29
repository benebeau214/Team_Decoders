## [모듈] summarize_orders — 2026-10-, 작성자: 
- 사용 도구: GitHub Copilot Chat
- 프롬프트: (원문 전체를 그대로 붙여넣기)
- 생성 코드 위치: 커밋 a1b2c3d (수정 전 원본)
- 코드 리딩에서 발견한 결함:
1) 가변 기본값 인자 orders=[]
2) 음수 amount 검증 누락 (명세 위반)
3) 타입 힌트 임의 제거
- 수정 내역: 커밋 d4e5f6a
- 테스트 결과: pytest 3 passed