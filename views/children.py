from datetime import date
import streamlit as st
from utils.db import fetch, insert, update

# 관리자 이중 확인 (직접 접근 방지)
if st.session_state.get("role") != "admin":
    st.error("접근 권한이 없습니다.")
    st.stop()

st.title("🧒 아동 명부")

tab_list, tab_add, tab_edit = st.tabs(["명단 보기", "신규 등록", "수정/퇴원 처리"])

COLS = {
    "name": "이름", "birth_date": "생년월일", "gender": "성별", "class_name": "반",
    "guardian_name": "보호자", "guardian_phone": "연락처", "allergy": "알레르기",
    "notes": "특이사항", "is_new_family": "새가족", "registered_at": "등록일",
}

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
                st.success(f"{name} 등록 완료")

with tab_edit:
    df = fetch("children", "name")
    if df.empty:
        st.info("수정할 아동이 없습니다.")
    else:
        options = {f"{r['name']} ({r.get('class_name') or '반 미정'})": r["id"] for _, r in df.iterrows()}
        pick = st.selectbox("아동 선택", list(options))
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
                st.success("저장되었습니다. 새로고침하면 반영됩니다.")
