import html
from datetime import date, timedelta
import pandas as pd
import streamlit as st
from utils import db
from utils.db import fetch, insert, update, delete, upsert

st.title("📋 주일 출석부")

# 열람은 누구나, 출석 체크·명단 수정은 관리자 로그인한 사람만
is_admin = st.session_state.get("role") == "admin"

PARTS = ["1부", "2부"]
GRADES = [("조이", "5세", "#fff6c9"), ("해피", "6세", "#e3e8fb"), ("홀리", "7세", "#f6dff0")]
GRADE_ORDER = {"조이": 0, "해피": 1, "홀리": 2, "새싹": 3, "스탭": 4}
NONE_CLASS = 0
WD = "월화수목금토일"
REASONS = [
    "연락안됨", "병결(본인 혹은 가족)", "출근, 출장", "가족모임(명절, 여행 등)",
    "경조사(장례식, 결혼식)", "이사", "외국", "출산", "타교회", "1회성", "기타 개인사정", "대예배",
]
NO_REASON = "(사유 선택)"
DEFAULT_CLASSES = {
    "1부": {"조이": 4, "해피": 4, "홀리": 4},
    "2부": {"조이": 5, "해피": 3, "홀리": 5},
}

st.markdown("""
<style>
.rs-wrap {overflow-x: auto; margin: .4rem 0 1rem;}
.rs {border-collapse: collapse; width: 100%; min-width: 680px; table-layout: fixed;
     font-size: .85rem; color: #1b3a5c;}
.rs th, .rs td {border: 1px solid #8a97a8; padding: .3rem .2rem; text-align: center;
                height: 2.1rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;}
.rs th {background: #f1f7fd; font-weight: 700;}
.rs th.ttl {font-size: 1.1rem; background: #fff; padding: .5rem;}
.rs td.g {font-weight: 700; line-height: 1.3; white-space: normal;}
.rs td.no {font-weight: 700; width: 2rem;}
.rs td.tch {font-weight: 700; white-space: normal; line-height: 1.25; width: 5rem;}
.rs td.nm.on {background: #b2f2bb; font-weight: 700; color: #1b6e2a;}
.rs td.nm.off {background: #ffe3e3;}
.rs td.nm small {display: block; font-size: .68rem; color: #c92a2a; line-height: 1.1;
                 overflow: hidden; text-overflow: ellipsis;}
.rs td.num {font-weight: 700; width: 2.8rem;}
.rs td.sub {background: #eef1f5; font-weight: 700;}
.rs td.lab {font-weight: 700; background: #fafbfc;}
.rs td.big {background: #e9ecef; font-weight: 700; font-size: 1rem;}
</style>
""", unsafe_allow_html=True)


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

status = {}  # member_id -> (present, reason)
for _, a in att[att["sunday_date"] == sunday].iterrows():
    status[a["member_id"]] = (bool(a["present"]),
                              a["reason"] if isinstance(a.get("reason"), str) else "")
present_ids = {k for k, v in status.items() if v[0]}

visitors = 0
if not vis.empty:
    vv = vis[(vis["part"] == part) & (pd.to_datetime(vis["sunday_date"]).dt.date == sunday)]
    if not vv.empty:
        visitors = int(vv.iloc[0]["count"])


def teacher_of(grade, no, sep="<br>"):
    m = cls[(cls["grade"] == grade) & (cls["class_no"] == no)]
    if m.empty or not isinstance(m.iloc[0]["teachers"], str):
        return ""
    return m.iloc[0]["teachers"].replace("\n", sep)


def members_of(grade, no):
    return mem[(mem["grade"] == grade) & (mem["class_no"] == no)].sort_values("sort_no")


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


