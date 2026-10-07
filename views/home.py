import html
from datetime import date
import pandas as pd
import streamlit as st
from utils.db import fetch
from utils.ui import hero
from utils.notice_ui import notice_cards
from utils.birthdays import collect, in_month, upcoming

try:
    from streamlit_calendar import calendar as st_calendar
except Exception:
    st_calendar = None

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

# ---------- 달력용 데이터 ----------
# 일정 칩 + 생일 칩 (생일은 앞뒤 해를 포함해 3개 연도 분량 생성)
cal_events = []
day_events = {}  # "YYYY-MM-DD" -> 일정 행 목록 (팝업용)
if not ev.empty:
    for _, r in ev.iterrows():
        iso = r["event_date"].isoformat()
        day_events.setdefault(iso, []).append(r)
        title = str(r["title"])
        cat = r.get("category")
        label = title if (not isinstance(cat, str) or not cat or cat == title) else f"{title}-{cat}"
        start = f"{iso}T{r['time_str']}:00" if r["time_str"] else iso
        cal_events.append({
            "id": str(r["id"]), "title": label, "start": start,
            "allDay": not bool(r["time_str"]),
            "backgroundColor": "#dff0ff", "borderColor": "#bfe0fa", "textColor": "#1b3a5c",
        })

day_bds = {}  # "YYYY-MM-DD" -> 생일 목록 (팝업용)
for y in (today.year - 1, today.year, today.year + 1):
    for m in range(1, 13):
        for d, plist in in_month(people, y, m).items():
            iso = date(y, m, d).isoformat()
            for p in plist:
                day_bds.setdefault(iso, []).append(p)
                cal_events.append({
                    "id": f"bd_{iso}_{p['name']}", "title": f"🎂 {p['name']}", "start": iso,
                    "allDay": True,
                    "backgroundColor": "#fff3bf", "borderColor": "#ffd43b", "textColor": "#5c4a00",
                })


@st.dialog("📅 일정 보기")
def show_day(iso: str):
    d = date.fromisoformat(iso)
    wd = "월화수목금토일"[d.weekday()]
    st.markdown(f"### {d.month}월 {d.day}일 ({wd})")
    evs = day_events.get(iso, [])
    bds = day_bds.get(iso, [])
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


# ---------- 월간 달력 ----------
st.subheader("🗓️ 월간 일정")

if st_calendar is None:
    st.warning("달력을 불러오지 못했습니다. requirements.txt에 streamlit-calendar가 있는지 확인해 주세요.")
else:
    # 팝업을 닫은 뒤 같은 날을 다시 눌러도 열리도록, 달력 key를 바꿔 클릭 기록을 초기화
    n = st.session_state.get("cal_reset", 0)
    options = {
        "initialView": "dayGridMonth",
        "locale": "ko",
        "firstDay": 0,
        "height": 650,
        "fixedWeekCount": False,
        "dayMaxEvents": 3,
        "moreLinkText": "개 더보기",
        "headerToolbar": {"left": "prev,next today", "center": "title", "right": ""},
        "buttonText": {"today": "오늘"},
        "dayCellClassNames": [],
    }
    custom_css = """
        .fc-toolbar-title {font-size: 1.3rem !important; font-weight: 700;}
        .fc-col-header-cell {background: #cfe9fc;}
        .fc-col-header-cell-cushion {color: #1b3a5c; text-decoration: none;}
        .fc-day-sun .fc-daygrid-day-number, .fc-day-sun .fc-col-header-cell-cushion {color: #d6336c !important;}
        .fc-day-sat .fc-daygrid-day-number, .fc-day-sat .fc-col-header-cell-cushion {color: #1c64f2 !important;}
        .fc-daygrid-day-number {text-decoration: none; font-weight: 700;}
        .fc-day-today {background: #fff3bf !important;}
        .fc-event {cursor: pointer; border-radius: 8px; padding: 0 3px; font-size: 0.78rem;}
        .fc-button-primary {background: #4a9fe0 !important; border-color: #4a9fe0 !important;}
    """
    state = st_calendar(events=cal_events, options=options, custom_css=custom_css,
                        callbacks=["dateClick", "eventClick"], key=f"cal_{n}")

    clicked_iso = None
    if state:
        if state.get("dateClick"):
            clicked_iso = str(state["dateClick"]["date"])[:10]
        elif state.get("eventClick"):
            start = str(state["eventClick"]["event"].get("start", ""))
            clicked_iso = start[:10] or None

    if clicked_iso:
        st.session_state["cal_reset"] = n + 1  # 다음 실행에서 클릭 기록 초기화
        show_day(clicked_iso)
