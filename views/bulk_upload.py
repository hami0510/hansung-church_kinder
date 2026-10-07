import io
import re
from datetime import date
import pandas as pd
import streamlit as st
from utils.auth import can_manage_roster as can_manage
from utils.db import fetch, insert
from utils.phone import format_phone

CLASSES = ["조이(5세)", "해피(6세)", "홀리(7세)", "새싹(새가족)"]
PARTS_C = ["1부", "2부"]
PARTS_T = ["1부", "2부", "1·2부 모두"]
ROLES = ["부장", "총무", "서기", "회계", "교사", "보조교사"]

CHILD_HEAD = ["이름", "성별", "생년월일", "보호자 이름", "보호자 연락처", "반", "부", "반 번호", "알레르기", "특이사항"]
TEACHER_HEAD = ["이름", "연락처", "생년월일", "담당 반", "부", "반 번호", "직분", "메모"]

CHILD_MAP = {"이름": "name", "성별": "gender", "생년월일": "birth", "보호자이름": "g_name", "보호자": "g_name",
             "보호자연락처": "g_phone", "연락처": "g_phone", "반": "cls", "부": "part", "반번호": "no",
             "알레르기": "allergy", "특이사항": "notes", "새가족": "new"}
TEACHER_MAP = {"이름": "name", "연락처": "phone", "전화번호": "phone", "생년월일": "birth", "담당반": "cls",
               "반": "cls", "부": "part", "반번호": "no", "직분": "role", "메모": "notes"}

st.title("📥 엑셀 일괄 업로드")

if not can_manage():
    st.warning("관리자 로그인 후 사용할 수 있습니다.")
    st.stop()

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))


# ------------------------------------------------------------ 값 정리 도우미
def s(v):
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return ""
    t = str(v).strip()
    return "" if t.lower() in ("nan", "nat", "none") else t


def parse_date(v):
    t = s(v)
    if not t:
        return None
    t = t.split(" ")[0].replace(".", "-").replace("/", "-").rstrip("-")
    d = pd.to_datetime(t, errors="coerce")
    if pd.isna(d) or not (1940 <= d.year <= date.today().year):
        return "ERR"
    return d.date()


def match_class(v):
    t = s(v).replace(" ", "")
    if not t:
        return None
    for c in CLASSES:
        if t == c or t in c:
            return c
    return "ERR"


def match_part(v, allowed):
    t = s(v).replace(" ", "")
    if not t:
        return None
    if t in ("1", "1부"):
        return "1부"
    if t in ("2", "2부"):
        return "2부"
    if "1·2부모두" in allowed.__repr__().replace(" ", "") and t in ("모두", "1·2부모두", "1,2부", "1·2부"):
        return "1·2부 모두"
    return "ERR"


def match_no(v):
    t = s(v)
    if not t:
        return None
    m = re.search(r"\d+", t)
    return int(m.group()) if m and 1 <= int(m.group()) <= 5 else "ERR"


def match_gender(v):
    t = s(v)
    if not t:
        return None
    if t in ("남", "남자", "남아", "M", "m"):
        return "남"
    if t in ("여", "여자", "여아", "F", "f"):
        return "여"
    return "ERR"


def norm_phone(v):
    t = s(v)
    if not t:
        return None
    if t.endswith(".0"):
        t = t[:-2]
    digits = re.sub(r"\D", "", t)
    if len(digits) == 10 and digits.startswith("10"):  # 엑셀이 앞의 0을 지운 경우
        t = "0" + digits
    return format_phone(t)


def read_file(f, mapping):
    if f.name.lower().endswith(".csv"):
        df = pd.read_csv(f, dtype=str, encoding="utf-8-sig")
    else:
        df = pd.read_excel(f, dtype=str, engine="openpyxl")
    rename = {}
    for col in df.columns:
        key = re.sub(r"[\s*]", "", str(col))
        if key in mapping:
            rename[col] = mapping[key]
    return df.rename(columns=rename)


