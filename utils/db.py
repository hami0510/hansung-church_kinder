import io
import time
import streamlit as st
import pandas as pd
from PIL import Image, ImageOps
from supabase import create_client

BUCKET = "child-photos"


@st.cache_resource
def get_client():
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])


# ---------- 읽기 (30초 캐시) ----------
@st.cache_data(ttl=30, show_spinner=False)
def _fetch_cached(table: str, order_by: str | None, desc: bool) -> pd.DataFrame:
    q = get_client().table(table).select("*")
    if order_by:
        q = q.order(order_by, desc=desc)
    return pd.DataFrame(q.execute().data)


def fetch(table: str, order_by: str | None = None, desc: bool = False) -> pd.DataFrame:
    # 복사본을 돌려줘서, 화면에서 표를 고쳐도 캐시가 오염되지 않게 함
    return _fetch_cached(table, order_by, desc).copy()


# ---------- 쓰기 (저장 직후 캐시 비움) ----------
def insert(table: str, row):
    res = get_client().table(table).insert(row).execute()
    _fetch_cached.clear()
    return res


def update(table: str, row_id: str, row: dict):
    res = get_client().table(table).update(row).eq("id", row_id).execute()
    _fetch_cached.clear()
    return res


def delete(table: str, row_id: str):
    res = get_client().table(table).delete().eq("id", row_id).execute()
    _fetch_cached.clear()
    return res


# ---------- 사진 ----------
def process_image(file, max_side: int = 800) -> bytes:
    """업로드 사진을 회전 보정 후 축소하고 JPEG로 변환 (위치 등 EXIF 정보는 제거됨)"""
    img = Image.open(file)
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def upload_photo(child_id: str, data: bytes, old_path: str | None = None) -> str:
    path = f"{child_id}_{int(time.time())}.jpg"
    get_client().storage.from_(BUCKET).upload(
        path, data, {"content-type": "image/jpeg", "upsert": "true"}
    )
    if old_path:
        remove_photo(old_path)
    return path


def remove_photo(path: str | None):
    if not path:
        return
    try:
        get_client().storage.from_(BUCKET).remove([path])
    except Exception:
        pass


@st.cache_data(ttl=3000, show_spinner=False)
def photo_url(path: str) -> str:
    """비공개 사진을 1시간 동안만 볼 수 있는 임시 주소로 변환"""
    if not path:
        return ""
    try:
        res = get_client().storage.from_(BUCKET).create_signed_url(path, 3600)
        return res.get("signedURL") or res.get("signedUrl") or ""
    except Exception:
        return ""
