import hmac
import streamlit as st
from utils.ui import inject_css

st.set_page_config(page_title="유치부 관리", page_icon="⛪", layout="wide")

# 사이드바 맨 위 로고 (logo.png가 app.py와 같은 위치에 있어야 함)
try:
    st.logo("logo.png", size="large")
except Exception:
    pass  # 로고 파일이 없어도 앱은 정상 동작

inject_css()

MAX_FAILS = 5  # 한 접속(세션)에서 비밀번호 틀릴 수 있는 횟수

# 처음 접속하면 일반(조회 중심)으로 시작
if "role" not in st.session_state:
    st.session_state["role"] = "guest"
    st.session_state["fails"] = 0

role = st.session_state["role"]

home = st.Page("views/home.py", title="홈", icon="🏠", default=True)
notices = st.Page("views/notices.py", title="공지사항", icon="📢")
events = st.Page("views/events.py", title="일정 관리", icon="📅")
children = st.Page("views/children.py", title="아동 명부", icon="🧒")
teachers = st.Page("views/teachers.py", title="교사·반 명단", icon="👩‍🏫")
sunday_report = st.Page("views/sunday_report.py", title="주일 출석 보고", icon="📝")
visit_request = st.Page("views/visit_request.py", title="심방 요청", icon="🏠")
prayer_request = st.Page("views/prayer_request.py", title="기도제목 요청", icon="🙏")
bulk_upload = st.Page("views/bulk_upload.py", title="엑셀 업로드", icon="📥")
promotion = st.Page("views/promotion.py", title="반 이동·진급", icon="🎓")

pages = {
    "메뉴": [home, notices, events, children, teachers, sunday_report,
           visit_request, prayer_request],
    "관리": [bulk_upload, promotion],
}

with st.sidebar:
    if role == "admin":
        st.caption("접속 권한: 관리자(목사님/임원)")
        if st.button("관리자 로그아웃"):
            st.session_state["role"] = "guest"
            st.session_state["fails"] = 0
            st.rerun()
    else:
        st.caption("접속 권한: 일반 (아동·교사 명부 수정은 관리자 로그인 필요)")
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
