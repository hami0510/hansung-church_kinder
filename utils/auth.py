import streamlit as st

# True  = 작업 중: 누구나 등록·수정·삭제·연락처 열람 가능
# False = 운영 모드: 관리자 로그인한 사람만 가능
OPEN_MODE = True


def is_admin() -> bool:
    return st.session_state.get("role") == "admin"


def can_manage() -> bool:
    """등록·수정·삭제 권한"""
    return OPEN_MODE or is_admin()


def can_see_contact() -> bool:
    """교사 연락처 열람 권한"""
    return OPEN_MODE or is_admin()
