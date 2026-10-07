from datetime import date, time
import pandas as pd
import streamlit as st
from utils.db import fetch, insert, update, delete

st.title("📅 일정 관리")

CATEGORIES = ["예배", "행사", "교사회의", "교육", "심방", "기타"]
WD = "월화수목금토일"


def fmt_time(v):
    """DB의 '10:00:00' → '10:00', 비어 있으면 ''"""
    if v is None or pd.isna(v):
        return ""
    return str(v)[:5]


def prepare(df):
    df = df.copy()
    df["event_date"] = pd.to_datetime(df["event_date"]).dt.date
    if "event_time" not in df.columns:
        df["event_time"] = None
    df["time_str"] = df["event_time"].apply(fmt_time)
    return df


def s_or_empty(v):
    return v if isinstance(v, str) else ""


def label_of(r):
    t = f" {r['time_str']}" if r["time_str"] else ""
    return f"{r['event_date']}{t} · {r['title']} ({r.get('category') or '구분 없음'})"


# ---------------------------------------------------------------- 수정 팝업
@st.dialog("✏️ 일정 수정")
def edit_dialog(eid: str):
    ev_all = prepare(fetch("events", "event_date"))
    m = ev_all[ev_all["id"].astype(str) == eid]
    if m.empty:
        st.warning("이미 삭제되었거나 찾을 수 없는 일정입니다.")
        return
    row = m.iloc[0]

    cur_cat = s_or_empty(row.get("category"))
    cat_opts = CATEGORIES + ([cur_cat] if cur_cat and cur_cat not in CATEGORIES else [])
    cur_time = None
    if row["time_str"]:
        try:
            h, mi = row["time_str"].split(":")[:2]
            cur_time = time(int(h), int(mi))
        except Exception:
            cur_time = None

    with st.form(f"edit_form_{eid}"):
        e_title = st.text_input("제목 *", value=s_or_empty(row.get("title")))
        e_use_time = st.checkbox("시간 지정 (체크 해제 후 저장하면 시간이 제거됩니다)",
                                 value=cur_time is not None)
        c1, c2 = st.columns(2)
        e_date = c1.date_input("날짜", value=row["event_date"])
        e_time = c2.time_input("시간", value=cur_time or time(10, 0), step=900)
        e_cat = st.selectbox("구분", cat_opts,
                             index=cat_opts.index(cur_cat) if cur_cat in cat_opts else 0)
        e_loc = st.text_input("장소", value=s_or_empty(row.get("location")))
        e_desc = st.text_area("내용", value=s_or_empty(row.get("description")))
        saved = st.form_submit_button("저장", type="primary", use_container_width=True)

    if saved:
        if not e_title.strip():
            st.error("제목은 필수입니다.")
        else:
            update("events", row["id"], {
                "title": e_title.strip(), "event_date": e_date.isoformat(),
                "event_time": e_time.strftime("%H:%M") if e_use_time else None,
                "category": e_cat, "location": e_loc or None,
                "description": e_desc or None,
            })
            st.session_state["flash"] = f"'{e_title.strip()}' 일정을 수정했습니다."
            st.session_state["ev_table_ver"] = st.session_state.get("ev_table_ver", 0) + 1
            st.rerun()

    st.divider()
    ok = st.checkbox("이 일정을 삭제합니다", key=f"del_ok_{eid}")
    if st.button("🗑️ 삭제", disabled=not ok, key=f"del_btn_{eid}", use_container_width=True):
        delete("events", row["id"])
        st.session_state["flash"] = "일정을 삭제했습니다."
        st.session_state["ev_table_ver"] = st.session_state.get("ev_table_ver", 0) + 1
        st.rerun()


# 삭제·수정 후 완료 메시지 (등록은 toast로 표시)
if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

tab_list, tab_add, tab_del = st.tabs(["일정 보기", "일정 등록", "일정 일괄 삭제"])

