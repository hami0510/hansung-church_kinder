from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from utils.db import fetch, insert, update

KST = ZoneInfo("Asia/Seoul")
STATUS = ["출석", "불참", "미정"]
ICON = {"출석": "✅", "불참": "❌", "미정": "❔"}

st.title("📝 주일 예정 출석 보고")

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

now = datetime.now(KST)


def target_sunday(today: date) -> date:
    return today + timedelta(days=(6 - today.weekday()) % 7)


def deadline_of(sunday: date) -> datetime:
    return datetime.combine(sunday - timedelta(days=1),
                            datetime.min.time().replace(hour=12), KST)


sunday = target_sunday(now.date())
deadline = deadline_of(sunday)
is_late = now > deadline

st.info(f"📅 **{sunday.month}월 {sunday.day}일 주일** 예정 출석 · "
        f"마감: {deadline.month}/{deadline.day}(토) 12:00 · "
        + ("⏰ **마감이 지났습니다. 입력은 가능하며 '늦게 제출'로 표시됩니다.**"
           if is_late else "제출 가능"))

tab_in, tab_sum = st.tabs(["내 출석 보고", "제출 현황"])

# ---------------------------------------------------------------- 내 출석 보고
with tab_in:
    name = st.text_input("선생님 이름", key="sr_name", placeholder="이름을 입력해 주세요").strip()

    if not name:
        st.info("이름을 입력하면 출석 보고를 할 수 있습니다.")
    else:
        rep = fetch("sunday_reports")
        mine = None
        if not rep.empty and "reporter_name" in rep.columns:
            rep["sunday_date"] = pd.to_datetime(rep["sunday_date"]).dt.date
            m = rep[(rep["reporter_name"] == name) & (rep["sunday_date"] == sunday)]
            if not m.empty:
                mine = m.iloc[0]
                st.success(
                    f"이미 제출함: {ICON[mine['status']]} {mine['status']}"
                    + (f" · {mine['reason']}" if mine.get("reason") else "")
                    + (" · 늦게 제출" if mine.get("is_late") else "")
                    + " (아래에서 수정할 수 있습니다)")

        with st.form("report_form"):
            cur = mine["status"] if mine is not None else "출석"
            status = st.radio("이번 주일 출석", STATUS,
                              index=STATUS.index(cur), horizontal=True)
            reason = st.text_input(
                "불참·미정 사유 (선택)",
                value=(mine["reason"] if mine is not None and mine.get("reason") else ""))
            if st.form_submit_button("제출" if mine is None else "수정",
                                     use_container_width=True):
                data = {"status": status, "reason": reason or None,
                        "is_late": bool(is_late), "submitted_at": now.isoformat()}
                if mine is None:
                    insert("sunday_reports", {"reporter_name": name,
                                              "sunday_date": sunday.isoformat(), **data})
                else:
                    update("sunday_reports", mine["id"], data)
                st.session_state["flash"] = ("출석 보고가 제출되었습니다."
                                              + (" (늦게 제출)" if is_late else ""))
                st.rerun()

# ---------------------------------------------------------------- 제출 현황
with tab_sum:
    rep = fetch("sunday_reports")
    sundays = [sunday - timedelta(weeks=i) for i in range(8)]
    pick = st.selectbox("주일 선택", sundays,
                        format_func=lambda d: f"{d.month}월 {d.day}일")
    if rep.empty or "reporter_name" not in rep.columns:
        sub = pd.DataFrame(columns=["reporter_name", "status", "reason", "is_late"])
    else:
        rep["sunday_date"] = pd.to_datetime(rep["sunday_date"]).dt.date
        sub = rep[(rep["sunday_date"] == pick) & rep["reporter_name"].notna()]

    c1, c2, c3 = st.columns(3)
    c1.metric("출석", int((sub["status"] == "출석").sum()))
    c2.metric("불참", int((sub["status"] == "불참").sum()))
    c3.metric("미정", int((sub["status"] == "미정").sum()))

    if sub.empty:
        st.write("이 주일에 제출된 보고가 없습니다.")
    else:
        show = pd.DataFrame({
            "이름": sub["reporter_name"],
            "상태": sub["status"].map(lambda s: f"{ICON.get(s, '')} {s}"),
            "사유": sub["reason"].fillna(""),
            "비고": sub["is_late"].map(lambda v: "늦게 제출" if v else ""),
        })
        st.dataframe(show, hide_index=True, use_container_width=True)
