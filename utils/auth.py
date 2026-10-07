import streamlit as st

# 관리자 권한이 필요한 영역은 '아동 명부'와 '교사·반 명단'(및 이를 일괄 변경하는 업로드·진급)입니다.
# 나머지 화면은 비밀번호 없이 누구나 사용합니다.

# 심방·기도제목 '요청 목록 열람·상태 변경'을 관리자 전용으로 둘지
# True  = 관리자만 (권장: 아이 사정이 담김)
# False = 누구나
REQUESTS_ADMIN_ONLY = True


def is_admin() -> bool:
    return st.session_state.get("role") == "admin"


def can_manage_roster() -> bool:
    """아동·교사 명부 등록·수정·삭제, 업로드, 진급"""
    return is_admin()


def can_see_contact() -> bool:
    """연락처 열람"""
    return is_admin()


def can_manage() -> bool:
    """명부 외 화면(일정·공지 등)의 등록·수정·삭제: 누구나"""
    return True


def can_view_requests() -> bool:
    """심방·기도제목 요청 목록 열람, 상태 변경·삭제"""
    return is_admin() if REQUESTS_ADMIN_ONLY else True
