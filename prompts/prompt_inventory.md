# 프롬프트 분류 및 원본 대조 결과

기준 파일: `franchise_checkup/llm_tasks.py`

## 분류

| 복사본 | 원본 위치 | 사용 함수 | 런타임 삽입값 |
| --- | --- | --- | --- |
| `report_analysis.txt` | 76-128행 | `_analysis_prompt` | `user_type`, `audience`, `serialized` |
| `related_party_deals.txt` | 273-291행 | `extract_related_party_deals` | `field_list`, `note_text` |
| `unfavorable_clauses.txt` | 380-396행 | `extract_unfavorable_clauses` | `type_list`, `clause_text` |

## 대조 결과

- 원본의 프롬프트 3개를 모두 확인했다.
- 각 복사본의 정적 지시문, 출력 형식, XML 태그(`<report_text>`, `<note_text>`, `<clause_text>`)는 원본과 일치한다.
- f-string으로 런타임에 삽입되는 값은 복사본에서 `{...}` 플레이스홀더로 표시했다.
- `_fallback_report`는 LLM에 전달하는 프롬프트가 아니므로 복사 대상에서 제외했다.
- 코드 수정은 하지 않았으며, 프롬프트 복사본만 `prompts/` 아래에 생성했다.
