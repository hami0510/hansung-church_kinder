from threading import Lock

import streamlit as st
import pandas as pd
from supabase import create_client


@st.cache_resource
def get_client():
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])


# ---------- 읽기 (30초 캐시) ----------
@st.cache_resource
def _table_versions() -> dict[str, int]:
    return {}


@st.cache_resource
def _table_versions_lock() -> Lock:
    return Lock()


def _cache_version(table: str) -> int:
    with _table_versions_lock():
        return _table_versions().get(table, 0)


def invalidate(table: str) -> None:
    """변경된 테이블만 다음 조회에서 새로 읽도록 캐시 버전을 올린다."""
    with _table_versions_lock():
        versions = _table_versions()
        versions[table] = versions.get(table, 0) + 1


@st.cache_data(ttl=30, show_spinner=False)
def _fetch_cached(table: str, order_by: str | None, desc: bool,
                  cache_version: int) -> pd.DataFrame:
    # cache_version은 테이블이 바뀔 때 이 함수의 캐시 키만 갱신하기 위한 값이다.
    q = get_client().table(table).select("*")
    if order_by:
        q = q.order(order_by, desc=desc)
    return pd.DataFrame(q.execute().data)


@st.cache_data(ttl=30, show_spinner=False)
def _fetch_where_cached(table: str, filters: tuple[tuple[str, object], ...],
                        cache_version: int) -> pd.DataFrame:
    # cache_version은 테이블이 바뀔 때 이 함수의 캐시 키만 갱신하기 위한 값이다.
    q = get_client().table(table).select("*")
    for column, value in filters:
        q = q.eq(column, value)
    return pd.DataFrame(q.execute().data)


def fetch(table: str, order_by: str | None = None, desc: bool = False) -> pd.DataFrame:
    # 복사본을 돌려줘서, 화면에서 표를 고쳐도 캐시가 오염되지 않게 함
    return _fetch_cached(table, order_by, desc, _cache_version(table)).copy()


def fetch_where(table: str, **eq: object) -> pd.DataFrame:
    """동등 조건을 DB 조회에 적용해 필요한 행만 가져온다."""
    filters = tuple(sorted(eq.items()))
    return _fetch_where_cached(table, filters, _cache_version(table)).copy()


# ---------- 쓰기 (저장 직후 변경된 테이블 캐시만 갱신) ----------
def insert(table: str, row):
    res = get_client().table(table).insert(row).execute()
    invalidate(table)
    return res


def update(table: str, row_id: str, row: dict):
    res = get_client().table(table).update(row).eq("id", row_id).execute()
    invalidate(table)
    return res


def delete(table: str, row_id: str):
    res = get_client().table(table).delete().eq("id", row_id).execute()
    invalidate(table)
    return res


def upsert(table: str, rows, on_conflict: str):
    res = get_client().table(table).upsert(rows, on_conflict=on_conflict).execute()
    invalidate(table)
    return res


def delete_where(table: str, **eq):
    q = get_client().table(table).delete()
    for k, v in eq.items():
        q = q.eq(k, v)
    res = q.execute()
    invalidate(table)
    return res
