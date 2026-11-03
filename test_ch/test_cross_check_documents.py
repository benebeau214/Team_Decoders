import pytest

from functions.cross_check_documents import cross_check_documents


def _deal():
    return {
        "related_party": "가상유통",
        "relationship": "종속회사",
        "transaction_type": "매출",
        "amount": "100만원",
    }


def test_normal_matching_deal():
    # 정상: 두 문서의 거래가 같으면 문제 없음
    assert cross_check_documents([_deal()], _deal()) == []


def test_boundary_empty_audit_deals():
    # 경계: 감사보고서 거래가 0건이면 확인 불가 문제 1건 반환
    issues = cross_check_documents([], _deal())
    assert len(issues) == 1
    assert "감사보고서 주석에서 확인되지 않습니다" in issues[0]["issue"]
    assert "가상유통" in issues[0]["evidence"]


def test_exception_invalid_deals_type():
    # 예외: 거래 목록에 잘못된 타입을 전달하면 TypeError 발생
    with pytest.raises(TypeError, match="deals"):
        cross_check_documents(None, _deal())
