from datetime import date
import pandas as pd
import streamlit as st
from utils.auth import can_manage, can_view_requests
from utils.db import fetch, insert, update, delete
from utils.notify import notify
from utils.passcode import valid_pin, make_hash, check, locked, add_fail, reset_fail

REASONS = ["결석이 이어짐", "아픔·건강", "가정 사정", "새가족 방문", "축하·격려", "기타"]
STATUS = ["접수", "예정", "완료"]
ICON = {"접수": "🆕", "예정": "📅", "완료": "✅"}

st.title("🏠 심방 요청")

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

manage = can_manage()
view_list = can_view_requests()

names = ["요청하기", "내 요청 수정·삭제"] + (["요청 목록"] if view_list else [])
tabs = st.tabs(names)

# ---------------------------------------------------------------- 요청하기
with tabs[0]:
    with st.form("visit_form", clear_on_submit=True):
        requester = st.text_input("요청하는 선생님 이름 *")
        pin = st.text_input("수정·삭제용 비밀번호 (숫자 4자리) *", type="password", max_chars=4,
                            help="나중에 내 요청을 고치거나 지울 때 필요합니다. 꼭 기억해 두세요.")
        child_text = st.text_input("대상 (선택)", placeholder="반 정도만 적어도 됩니다 (예: 조이반)")
        reason = st.selectbox("사유", REASONS)
        use_date = st.checkbox("희망 날짜 지정")
        want = st.date_input("희망 날짜", value=date.today())
        memo = st.text_area("메모 (상황을 간단히)")
        if st.form_submit_button("심방 요청 보내기", use_container_width=True):
            if not requester.strip():
                st.error("요청하는 선생님 이름을 입력해 주세요.")
            elif not valid_pin(pin):
                st.error("비밀번호는 숫자 4자리로 입력해 주세요.")
            else:
                insert("visit_requests", {
                    "requester_name": requester.strip(),
                    "pass_hash": make_hash(requester, pin),
                    "child_text": child_text.strip() or None,
                    "reason": reason,
                    "desired_date": want.isoformat() if use_date else None,
                    "memo": memo or None,
                })
                notify("visit", "새 심방 요청이 접수되었습니다.",
                       요청교사=requester.strip(), 대상=child_text.strip(), 사유=reason,
                       희망날짜=want.isoformat() if use_date else "", 메모=memo)
                st.session_state["flash"] = "심방 요청이 접수되었습니다. 비밀번호를 꼭 기억해 두세요."
                st.rerun()

# ---------------------------------------------------------------- 내 요청 수정·삭제
with tabs[1]:
    st.caption("요청할 때 정한 이름과 비밀번호(숫자 4자리)로 본인 요청을 찾습니다. "
               "'접수' 상태일 때만 수정·삭제할 수 있습니다.")
    c1, c2 = st.columns(2)
    my_name = c1.text_input("이름", key="vmy_name").strip()
    my_pin = c2.text_input("비밀번호 (숫자 4자리)", type="password", max_chars=4, key="vmy_pin")

    if locked("vmy"):
        st.error("시도 횟수를 초과했습니다. 페이지를 새로고침한 뒤 다시 시도하세요.")
    elif my_name and valid_pin(my_pin):
        req = fetch("visit_requests", "created_at", desc=True)
        mine = pd.DataFrame()
        if not req.empty and "pass_hash" in req.columns:
            mine = req[req.apply(
                lambda r: r.get("requester_name") == my_name and check(my_name, my_pin, r.get("pass_hash")),
                axis=1)]
        if mine.empty:
            add_fail("vmy")
            st.warning("일치하는 요청이 없습니다. 이름과 비밀번호를 확인해 주세요.")
        else:
            reset_fail("vmy")
            mine = mine.assign(_t=pd.to_datetime(mine["created_at"], utc=True).dt.tz_convert("Asia/Seoul"))
            st.caption(f"내 요청 {len(mine)}건")
            for _, r in mine.iterrows():
                rid = str(r["id"])
                stt = r["status"] if r["status"] in STATUS else "접수"
                title = f"{ICON[stt]} {r['_t']:%m/%d %H:%M} · {r['reason']} · {stt}"
                with st.expander(title):
                    if stt != "접수":
                        st.info("이미 처리가 진행되어 수정·삭제할 수 없습니다. 관리자에게 문의해 주세요.")
                        if isinstance(r.get("memo"), str) and r["memo"]:
                            st.write(f"**메모**: {r['memo']}")
                        continue
                    with st.form(f"vedit_{rid}"):
                        e_child = st.text_input("대상 (선택)",
                                                value=r["child_text"] if isinstance(r.get("child_text"), str) else "")
                        e_reason = st.selectbox("사유", REASONS,
                                                index=REASONS.index(r["reason"]) if r["reason"] in REASONS else 0)
                        e_memo = st.text_area("메모", value=r["memo"] if isinstance(r.get("memo"), str) else "")
                        s1, s2 = st.columns(2)
                        saved = s1.form_submit_button("저장", type="primary", use_container_width=True)
                        removed = s2.form_submit_button("삭제", use_container_width=True)
                    if saved:
                        update("visit_requests", r["id"], {
                            "child_text": e_child.strip() or None, "reason": e_reason,
                            "memo": e_memo or None})
                        st.session_state["flash"] = "요청을 수정했습니다."
                        st.rerun()
                    if removed:
                        delete("visit_requests", r["id"])
                        st.session_state["flash"] = "요청을 삭제했습니다."
                        st.rerun()
    else:
        st.info("이름과 비밀번호 4자리를 입력하면 내 요청이 나타납니다.")

# ---------------------------------------------------------------- 요청 목록 (관리자)
if view_list:
    with tabs[2]:
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
