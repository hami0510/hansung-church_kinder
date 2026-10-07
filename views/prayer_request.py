import pandas as pd
import streamlit as st
from utils.auth import can_manage, can_view_requests
from utils.db import fetch, insert, update, delete
from utils.notify import notify
from utils.pick import search_pick

CATS = ["아이", "가정", "교사", "부서", "기타"]
STATUS = ["접수", "기도중", "응답"]
ICON = {"접수": "🆕", "기도중": "🙏", "응답": "🌈"}

st.title("🙏 기도제목 요청")

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

manage = can_manage()
view_list = can_view_requests()

teachers = fetch("teachers", "name")
if teachers.empty:
    st.warning("먼저 '교사 · 반 명단'에서 교사를 등록해 주세요.")
    st.stop()
for col in ["service_part", "class_no"]:
    if col not in teachers.columns:
        teachers[col] = None
teachers = teachers[teachers["is_active"] == True]

tabs = st.tabs(["기도제목 올리기"] + (["기도제목 목록"] if view_list else []))

# ---------------------------------------------------------------- 올리기
with tabs[0]:
    teacher_id = search_pick(teachers, "선생님", key="pr_t")
    with st.form("prayer_form", clear_on_submit=True):
        cat = st.selectbox("구분", CATS)
        content = st.text_area("기도제목 *")
        if st.form_submit_button("기도제목 보내기", use_container_width=True):
            if teacher_id is None:
                st.error("선생님을 선택해 주세요.")
            elif not content.strip():
                st.error("기도제목 내용을 입력해 주세요.")
            else:
                insert("prayer_requests", {"teacher_id": teacher_id, "category": cat,
                                           "content": content.strip()})
                notify("prayer", "새 기도제목이 접수되었습니다.")
                st.session_state["flash"] = "기도제목이 접수되었습니다."
                st.rerun()

# ---------------------------------------------------------------- 목록
if view_list:
    with tabs[1]:
        req = fetch("prayer_requests", "created_at", desc=True)
        if req.empty:
            st.info("접수된 기도제목이 없습니다.")
        else:
            pick = st.selectbox("상태 보기", ["전체"] + STATUS)
            if pick != "전체":
                req = req[req["status"] == pick]
            t_name = dict(zip(teachers["id"], teachers["name"]))
            req = req.assign(_t=pd.to_datetime(req["created_at"], utc=True).dt.tz_convert("Asia/Seoul"))
            st.caption(f"총 {len(req)}건")
            for _, r in req.iterrows():
                stt = r["status"] if r["status"] in STATUS else "접수"
                first = str(r["content"]).replace("\n", " ")[:20]
                title = f"{ICON[stt]} {r['_t']:%m/%d %H:%M} · {r['category']} · {first}"
                with st.expander(title):
                    st.write(f"**선생님**: {t_name.get(r['teacher_id'], '(삭제된 교사)')}")
                    st.write(r["content"])
                    if manage:
                        new_status = st.selectbox("상태", STATUS, index=STATUS.index(stt),
                                                  key=f"ps_{r['id']}")
                        b1, b2 = st.columns(2)
                        if b1.button("저장", key=f"psave_{r['id']}", use_container_width=True):
                            update("prayer_requests", r["id"], {"status": new_status})
                            st.session_state["flash"] = "저장했습니다."
                            st.rerun()
                        if b2.button("삭제", key=f"pdel_{r['id']}", use_container_width=True):
                            delete("prayer_requests", r["id"])
                            st.session_state["flash"] = "기도제목을 삭제했습니다."
                            st.rerun()
