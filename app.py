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

# 사이드메뉴 바로가기 링크 (이름, 주소) — 공개 주소만 넣으세요
LINKS = [
    ("📰 펄스", "https://hansung-pulse.netlify.app"),
    ("📱 모바일주보",
     "https://sites.google.com/view/hansunguchi/%ED%95%9C%EC%84%B1-%EC%9C%A0%EC%B9%98%EB%B6%80-%EB%AA%A8%EB%B0%94%EC%9D%BC-%EC%A3%BC%EB%B3%B4"),
]

if "role" not in st.session_state:
    st.session_state["role"] = "guest"
    st.session_state["fails"] = 0

role = st.session_state["role"]

home = st.Page("views/home.py", title="홈", icon="🏠", default=True)
notices = st.Page("views/notices.py", title="공지사항", icon="📢")
events = st.Page("views/events.py", title="일정 관리", icon="📅")
roster = st.Page("views/roster_grid.py", title="주일 출석부", icon="📋")
talent = st.Page("views/talent.py", title="달란트", icon="🏅")
visit_request = st.Page("views/visit_request.py", title="심방 요청", icon="🏠")
prayer_request = st.Page("views/prayer_request.py", title="기도제목 요청", icon="🙏")
duties = st.Page("views/duties.py", title="섬김 배정", icon="🤝")

menu = [home, notices, events, roster, visit_request, prayer_request]
if role == "admin":
    menu.append(talent)
    menu.append(duties)
pages = {"메뉴": menu}


def load_duties(sunday_iso: str):
    from datetime import date as _d
    from utils.db import fetch
    df = fetch("duties_weekly")
    if df.empty:
        return {}
    target = _d.fromisoformat(sunday_iso)
    df["_d"] = pd.to_datetime(df["sunday_date"]).dt.date
    df = df[df["_d"] == target]
    return {str(r["part"]).strip(): r for r in df.to_dict("records")}


def duty_card():
    today = datetime.now(KST).date()
    sunday = today + timedelta(days=(6 - today.weekday()) % 7)
    try:
        data = load_duties(sunday.isoformat())
    except Exception as e:
        st.caption(f"섬김 배정을 불러오지 못했습니다: {e}")
        return
    wd = "월화수목금토일"[sunday.weekday()]
    colors = {"1부": ("#e7f1fe", "#1c64f2"), "2부": ("#e6f9e9", "#2b8a3e")}
    items = (("offering_prayer", "헌금기도"), ("main_prayer", "대표기도"), ("cleaning", "청소당번"))
    body = ""
    for part in ("1부", "2부"):
        bg, fg = colors[part]
        r = data.get(part)
        rows = ""
        if r:
            for key, label in items:
                v = r.get(key)
                val = html.escape(v) if isinstance(v, str) and v else "<span style='color:#b0b9c6'>-</span>"
                rows += (f"<div style='display:flex;gap:.5rem;padding:.18rem 0;align-items:baseline'>"
                         f"<span style='flex:0 0 3.6rem;font-size:.72rem;color:#8a97a8'>{label}</span>"
                         f"<span style='font-size:.92rem;font-weight:700;color:#1b3a5c'>{val}</span></div>")
        if not rows or not any(isinstance(r.get(k), str) and r.get(k) for k, _ in items):
            rows = "<div style='font-size:.8rem;color:#b0b9c6;padding:.15rem 0'>미배정</div>"
        body += (f"<div style='margin-top:.55rem'>"
                 f"<span style='background:{bg};color:{fg};font-weight:800;font-size:.76rem;"
                 f"padding:.1rem .6rem;border-radius:999px'>{part}</span>{rows}</div>")
    st.markdown(
        "<div style='background:#fff;border:1.5px solid #9ccbf0;border-radius:16px;"
        "padding:.75rem .85rem;box-shadow:0 2px 8px rgba(74,159,224,.15)'>"
        "<div style='display:flex;justify-content:space-between;align-items:center'>"
        "<b style='color:#1b3a5c'>🙏 이번 주 섬김</b>"
        f"<span style='background:#fff3bf;border-radius:999px;padding:.05rem .55rem;"
        f"font-size:.74rem;font-weight:800;color:#7c5e00'>{sunday.month}/{sunday.day}({wd})</span></div>"
        f"{body}</div>", unsafe_allow_html=True)


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

    # 바로가기 링크 (새 탭으로 열림)
    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
    for label, url in LINKS:
        st.link_button(label, url, use_container_width=True)

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
