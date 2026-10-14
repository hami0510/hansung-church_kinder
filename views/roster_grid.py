from datetime import date, timedelta
import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, JsCode, GridUpdateMode
from utils import db
from utils.db import fetch, insert, update, delete, upsert

st.title("📋 주일 출석부")

is_admin = st.session_state.get("role") == "admin"

PARTS = ["1부", "2부"]
GRADES = [("조이", "5세", "#fff6c9"), ("해피", "6세", "#e3e8fb"), ("홀리", "7세", "#f6dff0")]
NONE_CLASS = 0
WD = "월화수목금토일"
REASONS = [
    "연락안됨", "병결(본인 혹은 가족)", "출근, 출장", "가족모임(명절, 여행 등)",
    "경조사(장례식, 결혼식)", "이사", "외국", "출산", "타교회", "1회성", "기타 개인사정", "대예배",
]
DEFAULT_CLASSES = {
    "1부": {"조이": 4, "해피": 4, "홀리": 4},
    "2부": {"조이": 5, "해피": 3, "홀리": 5},
}
STUDENT_GRADES = ["조이", "해피", "홀리", "새싹"]
MOBILE_COLS = 5


def tg(grade):          # 담임 구분 이름 (예: 담임조이)
    return f"담임{grade}"


def parse_names(text: str):
    out = []
    for line in (text or "").replace(",", "\n").replace("，", "\n").splitlines():
        n = line.strip()
        if n and n not in out:
            out.append(n)
    return out


if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

c1, c2 = st.columns(2)
part = c1.radio("부", PARTS, horizontal=True, key="rg_part")
upcoming = date.today() + timedelta(days=(6 - date.today().weekday()) % 7)
sunday = c2.date_input("주일 날짜", value=upcoming, key="rg_date")

mem = fetch("roster_members", "sort_no")
cls = fetch("roster_classes")
att = fetch("roster_attendance")

if mem.empty:
    mem = pd.DataFrame(columns=["id", "part", "grade", "class_no", "name", "sort_no"])
if cls.empty:
    cls = pd.DataFrame(columns=["id", "part", "grade", "class_no", "teachers"])
if att.empty:
    att = pd.DataFrame(columns=["member_id", "sunday_date", "present", "reason"])
else:
    att["sunday_date"] = pd.to_datetime(att["sunday_date"]).dt.date
    if "reason" not in att.columns:
        att["reason"] = None

mem = mem[mem["part"] == part].copy()
mem["class_no"] = mem["class_no"].fillna(0).astype(int)
cls = cls[cls["part"] == part].copy()
cls["class_no"] = cls["class_no"].fillna(0).astype(int)

status = {}
for _, a in att[att["sunday_date"] == sunday].iterrows():
    status[a["member_id"]] = (bool(a["present"]),
                              a["reason"] if isinstance(a.get("reason"), str) else "")


def members_of(grade, no):
    return mem[(mem["grade"] == grade) & (mem["class_no"] == no)].sort_values("sort_no")


def teacher_text(grade, no):
    m = cls[(cls["grade"] == grade) & (cls["class_no"] == no)]
    if m.empty or not isinstance(m.iloc[0]["teachers"], str):
        return ""
    return m.iloc[0]["teachers"]


def class_numbers(grade):
    g = mem[mem["grade"] == grade]
    base = set(range(1, DEFAULT_CLASSES.get(part, {}).get(grade, 0) + 1))
    nos = sorted(base | set(g["class_no"]) | set(cls[cls["grade"] == grade]["class_no"]))
    return [n for n in nos if n > 0]


names_of = {a: f"{b} {a}" for a, b, _ in GRADES}

# ---------------------------------------------------------------- 화면 선택
VIEWS = ["출석부"] + (["명단 관리"] if is_admin else [])
if st.session_state.get("rg_view") not in VIEWS:
    st.session_state["rg_view"] = VIEWS[0]
view = st.segmented_control("화면", VIEWS, key="rg_view", label_visibility="collapsed")
view = view or VIEWS[0]

