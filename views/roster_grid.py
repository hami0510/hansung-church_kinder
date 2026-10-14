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
    row = {"age": "", "no": "", "tch": "", "en": "", "pr": "", "bg": "#ffffff", "nbg": "", "pick": ""}
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

base_style = JsCode("function(p){return {backgroundColor: p.data.bg || '#fff', fontWeight: '700', "
                    "textAlign: 'center', fontSize: '13px'};}")
col_defs = [
    {"field": "age", "headerName": "나이", "width": 90, "cellStyle": base_style, "sortable": False},
    {"field": "no", "headerName": "반", "width": 60, "cellStyle": base_style, "sortable": False},
    {"field": "tch", "headerName": "담임샘", "width": 110, "cellStyle": base_style, "sortable": False},
]
for n in range(1, NC + 1):
    style = J
