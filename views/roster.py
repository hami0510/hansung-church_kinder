import hashlib
from datetime import date, timedelta
from pathlib import Path
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from utils import db
from utils.db import fetch, insert, update, delete, upsert

st.title("📋 주일 출석부")

# 열람은 누구나, 출석 체크·명단 수정은 관리자 로그인한 사람만
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

# 표 컴포넌트 위치 확인 (components/roster_grid/index.html)
_GRID_DIR = Path(__file__).resolve().parent.parent / "components" / "roster_grid"
if not (_GRID_DIR / "index.html").exists():
    found = sorted(p.name for p in _GRID_DIR.glob("*")) if _GRID_DIR.exists() else "폴더 없음"
    st.error(f"표 파일(index.html)을 찾지 못했습니다. 위치: {_GRID_DIR} / 폴더 안 파일: {found}")
    st.stop()
_GRID = components.declare_component("roster_grid_v2", path=str(_GRID_DIR))


def parse_names(text: str):
    out = []
    for line in (text or "").replace(",", "\n").replace("，", "\n").splitlines():
        n = line.strip()
        if n and n not in out:
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
    att = pd.DataFrame(columns=["member_id", "sunday_date", "present", "reason"])
else:
    att["sunday_date"] = pd.to_datetime(att["sunday_date"]).dt.date
    if "reason" not in att.columns:
        att["reason"] = None

mem = mem[mem["part"] == part].copy()
mem["class_no"] = mem["class_no"].fillna(0).astype(int)
cls = cls[cls["part"] == part].copy()
cls["class_no"] = cls["class_no"].fillna(0).astype(int)

status = {}  # member_id -> [present, reason]
for _, a in att[att["sunday_date"] == sunday].iterrows():
    status[str(a["member_id"])] = [bool(a["present"]),
                                   a["reason"] if isinstance(a.get("reason"), str) else ""]

visitors = 0
if not vis.empty:
    vv = vis[(vis["part"] == part) & (pd.to_datetime(vis["sunday_date"]).dt.date == sunday)]
    if not vv.empty:
        visitors = int(vv.iloc[0]["count"])


def teacher_of(grade, no):
    m = cls[(cls["grade"] == grade) & (cls["class_no"] == no)]
    if m.empty or not isinstance(m.iloc[0]["teachers"], str):
        return ""
    return m.iloc[0]["teachers"]


def members_of(grade, no):
    df = mem[(mem["grade"] == grade) & (mem["class_no"] == no)].sort_values("sort_no")
    return [{"id": str(r["id"]), "name": str(r["name"])} for _, r in df.iterrows()]


def class_numbers(grade):
    g = mem[mem["grade"] == grade]
    base = set(range(1, DEFAULT_CLASSES.get(part, {}).get(grade, 0) + 1))
    nos = sorted(base | set(g["class_no"]) | set(cls[cls["grade"] == grade]["class_no"]))
    return [n for n in nos if n > 0]


names_of = {a: f"{b} {a}" for a, b, _ in GRADES}


def opt_label(o):
    g_, no_ = o
    if g_ == "새싹":
        return "🌱 새싹반"
    if g_ == "스탭":
        return "🧑‍🏫 스탭(교사)"
    return f"{names_of[g_]} {no_}반"


VIEWS = ["출석부"] + (["명단 관리"] if is_admin else [])
if st.session_state.get("rs_view") not in VIEWS:
    st.session_state["rs_view"] = VIEWS[0]
view = st.segmented_control("화면", VIEWS, key="rs_view", label_visibility="collapsed")
view = view or VIEWS[0]

