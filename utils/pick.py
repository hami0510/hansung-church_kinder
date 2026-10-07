import html
import streamlit as st
from utils.labels import class_label


def search_pick(df, label: str, key: str, none_option: str | None = None):
    """검색칸 + 선택 목록. 선택된 행의 id를 반환 (선택 없으면 None)."""
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


def _s(v):
    return v if isinstance(v, str) else ""


def search_one(df, label: str, key: str, kind: str = "teacher", optional: bool = False):
    """검색칸만 사용. 검색 결과가 정확히 1명일 때 그 사람의 id를 반환, 아니면 None.
    kind: "teacher"(교사) 또는 "child"(아동) - 카드 모양만 다름
    optional: True면 검색칸이 비어 있어도 괜찮다는 안내 문구를 보여줌 (반환은 None)
    """
    icon = "👩‍🏫" if kind == "teacher" else "🐑"
    c1, c2 = st.columns([3, 2])
    with c1:
        q = st.text_input(f"🔍 {label} 검색", key=f"{key}_q",
                          placeholder="이름 또는 반으로 검색 (예: 이경한, 조이, 1부)")
    kw = q.strip().replace(" ", "")

    rows = []
    for _, r in df.iterrows():
        text = f"{r['name']} {class_label(r)} {_s(r.get('role_title'))}".replace(" ", "")
        if kw and kw in text:
            rows.append(r)

    chosen = None
    with c2:
        if not kw:
            st.caption("선택하지 않아도 됩니다." if optional
                       else "이름을 입력하면 정보가 나타납니다.")
        elif not rows:
            st.warning("검색 결과가 없습니다.")
        elif len(rows) == 1:
            chosen = rows[0]
            role = _s(chosen.get("role_title")) if kind == "teacher" else ""
            st.markdown(
                "<div class='kcard'>"
                f"<div class='ktop'>{icon} {html.escape(str(chosen['name']))}"
                + (f"<span class='ktag'>{html.escape(role)}</span>" if role else "")
                + "</div>"
                f"<div class='ksub'>{html.escape(class_label(chosen))}</div>"
                "</div>",
                unsafe_allow_html=True,
            )
        else:
            st.info(f"{len(rows)}명이 검색되었습니다. 이름을 더 입력해 주세요.")

    if kw and len(rows) > 1:
        names = " · ".join(f"{r['name']}({class_label(r)})" for r in rows[:8])
        st.caption(("후보: " + names) + (" …" if len(rows) > 8 else ""))

    # 호출한 화면에서 '검색어는 있는데 1명이 아님'을 알 수 있도록 상태 보관
    st.session_state[f"{key}_ambiguous"] = bool(kw) and len(rows) != 1
    return None if chosen is None else chosen["id"]
