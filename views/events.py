from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from utils.db import fetch, insert, update, delete

st.title("📅 일정 관리")

CATS = ["예배", "행사", "교사회의", "교육", "심방", "기타"]
DOT = {"심방": "🔵", "예배": "🟡", "행사": "🟢", "교사회의": "🟣", "교육": "🟠", "기타": "⚪"}
WD = "월화수목금토일"
today = datetime.now(ZoneInfo("Asia/Seoul")).date()   # 한국 시간 기준 오늘

st.markdown("""
<style>
.dayband {display: flex; align-items: center; gap: .5rem; background: #eaf5ff;
          border-left: 5px solid #8ec9f5; border-radius: 10px; padding: .35rem .8rem;
          margin: 1rem 0 .2rem; font-weight: 800; color: #1b3a5c; font-size: .92rem;}
.dayband.today {background: #fff3bf; border-left-color: #f2c744;}
.dayband .badge {background: #4a9fe0; color: #fff; border-radius: 999px; padding: 0 .55rem;
                 font-size: .72rem; font-weight: 700;}
.evlegend {font-size: .78rem; color: #6b7c93; margin: .2rem 0 .4rem;}
.st-key-evlist [data-testid="stVerticalBlock"] {gap: 0 !important;}
.st-key-evlist [data-testid="stElementContainer"] {margin: 0 !important;}
.st-key-evlist .stButton > button {
  width: 100%; min-height: 2.2rem; height: 2.2rem; line-height: 2.2rem;
  border: none !important; background: transparent !important;
  box-shadow: none !important; border-bottom: 1px solid #edf1f6 !important; border-radius: 0 !important;
  justify-content: flex-start !important; text-align: left !important; padding: 0 .6rem;
  font-weight: 500; color: #1b3a5c;}
.st-key-evlist .stButton > button > div,
.st-key-evlist .stButton > button p {
  width: 100%; text-align: left !important; justify-content: flex-start !important; margin: 0;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}
.st-key-evlist .stButton > button:hover {background: #f1f8ff !important;}
</style>
""", unsafe_allow_html=True)

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))


def fmt_time(v):
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return ""
    return str(v)[:5]


def to_time(s):
    try:
        h, m = str(s)[:5].split(":")
        return time(int(h), int(m))
    except Exception:
        return time(9, 0)


def s(v):
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except Exception:
        pass
    return str(v)


ev = fetch("events", "event_date")
if not ev.empty:
    ev["event_date"] = pd.to_datetime(ev["event_date"]).dt.date
    if "event_time" not in ev.columns:
        ev["event_time"] = None
    ev["time_str"] = ev["event_time"].apply(fmt_time)
    ev = ev.assign(_k=ev["time_str"].replace("", "99:99")).sort_values(["event_date", "_k"])


# ---------------------------------------------------------------- 수정 팝업
@st.dialog("일정 수정")
def edit_dialog(row):
    rid = str(row["id"])
    with st.form(f"edit_{rid}"):
        title = st.text_input("제목 *", value=s(row["title"]))
        d = st.date_input("날짜", value=row["event_date"])
        use_t = st.checkbox("시간 지정", value=bool(row["time_str"]))
        t = st.time_input("시간", value=to_time(row["time_str"]) if row["time_str"] else time(9, 0))
        cat_cur = s(row.get("category"))
        cat = st.selectbox("구분", CATS, index=CATS.index(cat_cur) if cat_cur in CATS else len(CATS) - 1)
        loc = st.text_input("장소", value=s(row.get("location")))
        desc = st.text_area("설명", value=s(row.get("description")))
        saved = st.form_submit_button("저장", type="primary", use_container_width=True)
    if saved:
        if not title.strip():
            st.error("제목은 필수입니다.")
        else:
            update("events", row["id"], {
                "title": title.strip(), "event_date": d.isoformat(),
                "event_time": t.strftime("%H:%M") if use_t else None,
                "category": cat, "location": loc.strip() or None,
                "description": desc.strip() or None})
            st.session_state["flash"] = "일정을 수정했습니다."
            st.rerun()
    with st.expander("🗑️ 이 일정 삭제"):
        ok = st.checkbox("삭제에 동의합니다", key=f"edok_{rid}")
        if st.button("삭제하기", key=f"eddel_{rid}", type="primary", disabled=not ok,
                     use_container_width=True):
            delete("events", row["id"])
            st.session_state["flash"] = "일정을 삭제했습니다."
            st.rerun()


