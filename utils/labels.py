import pandas as pd


def _v(x):
    return None if x is None or (not isinstance(x, str) and pd.isna(x)) else x


def class_label(r) -> str:
    """예: 조이(5세) · 1부 · 3반 (비어 있는 항목은 생략)"""
    parts = []
    cls = _v(r.get("class_name"))
    part = _v(r.get("service_part"))
    no = _v(r.get("class_no"))
    if cls:
        parts.append(str(cls))
    if part:
        parts.append(str(part))
    if no:
        parts.append(f"{int(no)}반")
    return " · ".join(parts) if parts else "반 미정"
