from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, JsCode, GridUpdateMode
from utils.db import fetch, fetch_where, insert, update, delete, delete_where, upsert

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
CUSTOM = "상세(직접 입력)"
PLAN_STATES = ["예정", "불참", "미정"]
STAGE_PLAN = "📝 예정 (주중)"
STAGE_REAL = "✅ 실제 (주일)"
DEFAULT_CLASSES = {
    "1부": {"조이": 4, "해피": 4, "홀리": 4},
    "2부": {"조이": 5, "해피": 3, "홀리": 5},
}
STUDENT_GRADES = ["조이", "해피", "홀리", "새싹"]
MOBILE_COLS = 5
TOT = "#d6e4f2"       # 합계 줄 배경
SUB = "#eef3f8"       # 소계 줄 배경
BARMAP = {"#fff6c9": "#f2c744", "#e3e8fb": "#6c8eef", "#f6dff0": "#d67bb8",
          "#e9f7ec": "#5cb87a", SUB: "#8795a8", TOT: "#4f6b88", "#fafbfc": "#a3b1c2"}
KST = ZoneInfo("Asia/Seoul")

st.markdown("""
<style>
.st-key-ctl {background: #f3f9ff; border: 1px solid #cfe5f8 !important; border-radius: 16px !important;
             padding: .4rem .8rem !important; margin-bottom: .6rem;}
.sumcards {display: flex; gap: .5rem; flex-wrap: wrap; margin: .2rem 0 .7rem;}
.sumcard {flex: 1 1 110px; background: #fff; border: 1px solid #cfe5f8; border-radius: 14px;
          padding: .55rem .8rem; text-align: center;}
.sumcard .t {font-size: .74rem; color: #6b7c93; font-weight: 700;}
.sumcard .v {font-size: 1.35rem; font-weight: 800; color: #1b3a5c; line-height: 1.3;}
.sumcard .v small {font-size: .8rem; font-weight: 600; color: #8a97a8;}
.sumcard.hi {background: #e6f9e9; border-color: #b2f2bb;}
.sumcard.hi .v {color: #1b6e2a;}
.sumcard.warn {background: #fff9db; border-color: #ffe066;}
.sumcard.bad {background: #fff5f5; border-color: #ffc9c9;}
.sumcard.bad .v {color: #b91c1c;}
.rg-title {font-size: 1.05rem; font-weight: 800; color: #1b3a5c; margin: .2rem 0 .4rem;}
.rg-legend {display: flex; gap: .5rem; flex-wrap: wrap; font-size: .78rem; margin: .4rem 0;}
.rg-legend span {padding: .1rem .55rem; border-radius: 999px; font-weight: 700;}
.cmpbox {background: #f3f9ff; border: 1px solid #cfe5f8; border-radius: 14px; padding: .55rem .9rem;
         margin: .2rem 0 .7rem; font-weight: 700; color: #1b3a5c;}
.cmpbox .d {font-size: 1.05rem;}
@media (max-width: 640px) {
  .sumcards {gap: .3rem; flex-wrap: nowrap;}
  .sumcard {flex: 1 1 0; padding: .35rem .2rem; border-radius: 10px; min-width: 0;}
  .sumcard .t {font-size: .62rem;}
  .sumcard .v {font-size: 1.05rem;}
  .sumcard .v small {font-size: .62rem;}
}
</style>
""", unsafe_allow_html=True)


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

with st.container(key="ctl"):
    c1, c2 = st.columns(2)
    part = c1.radio("부", PARTS, horizontal=True, key="rg_part")
    _today = datetime.now(KST).date()
    upcoming = _today + timedelta(days=(6 - _today.weekday()) % 7)
    sunday = c2.date_input("주일 날짜", value=upcoming, key="rg_date")

mem = fetch("roster_members", "sort_no")
cls = fetch("roster_classes")
att = fetch_where("roster_attendance", sunday_date=sunday.isoformat())
try:
    plan = fetch_where("roster_plan", sunday_date=sunday.isoformat())
    plan_ok_table = True
except Exception:
    plan = pd.DataFrame()
    plan_ok_table = False

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
if plan.empty:
    plan = pd.DataFrame(columns=["member_id", "sunday_date", "status", "reason"])