# ================================================================ 명단 관리 (관리자)
if view == "명단 관리" and is_admin:
    st.caption("담임샘과 학생 이름을 쉼표 또는 줄바꿈으로 구분해 입력하세요. "
               "저장하면 해당 반이 **입력한 내용으로 바뀝니다.** "
               "(빠진 이름은 삭제되고, 그 이름의 출결 기록도 함께 지워집니다.)")
    max_no = {g_: max(DEFAULT_CLASSES.get(part, {}).get(g_, 0), 5) for g_, _, _ in GRADES}
    options = ([(g_, n_) for g_, _, _ in GRADES for n_ in range(1, max_no[g_] + 1)]
               + [("새싹", NONE_CLASS), ("스탭", NONE_CLASS)])

    def opt_label(o):
        g_, n_ = o
        if g_ == "새싹":
            return "🌱 새싹반"
        if g_ == "스탭":
            return "🧑‍🏫 스탭(교사)"
        return f"{names_of[g_]} {n_}반"

    sel_key = f"ed_sel_{part}"
    pend_key = f"ed_next_{part}"
    if pend_key in st.session_state:
        st.session_state[sel_key] = st.session_state.pop(pend_key)
    if st.session_state.get(sel_key) not in options:
        st.session_state[sel_key] = options[0]
    st.selectbox("편집할 반", options, format_func=opt_label, key=sel_key)
    g2, no2 = st.session_state[sel_key]
    has_teacher = g2 != "스탭"

    cur_stu = members_of(g2, no2)
    cur_tch = members_of(tg(g2), no2) if has_teacher else mem.iloc[0:0]
    tch_default = "\n".join(cur_tch["name"].tolist()) if not cur_tch.empty else (
        teacher_text(g2, no2) if has_teacher else "")

    fk = f"{part}_{g2}_{no2}"
    with st.form(f"ed_form_{fk}"):
        tch_txt = ""
        if has_teacher:
            tch_txt = st.text_area("담임샘 (출결 대상)", value=tch_default, height=80, key=f"et_{fk}")
        stu_txt = st.text_area("스탭 이름" if g2 == "스탭" else "학생 이름",
                               value="\n".join(cur_stu["name"].tolist()), height=180, key=f"es_{fk}")
        b1, b2 = st.columns(2)
        saved = b1.form_submit_button("저장", type="primary", use_container_width=True)
        saved_next = b2.form_submit_button("저장 후 다음 반", use_container_width=True)

    if saved or saved_next:
        cls_no = None if no2 == NONE_CLASS else no2

        def sync(grade_name, cur_df, new_names):
            old = {r["name"]: r["id"] for _, r in cur_df.iterrows()}
            for nm, mid in old.items():
                if nm not in new_names:
                    delete("roster_members", mid)
            for i, nm in enumerate(new_names):
                if nm in old:
                    update("roster_members", old[nm], {"sort_no": i})
                else:
                    insert("roster_members", {"part": part, "grade": grade_name,
                                              "class_no": cls_no, "name": nm, "sort_no": i})

        sync(g2, cur_stu, parse_names(stu_txt))
        if has_teacher:
            t_names = parse_names(tch_txt)
            sync(tg(g2), cur_tch, t_names)
            upsert("roster_classes", [{"part": part, "grade": g2, "class_no": no2,
                                       "teachers": "\n".join(t_names) or None}],
                   "part,grade,class_no")
        st.session_state["flash"] = f"{part} {opt_label((g2, no2))} 저장 완료"
        if saved_next:
            i = options.index((g2, no2))
            st.session_state[pend_key] = options[(i + 1) % len(options)]
        st.rerun()
    st.stop()

# ================================================================ 출석부 (표 클릭)
if is_admin:
    st.caption("이름 칸을 누르면 출결 팝업이 열립니다. (학생·담임·스탭 모두 동일)")
else:
    st.caption("🔒 출결 처리는 관리자 로그인 후 가능합니다.")

mobile = st.toggle("📱 모바일 보기 (휴대폰에서는 켜 주세요)", key="rg_mobile")

