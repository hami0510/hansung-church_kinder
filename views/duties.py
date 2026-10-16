from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from utils import db
from utils.db import fetch, upsert

st.title("🙏 섬김 배정")

KST = ZoneInfo("Asia/Seoul")
WD = "월화수목금토일"
is_admin = st.session_state.get("role") == "admin"

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

if not is_admin:
    st.info("🔒 섬김 배정은 관리자 로그인 후 입력할 수 있습니다. 이번 주 배정은 왼쪽 메뉴 아래에서 볼 수 있습니다.")
    st.stop()

today = datetime.now(KST).date()
upcoming = today + timedelta(days=(6 - today.weekday()) % 7)


def delete_duty(sunday_iso, part_name):
    db.get_client().table("duties_weekly").delete() \
        .eq("sunday_date", sunday_iso).eq("part", part_name).execute()
    db._fetch_cached.clear()


def sval(v):
    return v if isinstance(v, str) else ""


# ---------------------------------------------------------------- 수정·삭제 팝업
@st.dialog("섬김 배정 수정")
def edit_dialog(d_iso: str, part_name: str, off0: str, main0: str, cln0: str):
    d = datetime.fromisoformat(d_iso).date()
    st.markdown(f"### {d.month}월 {d.day}일 ({WD[d.weekday()]}) · {part_name}")
    k = f"{d_iso}_{part_name}"
    off = st.text_input("헌금기도", value=off0, key=f"de_o_{k}")
    main = st.text_input("대표기도", value=main0, key=f"de_m_{k}")
    cln = st.text_input("청소당번 (여러 명은 쉼표로)", value=cln0, key=f"de_c_{k}")
    b1, b2 = st.columns(2)
    if b1.button("저장", type="primary", use_container_width=True, key=f"de_s_{k}"):
        if not (off.strip() or main.strip() or cln.strip()):
            st.warning("입력된 내용이 없습니다. 지우려면 삭제를 사용하세요.")
        else:
            upsert("duties_weekly",
                   [{"sunday_date": d_iso, "part": part_name,
                     "offering_prayer": off.strip() or None, "main_prayer": main.strip() or None,
                     "cleaning": cln.strip() or None,
                     "updated_at": datetime.now(KST).isoformat()}], "sunday_date,part")
            st.session_state["du_ver"] = st.session_state.get("du_ver", 0) + 1
            st.session_state["flash"] = f"{d.month}/{d.day} {part_name} 배정을 수정했습니다."
            st.rerun()
    with b2.popover("삭제", use_container_width=True):
        ok = st.checkbox("삭제에 동의합니다 (되돌릴 수 없습니다)", key=f"de_ok_{k}")
        if st.button("삭제하기", type="primary", disabled=not ok, key=f"de_d_{k}",
                     use_container_width=True):
            delete_duty(d_iso, part_name)
            st.session_state["du_ver"] = st.session_state.get("du_ver", 0) + 1
            st.session_state["flash"] = f"{d.month}/{d.day} {part_name} 배정을 삭제했습니다."
            st.rerun()


# ---------------------------------------------------------------- 새로 등록
ver = st.session_state.get("du_ver", 0)

c1, c2 = st.columns(2)
sunday = c2.date_input("주일 날짜", value=upcoming, key="du_date")
part = c1.radio("부", ["1부", "2부"], horizontal=True, key="du_part")

df = fetch("duties_weekly")
if not df.empty:
    df["sunday_date"] = pd.to_datetime(df["sunday_date"]).dt.date

fk = f"{sunday}_{part}_{ver}"
with st.form(f"du_form_{fk}"):
    st.caption(f"{sunday.month}월 {sunday.day}일 ({WD[sunday.weekday()]}) · {part} · 새로 등록 "
               "(같은 날짜·부에 저장하면 덮어씁니다)")
    off = st.text_input("헌금기도", key=f"o_{fk}")
    main = st.text_input("대표기도", key=f"m_{fk}")
    cln = st.text_input("청소당번 (여러 명은 쉼표로)", key=f"c_{fk}")
    saved = st.form_submit_button("저장", type="primary", use_container_width=True)

if saved:
    if not (off.strip() or main.strip() or cln.strip()):
        st.warning("입력된 내용이 없습니다.")
    else:
        upsert("duties_weekly",
               [{"sunday_date": sunday.isoformat(), "part": part,
                 "offering_prayer": off.strip() or None, "main_prayer": main.strip() or None,
                 "cleaning": cln.strip() or None,
                 "updated_at": datetime.now(KST).isoformat()}], "sunday_date,part")
        st.session_state["du_ver"] = ver + 1
        st.session_state["flash"] = f"{sunday.month}/{sunday.day} {part} 섬김 배정을 저장했습니다."
        st.rerun()

# ---------------------------------------------------------------- 최근 배정 (행 클릭 → 수정·삭제)
st.divider()
st.markdown("#### 최근 배정")
if df.empty:
    st.caption("등록된 배정이 없습니다.")
else:
    st.caption("행을 누르면 수정·삭제 창이 열립니다.")
    show = df.sort_values(["sunday_date", "part"], ascending=[False, True]).head(20).reset_index(drop=True)
    tbl = pd.DataFrame({
        "주일": show["sunday_date"].apply(lambda d: f"{d.month}/{d.day}({WD[d.weekday()]})"),
        "부": show["part"],
        "헌금기도": show["offering_prayer"].fillna(""),
        "대표기도": show["main_prayer"].fillna(""),
        "청소당번": show["cleaning"].fillna(""),
    })
    ev = st.dataframe(tbl, hide_index=True, use_container_width=True,
                      on_select="rerun", selection_mode="single-row",
                      key=f"du_tbl_{ver}")
    rows = []
    try:
        rows = ev.selection.rows
    except Exception:
        rows = []
    if rows:
        r = show.iloc[rows[0]]
        edit_dialog(r["sunday_date"].isoformat(), str(r["part"]),
                    sval(r["offering_prayer"]), sval(r["main_prayer"]), sval(r["cleaning"]))