else:
    plan["sunday_date"] = pd.to_datetime(plan["sunday_date"]).dt.date

mem = mem[mem["part"] == part].copy()
mem["class_no"] = mem["class_no"].fillna(0).astype(int)
cls = cls[cls["part"] == part].copy()
cls["class_no"] = cls["class_no"].fillna(0).astype(int)

part_ids = set(mem["id"])      # 선택한 부의 명단 id (다른 부 기록이 섞이지 않게)

status = {}      # 실제 출결: member_id -> (present, reason)
for _, a in att[(att["sunday_date"] == sunday) & (att["member_id"].isin(part_ids))].iterrows():
    status[a["member_id"]] = (bool(a["present"]),
                              a["reason"] if isinstance(a.get("reason"), str) else "")
pstat = {}       # 예정: member_id -> (status, reason)
pmeta = {}       # 예정 마지막 수정: member_id -> (시각 문자열, 입력자)
for _, a in plan[(plan["sunday_date"] == sunday) & (plan["member_id"].isin(part_ids))].iterrows():
    pstat[a["member_id"]] = (str(a["status"]),
                             a["reason"] if isinstance(a.get("reason"), str) else "")
    when = ""
    try:
        u = pd.to_datetime(a.get("updated_at"), utc=True).tz_convert("Asia/Seoul")
        when = f"{u.month}/{u.day} {u:%H:%M}"
    except Exception:
        when = ""
    by = a.get("updated_by") if isinstance(a.get("updated_by"), str) else ""
    pmeta[a["member_id"]] = (when, by)


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
               "저장하면 해당 반이 **입력한 내용으로 바뀌고 가나다순으로 정렬됩니다.** "
               "(빠진 이름은 삭제되고, 그 이름의 출결·예정 기록도 함께 지워집니다.)")
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
            new_names = sorted(new_names)          # 가나다순 정렬
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
            t_names = sorted(parse_names(tch_txt))
            sync(tg(g2), cur_tch, t_names)
            upsert("roster_classes", [{"part": part, "grade": g2, "class_no": no2,
                                       "teachers": "\n".join(t_names) or None}],
                   "part,grade,class_no")
        st.session_state["flash"] = f"{part} {opt_label((g2, no2))} 저장 완료 (가나다순)"
        if saved_next:
            i = options.index((g2, no2))
            st.session_state[pend_key] = options[(i + 1) % len(options)]
        st.rerun()
    st.stop()

# ================================================================ 출석부 (표 클릭)
if st.session_state.get("rg_stage") not in (STAGE_PLAN, STAGE_REAL):
    # 일요일(KST)은 실제, 그 외 요일은 예정이 기본
    st.session_state["rg_stage"] = (
        STAGE_REAL if datetime.now(KST).weekday() == 6 else STAGE_PLAN)
stage = st.segmented_control("단계", [STAGE_PLAN, STAGE_REAL], key="rg_stage",
                             label_visibility="collapsed") or STAGE_REAL
is_plan = stage == STAGE_PLAN

if is_plan and not plan_ok_table:
    st.error("예정 기록용 테이블(roster_plan)이 아직 없습니다. Supabase SQL을 먼저 실행해 주세요.")
    st.stop()

# 예정 입력 가능 여부: 관리자는 항상, 선생님은 마감(토 12:00) 전까지
deadline = datetime.combine(sunday - timedelta(days=1), time(12, 0), tzinfo=KST)
plan_open = is_admin or datetime.now(KST) <= deadline

if is_plan:
    if datetime.now(KST) > deadline:
        st.warning(f"⏰ 예정 마감됨 ({deadline.month}/{deadline.day} 토 12:00 기준). "
                   "마감 후 수정은 관리자에게 요청해 주세요.")
    else:
        st.info(f"📝 예정 파악 중 · 마감 {deadline.month}/{deadline.day}(토) 12:00")
    if plan_open:
        st.caption("이름을 누르면 예정 / 불참 / 미정을 입력합니다. (선생님 누구나 입력 가능)")
    else:
        st.caption("🔒 마감되어 관리자만 수정할 수 있습니다.")