# ---------------------------------------------------------------- 일정 보기
with tab_list:
    ev = fetch("events", "event_date")
    if ev.empty:
        st.info("등록된 일정이 없습니다.")
    else:
        ev = prepare(ev)
        today = date.today()
        c1, c2 = st.columns([1, 2])
        only_future = c1.checkbox("지난 일정 숨기기", value=True)
        kw = c2.text_input("🔍 검색", placeholder="제목·장소·구분으로 검색",
                           label_visibility="collapsed").strip().replace(" ", "")
        if only_future:
            ev = ev[ev["event_date"] >= today]
        if kw:
            hay = (ev["title"].fillna("") + ev["location"].fillna("") + ev["category"].fillna("")
                   ).str.replace(" ", "")
            ev = ev[hay.str.contains(kw, case=False, na=False)]
        if ev.empty:
            st.info("표시할 일정이 없습니다.")
        else:
            ev = ev.assign(_k=ev["time_str"].replace("", "99:99")).sort_values(
                ["event_date", "_k"]).reset_index(drop=True)
            view = pd.DataFrame({
                "날짜": ev["event_date"].apply(lambda d: f"{d.month}/{d.day}({WD[d.weekday()]})"),
                "시간": ev["time_str"].replace("", "종일"),
                "제목": ev["title"],
                "구분": ev["category"].fillna(""),
                "장소": ev["location"].fillna(""),
            })
            st.caption("일정을 누르면 수정·삭제할 수 있습니다.")
            ver = st.session_state.get("ev_table_ver", 0)
            sel = st.dataframe(view, hide_index=True, use_container_width=True,
                               on_select="rerun", selection_mode="single-row",
                               key=f"ev_table_{ver}")
            rows = sel.selection.rows if sel and sel.selection else []
            if rows:
                eid = str(ev.iloc[rows[0]]["id"])
                # 팝업을 닫은 뒤 같은 행을 다시 눌러도 열리도록 표를 새로 만든다
                st.session_state["ev_table_ver"] = ver + 1
                edit_dialog(eid)

# ---------------------------------------------------------------- 일정 등록
with tab_add:
    with st.form("add_event", clear_on_submit=True):
        title = st.text_input("제목 *")
        use_time = st.checkbox("시간 지정 (체크하면 아래 시간이 저장됩니다)")

        c1, c2, c3 = st.columns(3)
        d = c1.date_input("날짜", value=date.today())
        t = c2.time_input("시간", value=time(10, 0), step=900)  # 15분 단위
        cat = c3.selectbox("구분", CATEGORIES)

        loc = st.text_input("장소")
        desc = st.text_area("내용")

        submitted = st.form_submit_button("등록", use_container_width=True)

    if submitted:
        if not title.strip():
            st.error("제목은 필수입니다.")
        else:
            insert("events", {
                "title": title.strip(), "event_date": d.isoformat(),
                "event_time": t.strftime("%H:%M") if use_time else None,
                "category": cat, "location": loc or None, "description": desc or None,
                "created_by": "교사",
            })
            st.toast("일정이 등록되었습니다.", icon="✅")

# ---------------------------------------------------------------- 일정 일괄 삭제
with tab_del:
    st.subheader("일정 일괄 삭제")
    ev_all = fetch("events", "event_date")
    if ev_all.empty:
        st.info("삭제할 일정이 없습니다.")
    else:
        ev_all = prepare(ev_all)
        ev_all = ev_all.assign(_k=ev_all["time_str"].replace("", "99:99")).sort_values(
            ["event_date", "_k"], ascending=False)
        opts_d = {label_of(r) + f"  #{str(r['id'])[:4]}": r["id"] for _, r in ev_all.iterrows()}
        picked = st.multiselect("삭제할 일정 선택 (여러 개 가능)", list(opts_d))
        if picked:
            st.warning(f"선택한 {len(picked)}개 일정이 삭제됩니다. 되돌릴 수 없습니다.")
            confirm = st.checkbox("삭제하는 것에 동의합니다", key="ev_del_confirm")
            if st.button("선택한 일정 삭제", type="primary", disabled=not confirm,
                         use_container_width=True):
                for label in picked:
                    delete("events", opts_d[label])
                st.session_state["flash"] = f"{len(picked)}개 일정을 삭제했습니다."
                st.rerun()
