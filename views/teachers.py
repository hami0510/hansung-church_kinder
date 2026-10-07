import streamlit as st
from utils.auth import can_manage, can_see_contact
from utils.db import fetch, insert, update, delete
from utils.labels import class_label

CLASSES = ["조이(5세)", "해피(6세)", "홀리(7세)", "새싹(새가족)"]
PARTS = ["1부", "2부", "1·2부 모두"]
NOS = [1, 2, 3, 4, 5]
ROLES = ["부장", "총무", "서기", "회계", "교사", "보조교사"]
NONE = "선택 안 함"

st.title("👩‍🏫 교사 · 반 명단")

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

manage = can_manage()
see_contact = can_see_contact()

tabs = st.tabs(["명단"] + (["등록", "수정/삭제"] if manage else []))


def to_no(v):
    try:
        return int(v)
    except Exception:
        return None


with tabs[0]:
    df = fetch("teachers", "name")
    if df.empty:
        st.info("등록된 교사가 없습니다.")
    else:
        for col in ["role_title", "service_part", "class_no"]:
            if col not in df.columns:
                df[col] = None
        df = df[df["is_active"] == True]
        df = df.sort_values(["service_part", "class_no", "name"], na_position="last")

        view_mode = st.radio("보기", ["반별", "전체"], horizontal=True)
        if view_mode == "반별":
            present = set(df["class_name"].dropna().unique())
            order = [c for c in CLASSES if c in present] + sorted(present - set(CLASSES))
            if df["class_name"].isna().any():
                order.append(None)
            for c in order:
                sub = df[df["class_name"] == c] if c else df[df["class_name"].isna()]
                st.subheader(f"🌟 {c or '반 미정'} ({len(sub)}명)")
                for _, r in sub.iterrows():
                    where = " · ".join(
                        x for x in [r["service_part"] if isinstance(r["service_part"], str) else "",
                                    f"{to_no(r['class_no'])}반" if to_no(r["class_no"]) else ""] if x)
                    line = f"- **{r['name']}**"
                    if isinstance(r.get("role_title"), str) and r["role_title"]:
                        line += f" · {r['role_title']}"
                    if where:
                        line += f" · {where}"
                    if see_contact and r.get("phone"):
                        line += f" · 📞 {r['phone']}"
                    st.markdown(line)
        else:
            show = df.copy()
            show["class_no"] = show["class_no"].apply(lambda v: f"{to_no(v)}반" if to_no(v) else "")
            cols = {"name": "이름", "role_title": "직분", "class_name": "반",
                    "service_part": "부", "class_no": "반 번호"}
            if see_contact:
                cols["phone"] = "연락처"
            cols["notes"] = "메모"
            st.dataframe(show[list(cols)].rename(columns=cols), hide_index=True,
                         use_container_width=True)
        st.caption(f"총 {len(df)}명")

if manage:
    with tabs[1]:
        with st.form("add_teacher", clear_on_submit=True):
            c1, c2 = st.columns(2)
            name = c1.text_input("이름 *")
            phone = c2.text_input("연락처")
            c3, c4, c5 = st.columns(3)
            cls = c3.selectbox("담당 반", [NONE] + CLASSES)
            part = c4.selectbox("부", [NONE] + PARTS)
            no = c5.selectbox("반 번호", [NONE] + NOS,
                              format_func=lambda x: x if x == NONE else f"{x}반")
            role = st.selectbox("직분", ROLES, index=ROLES.index("교사"))
            notes = st.text_area("메모")
            if st.form_submit_button("등록", use_container_width=True):
                if not name.strip():
                    st.error("이름은 필수입니다.")
                else:
                    insert("teachers", {
                        "name": name.strip(), "phone": phone or None,
                        "class_name": None if cls == NONE else cls,
                        "service_part": None if part == NONE else part,
                        "class_no": None if no == NONE else int(no),
                        "role_title": role, "notes": notes or None})
                    st.session_state["flash"] = f"{name.strip()} 선생님 등록 완료"
                    st.rerun()

    with tabs[2]:
        df_e = fetch("teachers", "name")
        if df_e.empty:
            st.info("수정할 교사가 없습니다.")
        else:
            for col in ["role_title", "service_part", "class_no"]:
                if col not in df_e.columns:
                    df_e[col] = None
            opts = {f"{r['name']} ({class_label(r)})": r["id"] for _, r in df_e.iterrows()}
            pick = st.selectbox("교사 선택", list(opts))
            row = df_e[df_e["id"] == opts[pick]].iloc[0]

            cur_cls = row.get("class_name") if isinstance(row.get("class_name"), str) else ""
            cls_opts = [NONE] + CLASSES + ([cur_cls] if cur_cls and cur_cls not in CLASSES else [])
            cur_part = row.get("service_part") if isinstance(row.get("service_part"), str) else ""
            part_opts = [NONE] + PARTS + ([cur_part] if cur_part and cur_part not in PARTS else [])
            cur_no = to_no(row.get("class_no"))
            no_opts = [NONE] + NOS
            cur_role = row.get("role_title") if isinstance(row.get("role_title"), str) and row.get("role_title") else "교사"
            role_opts = ROLES + ([cur_role] if cur_role not in ROLES else [])

            with st.form("edit_teacher"):
                e_phone = st.text_input("연락처", value=row.get("phone") or "")
                c3, c4, c5 = st.columns(3)
                e_cls = c3.selectbox("담당 반", cls_opts,
                                     index=cls_opts.index(cur_cls) if cur_cls in cls_opts else 0)
                e_part = c4.selectbox("부", part_opts,
                                      index=part_opts.index(cur_part) if cur_part in part_opts else 0)
                e_no = c5.selectbox("반 번호", no_opts,
                                    index=no_opts.index(cur_no) if cur_no in no_opts else 0,
                                    format_func=lambda x: x if x == NONE else f"{x}반")
                e_role = st.selectbox("직분", role_opts, index=role_opts.index(cur_role))
                e_notes = st.text_area("메모", value=row.get("notes") or "")
                e_active = st.checkbox("활동 중 (해제 시 명단에서 숨김)",
                                       value=bool(row["is_active"]))
                if st.form_submit_button("저장", use_container_width=True):
                    update("teachers", row["id"], {
                        "phone": e_phone or None,
                        "class_name": None if e_cls == NONE else e_cls,
                        "service_part": None if e_part == NONE else e_part,
                        "class_no": None if e_no == NONE else int(e_no),
                        "role_title": e_role, "notes": e_notes or None,
                        "is_active": e_active})
                    st.session_state["flash"] = f"{row['name']} 선생님 정보를 저장했습니다."
                    st.rerun()

            st.divider()
            st.caption("완전 삭제는 되돌릴 수 없고, 해당 교사의 보고 기록도 함께 삭제됩니다.")
            ok = st.checkbox("삭제에 동의합니다", key="t_del_ok")
            if st.button("이 교사 완전 삭제", type="primary", disabled=not ok,
                         use_container_width=True):
                delete("teachers", row["id"])
                st.session_state["flash"] = f"{row['name']} 선생님을 삭제했습니다."
                st.rerun()