stu = mem[mem["grade"].isin(STUDENT_GRADES)]
counts = stu.groupby(["grade", "class_no"]).size() if not stu.empty else pd.Series(dtype=int)
NC = MOBILE_COLS if mobile else max(10, int(counts.max()) if len(counts) else 10)
tm = mem[mem["grade"].str.startswith("담임")]
tcounts = tm.groupby(["grade", "class_no"]).size() if not tm.empty else pd.Series(dtype=int)
TN = max(2, int(tcounts.max()) if len(tcounts) else 2)


def count_pr(df):
    return int(sum(1 for i in df["id"] if status.get(i, (False, ""))[0]))


def make_row(**kw):
    row = {"age": "", "no": "", "en": "", "pr": "", "lab": "", "cnt": "",
           "bg": "#ffffff", "lbg": "#ffffff", "nbg": "", "tb": "", "pick": ""}
    for n in range(1, NC + 1):
        row[f"c{n}"] = ""
        row[f"i{n}"] = ""
        row[f"s{n}"] = ""
    if not mobile:
        for n in range(1, TN + 1):
            row[f"t{n}"] = ""
            row[f"ti{n}"] = ""
            row[f"ts{n}"] = ""
    row.update(kw)
    return row


def flag_of(mid):
    s = status.get(mid)
    if s is None:
        return ""
    return "on" if s[0] else "off"


def fill_names(row, kids_df, offset=0):
    sub = kids_df.iloc[offset:offset + NC]
    for n, (_, k) in enumerate(sub.iterrows(), start=1):
        row[f"c{n}"], row[f"i{n}"], row[f"s{n}"] = str(k["name"]), str(k["id"]), flag_of(k["id"])


def fill_teachers(row, grade, no):
    kids = members_of(tg(grade), no)
    for n, (_, k) in enumerate(kids.head(TN).iterrows(), start=1):
        row[f"t{n}"], row[f"ti{n}"], row[f"ts{n}"] = str(k["name"]), str(k["id"]), flag_of(k["id"])


def chunks(df):
    total = max(len(df), 1)
    return list(range(0, total, NC))


rows = []
stu_en = stu_pr = 0

if not mobile:
    # ---------------------------------------------------------------- PC 표 (10칸)
    for grade, age, color in GRADES:
        nos = class_numbers(grade)
        if not nos:
            continue
        g_en = g_pr = 0
        for idx, no in enumerate(nos):
            kids = members_of(grade, no)
            en, pr = len(kids), count_pr(kids)
            g_en += en
            g_pr += pr
            r = make_row(age=f"{age} {grade}" if idx == 0 else "", no=str(no), en=en, pr=pr, bg=color)
            fill_names(r, kids)
            fill_teachers(r, grade, no)
            rows.append(r)
            for extra in range(NC, len(kids), NC):
                r2 = make_row(bg=color)
                fill_names(r2, kids, extra)
                rows.append(r2)
        rows.append(make_row(no="소계", en=g_en, pr=g_pr, bg="#eef1f5", nbg="#eef1f5"))
        stu_en += g_en
        stu_pr += g_pr

    sp = members_of("새싹", NONE_CLASS)
    sp_pr = count_pr(sp)
    for off in range(0, max(len(sp), 1), NC):
        r = make_row(age="🌱새싹" if off == 0 else "", en=len(sp) if off == 0 else "",
                     pr=sp_pr if off == 0 else "", bg="#e9f7ec")
        fill_names(r, sp, off)
        if off == 0:
            fill_teachers(r, "새싹", NONE_CLASS)
        rows.append(r)
    stu_en += len(sp)
    stu_pr += sp_pr
    rows.append(make_row(age="학생합계", en=stu_en, pr=stu_pr, bg="#e9ecef", nbg="#e9ecef"))

    stf = members_of("스탭", NONE_CLASS)
    stf_pr = count_pr(stf)
    for off in range(0, max(len(stf), 1), NC):
        r = make_row(age="스탭" if off == 0 else "", en=len(stf) if off == 0 else "",
                     pr=stf_pr if off == 0 else "", bg="#fafbfc")
        fill_names(r, stf, off)
        rows.append(r)

    tch_all = mem[mem["grade"].str.startswith("담임")]
    tch_en = len(tch_all) + len(stf)
    tch_pr = count_pr(tch_all) + stf_pr
    rows.append(make_row(age="교사합계", en=tch_en, pr=tch_pr, bg="#e9ecef", nbg="#e9ecef"))
    rows.append(make_row(age="전체합계", pr=stu_pr + tch_pr, bg="#e9ecef", nbg="#e9ecef"))

