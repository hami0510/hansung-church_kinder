import calendar
import html
from datetime import date
import pandas as pd
import streamlit as st
from utils.db import fetch
from utils.ui import hero
from utils.notice_ui import notice_cards
from utils.birthdays import collect, in_month, upcoming

# 아동 생일(이름·반만)을 일반 방문자에게도 보여줄지 (False = 관리자만)
SHOW_CHILD_BIRTHDAY_TO_ALL = True

hero()

today = date.today()
is_admin = st.session_state.get("role") == "admin"

# ---------- 공지 ----------
try:
    nt = fetch("notices", "created_at", desc=True)
except Exception:
    nt = pd.DataFrame()
if not nt.empty:
    nt["_pin"] = nt["pinned"].apply(lambda v: str(v).lower() == "true")
    nt = nt.sort_values(["_pin", "created_at"], ascending=[False, False])
    st.subheader("📢 공지")
    notice_cards(nt.head(3))

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

# 생일 목록
children = fetch("children")
teachers = fetch("teachers")
people = collect(children if (SHOW_CHILD_BIRTHDAY_TO_ALL or is_admin) else None, teachers)

# ---------- 이번 주 생일 ----------
week = upcoming(people, today, days=7)
if week:
    st.subheader("🎂 이번 주 생일")
    cards = ["<div class='kcards'>"]
    for p in week:
        d = p["date"]
        if d == today:
            when = "오늘 🎉"
        elif (d - today).days == 1:
            when = "내일"
        else:
            when = f"{d.month}/{d.day}({'월화수목금토일'[d.weekday()]})"
        sub = p["cls"] if p["kind"] == "아동" else "선생님"
        cards.append(
            "<div class='kcard'>"
            f"<div class='kmuted'>{html.escape(when)}</div>"
            f"<div class='ktop'>🎂 {html.escape(str(p['name']))}"
            f"<span class='ktag'>{html.escape(p['kind'])}</span></div>"
            f"<div class='ksub'>{html.escape(sub)}</div></div>")
    cards.append("</div>")
    st.markdown("".join(cards), unsafe_allow_html=True)

# ---------- 월간 달력 ----------
st.subheader("🗓️ 월간 일정")

year, month = st.session_state["cal_year"], st.session_state["cal_month"]
st.markdown(f"<div class='calhead'>{year}년 {month}월</div>", unsafe_allow_html=True)

with st.container(key="calnav"):
    b1, b2, b3 = st.columns(3)
    b1.button("◀", on_click=move_month, args=(-1,), use_container_width=True, key="m_prev")
    b2.button("오늘", on_click=go_today, use_container_width=True, key="m_today")
    b3.button("▶", on_click=move_month, args=(1,), use_container_width=True, key="m_next")

# 날짜별 일정·생일 모으기
day_events = {}
by_day = {}
if not ev.empty:
    d_series = pd.to_datetime(ev["event_date"])
    month_ev = ev[(d_series.dt.year == year) & (d_series.dt.month == month)]
    for _, r in month_ev.iterrows():
        day_events.setdefault(r["event_date"].day, []).append(r)
        title = str(r["title"])
        cat = r.get("category")
        label = title if (not cat or cat == title) else f"{title}-{cat}"
        if r["time_str"]:
            label = f"{r['time_str']} {label}"
        by_day.setdefault(r["event_date"].day, []).append(label)

day_bds = in_month(people, year, month)
for day, plist in day_bds.items():
    for p in plist:
        by_day.setdefault(day, []).append(f"🎂 {p['name']}")

MAX_SHOW = 2
cal = calendar.Calendar(firstweekday=6)  # 일요일 시작
weeks = cal.monthdayscalendar(year, month)

rows = ["<table class='kcal'><tr>"
        "<th class='sun'>일</th><th>월</th><th>화</th><th>수</th><th>목</th><th>금</th><th class='sat'>토</th></tr>"]
for wk in weeks:
    rows.append("<tr>")
    for i, d in enumerate(wk):
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


# ---------- 날짜 선택 → 팝업 ----------
@st.dialog("📅 일정 보기")
def show_day(y: int, m: int, d: int):
    wd = "월화수목금토일"[date(y, m, d).weekday()]
    st.markdown(f"### {m}월 {d}일 ({wd})")
    evs = day_events.get(d, [])
    bds = day_bds.get(d, [])
    if not evs and not bds:
        st.write("이 날은 등록된 일정이 없습니다.")
        return
    cards = ["<div class='kcards' style='grid-template-columns:1fr'>"]
    for r in evs:
        title = str(r["title"])
        cat = r.get("category")
        cat = cat if isinstance(cat, str) and cat else ""
        when = r["time_str"] or "시간 미정"
        loc = r.get("location") if isinstance(r.get("location"), str) else ""
        desc = r.get("description") if isinstance(r.get("description"), str) else ""
        cards.append(
            "<div class='kcard'>"
            f"<div class='kmuted'>🕒 {html.escape(when)}</div>"
            f"<div class='ktop'>{html.escape(title)}"
            + (f"<span class='ktag'>{html.escape(cat)}</span>" if cat else "")
            + "</div>"
            + (f"<div class='ksub'>📍 {html.escape(loc)}</div>" if loc else "")
            + (f"<div class='ksub'>{html.escape(desc).replace(chr(10), '<br>')}</div>" if desc else "")
            + "</div>")
    for p in bds:
        sub = p["cls"] if p["kind"] == "아동" else "선생님"
        cards.append(
            "<div class='kcard'>"
            f"<div class='ktop'>🎂 {html.escape(str(p['name']))}"
            f"<span class='ktag'>{html.escape(p['kind'])}</span></div>"
            f"<div class='ksub'>{html.escape(sub)} 생일</div></div>")
    cards.append("</div>")
    st.markdown("".join(cards), unsafe_allow_html=True)


active_days = sorted(set(day_events) | set(day_bds))
if active_days:
    def fmt_day(d):
        wd = "월화수목금토일"[date(year, month, d).weekday()]
        names = [str(r["title"]) for r in day_events.get(d, [])]
        names += [f"🎂{p['name']}" for p in day_bds.get(d, [])]
        return f"{month}/{d}({wd}) · " + ", ".join(names[:2]) + (" …" if len(names) > 2 else "")

    c1, c2 = st.columns([4, 1])
    pick = c1.selectbox("일정 자세히 보기", active_days, format_func=fmt_day,
                        index=None, placeholder="날짜를 선택하면 팝업으로 열립니다",
                        key=f"day_pick_{year}_{month}")
    if pick is not None:
        show_day(year, month, pick)
else:
    st.caption("이 달에는 등록된 일정이 없습니다.")
