def normalize_whatsapp_phone(phone: str) -> str:
    digits = "".join(char for char in (phone or "") if char.isdigit())
    if digits.startswith("55") and len(digits) == 12:
        ddd = digits[2:4]
        local_number = digits[4:]
        return f"55{ddd}9{local_number}"
    return digits


def whatsapp_phone_variants(phone: str) -> set[str]:
    digits = "".join(char for char in (phone or "") if char.isdigit())
    canonical = normalize_whatsapp_phone(digits)
    variants = {value for value in (phone, digits, canonical) if value}

    if canonical.startswith("55") and len(canonical) == 13 and canonical[4] == "9":
        variants.add(canonical[:4] + canonical[5:])
    return variants


def mask_phone(phone: str | None) -> str:
    digits = "".join(char for char in (phone or "") if char.isdigit())
    return f"***{digits[-4:]}" if digits else "unknown"
