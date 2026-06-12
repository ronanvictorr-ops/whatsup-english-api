import asyncio
import json
import os
import re
import tempfile
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pathlib import Path
import requests
import bcrypt
from dotenv import load_dotenv
from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    Response,
)
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from openai import OpenAI
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import Base, SessionLocal, engine
from models import ConversationDB, LearningRecordDB, ProgressDB, StudentDB




# =========================
# CONFIGURAÇÕES INICIAIS
# =========================

load_dotenv()

Base.metadata.create_all(bind=engine)

app = FastAPI()

SECRET_KEY = os.getenv("SECRET_KEY", "whatsup-english-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


def get_local_timezone():
    timezone_name = os.getenv("LOCAL_TIMEZONE", "America/Sao_Paulo")

    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        fallback_offset = int(os.getenv("LOCAL_UTC_OFFSET_HOURS", "-3"))
        print(
            f"Timezone '{timezone_name}' nao encontrado. "
            f"Usando UTC{fallback_offset:+d} como fallback."
        )
        return timezone(timedelta(hours=fallback_offset))


LOCAL_TIMEZONE = get_local_timezone()
DAILY_WORD_TIME = os.getenv("DAILY_WORD_TIME", "09:00")
WEEKLY_QUIZ_DAY = os.getenv("WEEKLY_QUIZ_DAY", "Friday")
WEEKLY_QUIZ_TIME = os.getenv("WEEKLY_QUIZ_TIME", "10:00")
ACADEMIC_AUTOMATIONS_ENABLED = os.getenv("ACADEMIC_AUTOMATIONS_ENABLED", "true").lower() == "true"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


# =========================
# DATABASE
# =========================

def get_db():
    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


# =========================
# OPENAI
# =========================

def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="OPENAI_API_KEY não configurada no arquivo .env"
        )

    return OpenAI(api_key=api_key)


# =========================
# WHATSAPP CLOUD API / META
# =========================

def normalize_whatsapp_phone_for_send(phone: str):
    digits = "".join(char for char in phone if char.isdigit())

    # A Meta as vezes envia wa_id brasileiro sem o nono digito, mas a lista de
    # destinatarios de teste pode ficar cadastrada com o nono digito.
    if digits.startswith("55") and len(digits) == 12:
        ddd = digits[2:4]
        local_number = digits[4:]

        if not local_number.startswith("9"):
            return f"55{ddd}9{local_number}"

    return digits


def get_meta_whatsapp_config():
    phone_number_id = os.getenv("META_PHONE_NUMBER_ID")
    access_token = os.getenv("META_ACCESS_TOKEN")

    if not phone_number_id or not access_token:
        raise HTTPException(
            status_code=500,
            detail="META_PHONE_NUMBER_ID ou META_ACCESS_TOKEN nao configurado no .env"
        )

    return phone_number_id, access_token


def send_whatsapp_message(phone: str, text: str):
    phone_number_id, access_token = get_meta_whatsapp_config()
    recipient_phone = normalize_whatsapp_phone_for_send(phone)

    url = f"https://graph.facebook.com/v23.0/{phone_number_id}/messages"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_phone,
        "type": "text",
        "text": {
            "body": text
        }
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=20
    )

    if response.status_code >= 400:
        print("Erro ao enviar mensagem pela Meta:", response.text)
        print("Telefone recebido:", phone)
        print("Telefone usado no envio:", recipient_phone)
        raise HTTPException(
            status_code=502,
            detail="Erro ao enviar mensagem pelo WhatsApp Cloud API"
        )

    return response.json()


def upload_whatsapp_media(file_path: Path, mime_type: str):
    phone_number_id, access_token = get_meta_whatsapp_config()
    url = f"https://graph.facebook.com/v23.0/{phone_number_id}/media"

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    with file_path.open("rb") as file:
        response = requests.post(
            url,
            headers=headers,
            data={"messaging_product": "whatsapp"},
            files={"file": (file_path.name, file, mime_type)},
            timeout=30
        )

    if response.status_code >= 400:
        print("Erro ao subir audio na Meta:", response.text)
        raise HTTPException(
            status_code=502,
            detail="Erro ao subir audio para o WhatsApp Cloud API"
        )

    return response.json()["id"]


def send_whatsapp_audio(phone: str, media_id: str):
    phone_number_id, access_token = get_meta_whatsapp_config()
    recipient_phone = normalize_whatsapp_phone_for_send(phone)
    url = f"https://graph.facebook.com/v23.0/{phone_number_id}/messages"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_phone,
        "type": "audio",
        "audio": {
            "id": media_id
        }
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=20
    )

    if response.status_code >= 400:
        print("Erro ao enviar audio pela Meta:", response.text)
        print("Telefone recebido:", phone)
        print("Telefone usado no envio:", recipient_phone)
        raise HTTPException(
            status_code=502,
            detail="Erro ao enviar audio pelo WhatsApp Cloud API"
        )

    return response.json()


