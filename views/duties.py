from datetime import date, datetime, timedelta
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


c1, c2 = st.columns(2)
sunday = c2.date_input("주일 날짜", value=upcoming, key="du_date")
part = c1.radio("부", ["1부", "2부"], horizontal=True, key="du_part")

df = fetch("duties_weekly")
cur = {}
if not df.empty:
    df["sunday_date"] = pd.to_datetime(df["sunday_date"]).dt.date
    m = df[(df["sunday_date"] == sunday) & (df["part"] == part)]
    if not m.empty:
        cur = m.iloc[0].to_dict()


def sv(k):
    v = cur.get(k)
    return v if isinstance(v, str) else ""


# 저장할 때마다 번호가 바뀌어 입력칸이 새로(빈 값으로) 시작됨
ver = st.session_state.get("du_ver", 0)
load = False
if cur:
    load = st.checkbox("저장된 내용 불러와서 수정하기", key=f"du_load_{sunday}_{part}_{ver}")

fk = f"{sunday}_{part}_{ver}_{int(load)}"
with st.form(f"du_form_{fk}"):
    st.caption(f"{sunday.month}월 {sunday.day}일 ({WD[sunday.weekday()]}) · {part}")
    off = st.text_input("헌금기도", value=sv("offering_prayer") if load else "", key=f"o_{fk}")
    main = st.text_input("대표기도", value=sv("main_prayer") if load else "", key=f"m_{fk}")
    cln = st.text_input("청소당번 (여러 명은 쉼표로)", value=sv("cleaning") if load else "",
                        key=f"c_{fk}")
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

# ---------------------------------------------------------------- 선택한 날짜·부 삭제
if cur:
    with st.expander(f"🗑️ {sunday.month}/{sunday.day} {part} 배정 삭제"):
        st.caption(f"헌금기도 {sv('offering_prayer') or '-'} · 대표기도 {sv('main_prayer') or '-'} · "
                   f"청소당번 {sv('cleaning') or '-'}")
        ok1 = st.checkbox("삭제에 동의합니다 (되돌릴 수 없습니다)",
                          key=f"du_ok1_{sunday}_{part}_{ver}")
        if st.button("이 배정 삭제", type="primary", disabled=not ok1,
                     key=f"du_del1_{sunday}_{part}_{ver}", use_container_width=True):
            delete_duty(sunday.isoformat(), part)
            st.session_state["du_ver"] = ver + 1
            st.session_state["flash"] = f"{sunday.month}/{sunday.day} {part} 배정을 삭제했습니다."
            st.rerun()

st.divider()
st.markdown("#### 최근 배정")
if df.empty:
    st.caption("등록된 배정이 없습니다.")
else:
    show = df.sort_values(["sunday_date", "part"], ascending=[False, True]).head(12).copy()
    show["주일"] = show["sunday_date"].apply(
        lambda d: f"{d.month}/{d.day}({'월화수목금토일'[d.weekday()]})")
    tbl = show.rename(columns={"part": "부", "offering_prayer": "헌금기도",
                               "main_prayer": "대표기도", "cleaning": "청소당번"})
    st.dataframe(tbl[["주일", "부", "헌금기도", "대표기도", "청소당번"]].fillna(""),
                 hide_index=True, use_container_width=True)

    # ------------------------------------------------------------ 여러 건 선택 삭제
    with st.expander("🗑️ 여러 건 골라서 삭제"):
        opts = {}
        for _, r in show.iterrows():
            lab = f"{r['주일']} · {r['part']}"
            opts[lab] = (r["sunday_date"].isoformat(), r["part"])
        picked = st.multiselect("삭제할 배정 선택", list(opts.keys()), key=f"du_multi_{ver}")
        ok2 = st.checkbox("선택한 배정을 삭제하는 데 동의합니다 (되돌릴 수 없습니다)",
                          key=f"du_ok2_{ver}")
        if st.button(f"선택 {len(picked)}건 삭제", type="primary",
                     disabled=not (picked and ok2), key=f"du_del2_{ver}",
                     use_container_width=True):
            for lab in picked:
                d_iso, p_name = opts[lab]
                delete_duty(d_iso, p_name)
            st.session_state["du_ver"] = ver + 1
            st.session_state["flash"] = f"{len(picked)}건을 삭제했습니다."
            st.rerun()
