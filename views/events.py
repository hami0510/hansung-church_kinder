from datetime import date, time
import pandas as pd
import streamlit as st
from utils.db import fetch, insert, update, delete
from utils.ui import event_cards

st.title("📅 일정 관리")

CATEGORIES = ["예배", "행사", "교사회의", "교육", "심방", "기타"]


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


# 삭제·수정 후 완료 메시지 (등록은 toast로 표시)
if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

tab_list, tab_add, tab_edit, tab_del = st.tabs(
    ["일정 보기", "일정 등록", "일정 수정", "일정 삭제"])

# ---------------------------------------------------------------- 일정 보기
with tab_list:
    ev = fetch("events", "event_date")
    if ev.empty:
        st.info("등록된 일정이 없습니다.")
    else:
        ev = prepare(ev)
        only_future = st.checkbox("지난 일정 숨기기", value=True)
        if only_future:
            ev = ev[ev["event_date"] >= date.today()]
        if ev.empty:
            st.info("표시할 일정이 없습니다.")
        else:
            ev = ev.assign(_k=ev["time_str"].replace("", "99:99")).sort_values(["event_date", "_k"])
            event_cards(ev)

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

# ---------------------------------------------------------------- 일정 수정
with tab_edit:
    st.subheader("일정 수정")
    ev_e = fetch("events", "event_date")
    if ev_e.empty:
        st.info("수정할 일정이 없습니다.")
    else:
        ev_e = prepare(ev_e)
        today = date.today()
        # 오늘 이후 일정을 먼저(가까운 순), 지난 일정은 뒤에(최근 순)
        up = ev_e[ev_e["event_date"] >= today].sort_values(["event_date", "time_str"])
        past = ev_e[ev_e["event_date"] < today].sort_values(["event_date", "time_str"], ascending=False)
        ev_e = pd.concat([up, past])

        q = st.text_input("🔍 일정 검색", key="ev_edit_q",
                          placeholder="제목 또는 날짜로 검색 (예: 송혜미, 10/14, 심방)")
        kw = q.strip().replace(" ", "")
        opts = {}
        for _, r in ev_e.iterrows():
            lbl = label_of(r)
            alt = f"{r['event_date'].month}/{r['event_date'].day} {lbl}"
            if not kw or kw in alt.replace(" ", ""):
                opts[lbl + f"  #{str(r['id'])[:4]}"] = r["id"]  # 같은 이름 구분용 꼬리표

        if not opts:
            st.warning("검색 결과가 없습니다.")
        else:
            pick = st.selectbox(f"수정할 일정 ({len(opts)}건)", list(opts), key="ev_edit_pick")
            row = ev_e[ev_e["id"] == opts[pick]].iloc[0]
            eid = str(row["id"])

            cur_cat = s_or_empty(row.get("category"))
            cat_opts = CATEGORIES + ([cur_cat] if cur_cat and cur_cat not in CATEGORIES else [])
            cur_time = None
            if row["time_str"]:
                try:
                    h, mi = row["time_str"].split(":")[:2]
                    cur_time = time(int(h), int(mi))
                except Exception:
                    cur_time = None

            # 일정마다 입력칸 key를 달리해서, 다른 일정을 고르면 값이 새로 채워지게 함
            with st.form(f"edit_event_{eid}"):
                e_title = st.text_input("제목 *", value=s_or_empty(row.get("title")))
                e_use_time = st.checkbox("시간 지정 (체크 해제 후 저장하면 시간이 제거됩니다)",
                                         value=cur_time is not None)
                c1, c2, c3 = st.columns(3)
                e_date = c1.date_input("날짜", value=row["event_date"])
                e_time = c2.time_input("시간", value=cur_time or time(10, 0), step=900)
                e_cat = c3.selectbox("구분", cat_opts,
                                     index=cat_opts.index(cur_cat) if cur_cat in cat_opts else 0)
                e_loc = st.text_input("장소", value=s_or_empty(row.get("location")))
                e_desc = st.text_area("내용", value=s_or_empty(row.get("description")))
                saved = st.form_submit_button("수정 저장", use_container_width=True)

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
                    st.rerun()

# ---------------------------------------------------------------- 일정 삭제
with tab_del:
    st.subheader("일정 삭제")
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
