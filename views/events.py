from datetime import date
import pandas as pd
import streamlit as st
from utils.db import fetch, insert, delete

st.title("📅 일정 관리")
is_admin = st.session_state.get("role") == "admin"

CATEGORIES = ["예배", "행사", "교사회의", "교육", "심방", "기타"]

# 작업 완료 메시지 (rerun 후에도 보이도록 보관)
if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

tab_names = ["일정 보기", "일정 등록"] + (["일정 삭제"] if is_admin else [])
tabs = st.tabs(tab_names)
tab_list, tab_add = tabs[0], tabs[1]

with tab_list:
    ev = fetch("events", "event_date")
    if ev.empty:
        st.info("등록된 일정이 없습니다.")
    else:
        ev["event_date"] = pd.to_datetime(ev["event_date"]).dt.date
        only_future = st.checkbox("지난 일정 숨기기", value=True)
        if only_future:
            ev = ev[ev["event_date"] >= date.today()]
        if ev.empty:
            st.info("표시할 일정이 없습니다.")
        else:
            st.dataframe(
                ev[["event_date", "title", "category", "location", "description"]].rename(columns={
                    "event_date": "날짜", "title": "제목", "category": "구분",
                    "location": "장소", "description": "내용"}),
                hide_index=True, use_container_width=True,
            )

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
                st.session_state["flash"] = "일정이 등록되었습니다."
                st.rerun()

if is_admin:
    with tabs[2]:
        st.subheader("일정 삭제")
        ev_all = fetch("events", "event_date")
        if ev_all.empty:
            st.info("삭제할 일정이 없습니다.")
        else:
            ev_all["event_date"] = pd.to_datetime(ev_all["event_date"]).dt.date
            ev_all = ev_all.sort_values("event_date", ascending=False)
            opts = {
                f"{r['event_date']} · {r['title']} ({r.get('category') or '구분 없음'})": r["id"]
                for _, r in ev_all.iterrows()
            }
            picked = st.multiselect("삭제할 일정 선택 (여러 개 가능)", list(opts))
            if picked:
                st.warning(f"선택한 {len(picked)}개 일정이 삭제됩니다. 되돌릴 수 없습니다.")
                confirm = st.checkbox("삭제하는 것에 동의합니다", key="ev_del_confirm")
                if st.button("선택한 일정 삭제", type="primary", disabled=not confirm):
                    for label in picked:
                        delete("events", opts[label])
                    st.session_state["flash"] = f"{len(picked)}개 일정을 삭제했습니다."
                    st.rerun()
