from datetime import date, timedelta
import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, JsCode, GridUpdateMode
from utils import db
from utils.db import fetch, upsert

st.title("🧮 출석부 (표 클릭)")

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


if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

if is_admin:
    st.caption("이름 칸을 누르면 출결 팝업이 열립니다. (학생·담임·스탭 모두 동일)")
else:
    st.caption("🔒 출결 처리는 관리자 로그인 후 가능합니다.")

c1, c2 = st.columns(2)
part = c1.radio("부", PARTS, horizontal=True, key="rg_part")
upcoming = date.today() + timedelta(days=(6 - date.today().weekday()) % 7)
sunday = c2.date_input("주일 날짜", value=upcoming, key="rg_date")
mobile = st.toggle("📱 모바일 보기 (휴대폰에서는 켜 주세요)", key="rg_mobile")

mem = fetch("roster_members", "sort_no")
cls = fetch("roster_classes")
att = fetch("roster_attendance")
vis = fetch("roster_visitors")

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

visitors = 0
if not vis.empty:
    vv = vis[(vis["part"] == part) & (pd.to_datetime(vis["sunday_date"]).dt.date == sunday)]
    if not vv.empty:
        visitors = int(vv.iloc[0]["count"])


def members_of(grade, no):
    return mem[(mem["grade"] == grade) & (mem["class_no"] == no)].sort_values("sort_no")


def class_numbers(grade):
    g = mem[mem["grade"] == grade]
    base = set(range(1, DEFAULT_CLASSES.get(part, {}).get(grade, 0) + 1))
    nos = sorted(base | set(g["class_no"]) | set(cls[cls["grade"] == grade]["class_no"]))
    return [n for n in nos if n > 0]


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
    """학생 목록을 줄 단위(NC명)로 나눔 (최소 1줄)"""
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
    r = make_row(age="🌱새싹", en=len(sp), pr=sp_pr, bg="#e9f7ec")
    fill_names(r, sp)
    fill_teachers(r, "새싹", NONE_CLASS)
    rows.append(r)
    stu_en += len(sp)
    stu_pr += sp_pr
    rows.append(make_row(age="학생합계", en=stu_en, pr=stu_pr, bg="#e9ecef", nbg="#e9ecef"))
    rows.append(make_row(age="방문자", pr=visitors, bg="#ffffff"))

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
    rows.append(make_row(age="전체합계", pr=stu_pr + tch_pr + visitors, bg="#e9ecef", nbg="#e9ecef"))

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
        rows.append(make_row(lab="소계", lbg="#eef1f5", bg="#eef1f5", nbg="#eef1f5", cnt=f"{g_pr}/{g_en}"))
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
    rows.append(make_row(lab="학생합계", lbg="#e9ecef", bg="#e9ecef", nbg="#e9ecef", cnt=f"{stu_pr}/{stu_en}"))
    rows.append(make_row(lab="방문자", lbg="#ffffff", cnt=str(visitors)))

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
    rows.append(make_row(lab="교사합계", lbg="#e9ecef", bg="#e9ecef", nbg="#e9ecef", cnt=f"{tch_pr}/{tch_en}"))
    rows.append(make_row(lab="전체합계", lbg="#e9ecef", bg="#e9ecef", nbg="#e9ecef",
                         cnt=str(stu_pr + tch_pr + visitors)))

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
                         "minWidth": 40, "cellStyle": cell_style(f"ts{n}", bold=True), "sortable": False})
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

# 결석 사유 요약 (표 칸이 좁아 사유는 여기에 모아서 표시)
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
        if stamp != st.session_state.get("rg_last"):      # 같은 클릭은 한 번만 처리
            st.session_state["rg_last"] = stamp
            s = status.get(mid)
            attend_dialog(mid, label, sunday.isoformat(),
                          (s[0] if s else None), (s[1] if s else ""))