else:
    st.caption("이름 칸을 누르면 출결 팝업이 열립니다. (학생·담임·스탭 모두 동일)" if is_admin
               else "🔒 주일 출결 처리는 관리자만 가능합니다.")

mobile = st.toggle("📱 모바일 보기 (휴대폰에서는 켜 주세요)", key="rg_mobile")

stu = mem[mem["grade"].isin(STUDENT_GRADES)]
counts = stu.groupby(["grade", "class_no"]).size() if not stu.empty else pd.Series(dtype=int)
NC = MOBILE_COLS if mobile else max(10, int(counts.max()) if len(counts) else 10)
tm = mem[mem["grade"].str.startswith("담임")]
tcounts = tm.groupby(["grade", "class_no"]).size() if not tm.empty else pd.Series(dtype=int)
TN = max(2, int(tcounts.max()) if len(tcounts) else 2)


def is_ok(mid):
    if is_plan:
        return pstat.get(mid, ("", ""))[0] == "예정"
    return status.get(mid, (False, ""))[0]


def count_pr(df):
    return int(sum(1 for i in df["id"] if is_ok(i)))


def make_row(**kw):
    row = {"age": "", "no": "", "en": "", "pr": "", "lab": "", "cnt": "",
           "bg": "#ffffff", "lbg": "#ffffff", "nbg": "", "tb": "", "bar": "", "pick": ""}
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
    key = row["lbg"] if row["lbg"] != "#ffffff" else row["bg"]
    row["bar"] = BARMAP.get(key, "")
    return row


def flag_of(mid):
    if is_plan:
        s = pstat.get(mid)
        if s is None:
            return ""
        return {"예정": "pl", "불참": "no", "미정": "un"}.get(s[0], "")
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
        rows.append(make_row(no="소계", en=g_en, pr=g_pr, bg=SUB, nbg=SUB))
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
    rows.append(make_row(age="학생합계", en=stu_en, pr=stu_pr, bg=TOT, nbg=TOT))

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
    rows.append(make_row(age="교사합계", en=tch_en, pr=tch_pr, bg=TOT, nbg=TOT))
    rows.append(make_row(age="전체합계", pr=stu_pr + tch_pr, bg=TOT, nbg=TOT))

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
        rows.append(make_row(lab="소계", lbg=SUB, bg=SUB, nbg=SUB, cnt=f"{g_pr}/{g_en}"))
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
    rows.append(make_row(lab="학생합계", lbg=TOT, bg=TOT, nbg=TOT, cnt=f"{stu_pr}/{stu_en}"))

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
    rows.append(make_row(lab="교사합계", lbg=TOT, bg=TOT, nbg=TOT, cnt=f"{tch_pr}/{tch_en}"))
    rows.append(make_row(lab="전체합계", lbg=TOT, bg=TOT, nbg=TOT, cnt=str(stu_pr + tch_pr)))

df = pd.DataFrame(rows)
df["pick"] = ""

# ---------------------------------------------------------------- 요약 카드
all_ids = list(mem["id"])
n_plan = sum(1 for i in all_ids if pstat.get(i, ("", ""))[0] == "예정")
n_no = sum(1 for i in all_ids if pstat.get(i, ("", ""))[0] == "불참")
n_un = sum(1 for i in all_ids if pstat.get(i, ("", ""))[0] == "미정")
n_none = len(all_ids) - n_plan - n_no - n_un
n_real = sum(1 for i in all_ids if status.get(i, (False, ""))[0])
rate = round(stu_pr * 100 / stu_en) if stu_en else 0

if is_plan:
    st.markdown(
        "<div class='sumcards'>"
        f"<div class='sumcard hi'><div class='t'>학생 예정</div><div class='v'>{stu_pr}<small> / {stu_en}</small></div></div>"
        f"<div class='sumcard'><div class='t'>교사 예정</div><div class='v'>{tch_pr}<small> / {tch_en}</small></div></div>"
        f"<div class='sumcard warn'><div class='t'>미정·미입력</div><div class='v'>{n_un + n_none}</div></div>"
        f"<div class='sumcard bad'><div class='t'>불참</div><div class='v'>{n_no}</div></div>"
        "</div>", unsafe_allow_html=True)
