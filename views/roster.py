from datetime import date, timedelta
import pandas as pd
import streamlit as st
from utils.db import fetch, insert, update, delete, upsert

st.title("📋 주일 출석부")

# 열람은 누구나, 출석 체크·명단 수정은 관리자 로그인한 사람만
is_admin = st.session_state.get("role") == "admin"

PARTS = ["1부", "2부"]
GRADES = [("조이", "5세 조이", 5), ("해피", "6세 해피", 4), ("홀리", "7세 홀리", 5)]
NONE_CLASS = 0  # 새싹반·스탭용 번호


def parse_names(text: str):
    out = []
    for line in (text or "").replace(",", "\n").replace("，", "\n").splitlines():
        n = line.strip()
        if n:
            out.append(n)
    return out


if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

if not is_admin:
    st.caption("🔒 출석 체크와 명단 수정은 관리자 로그인 후 가능합니다. (왼쪽 메뉴 아래 '관리자 로그인')")

c1, c2 = st.columns(2)
part = c1.radio("부", PARTS, horizontal=True)
upcoming = date.today() + timedelta(days=(6 - date.today().weekday()) % 7)
sunday = c2.date_input("주일 날짜", value=upcoming)

mem = fetch("roster_members", "sort_no")
cls = fetch("roster_classes")
att = fetch("roster_attendance")
vis = fetch("roster_visitors")

if mem.empty:
    mem = pd.DataFrame(columns=["id", "part", "grade", "class_no", "name", "sort_no"])
if cls.empty:
    cls = pd.DataFrame(columns=["id", "part", "grade", "class_no", "teachers"])
if att.empty:
    att = pd.DataFrame(columns=["member_id", "sunday_date", "present"])
else:
    att["sunday_date"] = pd.to_datetime(att["sunday_date"]).dt.date

mem = mem[mem["part"] == part]
cls = cls[cls["part"] == part]
present_ids = set(att[(att["sunday_date"] == sunday) & (att["present"] == True)]["member_id"])

tabs = st.tabs(["출석 체크" if is_admin else "출석 현황"] + (["명단 관리"] if is_admin else []))
tab_att = tabs[0]


def teacher_of(grade, no):
    m = cls[(cls["grade"] == grade) & (cls["class_no"] == no)]
    if m.empty or not isinstance(m.iloc[0]["teachers"], str):
        return ""
    return m.iloc[0]["teachers"].replace("\n", " · ")


def member_checks(df):
    """학생 체크박스 목록. 관리자만 변경 가능, 일반은 보기만."""
    if df.empty:
        st.caption("등록된 인원이 없습니다.")
        return
    for _, k in df.sort_values("sort_no").iterrows():
        checked = k["id"] in present_ids
        new = st.checkbox(k["name"], value=checked, key=f"a_{sunday}_{k['id']}",
                          disabled=not is_admin)
        if is_admin and new != checked:
            upsert("roster_attendance",
                   [{"member_id": k["id"], "sunday_date": sunday.isoformat(),
                     "present": bool(new)}], "member_id,sunday_date")
            st.rerun()


