import re


def format_phone(raw) -> str | None:
    """숫자만 입력해도 010-1234-5678 형식으로 정리. 인식 못 하면 입력 그대로 반환."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    digits = re.sub(r"\D", "", s)
    if digits.startswith("82"):          # +82 10... → 010...
        digits = "0" + digits[2:]
    n = len(digits)

    if digits.startswith("02"):          # 서울
        if n == 9:
            return f"02-{digits[2:5]}-{digits[5:]}"
        if n == 10:
            return f"02-{digits[2:6]}-{digits[6:]}"
    elif digits.startswith(("010", "011", "016", "017", "018", "019")):
        if n == 10:
            return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
        if n == 11:
            return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
    elif digits.startswith(("03", "04", "05", "06")):   # 지역번호 031 등
        if n == 10:
            return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
        if n == 11:
            return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
    elif digits.startswith("070") and n in (10, 11):
        return f"070-{digits[3:-4]}-{digits[-4:]}"
    return s