def should_send_pronunciation_audio(question: str, answer: str):
    text = f"{question}\n{answer}".lower()

    triggers = (
        "como se diz",
        "como fala",
        "como eu digo",
        "pronuncia",
        "pronunciar",
        "pronunciation",
        "how do you say",
        "how can i say",
        "say in english",
        "em ingles",
        "em inglês",
    )

    example_markers = (
        "example:",
        "examples:",
        "for example",
        "frase:",
        "frases:",
        "sentences:",
    )

    return any(trigger in text for trigger in triggers) or any(
        marker in text for marker in example_markers
    )


def build_pronunciation_audio_text(question: str, answer: str):
    if not should_send_pronunciation_audio(question, answer):
        return None

    client = get_openai_client()

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": """
Extract only the English phrase or example sentences that should be spoken aloud.

Rules:
- Return only English.
- Do not include Portuguese explanations.
- Keep it under 45 words.
- If there is no useful English phrase, return an empty string.
"""
            },
            {
                "role": "user",
                "content": f"Student question:\n{question}\n\nTutor answer:\n{answer}"
            }
        ]
    )

    audio_text = response.choices[0].message.content.strip()
    audio_text = re.sub(r"^[\"'`]+|[\"'`]+$", "", audio_text).strip()

    if not audio_text:
        return None

    return audio_text[:500]


def generate_pronunciation_audio_file(text: str):
    client = get_openai_client()
    speech = client.audio.speech.create(
        model=os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts"),
        voice=os.getenv("OPENAI_TTS_VOICE", "alloy"),
        input=text,
        response_format="mp3",
    )

    audio_path = Path(tempfile.gettempdir()) / f"whatsup_audio_{os.urandom(8).hex()}.mp3"
    speech.write_to_file(audio_path)

    return audio_path


def send_pronunciation_audio_if_needed(phone: str, question: str, answer: str):
    audio_text = build_pronunciation_audio_text(question, answer)

    if not audio_text:
        return

    audio_path = generate_pronunciation_audio_file(audio_text)

    try:
        media_id = upload_whatsapp_media(audio_path, "audio/mpeg")
        send_whatsapp_audio(phone, media_id)
    finally:
        try:
            audio_path.unlink(missing_ok=True)
        except OSError:
            pass


def get_whatsapp_media_url(media_id: str):
    _, access_token = get_meta_whatsapp_config()
    url = f"https://graph.facebook.com/v23.0/{media_id}"

    response = requests.get(
        url,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=20
    )

    if response.status_code >= 400:
        print("Erro ao buscar URL do audio na Meta:", response.text)
        raise HTTPException(
            status_code=502,
            detail="Erro ao buscar audio no WhatsApp Cloud API"
        )

    return response.json()["url"]


def download_whatsapp_audio(media_id: str):
    _, access_token = get_meta_whatsapp_config()
    media_url = get_whatsapp_media_url(media_id)

    response = requests.get(
        media_url,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30
    )

    if response.status_code >= 400:
        print("Erro ao baixar audio da Meta:", response.text)
        raise HTTPException(
            status_code=502,
            detail="Erro ao baixar audio do WhatsApp Cloud API"
        )

    audio_path = Path(tempfile.gettempdir()) / f"whatsup_incoming_{os.urandom(8).hex()}.ogg"
    audio_path.write_bytes(response.content)

    return audio_path


def transcribe_audio_file(audio_path: Path):
    client = get_openai_client()

    with audio_path.open("rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model=os.getenv("OPENAI_TRANSCRIBE_MODEL", "whisper-1"),
            file=audio_file
        )

    return transcript.text.strip()


def transcribe_whatsapp_audio(media_id: str):
    audio_path = download_whatsapp_audio(media_id)

    try:
        return transcribe_audio_file(audio_path)
    finally:
        try:
            audio_path.unlink(missing_ok=True)
        except OSError:
            pass


def normalize_language_preference(value: str):
    text = (value or "").strip().lower()

    if text in {"2", "english", "ingles", "inglês"} or "engl" in text or "ingl" in text:
        return "English"

    if text in {"3", "both", "bilingual", "bilingue", "bilingüe"}:
        return "Both"

    if "dois" in text or "ambos" in text or "both" in text:
        return "Both"

    if text in {"1", "portuguese", "portugues", "português"}:
        return "Portuguese"

    if "port" in text:
        return "Portuguese"

    return "Portuguese"


def get_language_instruction(language: str):
    if language == "English":
        return (
            "Reply primarily in English. Do not switch to Portuguese unless the "
            "student explicitly asks for Portuguese or seems completely stuck."
        )

    if language == "Both":
        return (
            "Use English as the main practice language, and add short Portuguese "
            "explanations only when they help the student understand corrections."
        )

    return (
        "Use Portuguese for explanations and guidance, but include English examples "
        "and practice sentences."
    )


def get_assessment_prompt(language: str):
    if language == "English":
        return (
            "Great!\n\n"
            "Now I will do a quick assessment to understand your current English level.\n\n"
            "Don't worry about mistakes. Answer as best as you can.\n\n"
            "How would you introduce yourself in English to someone you just met?"
        )

    if language == "Both":
        return (
            "Perfect!\n\n"
            "Now I will do a quick assessment to understand your current English level.\n"
            "Nao se preocupe com erros. Responda da melhor forma que conseguir.\n\n"
            "How would you introduce yourself in English to someone you just met?"
        )

    return (
        "Otimo!\n\n"
        "Agora vou fazer uma avaliacao rapida para entender seu nivel atual de ingles.\n\n"
        "Nao se preocupe com erros. Responda da melhor forma que conseguir.\n\n"
        "Como voce se apresentaria em ingles para alguem que acabou de conhecer?"
    )


# =========================
# PYDANTIC MODELS
# =========================

class Student(BaseModel):
    name: str
    email: str
    password: str
    phone: str
    preferred_language: str = "Portuguese"
    learning_goal: str = "Conversation"


class Login(BaseModel):
    email: str
    password: str


class QuizAnswer(BaseModel):
    answer: str


class Progress(BaseModel):
    student_id: int
    score: int


class Conversation(BaseModel):
    student_id: int
    question: str
    answer: str


class ChatRequest(BaseModel):
    student_id: int
    question: str


class AssessmentRequest(BaseModel):
    student_id: int
    answer: str


class LearningRecord(BaseModel):
    student_id: int
    skill: str
    topic: str
    original_text: str
    corrected_text: str
    explanation: str | None = None
    xp_awarded: int | None = None


DAY_ALIASES = {
    0: ("segunda", "segunda-feira", "monday", "seg"),
    1: ("terca", "terça", "terca-feira", "terça-feira", "tuesday", "ter"),
    2: ("quarta", "quarta-feira", "wednesday", "qua"),
    3: ("quinta", "quinta-feira", "thursday", "qui"),
    4: ("sexta", "sexta-feira", "friday", "sex"),
    5: ("sabado", "sábado", "saturday", "sab", "sáb"),
    6: ("domingo", "sunday", "dom"),
}


def parse_clock_time(value: str):
    match = re.search(r"\b(\d{1,2})(?:[:hH](\d{2}))?\b", value or "")

    if not match:
        return None

    hour = int(match.group(1))
    minute = int(match.group(2) or 0)

    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None

    return f"{hour:02d}:{minute:02d}"


def normalize_day_name(day_index: int):
    names = {
        0: "segunda-feira",
        1: "terca-feira",
        2: "quarta-feira",
        3: "quinta-feira",
        4: "sexta-feira",
        5: "sabado",
        6: "domingo",
    }

    return names.get(day_index, "dia escolhido")


def parse_lesson_schedule(message: str):
    text = (message or "").lower()
    matches = []

    for day_index, aliases in DAY_ALIASES.items():
        for alias in aliases:
            for match in re.finditer(rf"\b{re.escape(alias)}\b", text):
                matches.append((match.start(), match.end(), day_index))

    matches = sorted(matches, key=lambda item: item[0])
    slots = []

    for index, (start, end, day_index) in enumerate(matches):
        next_start = matches[index + 1][0] if index + 1 < len(matches) else len(text)
        chunk = text[end:next_start]
        lesson_time = parse_clock_time(chunk)

        if not lesson_time:
            lesson_time = parse_clock_time(text)

        if not lesson_time:
            lesson_time = "09:00"

        slot = {
            "day": day_index,
            "time": lesson_time
        }

        if slot not in slots:
            slots.append(slot)

        if len(slots) == 2:
            break

    return slots


def format_lesson_schedule(slots):
    return " e ".join(
        f"{normalize_day_name(slot['day'])} as {slot['time']}"
        for slot in slots
    )


def get_student_lesson_schedule(student: StudentDB):
    if not student.lesson_schedule:
        return []

    try:
        slots = json.loads(student.lesson_schedule)
    except json.JSONDecodeError:
        return []

    if not isinstance(slots, list):
        return []

    return slots


def local_now():
    return datetime.now(LOCAL_TIMEZONE)


def current_week_key(now: datetime):
    year, week, _ = now.isocalendar()
    return f"{year}-W{week:02d}"


def has_time_arrived(now: datetime, clock_time: str):
    target = parse_clock_time(clock_time) or "09:00"
    hour, minute = [int(part) for part in target.split(":")]

    return (now.hour, now.minute) >= (hour, minute)


# =========================
# AUTH
# =========================

def create_access_token(data: dict):
    to_encode = data.copy()

    expire = datetime.utcnow() + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    to_encode.update({"exp": expire})

    return jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM
    )


def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        return payload

    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Token inválido"
        )


def get_recent_learning_summary(student_id: int, db: Session):
    records = (
        db.query(LearningRecordDB)
        .filter(LearningRecordDB.student_id == student_id)
        .order_by(LearningRecordDB.id.desc())
        .limit(8)
        .all()
    )

    if not records:
        return "No saved learning records yet."

    lines = []

    for record in reversed(records):
        lines.append(
            f"- {record.skill or 'general'} / {record.topic or 'general'}: "
            f"student said '{record.original_text}' -> corrected to "
            f"'{record.corrected_text}'. Note: {record.explanation or ''}"
        )

    return "\n".join(lines)


def extract_learning_record(student: StudentDB, question: str, answer: str):
    client = get_openai_client()

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": """
You extract useful academic memory from an English tutoring exchange.

