import pandas as pd
import streamlit as st
from utils.auth import can_manage
from utils.db import fetch, insert, update, delete
from utils.notice_ui import notice_cards

st.title("📢 공지사항")

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

manage = can_manage()
tabs = st.tabs(["공지 보기"] + (["작성", "수정/삭제"] if manage else []))


def load():
    df = fetch("notices", "created_at", desc=True)
    if df.empty:
        return df
    df["_pin"] = df["pinned"].apply(lambda v: str(v).lower() == "true")
    return df.sort_values(["_pin", "created_at"], ascending=[False, False])


with tabs[0]:
    df = load()
    if df.empty:
        st.info("등록된 공지가 없습니다.")
    else:
        notice_cards(df)

if manage:
    with tabs[1]:
        with st.form("add_notice", clear_on_submit=True):
            title = st.text_input("제목 *")
            content = st.text_area("내용", height=160)
            pinned = st.checkbox("📌 상단 고정")
            if st.form_submit_button("공지 올리기", use_container_width=True):
                if not title.strip():
                    st.error("제목은 필수입니다.")
                else:
                    insert("notices", {"title": title.strip(), "content": content or None,
                                       "pinned": pinned})
                    st.session_state["flash"] = "공지를 올렸습니다."
                    st.rerun()

    with tabs[2]:
        df = load()
        if df.empty:
            st.info("수정할 공지가 없습니다.")
        else:
            opts = {}
            for _, r in df.iterrows():
                d = pd.to_datetime(r["created_at"], utc=True).tz_convert("Asia/Seoul")
                opts[f"{'📌 ' if r['_pin'] else ''}{d:%m/%d} · {r['title']}"] = r["id"]
            pick = st.selectbox("공지 선택", list(opts))
            row = df[df["id"] == opts[pick]].iloc[0]
            with st.form("edit_notice"):
                e_title = st.text_input("제목 *", value=row["title"])
                e_content = st.text_area("내용", value=row["content"]
                                         if isinstance(row.get("content"), str) else "", height=160)
                e_pin = st.checkbox("📌 상단 고정", value=bool(row["_pin"]))
                if st.form_submit_button("저장", use_container_width=True):
                    if not e_title.strip():
                        st.error("제목은 필수입니다.")
                    else:
                        update("notices", row["id"], {"title": e_title.strip(),
                                                      "content": e_content or None,
                                                      "pinned": e_pin})
                        st.session_state["flash"] = "공지를 저장했습니다."
                        st.rerun()
            st.divider()
            ok = st.checkbox("삭제에 동의합니다", key="n_del_ok")
            if st.button("이 공지 삭제", type="primary", disabled=not ok, use_container_width=True):
                delete("notices", row["id"])
                st.session_state["flash"] = "공지를 삭제했습니다."
                st.rerun()
