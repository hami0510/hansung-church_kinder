from datetime import date
import streamlit as st
from utils.auth import can_manage, can_see_contact
from utils.db import (fetch, insert, update, delete,
                      process_image, upload_photo, remove_photo, photo_url)
from utils.labels import class_label
from utils.ui import child_cards

# 교사(일반)에게 보호자 이름·연락처를 보여줄지 (False = 가림)
TEACHER_SEE_CONTACT = False
# 교사(일반)에게 아이 사진을 보여줄지
TEACHER_SEE_PHOTO = True

CLASSES = ["조이(5세)", "해피(6세)", "홀리(7세)", "새싹(새가족)"]
PARTS = ["1부", "2부"]
NOS = [1, 2, 3, 4, 5]
NONE = "선택 안 함"
MAX_UPLOAD_MB = 10

manage = can_manage()
SHOW_CONTACT = can_see_contact() or TEACHER_SEE_CONTACT
SHOW_PHOTO = True if manage else TEACHER_SEE_PHOTO

st.title("🧒 아동 명부")

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

if manage:
    tab_list, tab_add, tab_edit, tab_del = st.tabs(
        ["명단", "신규 등록", "수정/퇴원", "완전 삭제"]
    )
else:
    tab_list = st.tabs(["명단 보기"])[0]
    st.caption("🔒 등록·수정·삭제는 관리자 로그인 후 가능합니다. (왼쪽 위 ≫ 메뉴에서 로그인)")

COLS = {
    "name": "이름", "birth_date": "생년월일", "gender": "성별", "class_name": "반",
    "service_part": "부", "class_no": "반 번호",
    "guardian_name": "보호자", "guardian_phone": "연락처", "allergy": "알레르기",
    "notes": "특이사항", "is_new_family": "새가족", "registered_at": "등록일",
}


def to_no(v):
    try:
        return int(v)
    except Exception:
        return None


def s_or_empty(v):
    return v if isinstance(v, str) else ""


def label_of(r):
    return f"{r['name']} ({class_label(r)}, {r.get('birth_date') or '생일 미입력'})"


def too_big(f):
    return f is not None and f.size > MAX_UPLOAD_MB * 1024 * 1024


def ensure_cols(df):
    for col in ["photo_path", "service_part", "class_no"]:
        if col not in df.columns:
            df[col] = None
    return df


with tab_list:
    df = fetch("children", "name")
    if df.empty:
        st.info("등록된 아동이 없습니다.")
    else:
        df = ensure_cols(df)
        if manage:
            show_inactive = st.checkbox("퇴원/비활성 포함", value=False)
            if not show_inactive:
                df = df[df["is_active"] == True]
        else:
            df = df[df["is_active"] == True]

        keyword = st.text_input("이름 검색")
        f1, f2 = st.columns(2)
        present = set(df["class_name"].dropna().unique())
        classes = [c for c in CLASSES if c in present] + sorted(present - set(CLASSES))
        pick_class = f1.selectbox("반 선택", ["전체"] + classes)
        pick_part = f2.selectbox("부 선택", ["전체"] + PARTS)
        if keyword:
            df = df[df["name"].str.contains(keyword, na=False)]
        if pick_class != "전체":
            df = df[df["class_name"] == pick_class]
        if pick_part != "전체":
            df = df[df["service_part"] == pick_part]

        df = df.assign(_no=df["class_no"].apply(lambda v: to_no(v) or 99)).sort_values(
            ["class_name", "service_part", "_no", "name"], na_position="last")

        if SHOW_PHOTO:
            df = df.copy()
            df["photo_url"] = df["photo_path"].apply(lambda p: photo_url(p) if p else "")

        st.caption(f"총 {len(df)}명")
        child_cards(df, show_contact=SHOW_CONTACT, show_inactive_tag=manage,
                    show_photo=SHOW_PHOTO)

        if manage and not df.empty:
            view = df[[c for c in COLS if c in df.columns]].rename(columns=COLS)
            st.download_button(
                "CSV 다운로드",
                view.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"유치부_명부_{date.today()}.csv",
                mime="text/csv",
                use_container_width=True,
            )