Return JSON only.

Schema:
{
  "save": true or false,
  "skill": "grammar|vocabulary|pronunciation|fluency|listening|writing|speaking|general",
  "topic": "short topic name",
  "original_text": "student's mistake or phrase",
  "corrected_text": "corrected English version",
  "explanation": "short teacher note"
}

Save only when there is a meaningful mistake, correction, pronunciation issue,
new phrase, or recurring learning point. Do not save greetings or casual chat.
"""
            },
            {
                "role": "user",
                "content": f"Student message:\n{question}\n\nTutor answer:\n{answer}"
            }
        ]
    )

    try:
        data = json.loads(response.choices[0].message.content)
    except (TypeError, json.JSONDecodeError):
        return None

    if not data.get("save"):
        return None

    original_text = (data.get("original_text") or "").strip()
    corrected_text = (data.get("corrected_text") or "").strip()

    if not original_text or not corrected_text:
        return None

    return LearningRecordDB(
        student_id=student.id,
        skill=(data.get("skill") or "general")[:50],
        topic=(data.get("topic") or "general")[:120],
        original_text=original_text,
        corrected_text=corrected_text,
        explanation=(data.get("explanation") or "").strip(),
        source="voice" if question.startswith("[Voice note transcription]") else "chat"
    )


def calculate_learning_xp(record: LearningRecordDB):
    base_xp_by_skill = {
        "pronunciation": 18,
        "speaking": 16,
        "grammar": 14,
        "vocabulary": 12,
        "fluency": 12,
        "listening": 12,
        "writing": 10,
        "general": 8,
    }

    skill = (record.skill or "general").lower()
    xp = base_xp_by_skill.get(skill, 8)

    if record.source == "voice":
        xp += 5

    if record.corrected_text and len(record.corrected_text.split()) >= 6:
        xp += 3

    return min(xp, 25)


def save_learning_record_if_needed(
    student: StudentDB,
    question: str,
    answer: str,
    db: Session
):
    try:
        record = extract_learning_record(student, question, answer)

        if not record:
            return

        xp_awarded = calculate_learning_xp(record)
        record.xp_awarded = xp_awarded
        student.xp = (student.xp or 0) + xp_awarded

        db.add(record)
        db.commit()
        db.refresh(student)

        print(
            "MEMORIA PEDAGOGICA SALVA:",
            record.skill,
            record.topic,
            f"+{xp_awarded} XP",
            f"total={student.xp}"
        )
    except Exception as error:
        db.rollback()
        print("Erro ao salvar memoria pedagogica:", error)


# =========================
# AI SERVICE
# =========================

def generate_ai_answer(student: StudentDB, question: str, db: Session):
    level = getattr(student, "level", None) or "Basic"
    language = normalize_language_preference(
        getattr(student, "preferred_language", None) or "Portuguese"
    )
    language_instruction = get_language_instruction(language)
    goal = getattr(student, "learning_goal", None) or "Conversation"
    learning_summary = get_recent_learning_summary(student.id, db)

    history = (
        db.query(ConversationDB)
        .filter(ConversationDB.student_id == student.id)
        .order_by(ConversationDB.id.desc())
        .limit(20)
        .all()
    )

    messages = [
        {
            "role": "system",
            "content": f"""