# ================================================================ 출석부 (클릭 가능한 표)
if view == "출석부":
    if mem.empty:
        st.info("등록된 명단이 없습니다." + (" '명단 관리'에서 이름을 붙여넣어 등록하세요." if is_admin else ""))

    grades_arg = []
    for grade, age, color in GRADES:
        grades_arg.append({
            "grade": grade, "age": age, "color": color,
            "classes": [{"no": no, "teachers": teacher_of(grade, no),
                         "members": members_of(grade, no)} for no in class_numbers(grade)],
        })
    sprout = {"teachers": teacher_of("새싹", NONE_CLASS), "members": members_of("새싹", NONE_CLASS)}
    staff = {"members": members_of("스탭", NONE_CLASS)}

    counts = mem.groupby(["grade", "class_no"]).size() if not mem.empty else pd.Series(dtype=int)
    ncols = max(10, int(counts.max()) if len(counts) else 10)

    sig = "|".join(sorted(f"{r.id}:{r.name}:{r.grade}:{r.class_no}" for r in mem.itertuples())) \
        + "|".join(sorted(f"{r.grade}:{r.class_no}:{r.teachers}" for r in cls.itertuples()))
    token = f"{part}|{sunday}|{hashlib.md5(sig.encode('utf-8')).hexdigest()}"

    p = part.replace("부", "")
    value = _GRID(
        token=token, admin=is_admin, reasons=REASONS, ncols=ncols,
        title=f"{sunday.year}년 유치{p}부 {sunday.month}월 {sunday.day}일 ({WD[sunday.weekday()]})",
        grades=grades_arg, sprout=sprout, staff=staff, status=status, visitors=visitors,
        key=f"roster_grid_{part}_{sunday}", default=None)

    # 표에서 바뀐 내용 저장 (이미 저장된 값과 다른 것만)
    if is_admin and value and isinstance(value, dict):
        rows_up = []
        for mid, (pr, reason) in (value.get("state") or {}).items():
            cur = status.get(mid)
            if pr is None:
                if cur is not None:
                    db.get_client().table("roster_attendance").delete() \
                        .eq("member_id", mid).eq("sunday_date", sunday.isoformat()).execute()
                    db._fetch_cached.clear()
            else:
                want = [bool(pr), (reason or "") if not pr else ""]
                if cur != want:
                    rows_up.append({"member_id": mid, "sunday_date": sunday.isoformat(),
                                    "present": bool(pr), "reason": want[1] or None})
        if rows_up:
            upsert("roster_attendance", rows_up, "member_id,sunday_date")
        new_v = value.get("visitors")
        if isinstance(new_v, int) and new_v != visitors:
            upsert("roster_visitors", [{"part": part, "sunday_date": sunday.isoformat(),
                                        "count": int(new_v)}], "part,sunday_date")

    if is_admin:
        st.caption("이름을 누르면 출석(초록), 다시 누르면 해제됩니다. 결석이면 이름 아래 칸에서 사유를 고르세요. "
                   "변경은 즉시 저장됩니다.")

# ================================================================ 명단 관리
elif view == "명단 관리" and is_admin:
    st.caption("이름은 쉼표 또는 줄바꿈으로 구분해 붙여넣을 수 있습니다. "
               "저장하면 해당 반의 명단이 **입력한 내용으로 바뀝니다.** "
               "(빠진 이름은 삭제되고, 출석 기록도 함께 지워집니다.)")
    max_no = {g_: max(DEFAULT_CLASSES.get(part, {}).get(g_, 0), 5) for g_, _, _ in GRADES}
    options = ([(g_, n_) for g_, _, _ in GRADES for n_ in range(1, max_no[g_] + 1)]
               + [("새싹", NONE_CLASS), ("스탭", NONE_CLASS)])

    sel_key = f"edit_sel_{part}"
    pending_key = f"edit_next_{part}"
    if pending_key in st.session_state:
        st.session_state[sel_key] = st.session_state.pop(pending_key)
    if st.session_state.get(sel_key) not in options:
        st.session_state[sel_key] = options[0]
    st.selectbox("편집할 반", options, format_func=opt_label, key=sel_key)
    sel2 = st.session_state[sel_key]
    g2, no2 = sel2

    cur = members_of(g2, no2)
    cur_teacher = teacher_of(g2, no2)
    cur_names = "\n".join(m["name"] for m in cur)

    fk = f"{part}_{g2}_{no2}"
    with st.form(f"edit_form_{fk}"):
        teachers_txt = st.text_area("담임샘 / 담당 (줄바꿈으로 구분)", value=cur_teacher,
                                    height=80, key=f"t_{fk}")
        names_txt = st.text_area("이름 목록", value=cur_names, height=180,
                                 help="한 줄에 한 명, 또는 쉼표로 구분", key=f"n_{fk}")
        b1, b2 = st.columns(2)
        saved2 = b1.form_submit_button("저장", type="primary", use_container_width=True)
        saved_next = b2.form_submit_button("저장 후 다음 반", use_container_width=True)

    if saved2 or saved_next:
        new_names = parse_names(names_txt)
        old = {m["name"]: m["id"] for m in cur}
        for n, mid in old.items():
            if n not in new_names:
                delete("roster_members", mid)
        for i, n in enumerate(new_names):
            if n in old:
                update("roster_members", old[n], {"sort_no": i})
            else:
                insert("roster_members", {"part": part, "grade": g2,
                                          "class_no": None if no2 == NONE_CLASS else no2,
                                          "name": n, "sort_no": i})
        upsert("roster_classes", [{"part": part, "grade": g2, "class_no": no2,
                                   "teachers": teachers_txt.strip() or None}],
               "part,grade,class_no")
        st.session_state["flash"] = f"{part} {opt_label(sel2)} 저장 완료 ({len(new_names)}명)"
        if saved_next:
            i = options.index(sel2)
            st.session_state[pending_key] = options[(i + 1) % len(options)]
        st.rerun()
