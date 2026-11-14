# 시연용 가상 데이터셋 안내

본 데이터셋은 프랜차이즈 재무 건강검진 서비스의 기능 검증과 1차 발표 시연을 위해 생성한 가상 데이터입니다. 모든 브랜드명, 재무 수치, 매출, 거래 및 계약 조항은 임의로 생성되었으며 실제 기업이나 실제 공시자료와 무관합니다. 실제 창업·투자·계약 판단에 사용할 수 없습니다.

## CSV 파일 (행 수는 헤더 제외)

| 파일 | 행 | 주요 필드 |
|---|---:|---|
| hq_financials.csv | 9 | brand, year, total_liabilities, total_equity, capital_stock, revenue, operating_income |
| franchise_disclosure.csv | 8 | brand, year, startup_cost, avg_annual_sales, stores_begin, contract_terminated, contract_ended, related_party, relationship, transaction_type, amount |
| region_sales.csv | 22 | brand, year, region, avg_annual_sales |
| audit_notes.csv | 8 | brand, year, note_text |
| disclosure_clauses.csv | 8 | brand, year, clause_text |

금액 단위는 가상 데이터 내부 규약인 만원입니다. 실제 공시의 공식 단위가 아닙니다. startup_cost, avg_annual_sales, deposit, key_money, loan_amount, monthly_net_profit은 모두 만원이고, 비율과 loan_rate는 %입니다.

## 브랜드와 연도 시나리오

- DEMO_치킨왕: 안정 사례. 재무와 공개자료 2022~2024년, 계약 종료율 (3+2)/100=5%. mock 거래 가상유통·종속회사·매출·100만원과 공개 항목이 일치합니다.
- DEMO_도자공방: 주의 사례. 재무 2022~2024년, 공개서와 문서 2022~2023년으로 최신 공통연도는 2023년입니다. 계약 종료율 12%, 영업이익률 악화. 부산광역시 지역 매출을 누락해 전국 평균 fallback을 시연하며, 거래 금액 120만원과 mock 100만원의 불일치를 확인합니다.
- DEMO_버거스튜디오: 위험 사례. 2022~2024년 자료, 2024년 음수 자본으로 기존 함수에서 부채비율이 산출되지 않고 자본완전잠식으로 판정됩니다. 영업손실, 종료율 25%, 공개 거래 필드 누락을 포함합니다.

도자공방의 2024년 공개자료와 관련 문서 누락은 의도한 최신성 경고 시나리오입니다. 지역 매출과 전국 평균은 같은 만원 단위입니다. 지역 자료가 없으면 0이 아니라 전국 평균으로 대체하도록 구성했습니다.

## LLM mock 응답과 인용 검증

거래 mock은 고정 JSON의 quote를 그대로 포함한 주석 텍스트에서 성공합니다. 사용하는 고정 문장:

> 당사는 종속회사인 가상유통에 상품 100만원을 매출하였다.

계약 조항 mock quote도 원문에 존재하도록 넣었습니다:

> 가맹점사업자는 가맹본부가 지정한 업체로부터 필수 품목을 전량 구매하여야 한다.

이는 mock 파싱, JSON 응답, 원문 quote 검증용이며 AI 분석 성능을 뜻하지 않습니다. 존재하지 않는 quote를 반환하면 추출 함수가 해당 항목을 제외합니다.

## 실행과 추천 시연 순서

프로젝트 루트에서 `python -m streamlit run franchise_checkup/app.py`를 실행합니다. CSV는 app.py가 찾는 루트 `data/`에 배치했습니다.

1. DEMO_치킨왕 / 2024 / 부산광역시: 정상 지표, 일치 거래, 조항 quote 및 회수 계산. 입력: deposit=2000, key_money=3000, loan_amount=0, loan_rate=0.
2. DEMO_도자공방 / 2023 / 부산광역시: 최신성 경고, 전국 평균 fallback, 긴 회수기간, 거래 금액 불일치.
3. DEMO_버거스튜디오 / 2024: 위험 지표, 거래 항목 누락, 불리 조항. 음수 순이익/불확실성 시연은 loan_amount=200000, loan_rate=12 (월 이자 2000만원)를 입력합니다.
