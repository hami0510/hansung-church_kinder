import streamlit as st
from utils.labels import class_label


def search_pick(df, label: str, key: str, none_option: str | None = None):
    """검색칸 + 선택 목록. 선택된 행의 id를 반환 (선택 없으면 None).

    df: id, name 열과 (class_name, service_part, class_no) 열이 있는 표
    none_option: 있으면 '해당 없음' 같은 선택지를 맨 앞에 추가
    """
    q = st.text_input(f"🔍 {label} 검색", key=f"{key}_q",
                      placeholder="이름 또는 반으로 검색 (예: 유, 조이, 1부)")
    items = [(f"{r['name']} ({class_label(r)})", r["id"]) for _, r in df.iterrows()]
    kw = q.strip().replace(" ", "")
    if kw:
        items = [(t, i) for t, i in items if kw in t.replace(" ", "")]

    if not items:
        st.warning("검색 결과가 없습니다. 다른 글자로 검색해 보세요.")
        return None

    opts = {t: i for t, i in items}
    names = list(opts)
    if none_option:
        names = [none_option] + names
    pick = st.selectbox(f"{label} 선택 ({len(items)}명)", names, key=f"{key}_sel")
    return None if pick == none_option else opts[pick]
