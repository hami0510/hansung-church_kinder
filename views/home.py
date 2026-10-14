import html
from datetime import date
import pandas as pd
import streamlit as st
from utils.db import fetch
from utils.ui import hero

try:
    from streamlit_calendar import calendar as st_calendar
except Exception:
    st_calendar = None

try:
    import holidays as _holidays
except Exception:
    _holidays = None

SHOW_HOLIDAYS = True
RENAME = {"기독탄신일": "성탄절", "신정연휴": "신정"}

# 이 화면 전용 여백 조정
st.markdown("""
<style>
.hero {margin-bottom: 1.4rem !important;}
.hero-sub {opacity: .75;}
.hsec {font-size: .85rem; font-weight: 700; color: #6b7c93; margin: 0 0 .5rem .2rem;}
.nbox {border: 1px solid rgba(128,128,128,.22); border-radius: 16px; padding: .2rem .6rem;
       background: rgba(120,180,240,.05); margin-bottom: 1.6rem;}
.nrow {display: flex; align-items: center; gap: .6rem; padding: .85rem .3rem; line-height: 1.4;}
.nrow .nt {flex: 1; min-width: 0; text-align: left; font-weight: 400; color: #1b3a5c;
           overflow: hidden; text-overflow: ellipsis; white-space: nowrap;}
.nrow.pin .nt {font-weight: 700;}
.nrow .nd {flex: 0 0 auto; font-size: .78rem; color: #9aa6b5;}
.nwrap {border-bottom: 1px solid rgba(128,128,128,.15);}
.nwrap:last-child {border-bottom: none;}
.nwrap:hover .nrow {background: rgba(74,159,224,.08); border-radius: 10px;}
.st-key-nlist [data-testid="stVerticalBlock"] {gap: 0;}
.st-key-nlist [data-testid="stElementContainer"] {margin: 0;}
.st-key-nlist [data-testid="stElementContainer"]:has(.stButton) {
  position: relative; margin-top: -3.1rem; height: 3.1rem; z-index: 2;}
.st-key-nlist .stButton, .st-key-nlist .stButton > button {width: 100%; height: 3.1rem;}
.st-key-nlist .stButton > button {opacity: 0; cursor: pointer; border: none; padding: 0;}
</style>
""", unsafe_allow_html=True)

hero()

today = date.today()


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

holiday_map = {}
if SHOW_HOLIDAYS and _holidays is not None:
    try:
        kr = _holidays.country_holidays(
            "KR", years=[today.year - 1, today.year, today.year + 1], language="ko")
        holiday_map = {d.isoformat(): RENAME.get(str(n), str(n)) for d, n in kr.items()}
    except Exception:
        holiday_map = {}


# ---------- 공지: 상단 고정 1건 + 최신 2건 (최대 3건) ----------
@st.dialog("📢 공지")
def show_notice(title: str, when: str, content: str):
    st.markdown(f"### {title}")
    if when:
        st.caption(when)
    st.markdown(html.escape(content).replace("\n", "  \n") if content else "내용이 없습니다.")


try:
    nt = fetch("notices", "created_at", desc=True)
except Exception:
    nt = pd.DataFrame()

if not nt.empty:
    nt["_pin"] = nt["pinned"].apply(lambda v: str(v).lower() == "true")
    nt = nt.sort_values("created_at", ascending=False)
    pinned = nt[nt["_pin"]].head(1)
    rest = nt[~nt.index.isin(pinned.index)].head(3 - len(pinned))
    show = pd.concat([pinned, rest])

    st.markdown("<div class='hsec'>📢 공지</div>", unsafe_allow_html=True)
    with st.container(key="nlist"):
        st.markdown("<div class='nbox'>", unsafe_allow_html=True)
        for _, r in show.iterrows():
            try:
                when = pd.to_datetime(r["created_at"], utc=True).tz_convert("Asia/Seoul")
                when_s = f"{when:%Y.%m.%d}"
            except Exception:
                when_s = ""
            mark = "📌" if r["_pin"] else "📢"
            content = r["content"] if isinstance(r.get("content"), str) else ""
            st.markdown(
                f"<div class='nwrap'><div class='nrow{' pin' if r['_pin'] else ''}'>"
                f"<span class='nt'>{mark} {html.escape(str(r['title']))}</span>"
                f"<span class='nd'>{html.escape(when_s)}</span></div></div>",
                unsafe_allow_html=True)
            if st.button(" ", key=f"notice_{r['id']}", use_container_width=True):
                show_notice(str(r["title"]), when_s, content)
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<div style='height:.4rem'></div>", unsafe_allow_html=True)

# ---------- 달력용 데이터 ----------
cal_events = []
day_events = {}
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
            "backgroundColor": "#e8f3ff", "borderColor": "#e8f3ff", "textColor": "#1b3a5c",
        })

