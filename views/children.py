from datetime import date
import streamlit as st
from utils.db import (fetch, insert, update, delete,
                      process_image, upload_photo, remove_photo, photo_url)
from utils.ui import child_cards

# 교사(일반)에게 보호자 이름·연락처를 보여줄지 (False = 가림)
TEACHER_SEE_CONTACT = False
# 교사(일반)에게 아이 사진을 보여줄지 (False = 관리자만)
TEACHER_SEE_PHOTO = False

CLASSES = ["조이(5세)", "해피(6세)", "홀리(7세)", "새싹(새가족)"]
MAX_UPLOAD_MB = 10

is_admin = st.session_state.get("role") == "admin"
SHOW_CONTACT = is_admin or TEACHER_SEE_CONTACT
SHOW_PHOTO = is_admin or TEACHER_SEE_PHOTO

st.title("🧒 아동 명부")

# 작업 완료 메시지 (rerun 후에도 보이도록 보관)
if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

if is_admin:
    tab_list, tab_add, tab_edit, tab_del = st.tabs(
        ["명단", "신규 등록", "수정/퇴원", "완전 삭제"]
    )
else:
    tab_list = st.tabs(["명단 보기"])[0]
    st.caption("🔒 등록·수정·삭제는 관리자 로그인 후 가능합니다. (왼쪽 위 ≫ 메뉴에서 로그인)")

COLS = {
    "name": "이름", "birth_date": "생년월일", "gender": "성별", "class_name": "반",
    "guardian_name": "보호자", "guardian_phone": "연락처", "allergy": "알레르기",
    "notes": "특이사항", "is_new_family": "새가족", "registered_at": "등록일",
}


def label_of(r):
    return f"{r['name']} ({r.get('class_name') or '반 미정'}, {r.get('birth_date') or '생일 미입력'})"


def too_big(f):
    return f is not None and f.size > MAX_UPLOAD_MB * 1024 * 1024


with tab_list:
    df = fetch("children", "name")
    if df.empty:
        st.info("등록된 아동이 없습니다.")
    else:
        if "photo_path" not in df.columns:
            df["photo_path"] = None
        if is_admin:
            show_inactive = st.checkbox("퇴원/비활성 포함", value=False)
            if not show_inactive:
                df = df[df["is_active"] == True]
        else:
            df = df[df["is_active"] == True]  # 교사에게는 재적 중인 아동만

        keyword = st.text_input("이름 검색")
        present = set(df["class_name"].dropna().unique())
        classes = [c for c in CLASSES if c in present] + sorted(present - set(CLASSES))
        pick_class = st.selectbox("반 선택", ["전체"] + classes)
        if keyword:
            df = df[df["name"].str.contains(keyword, na=False)]
        if pick_class != "전체":
            df = df[df["class_name"] == pick_class]

        if SHOW_PHOTO:
            df = df.copy()
            df["photo_url"] = df["photo_path"].apply(lambda p: photo_url(p) if p else "")

        st.caption(f"총 {len(df)}명")
        child_cards(df, show_contact=SHOW_CONTACT, show_inactive_tag=is_admin,
                    show_photo=SHOW_PHOTO)

        if is_admin and not df.empty:
            view = df[list(COLS)].rename(columns=COLS)
            st.download_button(
                "CSV 다운로드",
                view.to_csv(index=False).encode("utf-8-sig"),  # 엑셀에서 한글 안 깨지게
                file_name=f"유치부_명부_{date.today()}.csv",
                mime="text/csv",
                use_container_width=True,
            )

