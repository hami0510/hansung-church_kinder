from datetime import date
import pandas as pd
import streamlit as st
from utils.db import fetch, insert, delete

st.title("📅 일정 관리")
is_admin = st.session_state.get("role") == "admin"

CATEGORIES = ["예배", "행사", "교사회의", "교육", "심방", "기타"]

tab_list, tab_add = st.tabs(["일정 보기", "일정 등록"])

with tab_list:
    ev = fetch("events", "event_date")
    if ev.empty:
        st.info("등록된 일정이 없습니다.")
    else:
        ev["event_date"] = pd.to_datetime(ev["event_date"]).dt.date
        only_future = st.checkbox("지난 일정 숨기기", value=True)
        if only_future:
            ev = ev[ev["event_date"] >= date.today()]
        st.dataframe(
            ev[["event_date", "title", "category", "location", "description"]].rename(columns={
                "event_date": "날짜", "title": "제목", "category": "구분",
                "location": "장소", "description": "내용"}),
            hide_index=True, use_container_width=True,
        )
        if is_admin and not ev.empty:
            st.divider()
            opts = {f"{r['event_date']} · {r['title']}": r["id"] for _, r in ev.iterrows()}
            target = st.selectbox("삭제할 일정", ["선택 안 함"] + list(opts))
            if target != "선택 안 함" and st.button("선택한 일정 삭제"):
                delete("events", opts[target])
                st.success("삭제되었습니다. 새로고침하면 반영됩니다.")

with tab_add:
    with st.form("add_event", clear_on_submit=True):
        title = st.text_input("제목 *")
        c1, c2 = st.columns(2)
        d = c1.date_input("날짜", value=date.today())
        cat = c2.selectbox("구분", CATEGORIES)
        loc = st.text_input("장소")
        desc = st.text_area("내용")
        if st.form_submit_button("등록"):
            if not title.strip():
                st.error("제목은 필수입니다.")
            else:
                insert("events", {
                    "title": title.strip(), "event_date": d.isoformat(),
                    "category": cat, "location": loc or None, "description": desc or None,
                    "created_by": "관리자" if is_admin else "교사",
                })
                st.success("일정이 등록되었습니다.")