def render_days(df):
    """날짜별 띠 + 한 줄 일정 (줄을 누르면 수정창)"""
    for d, g in df.groupby("event_date", sort=True):
        is_today = d == today
        badge = "<span class='badge'>오늘</span>" if is_today else ""
        st.markdown(f"<div class='dayband{' today' if is_today else ''}'>"
                    f"{d.month}월 {d.day}일 ({WD[d.weekday()]}) {badge}</div>",
                    unsafe_allow_html=True)
        for _, r in g.iterrows():
            dot = DOT.get(s(r.get("category")), "⚪")
            tm = r["time_str"] or "종일"
            loc = s(r.get("location"))
            label = f"{tm}   {dot} {s(r['title'])}" + (f"  ·  {loc}" if loc else "")
            if st.button(label, key=f"ev_{r['id']}", use_container_width=True):
                edit_dialog(r)


tab_view, tab_add, tab_del = st.tabs(["일정 보기", "일정 등록", "일정 일괄 삭제"])

# ---------------------------------------------------------------- 일정 보기
with tab_view:
    c1, c2 = st.columns([1, 2])
    hide_past = c1.checkbox("지난 일정 숨기기", value=True)
    kw = c2.text_input("검색", placeholder="제목·장소·구분으로 검색",
                       label_visibility="collapsed").strip()
    st.markdown("<div class='evlegend'>" + "  ".join(f"{v} {k}" for k, v in DOT.items())
                + "  · 줄을 누르면 수정</div>", unsafe_allow_html=True)

    if ev.empty:
        st.info("등록된 일정이 없습니다.")
    else:
        view = ev.copy()
        if hide_past:
            view = view[view["event_date"] >= today]
        if kw:
            hay = (view["title"].fillna("") + view["location"].fillna("") + view["category"].fillna(""))
            view = view[hay.str.contains(kw, case=False, na=False)]
        if view.empty:
            st.info("표시할 일정이 없습니다.")
        else:
            with st.container(key="evlist"):
                limit = today + timedelta(days=7)
                if kw:
                    render_days(view)
                else:
                    near = view[view["event_date"] <= limit]
                    later = view[view["event_date"] > limit]
                    if not near.empty:
                        render_days(near)
                    else:
                        st.caption("이번 주 일정이 없습니다.")
                    if not later.empty:
                        with st.expander(f"이후 일정 {len(later)}건 보기"):
                            render_days(later)

# ---------------------------------------------------------------- 일정 등록
with tab_add:
    with st.form("add_event", clear_on_submit=True):
        title = st.text_input("제목 *")
        d = st.date_input("날짜", value=today)
        use_t = st.checkbox("시간 지정")
        t = st.time_input("시간", value=time(9, 0))
        cat = st.selectbox("구분", CATS)
        loc = st.text_input("장소")
        desc = st.text_area("설명")
        submitted = st.form_submit_button("일정 등록", type="primary", use_container_width=True)
    if submitted:
        if not title.strip():
            st.error("제목은 필수입니다.")
        else:
            insert("events", {
                "title": title.strip(), "event_date": d.isoformat(),
                "event_time": t.strftime("%H:%M") if use_t else None,
                "category": cat, "location": loc.strip() or None,
                "description": desc.strip() or None})
            st.toast("일정을 등록했습니다.", icon="✅")

# ---------------------------------------------------------------- 일괄 삭제
with tab_del:
    if ev.empty:
        st.info("삭제할 일정이 없습니다.")
    else:
        opts = {}
        for _, r in ev.iterrows():
            lab = f"{r['event_date']:%m/%d}({WD[r['event_date'].weekday()]}) {r['time_str'] or '종일'} · {s(r['title'])}"
            opts[lab + f"  [{str(r['id'])[:4]}]"] = r["id"]
        picked = st.multiselect("삭제할 일정 선택", list(opts.keys()))
        ok = st.checkbox("선택한 일정을 삭제하는 데 동의합니다")
        if st.button(f"선택 {len(picked)}건 삭제", type="primary",
                     disabled=not (picked and ok), use_container_width=True):
            for lab in picked:
                delete("events", opts[lab])
            st.session_state["flash"] = f"{len(picked)}건을 삭제했습니다."
            st.rerun()
