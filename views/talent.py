from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from utils.db import fetch, upsert

st.title("🏅 달란트")

KST = ZoneInfo("Asia/Seoul")
GRADES = [("조이", "5세"), ("해피", "6세"), ("홀리", "7세")]
DEFAULT_CLASSES = {"1부": {"조이": 4, "해피": 4, "홀리": 4},
                   "2부": {"조이": 5, "해피": 3, "홀리": 5}}
PT_ATT, PT_REC, PT_FAM, PT_EVA = 10, 10, 10, 30
is_admin = st.session_state.get("role") == "admin"

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

if not is_admin:
    st.caption("🔒 달란트 입력·수정은 관리자 로그인 후 가능합니다. 지금은 보기만 할 수 있습니다.")

today = datetime.now(KST).date()
upcoming = today + timedelta(days=(6 - today.weekday()) % 7)

c1, c2 = st.columns(2)
part = c1.radio("부", ["1부", "2부"], horizontal=True, key="tl_part")
sunday = c2.date_input("주일 날짜", value=upcoming, key="tl_date")

mem = fetch("roster_members", "sort_no")
if mem.empty:
    st.info("출석부에 명단이 없습니다.")
    st.stop()
mem = mem[(mem["part"] == part) & (mem["grade"].isin(["조이", "해피", "홀리", "새싹"]))].copy()
mem["class_no"] = mem["class_no"].fillna(0).astype(int)
ids = set(mem["id"])

try:
    log = fetch("talent_log")
    base = fetch("talent_base")
except Exception:
    st.error("달란트 테이블이 아직 없습니다. Supabase SQL을 먼저 실행해 주세요.")
    st.stop()

att = fetch("roster_attendance")
if att.empty:
    att = pd.DataFrame(columns=["member_id", "sunday_date", "present"])
else:
    att["sunday_date"] = pd.to_datetime(att["sunday_date"]).dt.date
    att = att[att["member_id"].isin(ids) & (att["present"] == True)]

if log.empty:
    log = pd.DataFrame(columns=["member_id", "sunday_date", "recite", "family", "evangel"])
else:
    log["sunday_date"] = pd.to_datetime(log["sunday_date"]).dt.date
    log = log[log["member_id"].isin(ids)]

base_map = ({r["member_id"]: int(r["base_points"] or 0) for _, r in base.iterrows()}
            if not base.empty else {})

year = sunday.year
att_year = att[pd.to_datetime(att["sunday_date"]).dt.year == year] if not att.empty else att
log_year = log[pd.to_datetime(log["sunday_date"]).dt.year == year] if not log.empty else log


def week_points(mid):
    a = PT_ATT if (not att.empty and ((att["member_id"] == mid) & (att["sunday_date"] == sunday)).any()) else 0
    row = log[(log["member_id"] == mid) & (log["sunday_date"] == sunday)]
    r = f = e = 0
    if not row.empty:
        r = PT_REC if bool(row.iloc[0]["recite"]) else 0
        f = PT_FAM if bool(row.iloc[0]["family"]) else 0
        e = PT_EVA * int(row.iloc[0]["evangel"] or 0)
    return a, r, f, e


def total_points(mid):
    t = base_map.get(mid, 0)
    if not att_year.empty:
        t += PT_ATT * int((att_year["member_id"] == mid).sum())
    if not log_year.empty:
        sub = log_year[log_year["member_id"] == mid]
        t += PT_REC * int(sub["recite"].fillna(False).astype(bool).sum())
        t += PT_FAM * int(sub["family"].fillna(False).astype(bool).sum())
        t += PT_EVA * int(sub["evangel"].fillna(0).astype(int).sum())
    return t


classes = [(g, n) for g, _ in GRADES for n in range(1, DEFAULT_CLASSES[part][g] + 1)] + [("새싹", 0)]
exist = {(r.grade, int(r.class_no)) for r in mem.itertuples()}
classes = [c for c in classes if c in exist] or sorted(exist)


def cl_label(o):
    return "🌱 새싹반" if o[0] == "새싹" else f"{o[0]}{o[1]}반"


def save_edits(editor_key, base_rows, sunday_iso):
    """표에서 칸을 고치는 즉시 저장하는 콜백"""
    if st.session_state.get("role") != "admin":
        return
    edited = (st.session_state.get(editor_key) or {}).get("edited_rows", {})
    who = (st.session_state.get("tl_editor") or "").strip() or None
    out = []
    for idx, ch in edited.items():
        r = base_rows[int(idx)]
        out.append({
            "member_id": r["id"], "sunday_date": sunday_iso,
            "recite": bool(ch.get("암송", r["recite"])),
            "family": bool(ch.get("가정예배", r["family"])),
            "evangel": max(0, int(ch.get("전도(횟수)", r["evangel"]) or 0)),
            "updated_by": who,
            "updated_at": datetime.now(KST).isoformat(),
        })
    if out:
        upsert("talent_log", out, "member_id,sunday_date")
    # 키를 바꿔 표를 새 데이터로 다시 시작 (합계 즉시 갱신)
    st.session_state["tl_ver"] = st.session_state.get("tl_ver", 0) + 1


tab_names = ["📊 반별 표", "🗓️ 월 집계"] + (["이월 점수"] if is_admin else [])
tabs = st.tabs(tab_names)

