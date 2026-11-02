---

## [payback] simulate_payback · calc_payback_months — 2026-11-02

- **작성자:** 오채윤
- **사용 도구:** GitHub Copilot Chat
- **프롬프트:**
    
    ```text
    (#file:test_payback.py 를 참고해서 아래 함수 2개를 구현해 주세요.

당신은 파이썬 백엔드 개발을 돕는 어시스턴트입니다.
'프랜차이즈 본사 재무 건강검진' 시스템의 원금 회수 기간 시뮬레이션 모듈(payback.py)에 들어갈 함수를 구현해 주세요. 이 모듈은 LLM·네트워크·파일에 의존하지 않는 순수 계산 계층입니다.
명세에 모호한 점이 있으면 코드를 쓰기 전에 질문 목록부터 알려 주세요. 추측해서 구현하지 마세요.

[함수 시그니처 — 변경 금지]
def calc_payback_months(investment: float, profit: float) -> float:
def simulate_payback(disc_row: dict, user_input: dict, scenarios: dict) -> pd.DataFrame:

[입력 명세]
disc_row: {"startup_cost": 창업비용, "avg_annual_sales": 연 평균매출}
 예) {"startup_cost": 10000, "avg_annual_sales": 24000}
user_input: {"deposit": 보증금, "key_money": 권리금, "loan_amount": 대출금, "loan_rate": 대출 연이율(%, 5.0은 5%)}
 예) {"deposit": 2000, "key_money": 3000, "loan_amount": 12000, "loan_rate": 5.0}
scenarios: {시나리오명: {"sales_factor": 매출 계수, "margin": 순이익률}}
 예) {"보수": {"sales_factor": 0.8, "margin": 0.05}, "평균": {"sales_factor": 1.0, "margin": 0.10}, "낙관": {"sales_factor": 1.2, "margin": 0.15}}
- 모든 금액은 호출자가 같은 단위로 통일해서 넘깁니다. 함수 안에서 단위 변환을 하지 않습니다.

[계산 규칙 — 이 순서와 식 그대로]
1. total_investment = startup_cost + deposit + key_money  (대출금은 투자금에서 빼지 않음)
2. monthly_interest = loan_amount * loan_rate / 100 / 12  (이자만 반영, 대출 원금 상환은 반영하지 않음)
3. monthly_sales = avg_annual_sales / 12
4. scenarios의 각 항목을 입력 순서대로 반복
   monthly_net_profit = monthly_sales * sales_factor * margin - monthly_interest
   payback_months = calc_payback_months(total_investment, monthly_net_profit)
   uncertain = (payback_months가 NaN) 또는 (payback_months > 60)
   - 정확히 60.0은 False. 판정은 반올림하기 전의 값으로 한다 (60.04는 표시가 60.0이어도 True).
5. calc_payback_months(investment, profit): profit <= 0이면 float("nan"), 아니면 investment / profit. 이 함수 안에서는 반올림하지 않는다.

[출력 명세]
simulate_payback은 열이 [scenario, monthly_net_profit, payback_months, uncertain] 순서인 DataFrame을 반환한다.
- 행 순서는 scenarios의 입력 순서
- monthly_net_profit, payback_months는 소수 첫째 자리까지 반올림하고 NaN은 그대로 둔다
- 월 순이익이 0 이하이면 payback_months는 NaN (회수 불가), uncertain은 True
- uncertain은 bool
- 입력 dict(disc_row, user_input, scenarios)는 수정하지 않는다

[예외·경계 방침 — 아래 순서로 검사하고, 예외 타입은 ValueError, 메시지는 문자열 그대로]
1. disc_row에 avg_annual_sales 키가 없거나 None이거나 0 이하 → "평균매출 없음"
2. disc_row에 startup_cost 키가 없거나 None이거나 0 미만 → "창업비용 없음"  (0은 허용)
3. user_input의 deposit, key_money, loan_amount, loan_rate 중 0 미만이 있음 → "음수 입력"
4. scenarios가 비어 있음 → "시나리오 없음"
- 월 순이익이 0 이하인 경우는 예외가 아니라 정상 흐름이다. ZeroDivisionError가 나면 안 된다.

[제약 조건]
- pandas와 표준 라이브러리(math)만 사용 (그 외 import 금지)
- 타입 힌트와 docstring(Args / Returns / Raises) 필수, 가변 기본값 인자 사용 금지
- 시그니처 변경·인자 추가 금지
- print, 로깅, 파일 입출력, 전역 변수 사용 금지
- 광범위한 except:, eval() 금지
- 매직 넘버 60은 모듈 상단 상수(UNCERTAIN_MONTHS = 60)로 선언해서 사용
- 명세에 없는 기능(시나리오 추가, 단위 변환, 로그 출력 등)을 추가하지 말 것
- test_payback.py는 수정하지 말 것

[통과해야 할 테스트 — test_payback.py의 전체 테스트]
기준 입력: DISC={"startup_cost":10000,"avg_annual_sales":24000}, USER={"deposit":2000,"key_money":3000,"loan_amount":0,"loan_rate":0}, 시나리오 보수(0.8, 0.05)·평균(1.0, 0.10)·낙관(1.2, 0.15) = (sales_factor, margin)
T01 정상: DISC, USER → 열 순서 [scenario, monthly_net_profit, payback_months, uncertain], 월 순이익 80/200/360, 회수 기간 187.5/75.0/41.7, uncertain True/True/False
T02 정상: USER에 loan_amount=12000, loan_rate=5.0 → 월 순이익 30/150/310, 회수 기간 500.0/100.0/48.4
T03 경계: loan_amount=40000, loan_rate=6.0 → 보수 NaN(음수), 평균 NaN(정확히 0), 낙관 93.8, uncertain 모두 True, ZeroDivisionError 없음
T04 예외: avg_annual_sales=None → ValueError("평균매출 없음")
T05 예외: deposit=-1000 → ValueError("음수 입력")
calc_payback_months: (15000, 200) → 75.0 / (15000, 0) → NaN / (15000, -5) → NaN

[답변 형식]
1. 모호한 점이 있으면 질문 목록만 먼저 답해 주세요.
2. 없으면 payback.py에 들어갈 코드만 주세요 (설명은 코드 뒤에 3줄 이내).)
    ```
    
