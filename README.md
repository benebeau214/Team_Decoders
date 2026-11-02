## 테스트 결과

(2) payback.py

pytest를 사용하여 payback.py의 백엔드 2개 함수(calc_payback_months, simulate_payback)의 정상·경계·예외 테스트와 코드 리딩에서 발견한 결함의 회귀 테스트를 검증했습니다.

- 테스트 실행 명령어: `python -m pytest tests/test_payback.py -v`
- 실행 결과: tests/payback_pytest_result.txt