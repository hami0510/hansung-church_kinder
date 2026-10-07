from datetime import date, timedelta
import pandas as pd
from utils.labels import class_label


def _bd(v):
    try:
        d = pd.to_datetime(v, errors="coerce")
        return None if pd.isna(d) else d.date()
    except Exception:
        return None


def _on(year, month, day):
    try:
        return date(year, month, day)
    except ValueError:  # 2/29 생일은 평년에 2/28로
        return date(year, 2, 28)


def collect(children, teachers):
    """아동·교사 생일 목록 (연도는 저장하지 않음)"""
    people = []
    for df, kind in ((children, "아동"), (teachers, "교사")):
        if df is None or df.empty or "birth_date" not in df.columns:
            continue
        if "is_active" in df.columns:
            df = df[df["is_active"] == True]
        for _, r in df.iterrows():
            d = _bd(r.get("birth_date"))
            if d:
                people.append({"name": r["name"], "kind": kind, "month": d.month,
                               "day": d.day, "cls": class_label(r)})
    return people


def in_month(people, year, month):
    out = {}
    for p in people:
        if p["month"] == month:
            out.setdefault(_on(year, month, p["day"]).day, []).append(p)
    return out


def upcoming(people, today, days=7):
    res = []
    for p in people:
        for y in (today.year, today.year + 1):
            d = _on(y, p["month"], p["day"])
            if today <= d <= today + timedelta(days=days):
                res.append({**p, "date": d})
                break
    return sorted(res, key=lambda x: (x["date"], x["name"]))