- **생성 코드 위치:** 커밋 `f1c0f15` (수정 전 원본)
- **코드 리딩에서 발견한 결함 및 개선 사항:**
    1. `user_input`에 필수 키가 없으면 `KeyError`, 값이 `None`이면 `TypeError`가 발생해 호출자가 원인을 알기 어려웠다.
    2. 반올림 부분에 불필요한 NaN 삼항식이 있었다. `round()`가 NaN을 그대로 돌려주므로 중복이다.
    3. docstring의 Raises 설명이 모호해 실제 예외 조건과 맞지 않았다.
- **수정 내역:**
    1. 음수 검사 앞에 `user_input` 값이 없거나 `None`이면 `ValueError("입력 누락")`을 발생시키는 검증을 추가했다.
    2. 불필요한 삼항식을 `round(payback_months, 1)`로 단순화했다.
    3. docstring의 Raises를 실제 예외 조건에 맞게 고쳤다.
    4. 계산식, 검증 순서, 60개월 판정(반올림 전 값 기준)은 유지했다.
- **명세 보완 사항:**
    - 예외 목록에 `"입력 누락"`을 추가했다. `scenarios` 내부 값(`sales_factor`, `margin`)의 검증은 호출 측 책임으로 두었다.
- **수정 코드 위치:** 커밋 `5c0ae26`
- **테스트 결과:** `pytest 7 pass`
    - 정상: 대출 없음·있음 시나리오별 월 순이익과 회수 기간 계산
    - 경계: 월 순이익이 0 이하이면 회수 기간 NaN, `uncertain=True`
    - 예외: 평균매출 없음·음수 입력 시 `ValueError`
    - 회귀: `user_input` 키 누락 시 `ValueError("입력 누락")`