else:
    st.markdown(
        "<div class='sumcards'>"
        f"<div class='sumcard hi'><div class='t'>학생 출석</div><div class='v'>{stu_pr}<small> / {stu_en}</small></div></div>"
        f"<div class='sumcard'><div class='t'>출석률</div><div class='v'>{rate}<small>%</small></div></div>"
        f"<div class='sumcard'><div class='t'>교사 출석</div><div class='v'>{tch_pr}<small> / {tch_en}</small></div></div>"
        f"<div class='sumcard'><div class='t'>전체 출석</div><div class='v'>{stu_pr + tch_pr}</div></div>"
        "</div>", unsafe_allow_html=True)
    diff = n_real - n_plan
    sign = "+" if diff > 0 else ""
    st.markdown(
        f"<div class='cmpbox'>📊 예정 vs 실제 · 예정 {n_plan}명 → 실제 {n_real}명 "
        f"<span class='d'>({sign}{diff})</span></div>", unsafe_allow_html=True)

p = part.replace("부", "")
st.markdown(f"<div class='rg-title'>{sunday.year}년 유치{p}부 · {sunday.month}월 {sunday.day}일 "
            f"({WD[sunday.weekday()]}) · {'예정 파악' if is_plan else '실제 출석'}</div>",
            unsafe_allow_html=True)

# ---------------------------------------------------------------- 표 스타일
FS = "13px" if mobile else "12px"
row_h, head_h = (38, 32) if mobile else (32, 34)
LH = f"{row_h - 4}px"

base_style = JsCode(
    "function(p){return {backgroundColor: p.data.bg || '#fff', fontWeight: '700', color: '#1b3a5c', "
    "textAlign: 'center', fontSize: '%s', padding: '0 1px', lineHeight: '%s', whiteSpace: 'nowrap'};}"
    % (FS, LH))
lab_style = JsCode(
    "function(p){return {backgroundColor: p.data.lbg || '#fff', fontWeight: '800', color: '#1b3a5c', "
    "textAlign: 'center', fontSize: '%s', padding: '0 1px', lineHeight: '%s', whiteSpace: 'nowrap', "
    "borderLeft: '5px solid ' + (p.data.bar || 'transparent')};}" % (FS, LH))


def cell_style(flag_field, bold=False):
    return JsCode(
        "function(p){var s=p.data.%s; var b={textAlign:'center',fontSize:'%s',padding:'0 1px',"
        "cursor:'pointer',lineHeight:'%s',whiteSpace:'nowrap',overflow:'hidden',color:'#1b3a5c'%s};"
        "var w='inset 0 0 0 2px #fff';"
        "if(s==='on'){b.backgroundColor='#b2f2bb';b.color='#14532d';b.fontWeight='700';b.boxShadow=w;}"
        "else if(s==='off'){b.backgroundColor='#ffd9d9';b.color='#b91c1c';b.fontWeight='700';b.boxShadow=w;}"
        "else if(s==='pl'){b.backgroundColor='#d3f9d8';b.color='#2b8a3e';b.fontWeight='700';b.boxShadow=w;}"
        "else if(s==='no'){b.backgroundColor='#ffe3e3';b.color='#c92a2a';b.fontWeight='700';b.boxShadow=w;}"
        "else if(s==='un'){b.backgroundColor='#fff3bf';b.color='#a16207';b.fontWeight='700';b.boxShadow=w;}"
        "else if(p.data.nbg){b.backgroundColor=p.data.nbg;}"
        "else if(p.data.tb==='1'||%s){b.backgroundColor=p.data.bg;b.fontWeight='700';}"
        "return b;}" % (flag_field, FS, LH, ",fontWeight:'700'" if bold else "",
                        "true" if bold else "false"))


def name_fmt(flag_field):
    return JsCode(
        "function(p){var s=p.data.%s; var v=p.value||''; if(!v){return '';}"
        "var m={on:'✓ ',off:'✕ ',pl:'○ ',no:'✕ ',un:'? '};"
        "return (m[s]||'')+v;}" % flag_field)