# ------------------------------------------------------------ 양식 만들기
def make_template(kind):
    from openpyxl import Workbook
    from openpyxl.worksheet.datavalidation import DataValidation
    wb = Workbook()
    ws = wb.active
    ws.title = "아동" if kind == "child" else "교사"
    head = CHILD_HEAD if kind == "child" else TEACHER_HEAD
    ws.append(head)
    for i in range(1, len(head) + 1):
        ws.column_dimensions[chr(64 + i)].width = 16
    text_cols = ["C", "E"] if kind == "child" else ["B", "C"]
    for col in text_cols:                       # 연락처·생년월일은 텍스트로 (앞자리 0 보존)
        for row in range(2, 501):
            ws[f"{col}{row}"].number_format = "@"

    def dv(options, col):
        v = DataValidation(type="list", formula1='"' + ",".join(options) + '"', allow_blank=True)
        ws.add_data_validation(v)
        v.add(f"{col}2:{col}500")

    if kind == "child":
        dv(["남", "여"], "B"); dv(CLASSES, "F"); dv(PARTS_C, "G"); dv(["1", "2", "3", "4", "5"], "H")
    else:
        dv(CLASSES, "D"); dv(PARTS_T, "E"); dv(["1", "2", "3", "4", "5"], "F"); dv(ROLES, "G")

    g = wb.create_sheet("작성 안내")
    for line in ["1행의 제목(열 이름)은 바꾸지 마세요. 2행부터 한 줄에 한 명씩 입력합니다.",
                 "이름은 필수이고 나머지는 비워도 됩니다.",
                 "생년월일: 2021-03-05 또는 2021.03.05 형식",
                 "연락처: 01012345678 처럼 숫자만 입력해도 010-1234-5678로 저장됩니다.",
                 "반: 조이(5세) / 해피(6세) / 홀리(7세) / 새싹(새가족), 부: 1부 / 2부, 반 번호: 1~5",
                 "이미 등록된 사람(이름+생년월일 같음)은 자동으로 건너뜁니다."]:
        g.append([line])
    g.column_dimensions["A"].width = 90
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ------------------------------------------------------------ 검증
def build_children(df, existing):
    exist = set()
    if not existing.empty:
        exist = {(r["name"], str(r.get("birth_date"))[:10] if pd.notna(r.get("birth_date")) else "")
                 for _, r in existing.iterrows()}
    seen, rows = set(), []
    for i, r in df.iterrows():
        errs = []
        name = s(r.get("name"))
        if not name:
            if not any(s(v) for v in r.values):
                continue  # 완전히 빈 줄
            errs.append("이름 없음")
        birth = parse_date(r.get("birth"))
        gender = match_gender(r.get("gender"))
        cls = match_class(r.get("cls"))
        part = match_part(r.get("part"), PARTS_C)
        no = match_no(r.get("no"))
        for label, val in (("생년월일", birth), ("성별", gender), ("반", cls), ("부", part), ("반 번호", no)):
            if val == "ERR":
                errs.append(f"{label} 확인")
        key = (name, birth.isoformat() if birth not in (None, "ERR") else "")
        status, note = "등록 예정", ""
        if errs:
            status, note = "오류", ", ".join(errs)
        elif key in exist or key in seen:
            status, note = "중복(건너뜀)", "이미 있음"
        seen.add(key)
        new_flag = s(r.get("new")).lower() in ("o", "y", "예", "네", "true", "1")
        rows.append({
            "행": i + 2, "이름": name, "성별": gender or "", "생년월일": key[1],
            "보호자": s(r.get("g_name")), "연락처": norm_phone(r.get("g_phone")) or "",
            "반": cls or "", "부": part or "", "반 번호": no or "",
            "상태": status, "비고": note,
            "_db": None if status != "등록 예정" else {
                "name": name, "gender": gender, "birth_date": key[1] or None,
                "guardian_name": s(r.get("g_name")) or None, "guardian_phone": norm_phone(r.get("g_phone")),
                "class_name": cls, "service_part": part, "class_no": no,
                "allergy": s(r.get("allergy")) or None, "notes": s(r.get("notes")) or None,
                "is_new_family": bool(new_flag or (cls or "").startswith("새싹"))},
        })
    return rows


