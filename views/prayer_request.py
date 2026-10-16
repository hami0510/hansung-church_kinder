import hmac
import pandas as pd
import streamlit as st
from utils.db import fetch, insert, update, delete
from utils.notify import notify
from utils.passcode import valid_pin, make_hash, check, locked, add_fail, reset_fail

CATS = ["아이", "가정", "교사", "부서", "기타"]
STATUS = ["접수", "기도중", "응답"]
ICON = {"접수": "🆕", "기도중": "🙏", "응답": "🌈"}
MAX_FAILS = 5

st.title("🙏 기도제목 요청")

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

is_pastor = st.session_state.get("pastor_ok") is True

names = ["기도제목 올리기", "내 기도제목 수정·삭제", "🔒 목사님 확인"]
tabs = st.tabs(names)

# ---------------------------------------------------------------- 올리기
with tabs[0]:
    st.caption("기도제목은 목사님만 확인합니다. 아이 실명이나 가정 사정은 필요한 만큼만 적어 주세요.")
    with st.form("prayer_form", clear_on_submit=True):
        requester = st.text_input("선생님 이름 *")
        pin = st.text_input("수정·삭제용 비밀번호 (숫자 4자리) *", type="password", max_chars=4,
                            help="나중에 내 기도제목을 고치거나 지울 때 필요합니다. 꼭 기억해 두세요.")
        cat = st.selectbox("구분", CATS)
        content = st.text_area("기도제목 *")
        if st.form_submit_button("기도제목 보내기", use_container_width=True):
            if not requester.strip():
                st.error("선생님 이름을 입력해 주세요.")
            elif not valid_pin(pin):
                st.error("비밀번호는 숫자 4자리로 입력해 주세요.")
            elif not content.strip():
                st.error("기도제목 내용을 입력해 주세요.")
            else:
                insert("prayer_requests", {"requester_name": requester.strip(),
                                           "pass_hash": make_hash(requester, pin),
                                           "category": cat, "content": content.strip()})
                notify("prayer", "새 기도제목이 접수되었습니다.",
                       선생님=requester.strip(), 구분=cat, 내용=content.strip())
                st.session_state["flash"] = "기도제목이 접수되었습니다. 비밀번호를 꼭 기억해 두세요."
                st.rerun()

# ---------------------------------------------------------------- 내 기도제목 수정·삭제
with tabs[1]:
    st.caption("올릴 때 정한 이름과 비밀번호(숫자 4자리)로 본인 기도제목을 찾습니다. "
               "'접수' 상태일 때만 수정·삭제할 수 있습니다.")
    c1, c2 = st.columns(2)
    my_name = c1.text_input("이름", key="pmy_name").strip()
    my_pin = c2.text_input("비밀번호 (숫자 4자리)", type="password", max_chars=4, key="pmy_pin")

    if locked("pmy"):
        st.error("시도 횟수를 초과했습니다. 페이지를 새로고침한 뒤 다시 시도하세요.")
    elif my_name and valid_pin(my_pin):
        req = fetch("prayer_requests", "created_at", desc=True)
        mine = pd.DataFrame()
        if not req.empty and "pass_hash" in req.columns:
            mine = req[req.apply(
                lambda r: r.get("requester_name") == my_name and check(my_name, my_pin, r.get("pass_hash")),
                axis=1)]
        if mine.empty:
            add_fail("pmy")
            st.warning("일치하는 기도제목이 없습니다. 이름과 비밀번호를 확인해 주세요.")
        else:
            reset_fail("pmy")
            mine = mine.assign(_t=pd.to_datetime(mine["created_at"], utc=True).dt.tz_convert("Asia/Seoul"))
            st.caption(f"내 기도제목 {len(mine)}건")
            for _, r in mine.iterrows():
                rid = str(r["id"])
                stt = r["status"] if r["status"] in STATUS else "접수"
                first = str(r["content"]).replace("\n", " ")[:20]
                with st.expander(f"{ICON[stt]} {r['_t']:%m/%d %H:%M} · {r['category']} · {first}"):
                    if stt != "접수":
                        st.info("이미 기도 중이거나 응답된 기도제목이라 수정·삭제할 수 없습니다.")
                        st.write(r["content"])
                        continue
                    with st.form(f"pedit_{rid}"):
                        e_cat = st.selectbox("구분", CATS,
                                             index=CATS.index(r["category"]) if r["category"] in CATS else 0)
                        e_content = st.text_area("기도제목 *", value=str(r["content"]))
                        s1, s2 = st.columns(2)
                        saved = s1.form_submit_button("저장", type="primary", use_container_width=True)
                        removed = s2.form_submit_button("삭제", use_container_width=True)
                    if saved:
                        if not e_content.strip():
                            st.error("기도제목 내용을 입력해 주세요.")
                        else:
                            update("prayer_requests", r["id"],
                                   {"category": e_cat, "content": e_content.strip()})
                            st.session_state["flash"] = "기도제목을 수정했습니다."
                            st.rerun()
                    if removed:
                        delete("prayer_requests", r["id"])
                        st.session_state["flash"] = "기도제목을 삭제했습니다."
                        st.rerun()
    else:
        st.info("이름과 비밀번호 4자리를 입력하면 내 기도제목이 나타납니다.")

