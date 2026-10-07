import html
from datetime import date, timedelta
import pandas as pd
import streamlit as st
from utils.db import fetch
from utils.ui import hero, stats_line
from utils.notice_ui import notice_cards
from utils.birthdays import collect, upcoming

try:
    from streamlit_calendar import calendar as st_calendar
except Exception:
    st_calendar = None

# 아동 생일(이름·반만)을 일반 방문자에게도 보여줄지 (False = 관리자만)
SHOW_CHILD_BIRTHDAY_TO_ALL = True
# 다가오는 생일을 며칠 앞까지 보여줄지
UPCOMING_DAYS = 30

hero()

today = date.today()
is_admin = st.session_state.get("role") == "admin"


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
for df_ in (children, teachers):
    for col in ("service_part", "class_no", "birth_date"):
        if not df_.empty and col not in df_.columns:
            df_[col] = None
show_children = SHOW_CHILD_BIRTHDAY_TO_ALL or is_admin
people_all = collect(children if show_children else None, teachers)

# ---------- 현황 한 줄 ----------
n_children = int((children["is_active"] == True).sum()) if not children.empty else 0
n_teachers = int((teachers["is_active"] == True).sum()) if not teachers.empty else 0
week_end = today + timedelta(days=7)
n_events = 0
if not ev.empty:
    n_events = int(((ev["event_date"] >= today) & (ev["event_date"] <= week_end)).sum())
n_bday = len(upcoming(people_all, today, days=7))
stats_line([
    ("👧", "재적 아동", f"{n_children}명"),
    ("👩‍🏫", "교사", f"{n_teachers}명"),
    ("📅", "이번 주 일정", f"{n_events}건"),
    ("🎂", "이번 주 생일", f"{n_bday}명"),
])

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

# ---------- 달력용 데이터 ----------
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

# 달력의 생일 칩(🎂)과 팝업용 생일 목록: 앞뒤 해를 포함해 3개 연도 분량
day_bds = {}  # "YYYY-MM-DD" -> 생일 목록
for y in (today.year - 1, today.year, today.year + 1):
    for p in people_all:
        try:
            d_ = date(y, p["month"], p["day"])
        except ValueError:  # 2/29 생일은 평년에 2/28로
            d_ = date(y, 2, 28)
        iso = d_.isoformat()
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
    options = {
        "initialView": "dayGridMonth",
        "initialDate": today.isoformat(),
        "locale": "ko",
        "firstDay": 0,
        "height": 650,
        "fixedWeekCount": False,
        "dayMaxEvents": 3,
        "moreLinkText": "개 더보기",
        "headerToolbar": {"left": "prev,next today", "center": "title", "right": ""},
        "buttonText": {"today": "오늘"},
        "eventTimeFormat": {"hour": "2-digit", "minute": "2-digit", "hour12": False},
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
        .fc-event-time {font-weight: 400; margin-right: 3px;}
        .fc-event-title {overflow: hidden; text-overflow: ellipsis;}
        .fc-button-primary {background: #4a9fe0 !important; border-color: #4a9fe0 !important;}
    """
    # key를 고정해서 달력이 다시 만들어지지 않게 함 (깜빡임·달 초기화 방지)
    state = st_calendar(events=cal_events, options=options, custom_css=custom_css,
                        callbacks=["dateClick", "eventClick"], key="home_cal")

    clicked_iso, click_id = None, None
    if state:
        if state.get("dateClick"):
            dc = state["dateClick"]
            clicked_iso = str(dc.get("date", ""))[:10] or None
            click_id = ("d", str(dc.get("date")), str(dc.get("timeStamp", "")))
        elif state.get("eventClick"):
            ec = state["eventClick"]
            start = str(ec.get("event", {}).get("start", ""))
            clicked_iso = start[:10] or None
            click_id = ("e", str(ec.get("event", {}).get("id", "")), str(ec.get("timeStamp", "")))

    # 새로운 클릭일 때만 팝업을 연다 (이미 처리한 클릭은 무시)
    if clicked_iso and click_id != st.session_state.get("last_click_id"):
        st.session_state["last_click_id"] = click_id
        show_day(clicked_iso)

# ---------- 다가오는 생일 (달력 아래, 항상 표시) ----------
st.subheader("🎂 다가오는 생일")
st.caption(f"오늘부터 {UPCOMING_DAYS}일 이내 생일입니다.")

soon = upcoming(people_all, today, days=UPCOMING_DAYS)
kids = [p for p in soon if p["kind"] == "아동"]
teas = [p for p in soon if p["kind"] == "교사"]


def bday_rows(items):
    out = []
    for p in items:
        d = p["date"]
        left = (d - today).days
        if left == 0:
            badge = "오늘 🎉"
        elif left == 1:
            badge = "내일"
        else:
            badge = f"D-{left}"
        sub = p["cls"] if p["kind"] == "아동" else "선생님"
        out.append(
            "<div style='display:flex;align-items:baseline;gap:.6rem;padding:.5rem .2rem;"
            "border-bottom:1px solid rgba(128,128,128,.18);line-height:1.35'>"
            f"<span style='flex:0 0 5.6rem;font-weight:700;color:#3b5f85'>"
            f"{d.month}/{d.day}({'월화수목금토일'[d.weekday()]})</span>"
            f"<span style='flex:1;min-width:0'><b>{html.escape(str(p['name']))}</b>"
            f"<span style='font-size:.85rem;color:#8a97a8'> · {html.escape(sub)}</span></span>"
            f"<span style='font-size:.78rem;padding:.05rem .55rem;border-radius:999px;"
            f"background:#fff3bf;color:#5c4a00;white-space:nowrap'>{html.escape(badge)}</span>"
            "</div>")
    return "".join(out)


def count_with_birth(df):
    if df is None or df.empty or "birth_date" not in df.columns:
        return 0
    return int(pd.to_datetime(df["birth_date"], errors="coerce").notna().sum())


t_kids, t_teas = st.tabs([f"아동 ({len(kids)})", f"교사 ({len(teas)})"])

with t_kids:
    if not show_children:
        st.info("아동 생일은 관리자 로그인 후 볼 수 있습니다.")
    elif kids:
        st.markdown(bday_rows(kids), unsafe_allow_html=True)
    else:
        st.write(f"{UPCOMING_DAYS}일 이내 생일인 아동이 없습니다.")
        st.caption(f"생년월일이 입력된 아동: {count_with_birth(children)}명")

with t_teas:
    if teas:
        st.markdown(bday_rows(teas), unsafe_allow_html=True)
    else:
        st.write(f"{UPCOMING_DAYS}일 이내 생일인 교사가 없습니다.")
        st.caption(f"생년월일이 입력된 교사: {count_with_birth(teachers)}명 "
                   "(교사 생년월일은 '교사·반 명단 → 수정'에서 입력)")