def build_teachers(df, existing):
    exist = set()
    if not existing.empty:
        exist = {(r["name"], s(r.get("phone"))) for _, r in existing.iterrows()}
    seen, rows = set(), []
    for i, r in df.iterrows():
        errs = []
        name = s(r.get("name"))
        if not name:
            if not any(s(v) for v in r.values):
                continue
            errs.append("이름 없음")
        phone = norm_phone(r.get("phone"))
        birth = parse_date(r.get("birth"))
        cls = match_class(r.get("cls"))
        part = match_part(r.get("part"), PARTS_T)
        no = match_no(r.get("no"))
        for label, val in (("생년월일", birth), ("담당 반", cls), ("부", part), ("반 번호", no)):
            if val == "ERR":
                errs.append(f"{label} 확인")
        key = (name, phone or "")
        status, note = "등록 예정", ""
        if errs:
            status, note = "오류", ", ".join(errs)
        elif key in exist or key in seen:
            status, note = "중복(건너뜀)", "이미 있음"
        seen.add(key)
        rows.append({
            "행": i + 2, "이름": name, "연락처": phone or "", "생년월일": birth.isoformat() if birth not in (None, "ERR") else "",
            "담당 반": cls or "", "부": part or "", "반 번호": no or "", "직분": s(r.get("role")),
            "상태": status, "비고": note,
            "_db": None if status != "등록 예정" else {
                "name": name, "phone": phone,
                "birth_date": birth.isoformat() if birth not in (None, "ERR") else None,
                "class_name": cls, "service_part": part, "class_no": no,
                "role_title": s(r.get("role")) or "교사", "notes": s(r.get("notes")) or None}},
        )
    return rows


def run_section(kind, table, mapping, builder, label):
    st.download_button(f"📄 {label} 엑셀 양식 내려받기", make_template(kind),
                       file_name=f"{label}_업로드_양식.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       use_container_width=True)
    f = st.file_uploader(f"{label} 엑셀(.xlsx) 또는 CSV 올리기", type=["xlsx", "csv"], key=f"up_{kind}")
    if f is None:
        return
    try:
        raw = read_file(f, mapping)
    except Exception:
        st.error("파일을 읽지 못했습니다. 내려받은 양식으로 작성했는지 확인해 주세요.")
        return
    if "name" not in raw.columns:
        st.error("'이름' 열을 찾지 못했습니다. 1행의 열 이름을 확인해 주세요.")
        return
    if len(raw) > 1000:
        st.error("한 번에 1,000줄까지만 올릴 수 있습니다. 나눠서 올려 주세요.")
        return

    rows = builder(raw, fetch(table))
    if not rows:
        st.info("등록할 내용이 없습니다.")
        return
    ok = [r for r in rows if r["상태"] == "등록 예정"]
    dup = [r for r in rows if r["상태"].startswith("중복")]
    bad = [r for r in rows if r["상태"] == "오류"]
    c1, c2, c3 = st.columns(3)
    c1.metric("등록 예정", len(ok))
    c2.metric("중복(건너뜀)", len(dup))
    c3.metric("오류", len(bad))

    show = pd.DataFrame([{k: v for k, v in r.items() if k != "_db"} for r in rows])
    st.dataframe(show, hide_index=True, use_container_width=True)
    if bad:
        st.warning("오류가 있는 줄은 등록되지 않습니다. 엑셀을 고쳐 다시 올리거나, 나머지만 먼저 등록할 수 있습니다.")

    if ok and st.button(f"✅ {len(ok)}명 등록하기", type="primary", key=f"go_{kind}",
                        use_container_width=True):
        payload = [r["_db"] for r in ok]
        for i in range(0, len(payload), 100):
            insert(table, payload[i:i + 100])
        st.session_state["flash"] = f"{len(payload)}명을 등록했습니다."
        st.rerun()


tab_c, tab_t = st.tabs(["아동 명부", "교사 명단"])
with tab_c:
    run_section("child", "children", CHILD_MAP, build_children, "아동")
with tab_t:
    run_section("teacher", "teachers", TEACHER_MAP, build_teachers, "교사")
