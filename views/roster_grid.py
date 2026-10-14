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

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

if is_admin:
    st.caption("이름 칸을 누르면 출결 팝업이 열립니다.")
else:
    st.caption("🔒 출결 처리는 관리자 로그인 후 가능합니다.")

c1, c2 = st.columns(2)
part = c1.radio("부", PARTS, horizontal=True, key="rg_part")
upcoming = date.today() + timedelta(days=(6 - date.today().weekday()) % 7)
sunday = c2.date_input("주일 날짜", value=upcoming, key="rg_date")

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


def teacher_of(grade, no):
    m = cls[(cls["grade"] == grade) & (cls["class_no"] == no)]
    if m.empty or not isinstance(m.iloc[0]["teachers"], str):
        return ""
    return m.iloc[0]["teachers"].replace("\n", " / ")


def members_of(grade, no):
    return mem[(mem["grade"] == grade) & (mem["class_no"] == no)].sort_values("sort_no")


def class_numbers(grade):
    g = mem[mem["grade"] == grade]
    base = set(range(1, DEFAULT_CLASSES.get(part, {}).get(grade, 0) + 1))
    nos = sorted(base | set(g["class_no"]) | set(cls[cls["grade"] == grade]["class_no"]))
    return [n for n in nos if n > 0]


counts = mem.groupby(["grade", "class_no"]).size() if not mem.empty else pd.Series(dtype=int)
NC = max(10, int(counts.max()) if len(counts) else 10)


def count_pr(df):
    return int(sum(1 for i in df["id"] if status.get(i, (False, ""))[0]))


def make_row(**kw):
    row = {"age": "", "no": "", "tch": "", "en": "", "pr": "", "bg": "#ffffff", "nbg": ""}
    for n in range(1, NC + 1):
        row[f"c{n}"] = ""
        row[f"i{n}"] = ""
        row[f"s{n}"] = ""
    row.update(kw)
    return row


def fill_names(row, kids_df, offset=0):
    sub = kids_df.iloc[offset:offset + NC]
    for n, (_, k) in enumerate(sub.iterrows(), start=1):
        s = status.get(k["id"])
        text = str(k["name"])
        flag = ""
        if s is not None:
            if s[0]:
                flag = "on"
            else:
                flag = "off"
                if s[1]:
                    text = f"{text} · {s[1]}"
        row[f"c{n}"], row[f"i{n}"], row[f"s{n}"] = text, str(k["id"]), flag


rows = []
stu_en = stu_pr = 0
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
        r = make_row(age=f"{age} {grade}" if idx == 0 else "", no=str(no),
                     tch=teacher_of(grade, no), en=en, pr=pr, bg=color)
        fill_names(r, kids)
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
r = make_row(age="🌱 새싹반", tch=teacher_of("새싹", NONE_CLASS), en=len(sp), pr=sp_pr, bg="#e9f7ec")
fill_names(r, sp)
rows.append(r)
stu_en += len(sp)
stu_pr += sp_pr
rows.append(make_row(age="학생 합계", en=stu_en, pr=stu_pr, bg="#e9ecef", nbg="#e9ecef"))
rows.append(make_row(age="방문자", pr=visitors, bg="#ffffff"))

stf = members_of("스탭", NONE_CLASS)
stf_pr = count_pr(stf)
r = make_row(age="스탭(교사)", en=len(stf), pr=stf_pr, bg="#fafbfc")
fill_names(r, stf)
rows.append(r)
rows.append(make_row(age="전체 합계", pr=stu_pr + stf_pr + visitors, bg="#e9ecef", nbg="#e9ecef"))

df = pd.DataFrame(rows)
df["pick"] = ""

base_style = JsCode("function(p){return {backgroundColor: p.data.bg || '#fff', fontWeight: '700', "
                    "textAlign: 'center', fontSize: '13px'};}")
col_defs = [
    {"field": "age", "headerName": "나이", "width": 90, "cellStyle": base_style, "sortable": False},
    {"field": "no", "headerName": "반", "width": 60, "cellStyle": base_style, "sortable": False},
    {"field": "tch", "headerName": "담임샘", "width": 110, "cellStyle": base_style, "sortable": False},
]
for n in range(1, NC + 1):
    style = JsCode(
        "function(p){var s=p.data.s%d; var base={textAlign:'center',fontSize:'13px',cursor:'pointer'};"
        "if(s==='on'){base.backgroundColor='#b2f2bb';base.color='#1b6e2a';base.fontWeight='700';}"
        "else if(s==='off'){base.backgroundColor='#ffe3e3';base.color='#c92a2a';}"
        "else if(p.data.nbg){base.backgroundColor=p.data.nbg;}"
        "return base;}" % n)
    col_defs.append({"field": f"c{n}", "headerName": str(n), "width": 92,
                     "cellStyle": style, "sortable": False})
    col_defs.append({"field": f"i{n}", "hide": True})
    col_defs.append({"field": f"s{n}", "hide": True})
col_defs += [
    {"field": "en", "headerName": "재적", "width": 70, "cellStyle": base_style, "sortable": False},
    {"field": "pr", "headerName": "출석", "width": 70, "cellStyle": base_style, "sortable": False},
    {"field": "bg", "hide": True},
    {"field": "nbg", "hide": True},
    {"field": "pick", "hide": True},
]

grid_options = {
    "columnDefs": col_defs,
    "rowHeight": 36,
    "headerHeight": 36,
    "suppressMovableColumns": True,
    "suppressCellFocus": True,
    "defaultColDef": {"resizable": False},
    "rowSelection": "single",
    "suppressRowClickSelection": False,
    "onCellClicked": JsCode(
        "function(e){var f=e.colDef.field||'';"
        "if(f.charAt(0)==='c' && /^[0-9]+$/.test(f.substring(1))){"
        "var id=e.data['i'+f.substring(1)];"
        "e.node.setDataValue('pick', id ? (id+'|'+e.value) : '');"
        "}}"),
}

ver = st.session_state.get("rg_ver", 0)
p = part.replace("부", "")
st.markdown(f"**{sunday.year}년 유치{p}부 {sunday.month}월 {sunday.day}일 ({WD[sunday.weekday()]})**")

resp = AgGrid(
    df, gridOptions=grid_options, allow_unsafe_jscode=True,
    update_mode=GridUpdateMode.SELECTION_CHANGED | GridUpdateMode.VALUE_CHANGED,
    height=min(900, 40 + 36 * len(df) + 6), fit_columns_on_grid_load=False,
    key=f"rg_grid_{part}_{sunday}_{ver}")


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
    if picked and "|" in str(picked):
        mid, label = str(picked).split("|", 1)
        st.session_state["rg_ver"] = ver + 1
        s = status.get(mid)
        attend_dialog(mid, label.split(" · ")[0], sunday.isoformat(),
                      (s[0] if s else None), (s[1] if s else ""))
