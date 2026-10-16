from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from utils import db
from utils.db import fetch, upsert

st.title("🙏 섬김 배정")

KST = ZoneInfo("Asia/Seoul")
WD = "월화수목금토일"
is_admin = st.session_state.get("role") == "admin"

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

if not is_admin:
    st.info("🔒 섬김 배정은 관리자 로그인 후 입력할 수 있습니다. 이번 주 배정은 왼쪽 메뉴 아래에서 볼 수 있습니다.")
    st.stop()

today = datetime.now(KST).date()
upcoming = today + timedelta(days=(6 - today.weekday()) % 7)

c1, c2 = st.columns(2)
sunday = c2.date_input("주일 날짜", value=upcoming, key="du_date")
part = c1.radio("부", ["1부", "2부"], horizontal=True, key="du_part")

df = fetch("duties_weekly")
cur = {}
if not df.empty:
    df["sunday_date"] = pd.to_datetime(df["sunday_date"]).dt.date
    m = df[(df["sunday_date"] == sunday) & (df["part"] == part)]
    if not m.empty:
        cur = m.iloc[0].to_dict()


def sv(k):
    v = cur.get(k)
    return v if isinstance(v, str) else ""


fk = f"{sunday}_{part}"
with st.form(f"du_form_{fk}"):
    st.caption(f"{sunday.month}월 {sunday.day}일 ({WD[sunday.weekday()]}) · {part}")
    off = st.text_input("헌금기도", value=sv("offering_prayer"), key=f"o_{fk}")
    main = st.text_input("대표기도", value=sv("main_prayer"), key=f"m_{fk}")
    cln = st.text_input("청소당번 (여러 명은 쉼표로)", value=sv("cleaning"), key=f"c_{fk}")
    saved = st.form_submit_button("저장", type="primary", use_container_width=True)

if saved:
    upsert("duties_weekly",
           [{"sunday_date": sunday.isoformat(), "part": part,
             "offering_prayer": off.strip() or None, "main_prayer": main.strip() or None,
             "cleaning": cln.strip() or None,
             "updated_at": datetime.now(KST).isoformat()}], "sunday_date,part")
    st.session_state["flash"] = f"{part} 섬김 배정을 저장했습니다."
    st.rerun()

st.divider()
st.markdown("#### 최근 배정")
if df.empty:
    st.caption("등록된 배정이 없습니다.")
else:
    show = df.sort_values(["sunday_date", "part"], ascending=[False, True]).head(12).copy()
    show["주일"] = show["sunday_date"].apply(lambda d: f"{d.month}/{d.day}")
    show = show.rename(columns={"part": "부", "offering_prayer": "헌금기도",
                                "main_prayer": "대표기도", "cleaning": "청소당번"})
    st.dataframe(show[["주일", "부", "헌금기도", "대표기도", "청소당번"]].fillna(""),
                 hide_index=True, use_container_width=True)