# ---------------------------------------------------------------- 반별 표 (칸 클릭 → 즉시 저장)
with tabs[0]:
    sel = st.selectbox("반", classes, format_func=cl_label, key="tl_cls_v")
    if is_admin:
        st.text_input("입력하는 선생님 이름 (선택)", key="tl_editor")
        st.caption("암송·가정예배를 체크하거나 전도 횟수를 고치면 **바로 저장**되고 합계가 바뀝니다. "
                   "출석은 출석부에서 자동 반영됩니다.")
    kids = mem[(mem["grade"] == sel[0]) & (mem["class_no"] == sel[1])].sort_values("sort_no")
    base_rows, rows = [], []
    for _, k in kids.iterrows():
        a, r, f, e = week_points(k["id"])
        row = log[(log["member_id"] == k["id"]) & (log["sunday_date"] == sunday)]
        rec0 = bool(row.iloc[0]["recite"]) if not row.empty else False
        fam0 = bool(row.iloc[0]["family"]) if not row.empty else False
        eva0 = int(row.iloc[0]["evangel"] or 0) if not row.empty else 0
        base_rows.append({"id": k["id"], "recite": rec0, "family": fam0, "evangel": eva0})
        rows.append({"이름": k["name"], "출석(10)": "o" if a else "x",
                     "암송": rec0, "가정예배": fam0, "전도(횟수)": eva0,
                     "금주합계": a + r + f + e, "총 합계": total_points(k["id"])})
    st.caption(f"{sunday.month}월 {sunday.day}일 · {part} {cl_label(sel)}")
    if not rows:
        st.info("이 반에 아이가 없습니다.")
    else:
        ver = st.session_state.get("tl_ver", 0)
        ekey = f"tl_editor_{part}_{sunday}_{sel[0]}_{sel[1]}_{ver}"
        st.data_editor(
            pd.DataFrame(rows), hide_index=True, use_container_width=True, key=ekey,
            disabled=(["이름", "출석(10)", "암송", "가정예배", "전도(횟수)", "금주합계", "총 합계"]
                      if not is_admin else ["이름", "출석(10)", "금주합계", "총 합계"]),
            column_config={
                "암송": st.column_config.CheckboxColumn("암송(10)"),
                "가정예배": st.column_config.CheckboxColumn("가정예배(10)"),
                "전도(횟수)": st.column_config.NumberColumn("전도(30)", min_value=0, max_value=20, step=1),
            },
            on_change=save_edits, args=(ekey, base_rows, sunday.isoformat()),
        )

# ---------------------------------------------------------------- 월 집계 (학년별 분리)
with tabs[1]:
    mo = st.selectbox("월", list(range(1, 13)), index=sunday.month - 1,
                      format_func=lambda m: f"{m}월")
    out = []
    for _, k in mem.sort_values(["grade", "class_no", "sort_no"]).iterrows():
        mid = k["id"]
        if not att.empty:
            a_sub = att[(att["member_id"] == mid)
                        & (pd.to_datetime(att["sunday_date"]).dt.month == mo)
                        & (pd.to_datetime(att["sunday_date"]).dt.year == year)]
            a = PT_ATT * len(a_sub)
        else:
            a = 0
        if not log.empty:
            sub = log[(log["member_id"] == mid)
                      & (pd.to_datetime(log["sunday_date"]).dt.month == mo)
                      & (pd.to_datetime(log["sunday_date"]).dt.year == year)]
        else:
            sub = log
        r = PT_REC * int(sub["recite"].fillna(False).astype(bool).sum()) if len(sub) else 0
        f = PT_FAM * int(sub["family"].fillna(False).astype(bool).sum()) if len(sub) else 0
        e = PT_EVA * int(sub["evangel"].fillna(0).astype(int).sum()) if len(sub) else 0
        out.append({"학년": k["grade"], "반": cl_label((k["grade"], k["class_no"])),
                    "이름": k["name"], "출석": a, "암송": r, "가정예배": f, "전도": e,
                    f"{mo}월 합계": a + r + f + e})
    dfm = pd.DataFrame(out)
    tot_col = f"{mo}월 합계"
    if dfm.empty:
        st.info("표시할 데이터가 없습니다.")
    else:
        gnames = ["조이", "해피", "홀리", "새싹"]
        gtabs = st.tabs(gnames)
        for gt, gname in zip(gtabs, gnames):
            with gt:
                sub_g = dfm[dfm["학년"] == gname].drop(columns=["학년"])
                if sub_g.empty:
                    st.caption("해당 학년 데이터가 없습니다.")
                    continue
                st.metric(f"{gname} {mo}월 합계", int(sub_g[tot_col].sum()))
                st.dataframe(sub_g, hide_index=True, use_container_width=True)
                if gname != "새싹":
                    st.markdown("**반별 합계**")
                    st.dataframe(sub_g.groupby("반")[tot_col].sum().reset_index(),
                                 hide_index=True, use_container_width=True)

# ---------------------------------------------------------------- 이월 점수 (관리자만)
if is_admin:
    with tabs[2]:
        st.caption("앱 사용 전의 누적 점수를 아이별로 입력합니다. 나중에 입력해도 됩니다.")
        sel_b = st.selectbox("반", classes, format_func=cl_label, key="tl_cls_b")
        kb = mem[(mem["grade"] == sel_b[0]) & (mem["class_no"] == sel_b[1])].sort_values("sort_no")
        with st.form(f"tl_base_{part}_{sel_b}"):
            vals = []
            for _, k in kb.iterrows():
                v = st.number_input(k["name"], min_value=0, step=10,
                                    value=base_map.get(k["id"], 0), key=f"b_{k['id']}")
                vals.append((k["id"], int(v)))
            sb = st.form_submit_button("이월 점수 저장", type="primary", use_container_width=True)
        if sb and is_admin:
            upsert("talent_base",
                   [{"member_id": m, "base_points": v,
                     "updated_at": datetime.now(KST).isoformat()} for m, v in vals], "member_id")
            st.session_state["flash"] = "이월 점수를 저장했습니다."
            st.rerun()