else:
    # ---------------------------------------------------------------- 모바일 표 (5칸)
    def teacher_row(label, grade, no, color):
        kids = members_of(tg(grade), no)
        r = make_row(lab=label, lbg=color, bg=color, tb="1")
        fill_names(r, kids.head(NC))
        rows.append(r)

    for grade, age, color in GRADES:
        nos = class_numbers(grade)
        if not nos:
            continue
        g_en = g_pr = 0
        for no in nos:
            kids = members_of(grade, no)
            en, pr = len(kids), count_pr(kids)
            g_en += en
            g_pr += pr
            teacher_row(f"{grade}{no}", grade, no, color)
            for k, off in enumerate(chunks(kids)):
                r = make_row(lab="", lbg=color, cnt=f"{pr}/{en}" if k == 0 else "")
                fill_names(r, kids, off)
                rows.append(r)
        rows.append(make_row(lab="소계", lbg="#eef1f5", bg="#eef1f5", nbg="#eef1f5",
                             cnt=f"{g_pr}/{g_en}"))
        stu_en += g_en
        stu_pr += g_pr

    sp = members_of("새싹", NONE_CLASS)
    sp_pr = count_pr(sp)
    teacher_row("🌱새싹", "새싹", NONE_CLASS, "#e9f7ec")
    for k, off in enumerate(chunks(sp)):
        r = make_row(lab="", lbg="#e9f7ec", cnt=f"{sp_pr}/{len(sp)}" if k == 0 else "")
        fill_names(r, sp, off)
        rows.append(r)
    stu_en += len(sp)
    stu_pr += sp_pr
    rows.append(make_row(lab="학생합계", lbg="#e9ecef", bg="#e9ecef", nbg="#e9ecef",
                         cnt=f"{stu_pr}/{stu_en}"))

    stf = members_of("스탭", NONE_CLASS)
    stf_pr = count_pr(stf)
    for k, off in enumerate(chunks(stf)):
        r = make_row(lab="스탭" if k == 0 else "", lbg="#fafbfc",
                     cnt=f"{stf_pr}/{len(stf)}" if k == 0 else "")
        fill_names(r, stf, off)
        rows.append(r)

    tch_all = mem[mem["grade"].str.startswith("담임")]
    tch_en = len(tch_all) + len(stf)
    tch_pr = count_pr(tch_all) + stf_pr
    rows.append(make_row(lab="교사합계", lbg="#e9ecef", bg="#e9ecef", nbg="#e9ecef",
                         cnt=f"{tch_pr}/{tch_en}"))
    rows.append(make_row(lab="전체합계", lbg="#e9ecef", bg="#e9ecef", nbg="#e9ecef",
                         cnt=str(stu_pr + tch_pr)))

df = pd.DataFrame(rows)
df["pick"] = ""

FS = "12px" if mobile else "11px"
base_style = JsCode("function(p){return {backgroundColor: p.data.bg || '#fff', fontWeight: '700', "
                    "textAlign: 'center', fontSize: '%s', padding: '0 1px'};}" % FS)
lab_style = JsCode("function(p){return {backgroundColor: p.data.lbg || '#fff', fontWeight: '700', "
                   "textAlign: 'center', fontSize: '%s', padding: '0 1px', lineHeight: '14px', "
                   "whiteSpace: 'normal'};}" % FS)


def cell_style(flag_field, bold=False):
    return JsCode(
        "function(p){var s=p.data.%s; var b={textAlign:'center',fontSize:'%s',padding:'0 1px',"
        "cursor:'pointer',lineHeight:'14px',whiteSpace:'normal',wordBreak:'break-all'%s};"
        "if(s==='on'){b.backgroundColor='#b2f2bb';b.color='#1b6e2a';b.fontWeight='700';}"
        "else if(s==='off'){b.backgroundColor='#ffe3e3';b.color='#c92a2a';b.fontWeight='700';}"
        "else if(p.data.nbg){b.backgroundColor=p.data.nbg;}"
        "else if(p.data.tb==='1'||%s){b.backgroundColor=p.data.bg;b.fontWeight='700';}"
        "return b;}" % (flag_field, FS, ",fontWeight:'700'" if bold else "", "true" if bold else "false"))


