import hmac
import html
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from utils.ui import inject_css

st.set_page_config(page_title="유치부 관리", page_icon="⛪", layout="wide")

try:
    st.logo("logo.png", size="large")
except Exception:
    pass

inject_css()

MAX_FAILS = 5
KST = ZoneInfo("Asia/Seoul")

if "role" not in st.session_state:
    st.session_state["role"] = "guest"
    st.session_state["fails"] = 0

role = st.session_state["role"]

home = st.Page("views/home.py", title="홈", icon="🏠", default=True)
notices = st.Page("views/notices.py", title="공지사항", icon="📢")
events = st.Page("views/events.py", title="일정 관리", icon="📅")
roster = st.Page("views/roster_grid.py", title="주일 출석부", icon="📋")
visit_request = st.Page("views/visit_request.py", title="심방 요청", icon="🏠")
prayer_request = st.Page("views/prayer_request.py", title="기도제목 요청", icon="🙏")
duties = st.Page("views/duties.py", title="섬김 배정", icon="🙏")

menu = [home, notices, events, roster, visit_request, prayer_request]
if role == "admin":
    menu.append(duties)
pages = {"메뉴": menu}


@st.cache_data(ttl=60)
def load_duties(sunday_iso: str):
    from utils.db import fetch
    df = fetch("duties_weekly")
    if df.empty:
        return {}
    df["sunday_date"] = pd.to_datetime(df["sunday_date"]).dt.date.astype(str)
    df = df[df["sunday_date"] == sunday_iso]
    return {r["part"]: r for r in df.to_dict("records")}


def duty_card():
    today = datetime.now(KST).date()
    sunday = today + timedelta(days=(6 - today.weekday()) % 7)
    try:
        data = load_duties(sunday.isoformat())
    except Exception:
        return
    parts_html = ""
    for part in ("1부", "2부"):
        r = data.get(part)
        if r and any(isinstance(r.get(k), str) and r.get(k) for k in
                     ("offering_prayer", "main_prayer", "cleaning")):
            def g(k):
                v = r.get(k)
                return html.escape(v) if isinstance(v, str) and v else "-"
            parts_html += (f"<div style='margin-top:.4rem'><b>{part}</b><br>"
                           f"헌금기도 {g('offering_prayer')}<br>"
                           f"대표기도 {g('main_prayer')}<br>"
                           f"청소당번 {g('cleaning')}</div>")
        else:
            parts_html += (f"<div style='margin-top:.4rem'><b>{part}</b><br>"
                           f"<span style='color:#8a97a8'>아직 배정되지 않았습니다</span></div>")
    st.markdown(
        "<div style='background:#f3f9ff;border:1px solid #cfe5f8;border-radius:14px;"
        "padding:.7rem .8rem;font-size:.82rem;color:#1b3a5c;line-height:1.5'>"
        f"<b>🙏 이번 주 섬김</b> · {sunday.month}/{sunday.day}"
        f"{parts_html}</div>", unsafe_allow_html=True)


with st.sidebar:
    if role == "admin":
        st.caption("접속 권한: 관리자(목사님/임원)")
        if st.button("관리자 로그아웃"):
            st.session_state["role"] = "guest"
            st.session_state["fails"] = 0
            st.rerun()
    else:
        st.caption("접속 권한: 일반")
        with st.expander("🔒 관리자 로그인"):
            if st.session_state["fails"] >= MAX_FAILS:
                st.error("시도 횟수를 초과했습니다. 페이지를 새로고침한 뒤 다시 시도하세요.")
            else:
                with st.form("admin_login"):
                    pw = st.text_input("관리자 비밀번호", type="password")
                    submitted = st.form_submit_button("로그인")
                if submitted:
                    if hmac.compare_digest(pw, st.secrets["auth"]["admin_password"]):
                        st.session_state["role"] = "admin"
                        st.session_state["fails"] = 0
                        st.rerun()
                    else:
                        st.session_state["fails"] += 1
                        left = MAX_FAILS - st.session_state["fails"]
                        st.error(f"비밀번호가 올바르지 않습니다. (남은 시도 {left}회)")

    st.divider()
    duty_card()

    try:
        from utils.verses import verse_of_week
        v = verse_of_week()
    except Exception:
        v = None
    if v:
        ref, text = v
        st.markdown(
            "<div style='background:#fffbea;border:1px solid #ffe066;border-radius:14px;"
            "padding:.7rem .8rem;font-size:.85rem;color:#1b3a5c;line-height:1.5;margin-top:.6rem'>"
            "<b>📖 이번 주 암송구절</b><br>"
            f"<span style='font-weight:700'>{html.escape(ref)}</span>"
            + (f"<br>{html.escape(text)}" if text else "")
            + "</div>", unsafe_allow_html=True)

st.navigation(pages).run()
