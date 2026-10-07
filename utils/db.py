import streamlit as st
import pandas as pd
from supabase import create_client


@st.cache_resource
def get_client():
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])


def fetch(table: str, order_by: str | None = None, desc: bool = False) -> pd.DataFrame:
    q = get_client().table(table).select("*")
    if order_by:
        q = q.order(order_by, desc=desc)
    return pd.DataFrame(q.execute().data)


def insert(table: str, row: dict):
    return get_client().table(table).insert(row).execute()


def update(table: str, row_id: str, row: dict):
    return get_client().table(table).update(row).eq("id", row_id).execute()


def delete(table: str, row_id: str):
    return get_client().table(table).delete().eq("id", row_id).execute()