def build_table():
    counts = mem.groupby(["grade", "class_no"]).size() if not mem.empty else pd.Series(dtype=int)
    ncols = max(10, int(counts.max()) if len(counts) else 10)
    rows = []
    p = part.replace("부", "")
    rows.append(f"<tr><th class='ttl' colspan='{ncols + 5}'>{sunday.year}년 유치{p}부 "
                f"{sunday.month}월 {sunday.day}일 ({WD[sunday.weekday()]})</th></tr>")
    head = "<tr><th style='width:3.2rem'>나이</th><th style='width:2rem'>반</th><th style='width:5rem'>담임샘</th>"
    head += "".join(f"<th>{i}</th>" for i in range(1, ncols + 1))
    head += "<th style='width:2.8rem'>재적</th><th style='width:2.8rem'>출석</th></tr>"
    rows.append(head)

    def name_cells(df):
        names, ids = df["name"].tolist(), df["id"].tolist()
        out = ""
        for i in range(ncols):
            if i < len(names):
                s = status.get(ids[i])
                c, extra = "", ""
                if s is not None:
                    if s[0]:
                        c = " on"
                    else:
                        c = " off"
                        if s[1]:
                            extra = f"<small>{html.escape(s[1])}</small>"
                out += f"<td class='nm{c}'>{html.escape(str(names[i]))}{extra}</td>"
            else:
                out += "<td class='nm'></td>"
        return out

    stu_en = stu_pr = 0
    for grade, age, color in GRADES:
        nos = class_numbers(grade)
        if not nos:
            continue
        g_en = g_pr = 0
        for idx, no in enumerate(nos):
            kids = members_of(grade, no)
            en, pr = len(kids), int(kids["id"].isin(present_ids).sum())
            g_en += en
            g_pr += pr
            row = "<tr>"
            if idx == 0:
                row += (f"<td class='g' rowspan='{len(nos) + 1}' "
                        f"style='background:{color}'>{age}<br>{grade}</td>")
            row += (f"<td class='no' style='background:{color}'>{no}</td>"
                    f"<td class='tch' style='background:{color}'>{teacher_of(grade, no)}</td>")
            row += name_cells(kids) + f"<td class='num'>{en}</td><td class='num'>{pr}</td></tr>"
            rows.append(row)
        rows.append(f"<tr><td class='sub' colspan='{ncols + 2}'>소계</td>"
                    f"<td class='sub'>{g_en}</td><td class='sub'>{g_pr}</td></tr>")
        stu_en += g_en
        stu_pr += g_pr

    sp = members_of("새싹", NONE_CLASS)
    sp_pr = int(sp["id"].isin(present_ids).sum())
    rows.append(f"<tr><td class='lab' colspan='2'>🌱 새싹반</td><td class='tch'>{teacher_of('새싹', NONE_CLASS)}</td>"
                f"{name_cells(sp)}<td class='num'>{len(sp)}</td><td class='num'>{sp_pr}</td></tr>")
    stu_en += len(sp)
    stu_pr += sp_pr
    rows.append(f"<tr><td class='big' colspan='3'>학생 합계</td><td class='big' colspan='{ncols}'></td>"
                f"<td class='big'>{stu_en}</td><td class='big'>{stu_pr}</td></tr>")
    rows.append(f"<tr><td class='lab' colspan='3'>방문자</td><td colspan='{ncols}'></td>"
                f"<td></td><td class='num'>{visitors}</td></tr>")
    stf = members_of("스탭", NONE_CLASS)
    stf_pr = int(stf["id"].isin(present_ids).sum())
    rows.append(f"<tr><td class='lab' colspan='3'>스탭(교사)</td>{name_cells(stf)}"
                f"<td class='num'>{len(stf)}</td><td class='num'>{stf_pr}</td></tr>")
    rows.append(f"<tr><td class='big' colspan='{ncols + 4}' style='text-align:right;padding-right:.6rem'>"
                f"전체(학생+교사+방문자) 출석 합계</td><td class='big'>{stu_pr + stf_pr + visitors}</td></tr>")
    return f"<div class='rs-wrap'><table class='rs'>{''.join(rows)}</table></div>"


def save_status(member_id, present, reason):
    """즉시 저장 (present=None 이면 기록 삭제)"""
    if present is None:
        db.get_client().table("roster_attendance").delete() \
            .eq("member_id", member_id).eq("sunday_date", sunday.isoformat()).execute()
        db._fetch_cached.clear()
    else:
        upsert("roster_attendance",
               [{"member_id": member_id, "sunday_date": sunday.isoformat(),
                 "present": bool(present), "reason": None if present else (reason or None)}],
               "member_id,sunday_date")


def on_name(member_id):
    cur = status.get(member_id)
    if cur is not None and cur[0]:
        save_status(member_id, None, None)       # 출석 → 해제
    else:
        save_status(member_id, True, None)       # 미확인/결석 → 출석