HEAD_PR = "예정" if is_plan else "출석"
if mobile:
    col_defs = [{"field": "lab", "headerName": "반", "width": 56, "minWidth": 46,
                 "cellStyle": lab_style, "sortable": False}]
    for n in range(1, NC + 1):
        col_defs.append({"field": f"c{n}", "headerName": "이름" if n == 1 else "", "width": 62,
                         "minWidth": 50, "cellStyle": cell_style(f"s{n}"),
                         "valueFormatter": name_fmt(f"s{n}"), "sortable": False})
        col_defs.append({"field": f"i{n}", "hide": True})
        col_defs.append({"field": f"s{n}", "hide": True})
    col_defs.append({"field": "cnt", "headerName": ("예/재" if is_plan else "출/재"),
                     "width": 48, "minWidth": 40, "cellStyle": base_style, "sortable": False})
else:
    col_defs = [
        {"field": "age", "headerName": "나이", "width": 62, "minWidth": 46,
         "cellStyle": lab_style, "sortable": False},
        {"field": "no", "headerName": "반", "width": 36, "minWidth": 28,
         "cellStyle": base_style, "sortable": False},
    ]
    for n in range(1, TN + 1):
        col_defs.append({"field": f"t{n}", "headerName": "담임샘" if n == 1 else "", "width": 56,
                         "minWidth": 42, "cellStyle": cell_style(f"ts{n}", bold=True),
                         "valueFormatter": name_fmt(f"ts{n}"), "sortable": False})
        col_defs.append({"field": f"ti{n}", "hide": True})
        col_defs.append({"field": f"ts{n}", "hide": True})
    for n in range(1, NC + 1):
        col_defs.append({"field": f"c{n}", "headerName": str(n), "width": 54, "minWidth": 34,
                         "cellStyle": cell_style(f"s{n}"),
                         "valueFormatter": name_fmt(f"s{n}"), "sortable": False})
        col_defs.append({"field": f"i{n}", "hide": True})
        col_defs.append({"field": f"s{n}", "hide": True})
    col_defs += [
        {"field": "en", "headerName": "재적", "width": 42, "minWidth": 32,
         "cellStyle": base_style, "sortable": False},
        {"field": "pr", "headerName": HEAD_PR, "width": 42, "minWidth": 32,
         "cellStyle": base_style, "sortable": False},
    ]

col_defs += [
    {"field": "bg", "hide": True},
    {"field": "lbg", "hide": True},
    {"field": "nbg", "hide": True},
    {"field": "tb", "hide": True},
    {"field": "bar", "hide": True},
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
    "suppressRowClickSelection": True,
    "onCellClicked": JsCode(
        "function(e){var f=e.colDef.field||'';var m=/^(c|t)([0-9]+)$/.exec(f);if(!m)return;"
        "var id=e.data[(m[1]==='c'?'i':'ti')+m[2]];"
        "e.node.setDataValue('pick', id ? (id+'|'+e.value+'|'+Date.now()) : '');}"),
    # 재사용된 Grid는 새 열 정의를 받은 뒤 자동 너비 맞춤이 다시 실행되지 않는다.
    "onRowDataUpdated": JsCode(
        "function(e){requestAnimationFrame(function(){requestAnimationFrame(function(){"
        "e.api.sizeColumnsToFit();});});}"),
}

grid_css = {
    ".ag-header": {"background-color": "#d6ecff !important", "border-bottom": "2px solid #9ccbf0 !important"},
    ".ag-header-cell": {"background-color": "#d6ecff !important"},
    ".ag-header-cell-label": {"justify-content": "center", "font-weight": "800", "color": "#1b3a5c"},
    ".ag-root-wrapper": {"border-radius": "12px", "border": "1px solid #bcd7ee"},
    ".ag-cell": {"border-color": "#e3edf6 !important"},
    ".ag-row": {"border-color": "#e3edf6 !important"},
    ".ag-body-viewport": {"overflow-y": "hidden !important"},
}

# 같은 열 구조에서는 Grid를 재사용하고, 열 수가 달라질 때만 새로 만든다.
grid_shape = f"mobile_{NC}" if mobile else f"desktop_{NC}_{TN}"
grid_key = f"rg_grid_{grid_shape}"

resp = AgGrid(
    df, gridOptions=grid_options, allow_unsafe_jscode=True, custom_css=grid_css,
    update_mode=GridUpdateMode.VALUE_CHANGED,
    server_sync_strategy="server_wins",
    height=head_h + row_h * (len(df) + 2) + 30, fit_columns_on_grid_load=True,
    key=grid_key)