if mobile:
    col_defs = [{"field": "lab", "headerName": "반", "width": 52, "minWidth": 44,
                 "cellStyle": lab_style, "sortable": False}]
    for n in range(1, NC + 1):
        col_defs.append({"field": f"c{n}", "headerName": "이름" if n == 1 else "", "width": 62,
                         "minWidth": 50, "cellStyle": cell_style(f"s{n}"), "sortable": False})
        col_defs.append({"field": f"i{n}", "hide": True})
        col_defs.append({"field": f"s{n}", "hide": True})
    col_defs.append({"field": "cnt", "headerName": "출/재", "width": 46, "minWidth": 40,
                     "cellStyle": base_style, "sortable": False})
    row_h, head_h = 36, 30
else:
    col_defs = [
        {"field": "age", "headerName": "나이", "width": 54, "minWidth": 40,
         "cellStyle": base_style, "sortable": False},
        {"field": "no", "headerName": "반", "width": 34, "minWidth": 26,
         "cellStyle": base_style, "sortable": False},
    ]
    for n in range(1, TN + 1):
        col_defs.append({"field": f"t{n}", "headerName": "담임샘" if n == 1 else "", "width": 52,
                         "minWidth": 40, "cellStyle": cell_style(f"ts{n}", bold=True),
                         "sortable": False})
        col_defs.append({"field": f"ti{n}", "hide": True})
        col_defs.append({"field": f"ts{n}", "hide": True})
    for n in range(1, NC + 1):
        col_defs.append({"field": f"c{n}", "headerName": str(n), "width": 50, "minWidth": 32,
                         "cellStyle": cell_style(f"s{n}"), "sortable": False})
        col_defs.append({"field": f"i{n}", "hide": True})
        col_defs.append({"field": f"s{n}", "hide": True})
    col_defs += [
        {"field": "en", "headerName": "재적", "width": 40, "minWidth": 30,
         "cellStyle": base_style, "sortable": False},
        {"field": "pr", "headerName": "출석", "width": 40, "minWidth": 30,
         "cellStyle": base_style, "sortable": False},
    ]
    row_h, head_h = 28, 28

col_defs += [
    {"field": "bg", "hide": True},
    {"field": "lbg", "hide": True},
    {"field": "nbg", "hide": True},
    {"field": "tb", "hide": True},
    {"field": "pick", "hide": True},
]

grid_options = {
    "columnDefs": col_defs,
    "rowHeight": row_h,
    "headerHeight": head_h,
    "suppressMovableColumns": True,
    "suppressCellFocus": True,
    "defaultColDef": {"resizable": False},
    "rowSelection": "single",
    "suppressRowClickSelection": False,
    "onCellClicked": JsCode(
        "function(e){var f=e.colDef.field||'';var m=/^(c|t)([0-9]+)$/.exec(f);if(!m)return;"
        "var id=e.data[(m[1]==='c'?'i':'ti')+m[2]];"
        "e.node.setDataValue('pick', id ? (id+'|'+e.value+'|'+Date.now()) : '');}"),
}

ver = st.session_state.get("rg_ver", 0)
p = part.replace("부", "")
st.markdown(f"**{sunday.year}년 유치{p}부 {sunday.month}월 {sunday.day}일 ({WD[sunday.weekday()]})**")

resp = AgGrid(
    df, gridOptions=grid_options, allow_unsafe_jscode=True,
    update_mode=GridUpdateMode.SELECTION_CHANGED | GridUpdateMode.VALUE_CHANGED,
    height=head_h + row_h * len(df) + 6, fit_columns_on_grid_load=True,
    key=f"rg_grid_{part}_{sunday}_{ver}_{int(bool(mobile))}")

name_of = {r["id"]: str(r["name"]) for _, r in mem.iterrows()}
absent = [f"{name_of[m]}({s[1] or '사유 없음'})" for m, s in status.items()
          if (not s[0]) and m in name_of]
