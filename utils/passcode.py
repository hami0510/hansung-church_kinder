import hashlib
import hmac
import re

import streamlit as st

MAX_FAILS = 5


def valid_pin(pin: str) -> bool:
    return bool(re.fullmatch(r"\d{4}", (pin or "").strip()))


def _salt() -> str:
    try:
        return st.secrets["supabase"]["key"][-12:]
    except Exception:
        return "kinder"


def make_hash(name: str, pin: str) -> str:
    raw = f"{_salt()}|{name.strip()}|{pin.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def check(name: str, pin: str, stored) -> bool:
    if not isinstance(stored, str) or not stored:
        return False
    return hmac.compare_digest(make_hash(name, pin), stored)


def locked(key: str) -> bool:
    return st.session_state.get(f"{key}_fails", 0) >= MAX_FAILS


def add_fail(key: str):
    st.session_state[f"{key}_fails"] = st.session_state.get(f"{key}_fails", 0) + 1


def reset_fail(key: str):
    st.session_state[f"{key}_fails"] = 0
