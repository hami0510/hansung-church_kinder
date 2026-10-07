from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from utils.auth import can_manage
from utils.db import fetch, insert, update, delete
from utils.labels import class_label
from utils.pick import search_pick

KST = ZoneInfo("Asia/Seoul")
STATUS = ["출석", "불참", "미정"]
ICON = {"출석": "✅", "불참": "❌", "미정": "❔"}

st.title("📝 주일 예정 출석 보고")

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

now = datetime.now(KST)


def target_sunday(today: date) -> date:
    """다가오는 주일(오늘이 일요일이면 오늘)"""
    return today + timedelta(days=(6 - today.weekday()) % 7)


def deadline_of(sunday: date) -> datetime:
    """해당 주일 직전 토요일 낮 12시"""
    return datetime.combine(sunday - timedelta(days=1), datetime.min.time().replace(hour=12), KST)


sunday = target_sunday(now.date())
deadline = deadline_of(sunday)
is_late = now > deadline

st.info(f"📅 **{sunday.month}월 {sunday.day}일 주일** 예정 출석 · "
        f"마감: {deadline.month}/{deadline.day}(토) 12:00 · "
        + ("⏰ **마감이 지났습니다. 입력은 가능하며 '늦게 제출'로 표시됩니다.**" if is_late else "제출 가능"))

teachers = fetch("teachers", "name")
if teachers.empty:
    st.warning("먼저 '교사 · 반 명단'에서 교사를 등록해 주세요.")
    st.stop()
for col in ["service_part", "class_no"]:
    if col not in teachers.columns:
        teachers[col] = None
teachers = teachers[teachers["is_active"] == True]

tab_in, tab_sum = st.tabs(["내 출석 보고", "제출 현황"])

with tab_in:
        tid = search_pick(teachers, "선생님", key="sr")
    if tid is None:
        st.stop()

    rep = fetch("sunday_reports")
    mine = None
    if not rep.empty:
        rep["sunday_date"] = pd.to_datetime(rep["sunday_date"]).dt.date
        m = rep[(rep["teacher_id"] == tid) & (rep["sunday_date"] == sunday)]
        if not m.empty:
            mine = m.iloc[0]
            st.success(f"이미 제출함: {ICON[mine['status']]} {mine['status']}"
                       + (f" · {mine['reason']}" if mine.get("reason") else "")
                       + (" · 늦게 제출" if mine.get("is_late") else "")
                       + " (아래에서 수정할 수 있습니다)")

    with st.form("report_form"):
        cur = mine["status"] if mine is not None else "출석"
        status = st.radio("이번 주일 출석", STATUS, index=STATUS.index(cur), horizontal=True)
        reason = st.text_input("불참·미정 사유 (선택)",
                               value=(mine["reason"] if mine is not None and mine.get("reason") else ""))
        if st.form_submit_button("제출" if mine is None else "수정", use_container_width=True):
            data = {"status": status, "reason": reason or None,
                    "is_late": bool(is_late), "submitted_at": now.isoformat()}
            if mine is None:
                insert("sunday_reports", {"teacher_id": tid, "sunday_date": sunday.isoformat(), **data})
            else:
                update("sunday_reports", mine["id"], data)
            st.session_state["flash"] = "출석 보고가 제출되었습니다." + (" (늦게 제출)" if is_late else "")
            st.rerun()

with tab_sum:
    rep = fetch("sunday_reports")
    # 주일 선택 (최근 8주)
    sundays = [sunday - timedelta(weeks=i) for i in range(8)]
    pick = st.selectbox("주일 선택", sundays, format_func=lambda d: f"{d.month}월 {d.day}일")
    if rep.empty:
        sub = pd.DataFrame(columns=["teacher_id", "status", "reason", "is_late"])
    else:
        rep["sunday_date"] = pd.to_datetime(rep["sunday_date"]).dt.date
        sub = rep[rep["sunday_date"] == pick]

    n_in = int((sub["status"] == "출석").sum())
    n_out = int((sub["status"] == "불참").sum())
    n_tbd = int((sub["status"] == "미정").sum())
    submitted_ids = set(sub["teacher_id"])
    missing = teachers[~teachers["id"].isin(submitted_ids)]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("출석", n_in)
    c2.metric("불참", n_out)
    c3.metric("미정", n_tbd)
    c4.metric("미제출", len(missing))

    if not sub.empty:
        name_of = dict(zip(teachers["id"], teachers["name"]))
        cls_of = {r["id"]: class_label(r) for _, r in teachers.iterrows()}
        show = sub.assign(
            이름=sub["teacher_id"].map(name_of),
            반=sub["teacher_id"].map(cls_of),
            상태=sub["status"].map(lambda s: f"{ICON.get(s, '')} {s}"),
            사유=sub["reason"].fillna(""),
            비고=sub["is_late"].map(lambda v: "늦게 제출" if v else ""),
        )[["이름", "반", "상태", "사유", "비고"]]
        st.dataframe(show, hide_index=True, use_container_width=True)

    st.subheader("⏳ 미제출 선생님")
    if missing.empty:
        st.write("모두 제출했습니다. 🎉")
    else:
        for _, r in missing.iterrows():
            st.write(f"- {r['name']} ({class_label(r)})")
