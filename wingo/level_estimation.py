import re
import unicodedata


def estimate_level_from_study_history(message: str):
    text = (message or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))

    year_match = re.search(r"(\d+)\s*(ano|anos|year|years)", text)
    month_match = re.search(r"(\d+)\s*(mes|meses|month|months)", text)

    years = int(year_match.group(1)) if year_match else 0
    months = int(month_match.group(1)) if month_match else 0
    total_months = years * 12 + months

    if total_months >= 36:
        return "Advanced"
    if total_months >= 12:
        return "Intermediate"
    if total_months >= 3:
        return "Basic 2"
    if re.search(r"\b(nao|no|nunca)\b", text) or "zero" in text:
        return "Basic"
    if "fluente" in text or "fluent" in text or "c2" in text:
        return "Fluent"
    if "avanc" in text or "advanced" in text or "c1" in text:
        return "Advanced"
    if "intermedi" in text or "b1" in text or "b2" in text:
        return "Intermediate"
    if "basic 2" in text or "basico 2" in text or "a1+" in text:
        return "Basic 2"
    if "basico" in text or "iniciante" in text or "a1" in text:
        return "Basic"

    return "Basic"