try:
    returned = resp["data"]
    records = returned.to_dict("records") if hasattr(returned, "to_dict") else returned
except Exception:
    records = []

if is_plan:
    st.markdown(
        "<div class='rg-legend'>"
        "<span style='background:#d3f9d8;color:#2b8a3e'>○ 예정</span>"
        "<span style='background:#ffe3e3;color:#c92a2a'>✕ 불참</span>"
        "<span style='background:#fff3bf;color:#a16207'>? 미정</span>"
        "<span style='background:#f1f3f5;color:#495057'>미입력</span>"
        + ("<span style='background:#e7f1fb;color:#1b3a5c'>예/재 = 예정/재적</span>" if mobile else "")
        + "</div>", unsafe_allow_html=True)
else:
    st.markdown(
        "<div class='rg-legend'>"
        "<span style='background:#b2f2bb;color:#14532d'>✓ 출석</span>"
        "<span style='background:#ffd9d9;color:#b91c1c'>✕ 결석</span>"
        "<span style='background:#f1f3f5;color:#495057'>미확인</span>"
        + ("<span style='background:#e7f1fb;color:#1b3a5c'>출/재 = 출석/재적</span>" if mobile else "")
        + "</div>", unsafe_allow_html=True)

name_of = {r["id"]: str(r["name"]) for _, r in mem.iterrows()}


# ---------------------------------------------------------------- 불참·결석 목록 (반별로 묶어 접어 두기)
def short_reason(r):
    return (r or "사유 없음").split("(")[0].strip()


def grouped_lines(pairs):
    """pairs: [(member_id, reason)] -> (반별 목록, 사유별 집계)"""
    by_cls, by_reason = {}, {}
    idx = {r["id"]: (r["grade"], int(r["class_no"])) for _, r in mem.iterrows()}
    for mid, rsn in pairs:
        if mid not in idx or mid not in name_of:
            continue
        g, n = idx[mid]
        if g == "스탭":
            key = "스탭"
        elif g == "새싹":
            key = "새싹"
        else:
            key = g + (str(n) if n else "")
        sr = short_reason(rsn)
        by_cls.setdefault(key, []).append(f"{name_of[mid]}({sr})")
        by_reason[sr] = by_reason.get(sr, 0) + 1
    return by_cls, by_reason


def show_grouped(title, pairs):
    pairs = [(m, r) for m, r in pairs if m in part_ids]
    if not pairs:
        return
    by_cls, by_reason = grouped_lines(pairs)
    with st.expander(f"{title} {len(pairs)}명 (눌러서 보기)", expanded=False):
        st.caption(" · ".join(f"{k} {v}명" for k, v in
                              sorted(by_reason.items(), key=lambda x: -x[1])))
        for k in sorted(by_cls):
            st.markdown(f"**{k}** · " + ", ".join(by_cls[k]))


# ---------------------------------------------------------------- 단계별 부가 정보
if is_plan:
    show_grouped("✕ 불참 예정", [(m, s[1]) for m, s in pstat.items() if s[0] == "불참"])

    # 반별 예정 요약 (카톡 복사용)
    lines = [f"[유치{p}부 {sunday.month}/{sunday.day}({WD[sunday.weekday()]}) 예배 참석 예정]"]
    for grade, age, color in GRADES:
        for no in class_numbers(grade):
            kids = members_of(grade, no)
            if kids.empty:
                continue
            a = sum(1 for i in kids["id"] if pstat.get(i, ("", ""))[0] == "예정")
            b = sum(1 for i in kids["id"] if pstat.get(i, ("", ""))[0] == "불참")
            c = sum(1 for i in kids["id"] if pstat.get(i, ("", ""))[0] == "미정")
            d = len(kids) - a - b - c
            lines.append(f"{grade}{no}반 예정 {a} / 재적 {len(kids)} (불참 {b}, 미정 {c}, 미입력 {d})")
    spk = members_of("새싹", NONE_CLASS)
    if not spk.empty:
        a = sum(1 for i in spk["id"] if pstat.get(i, ("", ""))[0] == "예정")
        lines.append(f"새싹반 예정 {a} / 재적 {len(spk)}")
    lines.append(f"학생 예정 {stu_pr} / 재적 {stu_en}")
    lines.append(f"교사 예정 {tch_pr} / {tch_en}")
    lines.append(f"합계 {stu_pr + tch_pr}명")
    with st.expander("📋 반별 예정 요약 (카톡에 복사해서 올리기)", expanded=False):
        st.code("\n".join(lines), language=None)