# ---------------------------------------------------------------- 목사님 확인 (목사님 전용)
with tabs[2]:
    if not is_pastor:
        st.caption("기도제목 목록은 목사님만 볼 수 있습니다. (총무·관리자도 열람할 수 없습니다.)")
        pastor_pw = None
        try:
            pastor_pw = st.secrets["auth"]["pastor_password"]
        except Exception:
            pass
        if not pastor_pw:
            st.error("목사님 비밀번호가 아직 설정되지 않았습니다. (Secrets의 [auth] pastor_password)")
        elif st.session_state.get("pastor_fails", 0) >= MAX_FAILS:
            st.error("시도 횟수를 초과했습니다. 페이지를 새로고침한 뒤 다시 시도하세요.")
        else:
            with st.form("pastor_login"):
                pw = st.text_input("목사님 비밀번호", type="password")
                go = st.form_submit_button("확인", use_container_width=True)
            if go:
                if hmac.compare_digest(pw, pastor_pw):
                    st.session_state["pastor_ok"] = True
                    st.session_state["pastor_fails"] = 0
                    st.rerun()
                else:
                    st.session_state["pastor_fails"] = st.session_state.get("pastor_fails", 0) + 1
                    left = MAX_FAILS - st.session_state["pastor_fails"]
                    st.error(f"비밀번호가 올바르지 않습니다. (남은 시도 {left}회)")
    else:
        top1, top2 = st.columns([3, 1])
        top1.success("목사님 확인 모드입니다.")
        if top2.button("🔒 잠그기", use_container_width=True):
            st.session_state["pastor_ok"] = False
            st.rerun()

        req = fetch("prayer_requests", "created_at", desc=True)
        if req.empty:
            st.info("접수된 기도제목이 없습니다.")
        else:
            pick = st.selectbox("상태 보기", ["전체"] + STATUS)
            if pick != "전체":
                req = req[req["status"] == pick]
            req = req.assign(_t=pd.to_datetime(req["created_at"], utc=True).dt.tz_convert("Asia/Seoul"))
            st.caption(f"총 {len(req)}건")
            for _, r in req.iterrows():
                stt = r["status"] if r["status"] in STATUS else "접수"
                first = str(r["content"]).replace("\n", " ")[:20]
                title = f"{ICON[stt]} {r['_t']:%m/%d %H:%M} · {r['category']} · {first}"
                with st.expander(title):
                    rn = r.get("requester_name") if isinstance(r.get("requester_name"), str) else "(미입력)"
                    st.write(f"**선생님**: {rn}")
                    st.write(r["content"])
                    new_status = st.selectbox("상태", STATUS, index=STATUS.index(stt),
                                              key=f"ps_{r['id']}")
                    b1, b2 = st.columns(2)
                    if b1.button("저장", key=f"psave_{r['id']}", use_container_width=True):
                        update("prayer_requests", r["id"], {"status": new_status})
                        st.session_state["flash"] = "저장했습니다."
                        st.rerun()
                    with b2.popover("삭제", use_container_width=True):
                        ok = st.checkbox("삭제에 동의합니다", key=f"pdok_{r['id']}")
                        if st.button("삭제하기", key=f"pdel_{r['id']}", type="primary",
                                     disabled=not ok, use_container_width=True):
                            delete("prayer_requests", r["id"])
                            st.session_state["flash"] = "기도제목을 삭제했습니다."
                            st.rerun()
