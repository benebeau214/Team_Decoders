# Streamlit 세션 상태

## 앱에서 사용하는 키

아래 위치는 모두 [`franchise_checkup/app.py`의 `main()`](../franchise_checkup/app.py#L83) 기준입니다. 앱에서 직접 관리하는 키 5개와 `key=`로 이름을 지정한 위젯 키 4개를 포함합니다. 이름을 지정하지 않은 파일 업로더, 숫자 입력, 라디오, 분석 버튼의 값은 앱에서 위젯 반환값으로 사용합니다.

`UploadSignature`는 표에서 `tuple[tuple[str, str], ...]`를 줄여 쓴 이름입니다. 파일명과 내용의 SHA-256 해시를 파일명 순서로 담습니다.

| 키 이름 | 자료형 | 초기화 위치 | 읽는 곳 | 쓰는 곳 |
| --- | --- | --- | --- | --- |
| `tables` | `dict[str, pandas.DataFrame] \| None` | [`main()` 시작부](../franchise_checkup/app.py#L99)에서 키가 없으면 `None` | [업로드 변경 판정](../franchise_checkup/app.py#L168)에서 테이블 캐시 유무 확인, [같은 파일이면 재사용](../franchise_checkup/app.py#L206) | [CSV 적재 성공](../franchise_checkup/app.py#L182) 시 저장. [파일 조합 변경 또는 캐시 누락](../franchise_checkup/app.py#L172) 시 `None`, [업로드가 비면](../franchise_checkup/app.py#L128) 삭제 |
| `upload_signature` | `UploadSignature \| None` | [`main()` 시작부](../franchise_checkup/app.py#L99)에서 키가 없으면 `None` | [업로드 변경 판정](../franchise_checkup/app.py#L165)에서 현재 서명과 비교 | [CSV 적재 성공](../franchise_checkup/app.py#L182) 시 저장. [파일 조합 변경 또는 캐시 누락](../franchise_checkup/app.py#L172) 시 `None`, [업로드가 비면](../franchise_checkup/app.py#L128) 삭제 |
| `upload_error` | `tuple[UploadSignature, str, bool] \| None` | [`main()` 시작부](../franchise_checkup/app.py#L99)에서 키가 없으면 `None` | [실패한 파일 조합 확인](../franchise_checkup/app.py#L152) 시 서명, 오류 메시지, 재시도 가능 여부 조회 | [CSV 적재 실패](../franchise_checkup/app.py#L186) 시 저장. [파일 조합 변경 또는 캐시 누락](../franchise_checkup/app.py#L172) 시 `None`, [업로드가 비거나](../franchise_checkup/app.py#L128) [재시도 버튼을](../franchise_checkup/app.py#L159) [누르면](../franchise_checkup/app.py#L201) 삭제 |
| `checkup_result` | `dict[str, Any] \| None` | [`main()` 시작부](../franchise_checkup/app.py#L99)에서 키가 없으면 `None` | [분석 실행 여부 판정](../franchise_checkup/app.py#L289), [결과 화면 표시](../franchise_checkup/app.py#L324) | [분석 성공](../franchise_checkup/app.py#L300) 시 `run_checkup()` 반환값 저장. [분석 실패](../franchise_checkup/app.py#L305) 또는 [파일 재적재](../franchise_checkup/app.py#L172) 시 `None`, [업로드가 비면](../franchise_checkup/app.py#L128) 삭제 |
| `last_input` | `dict[str, str \| float] \| None` | [`main()` 시작부](../franchise_checkup/app.py#L99)에서 키가 없으면 `None` | [분석 실행 여부 판정](../franchise_checkup/app.py#L289)에서 현재 입력과 비교 | [분석 성공](../franchise_checkup/app.py#L300) 시 현재 입력의 복사본 저장. [분석 실패](../franchise_checkup/app.py#L305) 또는 [파일 재적재](../franchise_checkup/app.py#L172) 시 `None`, [업로드가 비면](../franchise_checkup/app.py#L128) 삭제 |
| `selected_brand` | `str` | [브랜드 선택 상자](../franchise_checkup/app.py#L228) 생성 시 Streamlit이 첫 선택지로 초기화 | 위젯 반환값 `brand`를 [분석 입력](../franchise_checkup/app.py#L271)과 [결과 제목](../franchise_checkup/app.py#L334)에 사용 | Streamlit이 선택 변경을 저장. 앱은 [업로드가 비거나](../franchise_checkup/app.py#L128) [파일을 다시 읽을 때](../franchise_checkup/app.py#L172) 삭제 |
| `selected_region` | `str` | [지역 선택 상자](../franchise_checkup/app.py#L233) 생성 시 Streamlit이 첫 선택지로 초기화 | 위젯 반환값 `region`을 [분석 입력](../franchise_checkup/app.py#L271)에 사용 | Streamlit이 선택 변경을 저장. 앱은 [업로드가 비거나](../franchise_checkup/app.py#L128) [파일을 다시 읽을 때](../franchise_checkup/app.py#L172) 삭제 |
| `preview_table_name` | `str` | [미리보기 선택 상자](../franchise_checkup/app.py#L453) 생성 시 Streamlit이 첫 테이블로 초기화 | 위젯 반환값 `table_name`으로 [표시할 DataFrame](../franchise_checkup/app.py#L458) 조회 | Streamlit이 선택 변경을 저장. 앱은 [업로드가 비거나](../franchise_checkup/app.py#L128) [파일을 다시 읽을 때](../franchise_checkup/app.py#L172) 삭제 |
| `retry_upload` | `bool` | 예상치 못한 적재 오류가 발생했거나 같은 파일에서 해당 오류가 기록된 경우 [재시도 버튼](../franchise_checkup/app.py#L159) 표시 시 기본값 `False` | [이전에 기록된 오류](../franchise_checkup/app.py#L159)와 [이번 실행에서 발생한 오류](../franchise_checkup/app.py#L201) 분기에서 버튼 반환값 확인 | Streamlit이 클릭으로 시작된 실행에서만 `True`를 설정 |