You are Ronan AI from WhatsUp English, an English teacher inside WhatsApp.

Student profile:
- Level: {level}
- Preferred language: {language}
- Learning goal: {goal}

Recent academic memory:
{learning_summary}

Language rule:
- {language_instruction}

Teaching style:
- Be warm, direct, and encouraging.
- Keep the conversation natural, like a private tutor on WhatsApp.
- Adapt vocabulary and grammar to the student's level.
- Prefer short messages. Stay under 120 words.
- Follow the language rule above even if the conversation history used another language.
- Correct mistakes politely.
- Always show a corrected version when the student makes a mistake.
- When pronunciation practice would help, invite the student to send a short voice note.
- If the user's message starts with "[Voice note transcription]", treat it as something the student spoke aloud. Correct the English naturally and encourage them to repeat the improved version.
- Use the recent academic memory to review recurring mistakes naturally, but do not mention database records.
- When a student repeats an old mistake, briefly remind them of the corrected pattern.
- Ask one simple follow-up question to keep the student practicing.
- Do not overwhelm the student with long grammar theory.

Brand voice:
- You can occasionally use the slogan "Let's Bora!".
"""
        }
    ]

    for conversation in reversed(history):
        messages.append(
            {
                "role": "user",
                "content": conversation.question
            }
        )

        messages.append(
            {
                "role": "assistant",
                "content": conversation.answer
            }
        )

    messages.append(
        {
            "role": "user",
            "content": question
        }
    )

    client = get_openai_client()

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages
    )

    answer = response.choices[0].message.content

    conversation = ConversationDB(
        student_id=student.id,
        question=question,
        answer=answer
    )

    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    save_learning_record_if_needed(
        student=student,
        question=question,
        answer=answer,
        db=db
    )

    return answer


def generate_daily_word_challenge(student: StudentDB, db: Session):
    client = get_openai_client()
    learning_summary = get_recent_learning_summary(student.id, db)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": """
You create a short WhatsApp English word-of-the-day challenge.

Rules:
- Use the student's level and memory.
- Keep it under 90 words.
- Include one useful English word, pronunciation hint, meaning in Portuguese,
  one example sentence, and one tiny challenge for the student to answer.
