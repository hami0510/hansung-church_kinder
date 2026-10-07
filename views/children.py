from datetime import date
import streamlit as st
from utils.db import fetch, insert, update, delete

# 관리자 이중 확인 (직접 접근 방지)
if st.session_state.get("role") != "admin":
    st.error("접근 권한이 없습니다.")
    st.stop()

st.title("🧒 아동 명부")

# 작업 완료 메시지 (rerun 후에도 보이도록 보관)
if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

tab_list, tab_add, tab_edit, tab_del = st.tabs(
    ["명단 보기", "신규 등록", "수정/퇴원 처리", "완전 삭제"]
)

COLS = {
    "name": "이름", "birth_date": "생년월일", "gender": "성별", "class_name": "반",
    "guardian_name": "보호자", "guardian_phone": "연락처", "allergy": "알레르기",
    "notes": "특이사항", "is_new_family": "새가족", "registered_at": "등록일",
}


def label_of(r):
    return f"{r['name']} ({r.get('class_name') or '반 미정'}, {r.get('birth_date') or '생일 미입력'})"


with tab_list:
    df = fetch("children", "name")
    if df.empty:
        st.info("등록된 아동이 없습니다.")
    else:
        show_inactive = st.checkbox("퇴원/비활성 포함", value=False)
        if not show_inactive:
            df = df[df["is_active"] == True]
        keyword = st.text_input("이름 검색")
        if keyword:
            df = df[df["name"].str.contains(keyword, na=False)]
        view = df[list(COLS)].rename(columns=COLS)
        st.dataframe(view, hide_index=True, use_container_width=True)
        st.caption(f"총 {len(view)}명")
        st.download_button(
            "CSV 다운로드",
            view.to_csv(index=False).encode("utf-8-sig"),  # 엑셀에서 한글 안 깨지게
            file_name=f"유치부_명부_{date.today()}.csv",
            mime="text/csv",
        )

with tab_add:
    with st.form("add_child", clear_on_submit=True):
        c1, c2 = st.columns(2)
        name = c1.text_input("이름 *")
        birth = c2.date_input("생년월일", value=date(2021, 1, 1),
                              min_value=date(2015, 1, 1), max_value=date.today())
        gender = c1.selectbox("성별", ["", "남", "여"])
        class_name = c2.text_input("반 (예: 햇살반)")
        g_name = c1.text_input("보호자 이름")
        g_phone = c2.text_input("보호자 연락처")
        allergy = st.text_input("알레르기")
        notes = st.text_area("특이사항")
        new_family = st.checkbox("새가족")
        if st.form_submit_button("등록"):
            if not name.strip():
                st.error("이름은 필수입니다.")
            else:
                insert("children", {
                    "name": name.strip(), "birth_date": birth.isoformat(),
                    "gender": gender or None, "class_name": class_name or None,
                    "guardian_name": g_name or None, "guardian_phone": g_phone or None,
                    "allergy": allergy or None, "notes": notes or None,
                    "is_new_family": new_family,
                })
                st.session_state["flash"] = f"{name.strip()} 등록 완료"
                st.rerun()

with tab_edit:
    df = fetch("children", "name")
    if df.empty:
        st.info("수정할 아동이 없습니다.")
    else:
        options = {label_of(r): r["id"] for _, r in df.iterrows()}
        pick = st.selectbox("아동 선택", list(options), key="edit_pick")
        row = df[df["id"] == options[pick]].iloc[0]
        with st.form("edit_child"):
            c1, c2 = st.columns(2)
            e_class = c1.text_input("반", value=row.get("class_name") or "")
            e_phone = c2.text_input("보호자 연락처", value=row.get("guardian_phone") or "")
            e_allergy = st.text_input("알레르기", value=row.get("allergy") or "")
            e_notes = st.text_area("특이사항", value=row.get("notes") or "")
            e_active = st.checkbox("재적 중 (해제 시 퇴원 처리)", value=bool(row["is_active"]))
            if st.form_submit_button("저장"):
                update("children", row["id"], {
                    "class_name": e_class or None, "guardian_phone": e_phone or None,
                    "allergy": e_allergy or None, "notes": e_notes or None,
                    "is_active": e_active,
                })
                st.session_state["flash"] = f"{row['name']} 정보를 저장했습니다."
                st.rerun()

with tab_del:
    st.subheader("아동 완전 삭제")
    st.warning(
        "완전 삭제는 **되돌릴 수 없으며**, 해당 아동의 출석·심방 기록도 함께 삭제됩니다.\n\n"
        "기록을 남기고 명단에서만 빼려면 '수정/퇴원 처리' 탭에서 **퇴원 처리**를 사용하세요."
    )
    df_del = fetch("children", "name")
    if df_del.empty:
        st.info("삭제할 아동이 없습니다.")
    else:
        options = {label_of(r): (r["id"], r["name"]) for _, r in df_del.iterrows()}
        target = st.selectbox("삭제할 아동 선택", ["선택 안 함"] + list(options), key="del_pick")
        if target != "선택 안 함":
            child_id, child_name = options[target]
            typed = st.text_input(f"확인을 위해 아동 이름 '{child_name}'을(를) 그대로 입력하세요")
            ok = typed.strip() == child_name
            if st.button("완전 삭제", type="primary", disabled=not ok):
                delete("children", child_id)
                st.session_state["flash"] = f"{child_name} 정보를 완전히 삭제했습니다."
                st.rerun()