if is_admin:
    with tab_add:
        with st.form("add_child", clear_on_submit=True):
            c1, c2 = st.columns(2)
            name = c1.text_input("이름 *")
            birth = c2.date_input("생년월일", value=date(2021, 1, 1),
                                  min_value=date(2015, 1, 1), max_value=date.today())
            gender = c1.selectbox("성별", ["", "남", "여"])
            class_pick = c2.selectbox("반", ["선택 안 함"] + CLASSES)
            g_name = c1.text_input("보호자 이름")
            g_phone = c2.text_input("보호자 연락처")
            allergy = st.text_input("알레르기")
            notes = st.text_area("특이사항")
            new_family = st.checkbox("새가족 (새싹 반을 고르면 자동 체크)")
            photo = st.file_uploader("사진 (선택)", type=["jpg", "jpeg", "png", "webp"])
            if st.form_submit_button("등록", use_container_width=True):
                if not name.strip():
                    st.error("이름은 필수입니다.")
                elif too_big(photo):
                    st.error(f"사진은 {MAX_UPLOAD_MB}MB 이하만 올릴 수 있습니다.")
                else:
                    cls = None if class_pick == "선택 안 함" else class_pick
                    res = insert("children", {
                        "name": name.strip(), "birth_date": birth.isoformat(),
                        "gender": gender or None, "class_name": cls,
                        "guardian_name": g_name or None, "guardian_phone": g_phone or None,
                        "allergy": allergy or None, "notes": notes or None,
                        "is_new_family": bool(new_family or (cls or "").startswith("새싹")),
                    })
                    msg = f"{name.strip()} 등록 완료"
                    if photo is not None:
                        try:
                            new_id = res.data[0]["id"]
                            path = upload_photo(new_id, process_image(photo))
                            update("children", new_id, {"photo_path": path})
                        except Exception:
                            msg += " (사진 저장에 실패했습니다. 수정 탭에서 다시 올려 주세요.)"
                    st.session_state["flash"] = msg
                    st.rerun()

    with tab_edit:
        df_e = fetch("children", "name")
        if df_e.empty:
            st.info("수정할 아동이 없습니다.")
        else:
            if "photo_path" not in df_e.columns:
                df_e["photo_path"] = None
            options = {label_of(r): r["id"] for _, r in df_e.iterrows()}
            pick = st.selectbox("아동 선택", list(options), key="edit_pick")
            row = df_e[df_e["id"] == options[pick]].iloc[0]
            old_path = row.get("photo_path") or None

            if old_path:
                url = photo_url(old_path)
                if url:
                    st.image(url, width=120)

            cur_class = row.get("class_name") or ""
            class_opts = ["선택 안 함"] + CLASSES + ([cur_class] if cur_class and cur_class not in CLASSES else [])
            idx = class_opts.index(cur_class) if cur_class in class_opts else 0

            with st.form("edit_child"):
                c1, c2 = st.columns(2)
                e_class = c1.selectbox("반", class_opts, index=idx)
                e_phone = c2.text_input("보호자 연락처", value=row.get("guardian_phone") or "")
                e_allergy = st.text_input("알레르기", value=row.get("allergy") or "")
                e_notes = st.text_area("특이사항", value=row.get("notes") or "")
                e_photo = st.file_uploader("사진 변경 (선택)", type=["jpg", "jpeg", "png", "webp"],
                                           key=f"e_photo_{row['id']}")
                del_photo = st.checkbox("현재 사진 삭제") if old_path else False
                e_active = st.checkbox("재적 중 (해제 시 퇴원 처리)", value=bool(row["is_active"]))
                if st.form_submit_button("저장", use_container_width=True):
                    if too_big(e_photo):
                        st.error(f"사진은 {MAX_UPLOAD_MB}MB 이하만 올릴 수 있습니다.")
                    else:
                        cls = None if e_class == "선택 안 함" else e_class
                        data = {
                            "class_name": cls, "guardian_phone": e_phone or None,
                            "allergy": e_allergy or None, "notes": e_notes or None,
                            "is_active": e_active,
                        }
                        if (cls or "").startswith("새싹"):
                            data["is_new_family"] = True
                        msg = f"{row['name']} 정보를 저장했습니다."
                        if e_photo is not None:
                            try:
                                data["photo_path"] = upload_photo(
                                    row["id"], process_image(e_photo), old_path)
                            except Exception:
                                msg += " (사진 저장에 실패했습니다.)"
                        elif del_photo:
                            remove_photo(old_path)
                            data["photo_path"] = None
                        update("children", row["id"], data)
                        st.session_state["flash"] = msg
                        st.rerun()

    with tab_del:
        st.subheader("아동 완전 삭제")
        st.warning(
            "완전 삭제는 **되돌릴 수 없으며**, 해당 아동의 사진과 출석·심방 기록도 함께 삭제됩니다.\n\n"
            "기록을 남기고 명단에서만 빼려면 '수정/퇴원' 탭에서 **퇴원 처리**를 사용하세요."
        )
        df_del = fetch("children", "name")
        if df_del.empty:
            st.info("삭제할 아동이 없습니다.")
        else:
            if "photo_path" not in df_del.columns:
                df_del["photo_path"] = None
            options = {label_of(r): (r["id"], r["name"], r.get("photo_path") or None)
                       for _, r in df_del.iterrows()}
            target = st.selectbox("삭제할 아동 선택", ["선택 안 함"] + list(options), key="del_pick")
            if target != "선택 안 함":
                child_id, child_name, child_photo = options[target]
                typed = st.text_input(f"확인을 위해 아동 이름 '{child_name}'을(를) 그대로 입력하세요")
                ok = typed.strip() == child_name
                if st.button("완전 삭제", type="primary", disabled=not ok, use_container_width=True):
                    remove_photo(child_photo)
                    delete("children", child_id)
                    st.session_state["flash"] = f"{child_name} 정보를 완전히 삭제했습니다."
                    st.rerun()
