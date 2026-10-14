import pandas as pd
import streamlit as st
from utils.db import fetch, insert, update, delete

st.title("📢 공지사항")

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

# 공지 작성·수정·삭제·고정은 관리자 로그인한 사람만
manage = st.session_state.get("role") == "admin"

st.markdown("""
<style>
.st-key-nlist [data-testid="stVerticalBlock"] {gap: .5rem;}
.st-key-nlist [data-testid="stExpander"] {border-radius: 12px; background: #f6faff;
  border: 1px solid #d5e6f7;}
</style>
""", unsafe_allow_html=True)

if manage:
    tab_list, tab_add = st.tabs(["공지 보기", "작성"])
else:
    tab_list = st.tabs(["공지 보기"])[0]
    tab_add = None
    st.caption("🔒 공지 작성·삭제는 관리자 로그인 후 가능합니다. (왼쪽 메뉴 아래 '관리자 로그인')")


def to_when(v):
    try:
        d = pd.to_datetime(v, utc=True).tz_convert("Asia/Seoul")
        return f"{d:%Y.%m.%d}"
    except Exception:
        return ""


# ---------------------------------------------------------------- 공지 보기
with tab_list:
    df = fetch("notices", "created_at", desc=True)
    if df.empty:
        st.info("등록된 공지가 없습니다.")
    else:
        df["_pin"] = df["pinned"].apply(lambda v: str(v).lower() == "true")
        df = df.sort_values(["_pin", "created_at"], ascending=[False, False])

        kw = st.text_input("🔍 검색", placeholder="제목 또는 내용으로 검색",
                           label_visibility="collapsed").strip().replace(" ", "")
        if kw:
            hay = (df["title"].fillna("") + df["content"].fillna("")).str.replace(" ", "")
            df = df[hay.str.contains(kw, case=False, na=False)]

        if df.empty:
            st.warning("검색 결과가 없습니다.")
        else:
            with st.container(key="nlist"):
                for _, r in df.iterrows():
                    nid = str(r["id"])
                    mark = "📌" if r["_pin"] else "📢"
                    title = f"**{r['title']}**" if r["_pin"] else str(r["title"])
                    content = r["content"] if isinstance(r.get("content"), str) else ""
                    with st.expander(f"{mark} {title}  ·  {to_when(r['created_at'])}"):
                        edit_key = f"editing_{nid}"
                        if not (manage and st.session_state.get(edit_key)):
                            if content:
                                st.markdown(content.replace("\n", "  \n"))
                            else:
                                st.caption("내용이 없습니다.")
                            if manage:
                                c1, c2, c3 = st.columns(3)
                                if c1.button("✏️ 수정", key=f"e_{nid}", use_container_width=True):
                                    st.session_state[edit_key] = True
                                    st.rerun()
                                pin_label = "📌 고정 해제" if r["_pin"] else "📌 상단 고정"
                                if c2.button(pin_label, key=f"p_{nid}", use_container_width=True):
                                    update("notices", r["id"], {"pinned": not r["_pin"]})
                                    st.session_state["flash"] = "고정 상태를 바꿨습니다."
                                    st.rerun()
                                with c3.popover("🗑️ 삭제", use_container_width=True):
                                    ok = st.checkbox("삭제에 동의합니다", key=f"dok_{nid}")
                                    if st.button("삭제하기", key=f"d_{nid}", type="primary",
                                                 disabled=not ok, use_container_width=True):
                                        delete("notices", r["id"])
                                        st.session_state["flash"] = "공지를 삭제했습니다."
                                        st.rerun()
                        else:
                            with st.form(f"form_{nid}"):
                                e_title = st.text_input("제목 *", value=str(r["title"]))
                                e_content = st.text_area("내용", value=content, height=200)
                                e_pin = st.checkbox("📌 상단 고정", value=bool(r["_pin"]))
                                b1, b2 = st.columns(2)
                                saved = b1.form_submit_button("저장", type="primary",
                                                              use_container_width=True)
                                canceled = b2.form_submit_button("취소", use_container_width=True)
                            if saved:
                                if not e_title.strip():
                                    st.error("제목은 필수입니다.")
                                else:
                                    update("notices", r["id"], {
                                        "title": e_title.strip(), "content": e_content or None,
                                        "pinned": e_pin})
                                    st.session_state.pop(edit_key, None)
                                    st.session_state["flash"] = "공지를 저장했습니다."
                                    st.rerun()
                            if canceled:
                                st.session_state.pop(edit_key, None)
                                st.rerun()

# ---------------------------------------------------------------- 작성 (관리자만)
if manage and tab_add is not None:
    with tab_add:
        with st.form("add_notice", clear_on_submit=True):
            title = st.text_input("제목 *")
            content = st.text_area("내용", height=200)
            pinned = st.checkbox("📌 상단 고정")
            submitted = st.form_submit_button("공지 올리기", type="primary",
                                              use_container_width=True)
        if submitted:
            if not title.strip():
                st.error("제목은 필수입니다.")
            else:
                insert("notices", {"title": title.strip(), "content": content or None,
                                   "pinned": pinned})
                st.toast("공지를 올렸습니다.", icon="✅")