- Be warm and concise.
"""
            },
            {
                "role": "user",
                "content": f"Student: {student.name}\nLevel: {student.level}\nGoal: {student.learning_goal}\nMemory:\n{learning_summary}"
            }
        ]
    )

    return response.choices[0].message.content.strip()


def generate_weekly_quiz(student: StudentDB, db: Session):
    client = get_openai_client()
    learning_summary = get_recent_learning_summary(student.id, db)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": """
Create a weekly English progress quiz for WhatsApp.

Rules:
- Include 3 short writing questions.
- Include 1 speaking task asking the student to send a short audio.
- Personalize using recent mistakes.
- Keep it under 140 words.
- Do not include the answers yet.
"""
            },
            {
                "role": "user",
                "content": f"Student: {student.name}\nLevel: {student.level}\nGoal: {student.learning_goal}\nMemory:\n{learning_summary}"
            }
        ]
    )

    return response.choices[0].message.content.strip()


def generate_weekly_lesson(student: StudentDB, db: Session):
    client = get_openai_client()
    learning_summary = get_recent_learning_summary(student.id, db)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": """
Create one short personalized English mini-lesson for WhatsApp.

Rules:
- Use the student's level, goal, and recent academic memory.
- Teach one new point.
- Include a simple explanation, 2 examples, and 1 practice question.
- Keep it under 130 words.
- If useful, invite the student to send a voice note.
"""
            },
            {
                "role": "user",
                "content": f"Student: {student.name}\nLevel: {student.level}\nGoal: {student.learning_goal}\nMemory:\n{learning_summary}"
            }
        ]
    )

    return response.choices[0].message.content.strip()


def send_daily_word_challenges(db: Session, now: datetime):
    today_key = now.date().isoformat()

    if not has_time_arrived(now, DAILY_WORD_TIME):
        return

    students = db.query(StudentDB).filter(
        StudentDB.assessment_completed == "Yes"
    ).all()

    for student in students:
        if student.last_daily_word_date == today_key:
            continue

        try:
            message = generate_daily_word_challenge(student, db)
            send_whatsapp_message(student.phone, message)

            student.last_daily_word_date = today_key
            student.xp = (student.xp or 0) + 3
            db.commit()
        except Exception as error:
            db.rollback()
            print("Erro ao enviar Palavra do Dia:", student.id, error)


def send_weekly_quizzes(db: Session, now: datetime):
    if now.strftime("%A") != WEEKLY_QUIZ_DAY:
        return

    if not has_time_arrived(now, WEEKLY_QUIZ_TIME):
        return

    week_key = current_week_key(now)
    students = db.query(StudentDB).filter(
        StudentDB.assessment_completed == "Yes"
    ).all()

    for student in students:
        if student.last_weekly_quiz_week == week_key:
            continue

        try:
            message = generate_weekly_quiz(student, db)
            send_whatsapp_message(student.phone, message)

            student.last_weekly_quiz_week = week_key
            student.xp = (student.xp or 0) + 8
            db.commit()
        except Exception as error:
            db.rollback()
            print("Erro ao enviar quiz semanal:", student.id, error)


def send_scheduled_lessons(db: Session, now: datetime):
    students = db.query(StudentDB).filter(
        StudentDB.assessment_completed == "Yes",
        StudentDB.schedule_completed == "Yes"
    ).all()

    for student in students:
        slots = get_student_lesson_schedule(student)
        sent_keys = []

        try:
            sent_keys = json.loads(student.last_lesson_keys or "[]")
        except json.JSONDecodeError:
            sent_keys = []

        for slot in slots:
            if slot.get("day") != now.weekday():
                continue

            if not has_time_arrived(now, slot.get("time", "09:00")):
                continue

            lesson_key = f"{now.date().isoformat()}-{slot.get('day')}-{slot.get('time')}"

            if lesson_key in sent_keys:
                continue

            try:
                message = generate_weekly_lesson(student, db)
                send_whatsapp_message(student.phone, message)

                sent_keys.append(lesson_key)
                student.last_lesson_keys = json.dumps(sent_keys[-20:])
                student.xp = (student.xp or 0) + 10
                db.commit()
            except Exception as error:
                db.rollback()
                print("Erro ao enviar aula agendada:", student.id, error)


async def academic_automation_loop():
    while True:
        db = SessionLocal()

        try:
            now = local_now()
            send_daily_word_challenges(db, now)
            send_scheduled_lessons(db, now)
            send_weekly_quizzes(db, now)
        except Exception as error:
            print("Erro nas automacoes academicas:", error)
        finally:
            db.close()

        await asyncio.sleep(60)


@app.on_event("startup")
async def start_academic_automations():
    if not ACADEMIC_AUTOMATIONS_ENABLED:
        print("Automacoes academicas desativadas por ACADEMIC_AUTOMATIONS_ENABLED=false")
        return

    asyncio.create_task(academic_automation_loop())


# =========================
# STUDENTS
# =========================

@app.post("/register")
def register(student: Student, db: Session = Depends(get_db)):

    existing_student = db.query(StudentDB).filter(
        StudentDB.email == student.email
    ).first()

    if existing_student:
        raise HTTPException(
            status_code=400,
            detail="Este email já está cadastrado."
        )

    existing_phone = db.query(StudentDB).filter(
        StudentDB.phone == student.phone
    ).first()

    if existing_phone:
        raise HTTPException(
            status_code=400,
            detail="Este telefone já está cadastrado."
        )

    hashed_password = bcrypt.hashpw(
        student.password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    new_student = StudentDB(
    name=student.name,
    email=student.email,
    password=hashed_password,
    phone=student.phone,
    preferred_language=student.preferred_language,
    learning_goal=student.learning_goal,
    current_stage=0,
    last_activity=datetime.utcnow()
)

    db.add(new_student)
    db.commit()
    db.refresh(new_student)

    return {
        "message": "Aluno cadastrado com sucesso",
        "id": new_student.id,
        "name": new_student.name,
        "email": new_student.email,
        "phone": new_student.phone,
        "preferred_language": new_student.preferred_language,
        "learning_goal": new_student.learning_goal,
        "level": new_student.level,
        "assessment_completed": new_student.assessment_completed,
        "current_stage": new_student.current_stage,
        "last_activity": new_student.last_activity
    }


@app.get("/students")
def get_students(db: Session = Depends(get_db)):
    return db.query(StudentDB).all()


@app.get("/students/{student_id}")
def get_student(student_id: int, db: Session = Depends(get_db)):
    student = db.query(StudentDB).filter(
        StudentDB.id == student_id
    ).first()

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Aluno não encontrado"
        )

    return student


# =========================
# LOGIN
# =========================

@app.post("/login")
def login(data: Login, db: Session = Depends(get_db)):
    student = db.query(StudentDB).filter(
        StudentDB.email == data.email
    ).first()

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Aluno não encontrado"
        )

    if not bcrypt.checkpw(
        data.password.encode("utf-8"),
        student.password.encode("utf-8")
    ):
        raise HTTPException(
            status_code=401,
            detail="Senha incorreta"
        )

    token = create_access_token(
        {
            "student_id": student.id,
            "email": student.email
        }
    )

    return {
        "access_token": token,
        "token_type": "bearer"
    }


@app.get("/me")
def me(user=Depends(get_current_user)):
    return {
        "message": "Usuário autenticado",
        "user": user
    }


# =========================
# QUIZ
# =========================

@app.post("/quiz")
def quiz(data: QuizAnswer):
    correct_answer = "I am fine."

    if data.answer.strip().lower() == correct_answer.lower():
        return {
            "correct": True,
            "score": 10
        }

    return {
        "correct": False,
        "score": 0
    }


# =========================
# PROGRESS
# =========================

@app.post("/progress")
def save_progress(progress: Progress, db: Session = Depends(get_db)):
    new_progress = ProgressDB(
        student_id=progress.student_id,
        score=progress.score
    )

    db.add(new_progress)
    db.commit()
    db.refresh(new_progress)

    return {
        "message": "Progresso salvo",
        "id": new_progress.id
    }


@app.get("/progress")
def get_progress(db: Session = Depends(get_db)):
    return db.query(ProgressDB).all()


@app.get("/students/{student_id}/progress")
def get_student_progress(student_id: int, db: Session = Depends(get_db)):
    student = db.query(StudentDB).filter(
        StudentDB.id == student_id
    ).first()

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Aluno não encontrado"
        )

    return {
        "student": student.name,
        "scores": [
            progress.score
            for progress in student.progresses
        ]
    }


@app.get("/ranking")
def ranking(db: Session = Depends(get_db)):
    students = (
        db.query(StudentDB)
        .order_by(StudentDB.xp.desc(), StudentDB.id.asc())
        .all()
    )

    return [
        {
            "position": index + 1,
            "student_id": student.id,
            "name": student.name,
            "phone": student.phone,
            "level": student.level,
            "xp": student.xp or 0,
            "streak_days": student.streak_days or 0,
        }
        for index, student in enumerate(students)
    ]


# =========================
# CONVERSATIONS
# =========================

@app.post("/conversation")
def save_conversation(
    conversation: Conversation,
    db: Session = Depends(get_db)
):
    new_conversation = ConversationDB(
        student_id=conversation.student_id,
        question=conversation.question,
        answer=conversation.answer
    )

    db.add(new_conversation)
    db.commit()
    db.refresh(new_conversation)

    return {
        "message": "Conversa salva com sucesso",
        "id": new_conversation.id
    }


@app.get("/conversations")
def get_conversations(db: Session = Depends(get_db)):
    return db.query(ConversationDB).all()


@app.get("/students/{student_id}/conversations")
def get_student_conversations(
    student_id: int,
    db: Session = Depends(get_db)
):
    student = db.query(StudentDB).filter(
        StudentDB.id == student_id
    ).first()

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Aluno não encontrado"
        )

    return {
        "student": student.name,
        "conversations": [
            {
                "question": conversation.question,
                "answer": conversation.answer
            }
            for conversation in student.conversations
        ]
    }




# =========================
# LEARNING RECORDS
# =========================

@app.get("/students/{student_id}/learning-records")
def get_student_learning_records(
    student_id: int,
    db: Session = Depends(get_db)
):
    student = db.query(StudentDB).filter(
        StudentDB.id == student_id
    ).first()

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Aluno nao encontrado"
        )

    return (
        db.query(LearningRecordDB)
        .filter(LearningRecordDB.student_id == student_id)
        .order_by(LearningRecordDB.id.desc())
        .all()
    )


@app.post("/learning-records")
def create_learning_record(
    record: LearningRecord,
    db: Session = Depends(get_db)
):
    student = db.query(StudentDB).filter(
        StudentDB.id == record.student_id
    ).first()

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Aluno nao encontrado"
        )

    new_record = LearningRecordDB(
        student_id=record.student_id,
        skill=record.skill,
        topic=record.topic,
        original_text=record.original_text,
        corrected_text=record.corrected_text,
        explanation=record.explanation,
        source="manual"
    )

    xp_awarded = (
        record.xp_awarded
        if record.xp_awarded is not None
        else calculate_learning_xp(new_record)
    )

    new_record.xp_awarded = xp_awarded
    student.xp = (student.xp or 0) + xp_awarded

    db.add(new_record)
    db.commit()
    db.refresh(new_record)

    return new_record


# =========================
# CHAT IA
# =========================

@app.post("/chat")
def chat(data: ChatRequest, db: Session = Depends(get_db)):
    student = db.query(StudentDB).filter(
        StudentDB.id == data.student_id
    ).first()

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Aluno não encontrado"
        )

    answer = generate_ai_answer(
        student=student,
        question=data.question,
        db=db
    )

    return {
        "student": student.name,
        "question": data.question,
        "answer": answer
    }


# =========================
# WHATSAPP / META
# =========================

def get_or_create_whatsapp_student(phone: str, db: Session):
    now = datetime.utcnow()

    student = db.query(StudentDB).filter(
        StudentDB.phone == phone
    ).first()

    if student:
        student.last_activity = now
        db.commit()
        db.refresh(student)
        return student

    hashed_password = bcrypt.hashpw(
        os.urandom(32),
        bcrypt.gensalt()
    ).decode("utf-8")

    student = StudentDB(
        name="",
        email=f"{phone}@whatsapp.local",
        password=hashed_password,
        phone=phone,
        preferred_language="Portuguese",
        learning_goal="Conversation",
        current_stage=0,
        last_activity=now
    )

    db.add(student)
    db.commit()
    db.refresh(student)

    return student


def process_whatsapp_message(phone: str, message: str, db: Session):
    student = get_or_create_whatsapp_student(phone, db)

    if student.current_stage == 0:
        student.current_stage = 2
        student.last_activity = datetime.utcnow()
        db.commit()

        return (
            "Ola!\n\n"
            "Eu sou o Ronan AI, professor virtual do WhatsUp English.\n\n"
            "Vou te ajudar a aprender ingles de forma simples, pratica e no seu ritmo.\n\n"
            "Let's Bora!\n\n"
            "Primeiro, qual e o seu nome?"
        )

    student.last_activity = datetime.utcnow()
    db.commit()

    if student.current_stage == 2:
        student.name = message
        student.current_stage = 3
        db.commit()

        return (
            f"Prazer em conhecer voce, {student.name}!\n\n"
            "Qual e o seu principal objetivo com o ingles?\n\n"
            "1. Viagens\n"
            "2. Trabalho\n"
            "3. Negocios\n"
            "4. Conversacao\n"
            "5. Entrevistas de emprego\n"
            "6. Estudos\n"
            "7. Outro"
        )

    if student.current_stage == 3:
        student.learning_goal = message
        student.current_stage = 4
        db.commit()

        return (
            "Perfeito!\n\n"
            "Agora me diga:\n\n"
            "Voce prefere continuar nossas conversas em:\n\n"
            "Portugues\n"
            "Ingles\n"
            "Os dois"
        )

    if student.current_stage == 4:
        student.preferred_language = normalize_language_preference(message)
        student.current_stage = 5
        db.commit()

        return get_assessment_prompt(student.preferred_language)

    assessment_completed = getattr(student, "assessment_completed", "No")

    if student.current_stage == 5 and assessment_completed != "Yes":
        client = get_openai_client()

        assessment_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """
