from collections.abc import Mapping


_COMPARISON_FIELDS = (
    ("relationship", "관계"),
    ("transaction_type", "거래 유형"),
    ("amount", "금액"),
)


def _normalized(value: str) -> str:
    return " ".join(value.split()).casefold()


def _describe_deal(deal: Mapping[str, str]) -> str:
    fields = ("related_party", "relationship", "transaction_type", "amount")
    return ", ".join(f"{field}={deal.get(field, '')!r}" for field in fields)


def cross_check_documents(
    deals: list[dict[str, str]],
    disc_row: dict[str, str],
) -> list[dict[str, str]]:
    """감사보고서 거래와 정보공개서 행의 거래처·관계·유형·금액을 비교한다."""
    if not isinstance(deals, list):
        raise TypeError("deals는 거래 항목의 list여야 합니다.")
    if not isinstance(disc_row, dict):
        raise TypeError("disc_row는 정보공개서 행 dict여야 합니다.")
    if any(not isinstance(deal, dict) for deal in deals):
        raise TypeError("deals의 각 항목은 dict여야 합니다.")

    disclosure_party = disc_row.get("related_party", "")
    if not isinstance(disclosure_party, str):
        raise TypeError("disc_row['related_party']는 문자열이어야 합니다.")

    for deal in deals:
        for field in ("related_party", "relationship", "transaction_type", "amount"):
            if field in deal and not isinstance(deal[field], str):
                raise TypeError(f"deals 항목의 {field!r}은 문자열이어야 합니다.")
    for field in ("relationship", "transaction_type", "amount"):
        if field in disc_row and not isinstance(disc_row[field], str):
            raise TypeError(f"disc_row의 {field!r}은 문자열이어야 합니다.")

    issues: list[dict[str, str]] = []
    matching_deals = [
        deal
        for deal in deals
        if _normalized(deal.get("related_party", "")) == _normalized(disclosure_party)
        and _normalized(disclosure_party)
    ]

    if not matching_deals:
        if not deals:
            issue = "정보공개서에 기재된 특수관계자 거래가 감사보고서 주석에서 확인되지 않습니다."
            evidence = f"정보공개서: {_describe_deal(disc_row)}"
        else:
            audited_parties = ", ".join(
                repr(deal.get("related_party", "")) for deal in deals
            )
            issue = "정보공개서의 거래처가 감사보고서 주석의 거래처와 일치하지 않습니다."
            evidence = (
                f"정보공개서: {_describe_deal(disc_row)}; "
                f"감사보고서 거래처: {audited_parties}"
            )
        return [{"issue": issue, "evidence": evidence}]

    for deal in matching_deals:
        for field, label in _COMPARISON_FIELDS:
            audited_value = deal.get(field, "")
            disclosed_value = disc_row.get(field, "")
            if _normalized(audited_value) == _normalized(disclosed_value):
                continue

            issues.append(
                {
                    "issue": (
                        f"{disclosure_party!r} 거래의 {label}이 "
                        "감사보고서 주석과 정보공개서에서 다릅니다."
                    ),
                    "evidence": (
                        f"감사보고서: {field}={audited_value!r}; "
                        f"정보공개서: {field}={disclosed_value!r}; "
                        f"원문 인용: {deal.get('quote', '')!r}"
                    ),
                }
            )

    matched_party = _normalized(disclosure_party)
    for deal in deals:
        audited_party = deal.get("related_party", "")
        if _normalized(audited_party) and _normalized(audited_party) != matched_party:
            issues.append(
                {
                    "issue": (
                        f"감사보고서 주석의 거래처 {audited_party!r}가 "
                        "정보공개서에 기재되어 있지 않습니다."
                    ),
                    "evidence": (
                        f"감사보고서: {_describe_deal(deal)}; "
                        f"정보공개서: {_describe_deal(disc_row)}"
                    ),
                }
            )

    return issues
