import calendar
import html
from datetime import date
import pandas as pd
import streamlit as st
from utils.db import fetch

# 달력 칸에 시간을 함께 표시할지 (False로 바꾸면 '제목-구분'만 표시)
SHOW_TIME_IN_CALENDAR = True

st.title("🏠 유치부 홈")

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
    # 날짜 → 시간순 (시간 없는 일정은 그날의 맨 뒤)
    ev = ev.assign(_k=ev["time_str"].replace("", "99:99")).sort_values(["event_date", "_k"])

# ---------- 월간 달력 ----------
st.subheader("🗓️ 월간 일정")

b1, b2, b3, b4 = st.columns([1, 1, 1, 3])
b1.button("◀ 이전달", on_click=move_month, args=(-1,), use_container_width=True)
b2.button("오늘", on_click=go_today, use_container_width=True)
b3.button("다음달 ▶", on_click=move_month, args=(1,), use_container_width=True)

year, month = st.session_state["cal_year"], st.session_state["cal_month"]
b4.markdown(f"### {year}년 {month}월")

# 날짜별 '[시간] 제목-구분' 모으기
by_day = {}
if not ev.empty:
    d_series = pd.to_datetime(ev["event_date"])
    month_ev = ev[(d_series.dt.year == year) & (d_series.dt.month == month)]
    for _, r in month_ev.iterrows():
        title = str(r["title"])
        cat = r.get("category")
        label = title if (not cat or cat == title) else f"{title}-{cat}"
        if SHOW_TIME_IN_CALENDAR and r["time_str"]:
            label = f"{r['time_str']} {label}"
        by_day.setdefault(r["event_date"].day, []).append(label)

MAX_SHOW = 2
cal = calendar.Calendar(firstweekday=6)  # 일요일 시작
weeks = cal.monthdayscalendar(year, month)

css = """
<style>
.kcal {width:100%; border-collapse:collapse; table-layout:fixed;}
.kcal th {background:#ffd966; padding:6px 2px; border:1px solid #d9d9d9; font-size:14px;}
.kcal td {vertical-align:top; height:92px; padding:3px; border:1px solid #d9d9d9; font-size:12px;}
.kcal .d {font-weight:700; font-size:13px;}
.kcal .sun {color:#e03131;}
.kcal .sat {color:#1c64f2;}
.kcal .today {background:#fff3bf;}
.kcal .ev {background:#e7f1ff; border-radius:3px; margin-top:2px; padding:1px 3px;
           overflow:hidden; text-overflow:ellipsis; white-space:nowrap;}
.kcal .more {color:#868e96; margin-top:2px;}
@media (max-width: 640px) {
  .kcal td {height:70px; font-size:10px; padding:1px;}
  .kcal th {font-size:12px;}
}
</style>
"""

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
        rows.append(f"<td class='{td_cls}'><div class='{cls}'>{d}</div>{body}</td>")
    rows.append("</tr>")
rows.append("</table>")

st.markdown(css + "".join(rows), unsafe_allow_html=True)

# ---------- 이번 달 일정 목록 ----------
with st.expander(f"{month}월 일정 전체 목록", expanded=False):
    if not by_day:
        st.write("이 달에는 등록된 일정이 없습니다.")
    else:
        for day in sorted(by_day):
            wd = "월화수목금토일"[date(year, month, day).weekday()]
            st.write(f"**{month}/{day}({wd})** · " + " / ".join(by_day[day]))

# ---------- 다가오는 일정 ----------
st.subheader("📅 다가오는 일정")
if ev.empty:
    st.info("등록된 일정이 없습니다.")
else:
    upcoming = ev[ev["event_date"] >= today].head(5)
    if upcoming.empty:
        st.info("다가오는 일정이 없습니다.")
    else:
        st.dataframe(
            upcoming[["event_date", "time_str", "title", "category", "location"]].rename(
                columns={"event_date": "날짜", "time_str": "시간", "title": "제목",
                         "category": "구분", "location": "장소"}
            ),
            hide_index=True, use_container_width=True,
        )

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
