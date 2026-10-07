from datetime import date
import pandas as pd
import streamlit as st
from utils.db import fetch

st.title("🏠 유치부 홈")

# 다가오는 일정 (전체 공개)
st.subheader("📅 다가오는 일정")
ev = fetch("events", "event_date")
if ev.empty:
    st.info("등록된 일정이 없습니다.")
else:
    ev["event_date"] = pd.to_datetime(ev["event_date"]).dt.date
    upcoming = ev[ev["event_date"] >= date.today()].head(5)
    if upcoming.empty:
        st.info("다가오는 일정이 없습니다.")
    else:
        st.dataframe(
            upcoming[["event_date", "title", "category", "location"]].rename(
                columns={"event_date": "날짜", "title": "제목", "category": "구분", "location": "장소"}
            ),
            hide_index=True, use_container_width=True,
        )

# 이번 달 생일 (관리자만)
if st.session_state.get("role") == "admin":
    st.subheader("🎂 이번 달 생일")
    ch = fetch("children")
    if not ch.empty:
        ch = ch[ch["is_active"] == True].copy()
        ch["birth_date"] = pd.to_datetime(ch["birth_date"], errors="coerce")
        bd = ch[ch["birth_date"].dt.month == date.today().month]
        if bd.empty:
            st.write("이번 달 생일인 아이가 없습니다.")
        else:
            bd = bd.sort_values(by="birth_date", key=lambda s: s.dt.day)
            for _, r in bd.iterrows():
                st.write(f"🎈 {r['birth_date'].day}일 · {r['name']} ({r.get('class_name') or '반 미정'})")