if manage:
    with tab_add:
        with st.form("add_child", clear_on_submit=True):
            c1, c2 = st.columns(2)
            name = c1.text_input("이름 *")
            birth = c2.date_input("생년월일", value=date(2021, 1, 1),
                                  min_value=date(2015, 1, 1), max_value=date.today())
            gender = c1.selectbox("성별", ["", "남", "여"])
            g_name = c2.text_input("보호자 이름")
            c3, c4, c5 = st.columns(3)
            class_pick = c3.selectbox("반", [NONE] + CLASSES)
            part_pick = c4.selectbox("부", [NONE] + PARTS)
            no_pick = c5.selectbox("반 번호", [NONE] + NOS,
                                   format_func=lambda x: x if x == NONE else f"{x}반")
            g_phone = st.text_input("보호자 연락처")
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
                    cls = None if class_pick == NONE else class_pick
                    res = insert("children", {
                        "name": name.strip(), "birth_date": birth.isoformat(),
                        "gender": gender or None, "class_name": cls,
                        "service_part": None if part_pick == NONE else part_pick,
                        "class_no": None if no_pick == NONE else int(no_pick),
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
            df_e = ensure_cols(df_e)
            options = {label_of(r): r["id"] for _, r in df_e.iterrows()}
            pick = st.selectbox("아동 선택", list(options), key="edit_pick")
            row = df_e[df_e["id"] == options[pick]].iloc[0]
            old_path = row.get("photo_path") if isinstance(row.get("photo_path"), str) else None

            if old_path:
                url = photo_url(old_path)
                if url:
                    st.image(url, width=120)

            cur_class = s_or_empty(row.get("class_name"))
            class_opts = [NONE] + CLASSES + ([cur_class] if cur_class and cur_class not in CLASSES else [])
            cur_part = s_or_empty(row.get("service_part"))
            part_opts = [NONE] + PARTS + ([cur_part] if cur_part and cur_part not in PARTS else [])
            cur_no = to_no(row.get("class_no"))
            no_opts = [NONE] + NOS

            with st.form("edit_child"):
                c3, c4, c5 = st.columns(3)
                e_class = c3.selectbox("반", class_opts,
                                       index=class_opts.index(cur_class) if cur_class in class_opts else 0)
                e_part = c4.selectbox("부", part_opts,
                                      index=part_opts.index(cur_part) if cur_part in part_opts else 0)
                e_no = c5.selectbox("반 번호", no_opts,
                                    index=no_opts.index(cur_no) if cur_no in no_opts else 0,
                                    format_func=lambda x: x if x == NONE else f"{x}반")
                e_phone = st.text_input("보호자 연락처", value=row.get("guardian_phone") or "")
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
                        cls = None if e_class == NONE else e_class
                        data = {
                            "class_name": cls,
                            "service_part": None if e_part == NONE else e_part,
                            "class_no": None if e_no == NONE else int(e_no),
                            "guardian_phone": e_phone or None,
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
            df_del = ensure_cols(df_del)
            options = {label_of(r): (r["id"], r["name"],
                                     r["photo_path"] if isinstance(r.get("photo_path"), str) else None)
                       for _, r in df_del.iterrows()}
            target = st.selectbox("삭제할 아동 선택", [NONE] + list(options), key="del_pick")
            if target != NONE:
                child_id, child_name, child_photo = options[target]
                typed = st.text_input(f"확인을 위해 아동 이름 '{child_name}'을(를) 그대로 입력하세요")
                ok = typed.strip() == child_name
                if st.button("완전 삭제", type="primary", disabled=not ok, use_container_width=True):
                    remove_photo(child_photo)
                    delete("children", child_id)
                    st.session_state["flash"] = f"{child_name} 정보를 완전히 삭제했습니다."
                    st.rerun()