else:
    miss = [name_of[m] for m, s in pstat.items()
            if s[0] == "예정" and m in name_of and m in status and not status[m][0]]
    unchecked = [name_of[m] for m, s in pstat.items()
                 if s[0] == "예정" and m in name_of and m not in status]
    box = []
    if miss:
        box.append("📉 <b>예정했으나 결석</b> · " + ", ".join(miss))
    if unchecked:
        box.append(f"⏳ <b>예정했으나 아직 미확인</b> · {len(unchecked)}명")
    if box:
        st.markdown(
            "<div style='background:#fff9db;border:1px solid #ffe066;border-radius:12px;"
            "padding:.5rem .8rem;font-size:.85rem;color:#7c5e00'>" + "<br>".join(box) + "</div>",
            unsafe_allow_html=True)
    show_grouped("❌ 결석", [(m, s[1]) for m, s in status.items() if not s[0]])


# ---------------------------------------------------------------- 사유 선택 (상세 직접 입력 포함)
def reason_picker(label, key_sel, key_txt, cur_reason):
    """드롭다운 + '상세(직접 입력)' 선택 시 입력칸. 반환: 사유 문자열 또는 None"""
    opts = ["(사유 선택)"] + REASONS + [CUSTOM]
    is_custom0 = bool(cur_reason) and cur_reason not in REASONS
    if is_custom0:
        idx = opts.index(CUSTOM)
    elif cur_reason in opts:
        idx = opts.index(cur_reason)
    else:
        idx = 0
    sel = st.selectbox(label, opts, index=idx, key=key_sel)
    if sel == CUSTOM:
        txt = st.text_input("상세 사유", value=cur_reason if is_custom0 else "",
                            key=key_txt, placeholder="예: 할머니 댁 방문").strip()
        if not txt:
            st.caption("⚠️ 상세 사유를 입력해 주세요.")
            return None
        return txt
    if sel == "(사유 선택)":
        return None
    return sel


# ---------------------------------------------------------------- 팝업
@st.dialog("출결 처리")
def attend_dialog(member_id: str, name: str, d_iso: str, cur_present, cur_reason: str):
    d = date.fromisoformat(d_iso)
    st.markdown(f"### {name}")
    st.caption(f"{d.month}월 {d.day}일 ({WD[d.weekday()]}) · {part}")
    ps = pstat.get(member_id)
    if ps:
        st.caption(f"📝 주중 예정: {ps[0]}" + (f" ({ps[1]})" if ps[1] else ""))
    choice = st.radio("출결", ["출석", "결석"], horizontal=True,
                      index=1 if cur_present is False else 0, key=f"rgd_c_{member_id}")
    reason = None
    if choice == "결석":
        reason = reason_picker("결석 사유", f"rgd_r_{member_id}", f"rgd_t_{member_id}", cur_reason)
    b1, b2 = st.columns(2)
    if b1.button("저장", type="primary", use_container_width=True, key=f"rgd_s_{member_id}"):
        if not is_admin:
            st.stop()
        upsert("roster_attendance",
               [{"member_id": member_id, "sunday_date": d_iso, "present": choice == "출석",
                 "reason": reason if choice == "결석" else None}], "member_id,sunday_date")
        st.rerun()
    if b2.button("기록 지우기", use_container_width=True, key=f"rgd_d_{member_id}"):
        if not is_admin:
            st.stop()
        delete_where("roster_attendance", member_id=member_id, sunday_date=d_iso)
        st.rerun()