# ================================================================ 출석 체크 / 현황
with tab_att:
    total_enrolled = 0
    total_present = 0

    for grade, label, _ in GRADES:
        g = mem[mem["grade"] == grade]
        classes = sorted(set(g["class_no"].dropna().astype(int)) |
                         set(cls[cls["grade"] == grade]["class_no"].astype(int)))
        g_enrolled = g_present = 0
        st.markdown(f"#### {label}")
        for no in classes:
            kids = g[g["class_no"] == no]
            en = len(kids)
            pr = int(kids["id"].isin(present_ids).sum())
            g_enrolled += en
            g_present += pr
            with st.expander(f"{no}반 · {teacher_of(grade, no) or '담임 미입력'} · 재적 {en} · 출석 {pr}"):
                member_checks(kids)
        st.caption(f"**{label} 소계** 재적 {g_enrolled} · 출석 {g_present}")
        total_enrolled += g_enrolled
        total_present += g_present

    # 새싹반
    sp = mem[mem["grade"] == "새싹"]
    sp_en = len(sp)
    sp_pr = int(sp["id"].isin(present_ids).sum())
    st.markdown("#### 🌱 새싹반")
    with st.expander(f"{teacher_of('새싹', NONE_CLASS) or '담당 미입력'} · 재적 {sp_en} · 출석 {sp_pr}"):
        member_checks(sp)
    total_enrolled += sp_en
    total_present += sp_pr

    # 방문자
    vrow = pd.DataFrame()
    if not vis.empty:
        vrow = vis[(vis["part"] == part) & (pd.to_datetime(vis["sunday_date"]).dt.date == sunday)]
    cur_v = int(vrow.iloc[0]["count"]) if not vrow.empty else 0
    if is_admin:
        v_new = st.number_input("방문자 수", min_value=0, value=cur_v, step=1, key=f"v_{part}_{sunday}")
        if v_new != cur_v:
            upsert("roster_visitors", [{"part": part, "sunday_date": sunday.isoformat(),
                                        "count": int(v_new)}], "part,sunday_date")
            st.rerun()
    else:
        v_new = cur_v

    # 스탭
    st_m = mem[mem["grade"] == "스탭"]
    st_pr = int(st_m["id"].isin(present_ids).sum())
    st.markdown("#### 🧑‍🏫 스탭")
    with st.expander(f"교사 재적 {len(st_m)} · 출석 {st_pr}"):
        member_checks(st_m)

    st.divider()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("학생 재적", total_enrolled)
    m2.metric("학생 출석", total_present)
    m3.metric("방문자", int(v_new))
    m4.metric("교사 출석", st_pr)
    st.metric("전체(학생+교사+방문자) 출석 합계", total_present + st_pr + int(v_new))

# ================================================================ 명단 관리 (관리자만)
if is_admin:
    with tabs[1]:
        st.caption("이름은 쉼표 또는 줄바꿈으로 구분해 붙여넣을 수 있습니다. "
                   "저장하면 해당 반의 명단이 **입력한 내용으로 바뀝니다.** (빠진 이름은 삭제되고, 출석 기록도 함께 지워집니다.)")

        options = ([(g_, no_) for g_, _, _ in GRADES for no_ in range(1, 6)]
                   + [("새싹", NONE_CLASS), ("스탭", NONE_CLASS)])
        names_of = {a: b for a, b, _ in GRADES}

        def opt_label(o):
            g_, no_ = o
            if g_ == "새싹":
                return "🌱 새싹반"
            if g_ == "스탭":
                return "🧑‍🏫 스탭(교사)"
            return f"{names_of[g_]} {no_}반"

        sel = st.selectbox("편집할 반", options, format_func=opt_label)
        g, no = sel
        cur = mem[(mem["grade"] == g) & (mem["class_no"].fillna(0).astype(int) == no)].sort_values("sort_no")
        cur_names = "\n".join(cur["name"].tolist())
        cur_teacher = ""
        mt = cls[(cls["grade"] == g) & (cls["class_no"] == no)]
        if not mt.empty and isinstance(mt.iloc[0]["teachers"], str):
            cur_teacher = mt.iloc[0]["teachers"]

        with st.form(f"edit_{part}_{g}_{no}"):
            teachers_txt = st.text_area("담임샘 / 담당 (줄바꿈으로 구분)", value=cur_teacher, height=80)
            names_txt = st.text_area("이름 목록", value=cur_names, height=180,
                                     help="한 줄에 한 명, 또는 쉼표로 구분")
            saved = st.form_submit_button("저장", type="primary", use_container_width=True)

        if saved and is_admin:
            new_names = parse_names(names_txt)
            old = {r["name"]: r["id"] for _, r in cur.iterrows()}
            for n, mid in old.items():
                if n not in new_names:
                    delete("roster_members", mid)
            for i, n in enumerate(new_names):
                if n in old:
                    update("roster_members", old[n], {"sort_no": i})
                else:
                    insert("roster_members", {"part": part, "grade": g,
                                              "class_no": None if no == NONE_CLASS else no,
                                              "name": n, "sort_no": i})
            upsert("roster_classes", [{"part": part, "grade": g, "class_no": no,
                                       "teachers": teachers_txt.strip() or None}],
                   "part,grade,class_no")
            st.session_state["flash"] = f"{part} {opt_label(sel)} 명단을 저장했습니다."
            st.rerun()
