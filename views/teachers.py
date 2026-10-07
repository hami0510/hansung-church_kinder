from datetime import date
import streamlit as st
from utils.auth import can_manage, can_see_contact
from utils.db import fetch, insert, update, delete

CLASSES = ["조이(5세)", "해피(6세)", "홀리(7세)", "새싹(새가족)"]
ROLES = ["부장", "총무", "서기", "회계", "교사", "보조교사"]

st.title("👩‍🏫 교사 · 반 명단")

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

manage = can_manage()
see_contact = can_see_contact()

names = ["명단"] + (["등록", "수정/삭제"] if manage else [])
tabs = st.tabs(names)

with tabs[0]:
    df = fetch("teachers", "name")
    if df.empty:
        st.info("등록된 교사가 없습니다.")
    else:
        if "role_title" not in df.columns:
            df["role_title"] = None
        df = df[df["is_active"] == True]
        view_mode = st.radio("보기", ["반별", "전체"], horizontal=True)
        if view_mode == "반별":
            present = set(df["class_name"].dropna().unique())
            order = [c for c in CLASSES if c in present] + sorted(present - set(CLASSES))
            for c in order + ([None] if df["class_name"].isna().any() else []):
                sub = df[df["class_name"] == c] if c else df[df["class_name"].isna()]
                st.subheader(f"🌟 {c or '반 미정'} ({len(sub)}명)")
                for _, r in sub.iterrows():
                    line = f"- **{r['name']}** {('· ' + r['role_title']) if r.get('role_title') else ''}"
                    if see_contact and r.get("phone"):
                        line += f" · 📞 {r['phone']}"
                    st.markdown(line)
        else:
            cols = {"name": "이름", "role_title": "직분", "class_name": "반"}
            if see_contact:
                cols["phone"] = "연락처"
            cols["notes"] = "메모"
            st.dataframe(df[list(cols)].rename(columns=cols), hide_index=True,
                         use_container_width=True)
        st.caption(f"총 {len(df)}명")

if manage:
    with tabs[1]:
        with st.form("add_teacher", clear_on_submit=True):
            c1, c2 = st.columns(2)
            name = c1.text_input("이름 *")
            phone = c2.text_input("연락처")
            cls = c1.selectbox("담당 반", ["선택 안 함"] + CLASSES)
            role = c2.selectbox("직분", ROLES, index=ROLES.index("교사"))
            notes = st.text_area("메모")
            if st.form_submit_button("등록", use_container_width=True):
                if not name.strip():
                    st.error("이름은 필수입니다.")
                else:
                    insert("teachers", {
                        "name": name.strip(), "phone": phone or None,
                        "class_name": None if cls == "선택 안 함" else cls,
                        "role_title": role, "notes": notes or None})
                    st.session_state["flash"] = f"{name.strip()} 선생님 등록 완료"
                    st.rerun()

    with tabs[2]:
        df_e = fetch("teachers", "name")
        if df_e.empty:
            st.info("수정할 교사가 없습니다.")
        else:
            opts = {f"{r['name']} ({r.get('class_name') or '반 미정'})": r["id"]
                    for _, r in df_e.iterrows()}
            pick = st.selectbox("교사 선택", list(opts))
            row = df_e[df_e["id"] == opts[pick]].iloc[0]
            cur_cls = row.get("class_name") or ""
            cls_opts = ["선택 안 함"] + CLASSES + ([cur_cls] if cur_cls and cur_cls not in CLASSES else [])
            cur_role = row.get("role_title") or "교사"
            role_opts = ROLES + ([cur_role] if cur_role not in ROLES else [])
            with st.form("edit_teacher"):
                c1, c2 = st.columns(2)
                e_phone = c1.text_input("연락처", value=row.get("phone") or "")
                e_cls = c2.selectbox("담당 반", cls_opts,
                                     index=cls_opts.index(cur_cls) if cur_cls in cls_opts else 0)
                e_role = c1.selectbox("직분", role_opts, index=role_opts.index(cur_role))
                e_notes = st.text_area("메모", value=row.get("notes") or "")
                e_active = st.checkbox("활동 중 (해제 시 명단에서 숨김)",
                                       value=bool(row["is_active"]))
                if st.form_submit_button("저장", use_container_width=True):
                    update("teachers", row["id"], {
                        "phone": e_phone or None,
                        "class_name": None if e_cls == "선택 안 함" else e_cls,
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