@st.dialog("예정 입력")
def plan_dialog(member_id: str, name: str, d_iso: str, cur_status, cur_reason: str):
    d = date.fromisoformat(d_iso)
    st.markdown(f"### {name}")
    st.caption(f"{d.month}월 {d.day}일 ({WD[d.weekday()]}) 예배 · {part} · 주중 예정 파악")
    meta = pmeta.get(member_id)
    if meta and meta[0]:
        st.caption(f"🕒 마지막 수정: {meta[0]}" + (f" · {meta[1]}" if meta[1] else ""))
    choice = st.radio("예정", PLAN_STATES, horizontal=True,
                      index=PLAN_STATES.index(cur_status) if cur_status in PLAN_STATES else 0,
                      key=f"pld_c_{member_id}")
    reason = None
    if choice == "불참":
        reason = reason_picker("불참 사유", f"pld_r_{member_id}", f"pld_t_{member_id}", cur_reason)
    editor = st.text_input("입력하는 선생님 이름 (선택)", key="rg_editor_name",
                           placeholder="예: 홍길동")
    b1, b2 = st.columns(2)
    if b1.button("저장", type="primary", use_container_width=True, key=f"pld_s_{member_id}"):
        if not plan_open:
            st.error("마감되어 저장할 수 없습니다. 관리자에게 요청해 주세요.")
            st.stop()
        upsert("roster_plan",
               [{"member_id": member_id, "sunday_date": d_iso, "status": choice,
                 "reason": reason if choice == "불참" else None,
                 "updated_by": editor.strip() or None,
                 "updated_at": datetime.now(KST).isoformat()}], "member_id,sunday_date")
        st.rerun()
    if b2.button("기록 지우기", use_container_width=True, key=f"pld_d_{member_id}"):
        if not plan_open:
            st.error("마감되어 수정할 수 없습니다. 관리자에게 요청해 주세요.")
            st.stop()
        delete_where("roster_plan", member_id=member_id, sunday_date=d_iso)
        st.rerun()


# 이름 클릭 처리: 예정 단계는 선생님 누구나(마감 전), 실제 단계는 관리자만
picked = None
try:
    candidates = [r.get("pick") for r in records if hasattr(r, "get") and r.get("pick")]
    if candidates:
        picked = max(candidates, key=lambda v: int(str(v).rsplit("|", 1)[-1]))
except Exception:
    picked = None
if picked and str(picked).count("|") >= 2:
    mid, label, stamp = str(picked).split("|", 2)
    for pre in ("✓ ", "✕ ", "○ ", "? "):
        label = label.replace(pre, "")
    if stamp != st.session_state.get("rg_last"):
        st.session_state["rg_last"] = stamp
        if is_plan:
            if plan_open:
                s = pstat.get(mid)
                plan_dialog(mid, label, sunday.isoformat(), (s[0] if s else None), (s[1] if s else ""))
            else:
                st.warning("⏰ 예정 입력이 마감되었습니다. 수정은 관리자에게 요청해 주세요.")
        elif is_admin:
            s = status.get(mid)
            attend_dialog(mid, label, sunday.isoformat(),
                          (s[0] if s else None), (s[1] if s else ""))

# ---------------------------------------------------------------- 새신자 추가 (실제 단계, 관리자)
if is_admin and not is_plan:
    st.divider()
    st.markdown("#### 🌟 새신자 추가")
    st.caption("이름을 입력하면 🌱 새싹반에 추가(가나다순)되고, 선택한 주일 날짜 출석으로 기록됩니다.")

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
            res = insert("roster_members", {
                "part": part, "grade": "새싹", "class_no": None,
                "name": nm, "sort_no": order,
            })
            try:
                new_id = res.data[0]["id"]
                upsert("roster_attendance",
                       [{"member_id": new_id, "sunday_date": sunday.isoformat(),
                         "present": True, "reason": None}], "member_id,sunday_date")
            except Exception:
                pass
            try:
                allsp = fetch_where("roster_members", part=part, grade="새싹")
                reordered = [
                    {
                        "id": r["id"], "part": r["part"], "grade": r["grade"],
                        "class_no": None, "name": r["name"], "sort_no": i,
                    }
                    for i, r in enumerate(
                        sorted(allsp.to_dict("records"), key=lambda row: row["name"])
                    )
                ]
                if reordered:
                    upsert("roster_members", reordered, "id")
            except Exception:
                pass
            st.session_state["flash"] = f"새신자 '{nm}'을(를) 새싹반에 추가했습니다. (출석 처리됨)"
            st.rerun()
