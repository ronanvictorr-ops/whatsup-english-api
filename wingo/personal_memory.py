import json
import re
import unicodedata
from difflib import SequenceMatcher

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from models import PersonalNoteDB, StudentDB


PERSONAL_NOTE_CUES = (
    "vou viajar",
    "viajar para",
    "viajar pra",
    "minha viagem",
    "semana que vem",
    "amanha",
    "amanhã",
    "prova",
    "entrevista",
    "aniversario",
    "aniversário",
    "casamento",
    "formatura",
    "consulta",
    "meu cachorro",
    "minha cachorra",
    "meu gato",
    "minha gata",
    "meu pet",
    "meu time",
    "minha familia",
    "minha família",
    "meu filho",
    "minha filha",
    "my dog",
    "my cat",
    "my pet",
    "my team",
    "my exam",
    "my test",
    "my birthday",
    "i will travel",
    "i'm traveling",
    "i am traveling",
    "next week",
)


def normalize_personal_note_key(text: str):
    normalized = unicodedata.normalize("NFKD", text or "")
    normalized = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    normalized = re.sub(r"\s+", " ", normalized.lower()).strip()
    return normalized


def should_extract_personal_note(message: str):
    normalized = normalize_personal_note_key(message)

    if len(normalized) < 12:
        return False

    if normalized.startswith("[voice note transcription]"):
        normalized = normalized.replace("[voice note transcription]", "", 1).strip()

    return any(cue in normalized for cue in PERSONAL_NOTE_CUES)


def get_recent_personal_notes_summary(student_id: int, db: Session, limit: int = 6):
    try:
        notes = (
            db.query(PersonalNoteDB)
            .filter(PersonalNoteDB.student_id == student_id)
            .order_by(PersonalNoteDB.id.desc())
            .limit(limit)
            .all()
        )
    except SQLAlchemyError as error:
        db.rollback()
        print("Memoria pessoal indisponivel:", type(error).__name__)
        return "No personal relationship memory saved yet."

    if not notes:
        return "No personal relationship memory saved yet."

    lines = []
    for note in reversed(notes):
        category = note.category or "life"
        lines.append(f"- {category}: {note.note}")

    return "\n".join(lines)


def extract_personal_notes(
    student: StudentDB,
    message: str,
    get_openai_client,
    call_with_retry,
):
    if not should_extract_personal_note(message):
        return []

    client = get_openai_client()

    response = call_with_retry(
        client.chat.completions.create,
        operation="chat_completion",
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": """
You extract relationship memory for an English tutor.

Return JSON only.

Schema:
{
  "notes": [
    {
      "category": "travel|family|pet|work|school|health|hobby|event|preference|other",
      "note": "short useful fact in Portuguese"
    }
  ]
}

Save only stable or follow-up-worthy personal facts, such as trips, exams,
important events, family, pets, hobbies, teams, work, or preferences.
Do not save grammar mistakes, lesson topics, greetings, commands, passwords,
documents, payment data, private secrets, or sensitive health details.
Write notes as concise facts the tutor can use later with care.
""",
            },
            {
                "role": "user",
                "content": (
                    f"Student name: {student.name or 'unknown'}\n"
                    f"Student message:\n{message}"
                ),
            },
        ],
    )

    try:
        data = json.loads(response.choices[0].message.content)
    except (AttributeError, TypeError, json.JSONDecodeError):
        return []

    extracted = []
    for item in data.get("notes") or []:
        note = (item.get("note") or "").strip()
        if not note:
            continue
        extracted.append(
            {
                "category": (item.get("category") or "other")[:40],
                "note": note[:400],
            }
        )

    return extracted[:3]


def personal_note_already_exists(student_id: int, note: str, db: Session):
    target = normalize_personal_note_key(note)
    recent_notes = (
        db.query(PersonalNoteDB)
        .filter(PersonalNoteDB.student_id == student_id)
        .order_by(PersonalNoteDB.id.desc())
        .limit(30)
        .all()
    )

    for existing in recent_notes:
        existing_key = normalize_personal_note_key(existing.note)
        if existing_key == target:
            return True
        if SequenceMatcher(None, existing_key, target).ratio() >= 0.92:
            return True

    return False


def save_personal_notes_if_needed(
    student: StudentDB,
    message: str,
    db: Session,
    get_openai_client,
    call_with_retry,
):
    try:
        notes = extract_personal_notes(
            student,
            message,
            get_openai_client=get_openai_client,
            call_with_retry=call_with_retry,
        )
        saved = 0

        for item in notes:
            note_text = item["note"]
            if personal_note_already_exists(student.id, note_text, db):
                continue

            db.add(
                PersonalNoteDB(
                    student_id=student.id,
                    category=item["category"],
                    note=note_text,
                    source_message=message[:1000],
                )
            )
            saved += 1

        if not saved:
            return

        db.commit()
        print("MEMORIA DE RELACIONAMENTO SALVA:", saved)
    except Exception as error:
        db.rollback()
        print("Erro ao salvar memoria de relacionamento:", error)
