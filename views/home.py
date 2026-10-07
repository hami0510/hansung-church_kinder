from utils.ui import event_cards, hero
import calendar
import html
from datetime import date
import pandas as pd
import streamlit as st
from utils.db import fetch

hero()

today = date.today()

# 보고 있는 달 (세션에 보관)
if "cal_year" not in st.session_state:
    st.session_state["cal_year"] = today.year
    st.session_state["cal_month"] = today.month


def move_month(delta: int):
    y, m = st.session_state["cal_year"], st.session_state["cal_month"] + delta
    if m < 1:
        y, m = y - 1, 12
    elif m > 12:
        y, m = y + 1, 1
    st.session_state["cal_year"], st.session_state["cal_month"] = y, m


def go_today():
    st.session_state["cal_year"], st.session_state["cal_month"] = today.year, today.month


def fmt_time(v):
    if v is None or pd.isna(v):
        return ""
    return str(v)[:5]


ev = fetch("events", "event_date")
if not ev.empty:
    ev["event_date"] = pd.to_datetime(ev["event_date"]).dt.date
    if "event_time" not in ev.columns:
        ev["event_time"] = None
    ev["time_str"] = ev["event_time"].apply(fmt_time)
    ev = ev.assign(_k=ev["time_str"].replace("", "99:99")).sort_values(["event_date", "_k"])

# ---------- 월간 달력 ----------
st.subheader("🗓️ 월간 일정")

year, month = st.session_state["cal_year"], st.session_state["cal_month"]
st.markdown(f"<div class='calhead'>{year}년 {month}월</div>", unsafe_allow_html=True)

with st.container(key="calnav"):
    b1, b2, b3 = st.columns(3)
    b1.button("◀", on_click=move_month, args=(-1,), use_container_width=True, key="m_prev")
    b2.button("오늘", on_click=go_today, use_container_width=True, key="m_today")
    b3.button("▶", on_click=move_month, args=(1,), use_container_width=True, key="m_next")

# 날짜별 일정 모으기
by_day = {}
month_ev = ev.iloc[0:0] if ev.empty else ev
if not ev.empty:
    d_series = pd.to_datetime(ev["event_date"])
    month_ev = ev[(d_series.dt.year == year) & (d_series.dt.month == month)]
    for _, r in month_ev.iterrows():
        title = str(r["title"])
        cat = r.get("category")
        label = title if (not cat or cat == title) else f"{title}-{cat}"
        if r["time_str"]:
            label = f"{r['time_str']} {label}"
        by_day.setdefault(r["event_date"].day, []).append(label)

MAX_SHOW = 2
cal = calendar.Calendar(firstweekday=6)  # 일요일 시작
weeks = cal.monthdayscalendar(year, month)

rows = ["<table class='kcal'><tr>"
        "<th class='sun'>일</th><th>월</th><th>화</th><th>수</th><th>목</th><th>금</th><th class='sat'>토</th></tr>"]
for week in weeks:
    rows.append("<tr>")
    for i, d in enumerate(week):
        if d == 0:
            rows.append("<td></td>")
            continue
        cls = "d sun" if i == 0 else ("d sat" if i == 6 else "d")
        td_cls = "today" if (year, month, d) == (today.year, today.month, today.day) else ""
        items = by_day.get(d, [])
        body = "".join(f"<div class='ev'>{html.escape(x)}</div>" for x in items[:MAX_SHOW])
        if len(items) > MAX_SHOW:
            body += f"<div class='more'>+{len(items) - MAX_SHOW}개 더보기</div>"
        if items:  # 모바일용 점 표시
            body += "<div class='dots'>" + "<span class='dot'></span>" * min(len(items), 4) + "</div>"
        rows.append(f"<td class='{td_cls}'><div class='{cls}'>{d}</div>{body}</td>")
    rows.append("</tr>")
rows.append("</table>")

st.markdown("".join(rows), unsafe_allow_html=True)

# ---------- 이번 달 일정 (카드) ----------
st.subheader(f"📋 {month}월 일정")
if month_ev.empty:
    st.write("이 달에는 등록된 일정이 없습니다.")
else:
    event_cards(month_ev)

# ---------- 다가오는 일정 ----------
st.subheader("📅 다가오는 일정")
if ev.empty:
    st.info("등록된 일정이 없습니다.")
else:
    upcoming = ev[ev["event_date"] >= today].head(5)
    if upcoming.empty:
        st.info("다가오는 일정이 없습니다.")
    else:
        event_cards(upcoming)

# ---------- 이번 달 생일 (관리자만) ----------
if st.session_state.get("role") == "admin":
    st.subheader("🎂 이번 달 생일")
    ch = fetch("children")
    if not ch.empty:
        ch = ch[ch["is_active"] == True].copy()
        ch["birth_date"] = pd.to_datetime(ch["birth_date"], errors="coerce")
        bd = ch[ch["birth_date"].dt.month == today.month]
        if bd.empty:
            st.write("이번 달 생일인 아이가 없습니다.")
        else:
            bd = bd.sort_values(by="birth_date", key=lambda s: s.dt.day)
            for _, r in bd.iterrows():
                st.write(f"🎈 {r['birth_date'].day}일 · {r['name']} ({r.get('class_name') or '반 미정'})")