if absent:
    st.caption("❌ 결석: " + ", ".join(absent))
st.caption("초록 = 출석 · 빨강 = 결석 · 흰색 = 미확인" + (" · 출/재 = 출석/재적" if mobile else ""))


@st.dialog("출결 처리")
def attend_dialog(member_id: str, name: str, d_iso: str, cur_present, cur_reason: str):
    d = date.fromisoformat(d_iso)
    st.markdown(f"### {name}")
    st.caption(f"{d.month}월 {d.day}일 ({WD[d.weekday()]}) · {part}")
    choice = st.radio("출결", ["출석", "결석"], horizontal=True,
                      index=1 if cur_present is False else 0, key=f"rgd_c_{member_id}")
    reason = None
    if choice == "결석":
        opts = ["(사유 선택)"] + REASONS
        idx = opts.index(cur_reason) if cur_reason in opts else 0
        reason = st.selectbox("결석 사유", opts, index=idx, key=f"rgd_r_{member_id}")
        if reason == "(사유 선택)":
            reason = None
    b1, b2 = st.columns(2)
    if b1.button("저장", type="primary", use_container_width=True, key=f"rgd_s_{member_id}"):
        upsert("roster_attendance",
               [{"member_id": member_id, "sunday_date": d_iso, "present": choice == "출석",
                 "reason": reason if choice == "결석" else None}], "member_id,sunday_date")
        st.session_state["rg_ver"] = st.session_state.get("rg_ver", 0) + 1
        st.rerun()
    if b2.button("기록 지우기", use_container_width=True, key=f"rgd_d_{member_id}"):
        db.get_client().table("roster_attendance").delete() \
            .eq("member_id", member_id).eq("sunday_date", d_iso).execute()
        db._fetch_cached.clear()
        st.session_state["rg_ver"] = st.session_state.get("rg_ver", 0) + 1
        st.rerun()


if is_admin:
    picked = None
    try:
        sel = resp["selected_rows"]
        if sel is not None and len(sel) > 0:
            first = sel.iloc[0] if hasattr(sel, "iloc") else sel[0]
            picked = first.get("pick") if hasattr(first, "get") else None
    except Exception:
        picked = None
    if picked and str(picked).count("|") >= 2:
        mid, label, stamp = str(picked).split("|", 2)
        if stamp != st.session_state.get("rg_last"):
            st.session_state["rg_last"] = stamp
            s = status.get(mid)
            attend_dialog(mid, label, sunday.isoformat(),
                          (s[0] if s else None), (s[1] if s else ""))

    # ------------------------------------------------------------ 새신자 추가 (관리자)
    st.divider()
    st.markdown("#### 🌟 새신자 추가")
    st.caption("이름을 입력하면 🌱 새싹반 맨 끝에 추가되고, 선택한 주일 날짜 출석으로 기록됩니다.")

    with st.form(f"newcomer_{part}", clear_on_submit=True):
        new_name = st.text_input("새신자 이름")
        add_ok = st.form_submit_button("새신자 추가", type="primary", use_container_width=True)
    if add_ok:
        nm = new_name.strip()
        if not nm:
            st.error("이름을 입력해 주세요.")
        elif nm in set(members_of("새싹", NONE_CLASS)["name"]):
            st.warning(f"새싹반에 이미 '{nm}'이(가) 있습니다.")
        else:
            order = len(members_of("새싹", NONE_CLASS))
            res = db.get_client().table("roster_members").insert(
                {"part": part, "grade": "새싹", "class_no": None,
                 "name": nm, "sort_no": order}).execute()
            db._fetch_cached.clear()
            try:
                new_id = res.data[0]["id"]
                upsert("roster_attendance",
                       [{"member_id": new_id, "sunday_date": sunday.isoformat(),
                         "present": True, "reason": None}], "member_id,sunday_date")
            except Exception:
                pass
            st.session_state["rg_ver"] = st.session_state.get("rg_ver", 0) + 1
            st.session_state["flash"] = f"새신자 '{nm}'을(를) 새싹반에 추가했습니다. (출석 처리됨)"
            st.rerun()