def on_reason(member_id, key):
    val = st.session_state.get(key)
    if val and val != NO_REASON:
        save_status(member_id, False, val)
    else:
        cur = status.get(member_id)
        if cur is not None and not cur[0]:
            save_status(member_id, None, None)


def on_all(kids):
    rows_ = [{"member_id": r["id"], "sunday_date": sunday.isoformat(),
              "present": True, "reason": None} for _, r in kids.iterrows()]
    if rows_:
        upsert("roster_attendance", rows_, "member_id,sunday_date")


VIEWS = ["출석부"] + (["명단 관리"] if is_admin else [])
if st.session_state.get("rs_view") not in VIEWS:
    st.session_state["rs_view"] = VIEWS[0]
view = st.segmented_control("화면", VIEWS, key="rs_view", label_visibility="collapsed")
view = view or VIEWS[0]

# ================================================================ 출석부 + 빠른 입력
if view == "출석부":
    if mem.empty:
        st.info("등록된 명단이 없습니다." + (" '명단 관리'에서 이름을 붙여넣어 등록하세요." if is_admin else ""))
    st.markdown(build_table(), unsafe_allow_html=True)
    st.caption("초록 = 출석 · 연한 빨강 = 결석(사유 표시) · 흰색 = 아직 확인 안 됨")

    if is_admin:
        st.markdown("### ✏️ 빠른 입력")
        combos = sorted({(r.grade, int(r.class_no)) for r in mem.itertuples()},
                        key=lambda x: (GRADE_ORDER.get(x[0], 9), x[1]))
        if not combos:
            st.info("먼저 '명단 관리'에서 명단을 등록해 주세요.")
        else:
            sel_key = f"qi_sel_{part}"
            if st.session_state.get(sel_key) not in combos:
                st.session_state[sel_key] = combos[0]
            st.selectbox("반 선택", combos, format_func=opt_label, key=sel_key)
            g, no = st.session_state[sel_key]
            kids = members_of(g, no)
            st.caption("이름을 누르면 출석(초록), 다시 누르면 해제됩니다. 결석이면 이름 아래에서 사유를 고르세요. 바로 저장됩니다.")
            st.button("✅ 이 반 전원 출석", key=f"all_{part}_{sunday}_{g}_{no}",
                      on_click=on_all, args=(kids,), use_container_width=True)

            cols_n = 3
            kid_rows = [kids.iloc[i:i + cols_n] for i in range(0, len(kids), cols_n)]
            for chunk in kid_rows:
                cols = st.columns(cols_n)
                for col, (_, k) in zip(cols, chunk.iterrows()):
                    mid = k["id"]
                    s = status.get(mid)
                    mark = "✅ " if (s and s[0]) else ("❌ " if s else "")
                    with col:
                        st.button(f"{mark}{k['name']}", key=f"nm_{part}_{sunday}_{mid}",
                                  on_click=on_name, args=(mid,), use_container_width=True,
                                  type="primary" if (s and s[0]) else "secondary")
                        rk = f"rsn_{part}_{sunday}_{mid}"
                        opts = [NO_REASON] + REASONS
                        cur_reason = s[1] if (s and not s[0] and s[1] in REASONS) else NO_REASON
                        # 서버 상태와 선택칸을 항상 맞춤
                        st.session_state[rk] = cur_reason
                        st.selectbox("사유", opts, key=rk, label_visibility="collapsed",
                                     on_change=on_reason, args=(mid, rk))

        with st.form(f"vis_{part}_{sunday}"):
            v_new = st.number_input("방문자 수", min_value=0, value=visitors, step=1)
            v_saved = st.form_submit_button("방문자 수 저장", use_container_width=True)
        if v_saved:
            upsert("roster_visitors", [{"part": part, "sunday_date": sunday.isoformat(),
                                        "count": int(v_new)}], "part,sunday_date")
            st.session_state["flash"] = "방문자 수를 저장했습니다."
            st.rerun()

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
    cur_teacher = teacher_of(g2, no2, "\n")
    cur_names = "\n".join(cur["name"].tolist())

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
        old = {r["name"]: r["id"] for _, r in cur.iterrows()}
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
