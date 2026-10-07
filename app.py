import hmac
import streamlit as st

st.set_page_config(page_title="유치부 관리", page_icon="⛪", layout="wide")


def check_login():
    if st.session_state.get("role"):
        return True

    st.title("⛪ 유치부 관리 시스템")
    with st.form("login"):
        pw = st.text_input("비밀번호", type="password")
        submitted = st.form_submit_button("로그인")

    if submitted:
        admin_pw = st.secrets["auth"]["admin_password"]
        teacher_pw = st.secrets["auth"]["teacher_password"]
        if hmac.compare_digest(pw, admin_pw):
            st.session_state["role"] = "admin"
            st.rerun()
        elif hmac.compare_digest(pw, teacher_pw):
            st.session_state["role"] = "teacher"
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")
    return False


if not check_login():
    st.stop()

role = st.session_state["role"]

home = st.Page("views/home.py", title="홈", icon="🏠", default=True)
events = st.Page("views/events.py", title="일정 관리", icon="📅")
children = st.Page("views/children.py", title="아동 명부", icon="🧒")

# 권한별 메뉴: 교사는 일정/홈만, 관리자는 전체
if role == "admin":
    pages = {"공통": [home, events], "관리자 전용": [children]}
else:
    pages = {"공통": [home, events]}

with st.sidebar:
    label = "관리자(목사님/임원)" if role == "admin" else "교사"
    st.caption(f"접속 권한: {label}")
    if st.button("로그아웃"):
        st.session_state.clear()
        st.rerun()

st.navigation(pages).run()