You are an English placement test evaluator.

Analyze the student's English answer.

Return ONLY ONE level:

Basic
Basic 2
Intermediate
Advanced
"""
                },
                {
                    "role": "user",
                    "content": message
                }
            ]
        )

        level = assessment_response.choices[0].message.content.strip()

        student.level = level
        student.assessment_completed = "Yes"
        student.current_stage = 6
        db.commit()

        return (
            f"Excelente!\n\n"
            f"Seu nivel atual de ingles e: {level}\n\n"
            "Agora vou preparar duas aulas por semana para voce.\n\n"
            "Quais sao os melhores dias e horarios?\n"
            "Exemplo: segunda 9h e quinta 19h"
        )

    if student.current_stage == 6:
        slots = parse_lesson_schedule(message)

        if len(slots) < 2:
            return (
                "Me mande dois dias e horarios para suas aulas semanais.\n\n"
                "Exemplo: segunda 9h e quinta 19h"
            )

        student.lesson_schedule = json.dumps(slots)
        student.schedule_completed = "Yes"
        student.current_stage = 7
        db.commit()

        return (
            "Combinado! Suas aulas semanais ficaram em "
            f"{format_lesson_schedule(slots)}.\n\n"
            "Todos os dias de manha eu tambem vou te mandar a Palavra do Dia "
            "com um desafio rapido. Uma vez por semana, voce recebe um quiz "
            "com escrita e fala para medir sua evolucao.\n\n"
            "Agora me envie uma frase em ingles ou diga o que voce gostaria "
            "de praticar hoje."
        )

    return generate_ai_answer(
        student=student,
        question=message,
        db=db
    )




@app.get("/students/{student_id}/lesson-schedule")
def get_student_lesson_schedule_endpoint(
    student_id: int,
    db: Session = Depends(get_db)
):
    student = db.query(StudentDB).filter(
        StudentDB.id == student_id
    ).first()

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Aluno nao encontrado"
        )

    return {
        "student_id": student.id,
        "schedule_completed": student.schedule_completed,
        "lesson_schedule": get_student_lesson_schedule(student),
        "daily_word_time": DAILY_WORD_TIME,
        "weekly_quiz_day": WEEKLY_QUIZ_DAY,
        "weekly_quiz_time": WEEKLY_QUIZ_TIME,
    }


@app.post("/students/{student_id}/lesson-schedule")
def update_student_lesson_schedule(
    student_id: int,
    schedule: dict,
    db: Session = Depends(get_db)
):
    student = db.query(StudentDB).filter(
        StudentDB.id == student_id
    ).first()

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Aluno nao encontrado"
        )

    message = schedule.get("message", "")
    slots = parse_lesson_schedule(message)

    if len(slots) < 2:
        raise HTTPException(
            status_code=400,
            detail="Informe dois dias e horarios. Exemplo: segunda 9h e quinta 19h"
        )

    student.lesson_schedule = json.dumps(slots)
    student.schedule_completed = "Yes"
    db.commit()

    return {
        "student_id": student.id,
        "lesson_schedule": slots,
        "message": f"Aulas atualizadas para {format_lesson_schedule(slots)}"
    }


# =========================
# ASSESSMENT
# =========================

@app.post("/assessment")
def assessment(data: AssessmentRequest, db: Session = Depends(get_db)):
    student = db.query(StudentDB).filter(
        StudentDB.id == data.student_id
    ).first()

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Aluno não encontrado"
        )

    client = get_openai_client()

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": """
You are an English placement test evaluator.