for iso, name in holiday_map.items():
    cal_events.append({
        "id": f"hol_{iso}", "title": name, "start": iso, "allDay": True,
        "backgroundColor": "#ffe9e9", "borderColor": "#ffe9e9", "textColor": "#c92a2a",
        "classNames": ["kholiday"],
    })
    cal_events.append({
        "id": f"holbg_{iso}", "start": iso, "allDay": True, "display": "background",
        "backgroundColor": "#fff6f6",
    })


@st.dialog("📅 일정 보기")
def show_day(iso: str):
    d = date.fromisoformat(iso)
    wd = "월화수목금토일"[d.weekday()]
    st.markdown(f"### {d.month}월 {d.day}일 ({wd})")
    if iso in holiday_map:
        st.markdown(
            f"<div style='color:#c92a2a;font-weight:700;margin-bottom:.4rem'>"
            f"{html.escape(holiday_map[iso])}</div>", unsafe_allow_html=True)
    evs = day_events.get(iso, [])
    if not evs:
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
    cards.append("</div>")
    st.markdown("".join(cards), unsafe_allow_html=True)


# ---------- 월간 달력 ----------
if st_calendar is None:
    st.warning("달력을 불러오지 못했습니다. requirements.txt에 streamlit-calendar가 있는지 확인해 주세요.")
else:
    options = {
        "initialView": "dayGridMonth",
        "initialDate": today.isoformat(),
        "locale": "ko",
        "firstDay": 0,
        "height": 620,
        "fixedWeekCount": False,
        "dayMaxEvents": 2,
        "moreLinkClick": "none",
        "moreLinkText": "개 더보기",
        "headerToolbar": {"left": "prev,next today", "center": "title", "right": ""},
        "buttonText": {"today": "오늘"},
        "eventTimeFormat": {"hour": "2-digit", "minute": "2-digit", "hour12": False},
    }
    custom_css = """
        .fc {--fc-border-color: #e6edf5;}
        .fc-toolbar {margin-bottom: .9rem !important;}
        .fc-toolbar-title {font-size: 1.2rem !important; font-weight: 700;}
        .fc-col-header-cell {background: #f1f7fd;}
        .fc-col-header-cell-cushion {color: #1b3a5c; text-decoration: none; padding: 6px 0;}
        .fc-day-sun .fc-daygrid-day-number, .fc-day-sun .fc-col-header-cell-cushion {color: #d6336c !important;}
        .fc-day-sat .fc-daygrid-day-number, .fc-day-sat .fc-col-header-cell-cushion {color: #1c64f2 !important;}
        .fc-daygrid-day-number {text-decoration: none; font-weight: 700; pointer-events: none; padding: 6px 8px;}
        .fc-daygrid-day:has(.kholiday) .fc-daygrid-day-number {color: #e03131 !important;}
        .fc-day-today {background: #fff6d6 !important;}
        .fc-daygrid-day-frame {cursor: default;}
        .fc-daygrid-event-harness {margin: 0 4px 3px 4px !important;}
        .fc-event {cursor: pointer; border-radius: 8px; padding: 2px 5px; font-size: 0.78rem;}
        .fc-event.kholiday {cursor: default; font-weight: 700;}
        .fc-event-time {font-weight: 400; margin-right: 3px;}
        .fc-event-title {overflow: hidden; text-overflow: ellipsis;}
        .fc-more-link {pointer-events: none; color: #9aa6b5; margin-left: 6px;}
        .fc-button-primary {background: #4a9fe0 !important; border-color: #4a9fe0 !important;}
        @media (max-width: 640px) {
          .fc-event {padding: 2px 3px; font-size: 0.7rem;}
          .fc-event-time {display: none;}
          .fc-daygrid-day-number {font-size: 0.75rem; padding: 3px 4px;}
          .fc-daygrid-event-harness {margin: 0 2px 2px 2px !important;}
          .fc-toolbar-title {font-size: 1.05rem !important;}
        }
    """
    state = st_calendar(events=cal_events, options=options, custom_css=custom_css,
                        callbacks=["eventClick"], key="home_cal")

    clicked_iso, click_id = None, None
    if state and state.get("eventClick"):
        ec = state["eventClick"]
        ev_id = str(ec.get("event", {}).get("id", ""))
        start = str(ec.get("event", {}).get("start", ""))
        if not ev_id.startswith("hol"):
            clicked_iso = start[:10] or None
            click_id = (ev_id, str(ec.get("timeStamp", "")))

    if clicked_iso and click_id != st.session_state.get("last_click_id"):
        st.session_state["last_click_id"] = click_id
        show_day(clicked_iso)
