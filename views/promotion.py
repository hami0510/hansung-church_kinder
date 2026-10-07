from datetime import date
import pandas as pd
import streamlit as st
from utils.auth import can_manage
from utils.db import fetch, update
from utils.labels import class_label

NEXT = {"조이(5세)": "해피(6세)", "해피(6세)": "홀리(7세)", "홀리(7세)": None}  # None = 졸업

st.title("🎓 반 이동 · 진급")

if not can_manage():
    st.warning("관리자 로그인 후 사용할 수 있습니다.")
    st.stop()

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

df = fetch("children", "name")
if df.empty:
    st.info("등록된 아동이 없습니다.")
    st.stop()
for col in ["service_part", "class_no"]:
    if col not in df.columns:
        df[col] = None

st.info("조이→해피, 해피→홀리로 한 학년씩 올라가고, 홀리는 졸업(퇴원 처리)됩니다. "
        "새싹(새가족)과 반이 없는 아동은 이동하지 않습니다. **연말에 한 번만** 실행하세요.")

st.download_button("💾 진급 전 백업 CSV 내려받기 (먼저 받아 두세요)",
                   df.to_csv(index=False).encode("utf-8-sig"),
                   file_name=f"명부_백업_{date.today()}.csv", mime="text/csv",
                   use_container_width=True)

c1, c2 = st.columns(2)
graduate = c1.checkbox("홀리(7세)는 졸업 처리", value=True)
reset_no = c2.checkbox("반 번호 비우기 (새 반 번호는 나중에 입력)", value=True)

act = df[(df["is_active"] == True) & (df["class_name"].isin(NEXT))].copy()
if not graduate:
    act = act[act["class_name"] != "홀리(7세)"]
if act.empty:
    st.info("이동할 아동이 없습니다.")
    st.stop()


def to_no(v):
    try:
        return int(v)
    except Exception:
        return None


act = act.sort_values(["class_name", "service_part", "name"], na_position="last")
view = pd.DataFrame({
    "진급": True,
    "이름": act["name"],
    "현재 반": act["class_name"],
    "부": act["service_part"].apply(lambda v: v if isinstance(v, str) else ""),
    "변경 후": act["class_name"].apply(lambda c: NEXT[c] or "🎓 졸업(퇴원 처리)"),
}, index=act["id"])

st.caption("이동하지 않을 아동은 '진급' 체크를 해제하세요.")
edited = st.data_editor(
    view, hide_index=True, use_container_width=True, key="promo_editor",
    disabled=["이름", "현재 반", "부", "변경 후"],
    column_config={"진급": st.column_config.CheckboxColumn("진급", default=True)})

sel = edited[edited["진급"] == True]
st.metric("적용 대상", f"{len(sel)}명")

typed = st.text_input("적용하려면 '진급'을 입력하세요")
if st.button("🎓 진급 적용", type="primary", disabled=(typed.strip() != "진급" or sel.empty),
             use_container_width=True):
    year = date.today().year
    base = act.set_index("id")
    for cid in sel.index:
        src = base.loc[cid]
        nxt = NEXT[src["class_name"]]
        if nxt:
            data = {"class_name": nxt}
            if reset_no:
                data["class_no"] = None
        else:
            old = src["notes"] if isinstance(src.get("notes"), str) else ""
            data = {"is_active": False, "notes": (old + " / " if old else "") + f"{year} 졸업"}
        update("children", cid, data)
    st.session_state["flash"] = f"{len(sel)}명의 반 이동을 적용했습니다."
    st.rerun()