Analyze the student's English answer.

Return ONLY ONE level:

Basic
Basic 2
Intermediate
Advanced
"""
            },
            {
                "role": "user",
                "content": data.answer
            }
        ]
    )

    level = response.choices[0].message.content.strip()

    student.level = level
    student.assessment_completed = "Yes"

    db.commit()

    return {
        "student": student.name,
        "level": level
    }


@app.get("/meta-webhook")
def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):

    if (
        hub_mode == "subscribe"
        and hub_verify_token == os.getenv("META_VERIFY_TOKEN")
    ):
        return Response(
            content=hub_challenge,
            media_type="text/plain"
        )

    raise HTTPException(
        status_code=403,
        detail="Verification failed"
    )
@app.post("/meta-webhook")
async def receive_message(
    request: Request,
    db: Session = Depends(get_db)
):
    data = await request.json()

    print("WEBHOOK META")
    print(data)

    try:
        value = data["entry"][0]["changes"][0]["value"]

        if "messages" not in value:
            return {"status": "ok"}

        incoming_message = value["messages"][0]
        phone = incoming_message["from"]
        message_type = incoming_message.get("type")

        if message_type == "text":
            message = incoming_message.get("text", {}).get("body", "").strip()
        elif message_type == "audio":
            media_id = incoming_message.get("audio", {}).get("id")

            if not media_id:
                send_whatsapp_message(
                    phone,
                    "Nao consegui abrir esse audio. Pode tentar mandar novamente?"
                )
                return {"status": "ok"}

            transcript = transcribe_whatsapp_audio(media_id)

            if not transcript:
                send_whatsapp_message(
                    phone,
                    "Nao consegui entender o audio. Pode gravar de novo, bem curtinho?"
                )
                return {"status": "ok"}

            message = f"[Voice note transcription] {transcript}"
        else:
            send_whatsapp_message(
                phone,
                "Por enquanto consigo responder mensagens de texto e audio. Me envie uma frase, pergunta ou audio curto."
            )
            return {"status": "ok"}

        if not message:
            send_whatsapp_message(
                phone,
                "Por enquanto consigo responder mensagens de texto e audio. Me envie uma frase, pergunta ou audio curto."
            )
            return {"status": "ok"}

        print("TELEFONE:", phone)
        print("TELEFONE ENVIO:", normalize_whatsapp_phone_for_send(phone))
        print("MENSAGEM:", message)

        reply = process_whatsapp_message(
            phone=phone,
            message=message,
            db=db
        )

        send_whatsapp_message(
            phone,
            reply
        )

        send_pronunciation_audio_if_needed(
            phone=phone,
            question=message,
            answer=reply
        )

    except Exception as e:
        print("Erro ao processar mensagem:", e)

    return {"status": "ok"}
