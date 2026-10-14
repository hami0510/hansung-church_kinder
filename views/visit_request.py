from datetime import date
import pandas as pd
import streamlit as st
from utils.auth import can_manage, can_view_requests
from utils.db import fetch, insert, update, delete
from utils.notify import notify

REASONS = ["결석이 이어짐", "아픔·건강", "가정 사정", "새가족 방문", "축하·격려", "기타"]
STATUS = ["접수", "예정", "완료"]
ICON = {"접수": "🆕", "예정": "📅", "완료": "✅"}

st.title("🏠 심방 요청")

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

manage = can_manage()
view_list = can_view_requests()

tabs = st.tabs(["요청하기"] + (["요청 목록"] if view_list else []))

# ---------------------------------------------------------------- 요청하기
with tabs[0]:
    with st.form("visit_form", clear_on_submit=True):
        requester = st.text_input("요청하는 선생님 이름 *")
        child_text = st.text_input("대상 (선택)", placeholder="반 정도만 적어도 됩니다 (예: 조이반)")
        reason = st.selectbox("사유", REASONS)
        use_date = st.checkbox("희망 날짜 지정")
        want = st.date_input("희망 날짜", value=date.today())
        memo = st.text_area("메모 (상황을 간단히)")
        if st.form_submit_button("심방 요청 보내기", use_container_width=True):
            if not requester.strip():
                st.error("요청하는 선생님 이름을 입력해 주세요.")
            else:
                insert("visit_requests", {
                    "requester_name": requester.strip(),
                    "child_text": child_text.strip() or None,
                    "reason": reason,
                    "desired_date": want.isoformat() if use_date else None,
                    "memo": memo or None,
                })
                notify("visit", "새 심방 요청이 접수되었습니다.")
                st.session_state["flash"] = "심방 요청이 접수되었습니다."
                st.rerun()

# ---------------------------------------------------------------- 요청 목록
if view_list:
    with tabs[1]:
        req = fetch("visit_requests", "created_at", desc=True)
        if req.empty:
            st.info("접수된 요청이 없습니다.")
        else:
            pick = st.selectbox("상태 보기", ["전체"] + STATUS)
            if pick != "전체":
                req = req[req["status"] == pick]
            req = req.assign(_t=pd.to_datetime(req["created_at"], utc=True).dt.tz_convert("Asia/Seoul"))
            st.caption(f"총 {len(req)}건")
            for _, r in req.iterrows():
                who = r.get("child_text") if isinstance(r.get("child_text"), str) and r.get("child_text") else "대상 없음"
                stt = r["status"] if r["status"] in STATUS else "접수"
                title = f"{ICON[stt]} {r['_t']:%m/%d %H:%M} · {who} · {r['reason']}"
                with st.expander(title):
                    rn = r.get("requester_name") if isinstance(r.get("requester_name"), str) else "(미입력)"
                    st.write(f"**요청 교사**: {rn}")
                    if isinstance(r.get("desired_date"), str) and r["desired_date"]:
                        st.write(f"**희망 날짜**: {r['desired_date']}")
                    if isinstance(r.get("memo"), str) and r["memo"]:
                        st.write(f"**메모**: {r['memo']}")
                    if manage:
                        new_status = st.selectbox("처리 상태", STATUS, index=STATUS.index(stt),
                                                  key=f"vs_{r['id']}")
                        note = st.text_input("교역자 메모", value=r["handler_note"]
                                             if isinstance(r.get("handler_note"), str) else "",
                                             key=f"vn_{r['id']}")
                        b1, b2 = st.columns(2)
                        if b1.button("저장", key=f"vsave_{r['id']}", use_container_width=True):
                            update("visit_requests", r["id"],
                                   {"status": new_status, "handler_note": note or None})
                            st.session_state["flash"] = "저장했습니다."
                            st.rerun()
                        if b2.button("삭제", key=f"vdel_{r['id']}", use_container_width=True):
                            delete("visit_requests", r["id"])
                            st.session_state["flash"] = "요청을 삭제했습니다."
                            st.rerun()
