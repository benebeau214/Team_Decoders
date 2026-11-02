from collections.abc import Mapping
from decimal import Decimal
import re


_COMPARISON_FIELDS = (
    ("relationship", "관계"),
    ("transaction_type", "거래 유형"),
    ("amount", "금액"),
)


def _normalized(value: str) -> str:
    return " ".join(value.split()).casefold()


def _normalized_amount(value: str):
    compact = re.sub(r"\s+", "", value)
    match = re.fullmatch(r"([+-]?(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.[0-9]+)?)(원|만원|백만원|억원)", compact)
    if match:
        scales = {"원": 1, "만원": 10000, "백만원": 1000000, "억원": 100000000}
        return Decimal(match[1].replace(",", "")) * scales[match[2]]
    return _normalized(value)


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
    for field in ("related_party", "relationship", "transaction_type", "amount"):
        if not _normalized(disc_row.get(field, "")):
            issues.append({"issue": f"정보공개서의 {field} 값이 누락되었습니다.",
                           "evidence": _describe_deal(disc_row)})
    if issues:
        return issues

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

    same_type = [deal for deal in matching_deals
                 if _normalized(deal.get("transaction_type", ""))
                 == _normalized(disc_row["transaction_type"])]
    if same_type:
        matching_deals = same_type
    if len(matching_deals) > 1:
        return [{"issue": "동일 거래처의 비교 대상이 여러 건이므로 개별 거래 또는 합계 기준 확인이 필요합니다.",
                 "evidence": "; ".join(_describe_deal(deal) for deal in matching_deals)}]

    for deal in matching_deals:
        for field, label in _COMPARISON_FIELDS:
            audited_value = deal.get(field, "")
            disclosed_value = disc_row.get(field, "")
            if not _normalized(audited_value):
                issues.append({"issue": f"감사보고서의 {label} 값이 누락되었습니다.",
                               "evidence": _describe_deal(deal)})
                continue
            normalize = _normalized_amount if field == "amount" else _normalized
            if normalize(audited_value) == normalize(disclosed_value):
                continue

            issues.append(
                {
                    "issue": (
                        f"{disclosure_party!r} 거래의 {label} 값이 "
                        "감사보고서 주석과 정보공개서에서 다릅니다."
                    ),
                    "evidence": (
                        f"감사보고서: {field}={audited_value!r}; "
                        f"정보공개서: {field}={disclosed_value!r}; "
                        f"원문 인용: {deal.get('quote', '')!r}"
                    ),
                }
            )

    return issues
