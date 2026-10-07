import hmac
import streamlit as st

st.set_page_config(page_title="유치부 관리", page_icon="⛪", layout="wide")

MAX_FAILS = 5  # 한 접속(세션)에서 비밀번호 틀릴 수 있는 횟수

# 처음 접속하면 일반(조회 전용)으로 시작
if "role" not in st.session_state:
    st.session_state["role"] = "guest"
    st.session_state["fails"] = 0

role = st.session_state["role"]

home = st.Page("views/home.py", title="홈", icon="🏠", default=True)
events = st.Page("views/events.py", title="일정 관리", icon="📅")
children = st.Page("views/children.py", title="아동 명부", icon="🧒")

# 모든 방문자에게 같은 메뉴 (등록·수정·삭제는 각 화면에서 관리자만)
pages = {"메뉴": [home, events, children]}

with st.sidebar:
    if role == "admin":
        st.caption("접속 권한: 관리자(목사님/임원)")
        if st.button("관리자 로그아웃"):
            st.session_state["role"] = "guest"
            st.session_state["fails"] = 0
            st.rerun()
    else:
        st.caption("접속 권한: 일반 (조회 전용)")
        with st.expander("🔒 관리자 로그인"):
            if st.session_state["fails"] >= MAX_FAILS:
                st.error("시도 횟수를 초과했습니다. 페이지를 새로고침한 뒤 다시 시도하세요.")
            else:
                with st.form("admin_login"):
                    pw = st.text_input("관리자 비밀번호", type="password")
                    submitted = st.form_submit_button("로그인")
                if submitted:
                    if hmac.compare_digest(pw, st.secrets["auth"]["admin_password"]):
                        st.session_state["role"] = "admin"
                        st.session_state["fails"] = 0
                        st.rerun()
                    else:
                        st.session_state["fails"] += 1
                        left = MAX_FAILS - st.session_state["fails"]
                        st.error(f"비밀번호가 올바르지 않습니다. (남은 시도 {left}회)")

st.navigation(pages).run()
