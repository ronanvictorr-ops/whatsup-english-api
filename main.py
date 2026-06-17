import asyncio
import json
import os
import re
import tempfile
import unicodedata
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
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
from sqlalchemy import text

from database import Base, SessionLocal, engine
from models import (
    ConversationDB,
    LearningRecordDB,
    ProcessedWebhookMessageDB,
    ProgressDB,
    StudentDB,
)




# =========================
# CONFIGURAÇÕES INICIAIS
# =========================

load_dotenv()

Base.metadata.create_all(bind=engine)


def ensure_runtime_columns():
    if engine.dialect.name != "sqlite":
        return

    with engine.connect() as connection:
        columns = connection.execute(text("PRAGMA table_info(students)")).fetchall()
        column_names = {column[1] for column in columns}

        runtime_columns = {
            "current_lesson": "INTEGER DEFAULT 1",
            "onboarding_notes": "TEXT DEFAULT '[]'",
            "interests": "TEXT DEFAULT ''",
            "lesson_stage": "TEXT DEFAULT 'context_question'",
            "engagement_minutes": "INTEGER DEFAULT 0",
            "messages_in_current_lesson": "INTEGER DEFAULT 0",
            "last_lesson_date": "TEXT",
        }

        for column_name, definition in runtime_columns.items():
            if column_name not in column_names:
                connection.execute(
                    text(f"ALTER TABLE students ADD COLUMN {column_name} {definition}")
                )
                connection.commit()


ensure_runtime_columns()

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


CURRICULUM = [
    {"number": 1, "level": "Basic 1 (A1)", "title": "Greetings", "focus": "Hi, Hello, Good morning; What's your name?; My name is..."},
    {"number": 2, "level": "Basic 1 (A1)", "title": "Countries & Nationalities", "focus": "Where are you from?; I am from Brazil"},
    {"number": 3, "level": "Basic 1 (A1)", "title": "Numbers (0-100) and Age", "focus": "How old are you?"},
    {"number": 4, "level": "Basic 1 (A1)", "title": "Verb To Be", "focus": "I am, You are, He is"},
    {"number": 5, "level": "Basic 1 (A1)", "title": "Family", "focus": "Father, Mother, Brother"},
    {"number": 6, "level": "Basic 1 (A1)", "title": "Professions", "focus": "What do you do?"},
    {"number": 7, "level": "Basic 1 (A1)", "title": "Days and Months", "focus": "Basic calendar vocabulary"},
    {"number": 8, "level": "Basic 1 (A1)", "title": "Time", "focus": "What time is it?"},
    {"number": 9, "level": "Basic 1 (A1)", "title": "Colors", "focus": "Basic color vocabulary"},
    {"number": 10, "level": "Basic 1 (A1)", "title": "Basic Review", "focus": "Review greetings, personal info, numbers, family, time, and colors"},
    {"number": 11, "level": "Basic 2 (A1+)", "title": "Daily Routine", "focus": "Wake up, work, study"},
    {"number": 12, "level": "Basic 2 (A1+)", "title": "Simple Present", "focus": "Habits and routines"},
    {"number": 13, "level": "Basic 2 (A1+)", "title": "Likes and Dislikes", "focus": "I like, I don't like"},
    {"number": 14, "level": "Basic 2 (A1+)", "title": "Food", "focus": "Common food vocabulary"},
    {"number": 15, "level": "Basic 2 (A1+)", "title": "Restaurant Conversation", "focus": "Ordering food and polite requests"},
    {"number": 16, "level": "Basic 2 (A1+)", "title": "Shopping", "focus": "Prices, sizes, and buying items"},
    {"number": 17, "level": "Basic 2 (A1+)", "title": "Weather", "focus": "It's sunny, rainy, cold, hot"},
    {"number": 18, "level": "Basic 2 (A1+)", "title": "House Vocabulary", "focus": "Rooms and objects at home"},
    {"number": 19, "level": "Basic 2 (A1+)", "title": "City Vocabulary", "focus": "Places around town"},
    {"number": 20, "level": "Basic 2 (A1+)", "title": "Review + Speaking Test", "focus": "Review routines, likes, food, shopping, weather, house, and city"},
    {"number": 21, "level": "Intermediate 1 (A2)", "title": "Present Continuous", "focus": "Actions happening now"},
    {"number": 22, "level": "Intermediate 1 (A2)", "title": "Past Simple", "focus": "Talking about the past"},
    {"number": 23, "level": "Intermediate 1 (A2)", "title": "Regular Verbs", "focus": "Past forms with -ed"},
    {"number": 24, "level": "Intermediate 1 (A2)", "title": "Irregular Verbs", "focus": "Common irregular past forms"},
    {"number": 25, "level": "Intermediate 1 (A2)", "title": "Talking About Experiences", "focus": "Personal experiences"},
    {"number": 26, "level": "Intermediate 1 (A2)", "title": "Travel English", "focus": "Useful travel situations"},
    {"number": 27, "level": "Intermediate 1 (A2)", "title": "Airport English", "focus": "Check-in, boarding, luggage"},
    {"number": 28, "level": "Intermediate 1 (A2)", "title": "Hotel English", "focus": "Booking and hotel requests"},
    {"number": 29, "level": "Intermediate 1 (A2)", "title": "Giving Directions", "focus": "Directions and locations"},
    {"number": 30, "level": "Intermediate 1 (A2)", "title": "Review", "focus": "Review present continuous, past, travel, hotel, and directions"},
    {"number": 31, "level": "Intermediate 2 (B1)", "title": "Future (Will)", "focus": "Future decisions and predictions"},
    {"number": 32, "level": "Intermediate 2 (B1)", "title": "Going To", "focus": "Plans and intentions"},
    {"number": 33, "level": "Intermediate 2 (B1)", "title": "Comparatives", "focus": "Bigger, better, more expensive"},
    {"number": 34, "level": "Intermediate 2 (B1)", "title": "Superlatives", "focus": "The best, the most important"},
    {"number": 35, "level": "Intermediate 2 (B1)", "title": "Modal Verbs", "focus": "Ability, advice, obligation"},
    {"number": 36, "level": "Intermediate 2 (B1)", "title": "Can / Could", "focus": "Ability and polite requests"},
    {"number": 37, "level": "Intermediate 2 (B1)", "title": "Should / Must", "focus": "Advice and obligation"},
    {"number": 38, "level": "Intermediate 2 (B1)", "title": "Job Interviews", "focus": "Common interview questions"},
    {"number": 39, "level": "Intermediate 2 (B1)", "title": "Phone Calls", "focus": "Professional phone language"},
    {"number": 40, "level": "Intermediate 2 (B1)", "title": "Review + Speaking", "focus": "Review future, comparisons, modals, interviews, and calls"},
    {"number": 41, "level": "Upper Intermediate (B2)", "title": "Present Perfect", "focus": "Life experience and recent actions"},
    {"number": 42, "level": "Upper Intermediate (B2)", "title": "Present Perfect vs Past Simple", "focus": "Experience vs finished past"},
    {"number": 43, "level": "Upper Intermediate (B2)", "title": "Passive Voice", "focus": "Focus on actions and results"},
    {"number": 44, "level": "Upper Intermediate (B2)", "title": "First Conditional", "focus": "Real future possibilities"},
    {"number": 45, "level": "Upper Intermediate (B2)", "title": "Second Conditional", "focus": "Hypothetical situations"},
    {"number": 46, "level": "Upper Intermediate (B2)", "title": "Phrasal Verbs", "focus": "Common phrasal verbs"},
    {"number": 47, "level": "Upper Intermediate (B2)", "title": "Business English", "focus": "Professional vocabulary"},
    {"number": 48, "level": "Upper Intermediate (B2)", "title": "Meetings", "focus": "Participating in meetings"},
    {"number": 49, "level": "Upper Intermediate (B2)", "title": "Presentations", "focus": "Presenting ideas clearly"},
    {"number": 50, "level": "Upper Intermediate (B2)", "title": "Review", "focus": "Review B2 grammar and professional communication"},
    {"number": 51, "level": "Advanced (C1)", "title": "Advanced Vocabulary", "focus": "Precise and expressive vocabulary"},
    {"number": 52, "level": "Advanced (C1)", "title": "Idioms", "focus": "Common idiomatic expressions"},
    {"number": 53, "level": "Advanced (C1)", "title": "Slang", "focus": "Natural informal English"},
    {"number": 54, "level": "Advanced (C1)", "title": "Storytelling", "focus": "Narrative structure and flow"},
    {"number": 55, "level": "Advanced (C1)", "title": "Debate", "focus": "Arguing and defending opinions"},
    {"number": 56, "level": "Advanced (C1)", "title": "Persuasion", "focus": "Convincing language"},
    {"number": 57, "level": "Advanced (C1)", "title": "Advanced Listening", "focus": "Understanding natural speech"},
    {"number": 58, "level": "Advanced (C1)", "title": "Academic English", "focus": "Formal and academic communication"},
    {"number": 59, "level": "Advanced (C1)", "title": "Public Speaking", "focus": "Speaking clearly to an audience"},
    {"number": 60, "level": "Advanced (C1)", "title": "Review", "focus": "Review advanced communication skills"},
    {"number": 61, "level": "Fluent Conversation (C1/C2)", "title": "Politics", "focus": "Discussing political ideas respectfully"},
    {"number": 62, "level": "Fluent Conversation (C1/C2)", "title": "Technology", "focus": "Technology trends and impact"},
    {"number": 63, "level": "Fluent Conversation (C1/C2)", "title": "Artificial Intelligence", "focus": "AI vocabulary and opinions"},
    {"number": 64, "level": "Fluent Conversation (C1/C2)", "title": "Psychology", "focus": "Behavior, emotions, and the mind"},
    {"number": 65, "level": "Fluent Conversation (C1/C2)", "title": "Philosophy", "focus": "Abstract ideas and reasoning"},
    {"number": 66, "level": "Fluent Conversation (C1/C2)", "title": "Business", "focus": "Business strategy and communication"},
    {"number": 67, "level": "Fluent Conversation (C1/C2)", "title": "Leadership", "focus": "Leadership language and scenarios"},
    {"number": 68, "level": "Fluent Conversation (C1/C2)", "title": "Negotiation", "focus": "Persuasion and compromise"},
    {"number": 69, "level": "Fluent Conversation (C1/C2)", "title": "Cultural Differences", "focus": "Cross-cultural communication"},
    {"number": 70, "level": "Fluent Conversation (C1/C2)", "title": "Final Assessment", "focus": "Final speaking and communication assessment"},
]

CURRICULUM_BY_NUMBER = {
    lesson["number"]: lesson
    for lesson in CURRICULUM
}

PLACEMENT_TEST_QUESTIONS_BY_LEVEL = {
    "Basic": [
        "Pergunta 1 de 5: escreva uma frase em ingles que voce sabe. Se nao souber, nao tem problema: pode me dizer que nao sabe.",
        "Pergunta 2 de 5: como voce diria 'Meu nome e ...' em ingles?",
        "Pergunta 3 de 5: tente responder em ingles: Where are you from?",
        "Pergunta 4 de 5: escreva uma frase simples sobre voce. Pode ser bem curta.",
        "Pergunta 5 de 5: tente dizer em ingles uma coisa que voce gosta. Se nao souber, pode responder em portugues.",
    ],
    "Basic 2": [
        "Pergunta 1 de 5: escreva uma frase se apresentando em ingles.",
        "Pergunta 2 de 5: responda em ingles: What do you do every day?",
        "Pergunta 3 de 5: escreva 3 coisas que voce gosta em ingles.",
        "Pergunta 4 de 5: como voce pediria comida em um restaurante?",
        "Pergunta 5 de 5: escreva uma frase sobre o clima de hoje.",
    ],
    "Intermediate": [
        "Pergunta 1 de 5: introduce yourself in 2 short sentences.",
        "Pergunta 2 de 5: What did you do yesterday?",
        "Pergunta 3 de 5: What are you doing this week?",
        "Pergunta 4 de 5: Tell me about a travel experience or a place you want to visit.",
        "Pergunta 5 de 5: Write one question you would ask at a hotel or airport.",
    ],
    "Advanced": [
        "Question 1 of 5: introduce yourself and explain your English goal.",
        "Question 2 of 5: describe a challenge you faced recently and how you handled it.",
        "Question 3 of 5: give your opinion about technology in everyday life.",
        "Question 4 of 5: write one sentence using a conditional idea, such as 'If I had more time...'.",
        "Question 5 of 5: explain what makes communication effective in business or study.",
    ],
    "Fluent": [
        "Question 1 of 5: introduce yourself naturally and explain what you want to improve.",
        "Question 2 of 5: give your opinion about artificial intelligence in education.",
        "Question 3 of 5: describe a disagreement and how you would negotiate a solution.",
        "Question 4 of 5: explain a cultural difference you find interesting.",
        "Question 5 of 5: tell a short story using natural connectors like however, although, and eventually.",
    ],
}


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

    if is_negative(text) or "nunca" in text or "zero" in text:
        return "Basic"

    if "fluente" in text or "fluent" in text or "c2" in text:
        return "Fluent"

    if "avanc" in text or "advanced" in text or "c1" in text:
        return "Advanced"

    if "intermedi" in text or "b1" in text or "b2" in text:
        return "Intermediate"

    if "basic 2" in text or "básico 2" in text or "a1+" in text:
        return "Basic 2"

    if "basico" in text or "básico" in text or "iniciante" in text or "a1" in text:
        return "Basic"

    return "Basic"


def get_placement_questions(level: str):
    return PLACEMENT_TEST_QUESTIONS_BY_LEVEL.get(
        level,
        PLACEMENT_TEST_QUESTIONS_BY_LEVEL["Basic"]
    )


def count_answer_words(message: str):
    return len(re.findall(r"[A-Za-zÀ-ÿ']+", message or ""))


def is_valid_placement_answer(level: str, question_index: int, message: str):
    text = (message or "").strip()

    if count_answer_words(text) == 0:
        return False

    normalized_level = level or "Basic"

    if normalized_level == "Basic" and question_index == 0:
        return is_negative(text) or count_answer_words(text) >= 2

    if normalized_level in {"Basic", "Basic 2"}:
        return len(text) >= 3

    return count_answer_words(text) >= 2


def repeat_placement_question(level: str, question_index: int):
    questions = get_placement_questions(level)
    question = questions[question_index]

    if level == "Basic" and question_index == 0:
        return (
            "Acho que essa resposta veio incompleta.\n\n"
            "Escreva uma frase em ingles que voce sabe. "
            "Se nao souber, pode responder: nao sei."
        )

    return (
        "Acho que essa resposta veio incompleta.\n\n"
        f"Vamos tentar de novo: {question}"
    )


def get_start_lesson_for_level(level: str):
    normalized = (level or "").strip().lower()

    if "basic 2" in normalized or "a1+" in normalized:
        return 11

    if "intermediate 2" in normalized or "b1" in normalized:
        return 31

    if "upper" in normalized or "b2" in normalized:
        return 41

    if "fluent" in normalized or "fluente" in normalized or "c2" in normalized:
        return 61

    if "advanced" in normalized or "avanc" in normalized or "c1" in normalized:
        return 51

    if "intermediate" in normalized or "a2" in normalized:
        return 21

    return 1


def detect_requested_level_change(message: str):
    text = normalize_intent_text(message)

    change_intent_patterns = [
        r"\bmudar\b",
        r"\btrocar\b",
        r"\bir para\b",
        r"\bir pro\b",
        r"\bir pra\b",
        r"\bvoltar para\b",
        r"\bvoltar pro\b",
        r"\bquero.*nivel\b",
        r"\bprefiro.*nivel\b",
        r"\bnivel\b",
    ]

    if not any(re.search(pattern, text) for pattern in change_intent_patterns):
        return None

    if re.search(r"\b(fluente|fluent|c2)\b", text):
        return "Fluent"

    if re.search(r"\b(avancado|advanced|c1)\b", text):
        return "Advanced"

    if re.search(r"\b(intermediario|intermediate|a2|b1|b2)\b", text):
        return "Intermediate"

    if re.search(r"\b(basic 2|basico 2|a1\+)\b", text):
        return "Basic 2"

    if re.search(r"\b(basico|basic|iniciante|inicio|comeco|comecar do zero|a1)\b", text):
        return "Basic"

    return None


def is_lesson_start_request(message: str):
    text = normalize_intent_text(message)
    return any(
        re.search(pattern, text)
        for pattern in [
            r"\bvamos comecar\b",
            r"\bcomecar\b",
            r"\bcomeçar\b",
            r"\bstart\b",
            r"\blet'?s start\b",
            r"\biniciar\b",
            r"\bproxima aula\b",
            r"\bpróxima aula\b",
            r"\bquero aula\b",
            r"\bcontinuar aula\b",
            r"\bstart lesson\b",
        ]
    )


def is_level_retest_request(message: str):
    text = normalize_intent_text(message)
    return any(
        re.search(pattern, text)
        for pattern in [
            r"\brefazer.*teste\b",
            r"\bfazer.*teste.*nivel\b",
            r"\bnovo.*teste.*nivel\b",
            r"\bteste.*nivel\b",
            r"\bavaliar.*nivel\b",
            r"\breavaliar\b",
            r"\breavaliacao\b",
            r"\bver.*se.*melhorei\b",
            r"\bsaber.*se.*melhorei\b",
            r"\bmeu nivel melhorou\b",
        ]
    )


def get_current_lesson(student: StudentDB):
    lesson_number = getattr(student, "current_lesson", None)

    if not lesson_number:
        lesson_number = get_start_lesson_for_level(
            getattr(student, "level", None)
        )

    lesson_number = max(1, min(int(lesson_number), 70))

    return CURRICULUM_BY_NUMBER.get(lesson_number, CURRICULUM_BY_NUMBER[1])


def get_lesson_context(student: StudentDB):
    lesson = get_current_lesson(student)
    next_lesson = CURRICULUM_BY_NUMBER.get(lesson["number"] + 1)

    next_lesson_text = "This is the final lesson."

    if next_lesson:
        next_lesson_text = (
            f"Next topic: {next_lesson['title']}."
        )

    return (
        f"Current structured lesson:\n"
        f"- Topic ({lesson['level']}): {lesson['title']}\n"
        f"- Focus: {lesson['focus']}\n"
        f"- {next_lesson_text}"
    )


def format_lesson_title(lesson):
    return lesson["title"]


LESSON_STAGES = [
    "context_question",
    "short_explanation",
    "more_examples",
    "comprehension",
    "structure",
    "exercise_1",
    "exercise_2",
    "production",
    "conversation",
    "expansion",
    "challenge",
]

LESSON_COMPLETED_STAGE = "completed"


def get_lesson_stage(student: StudentDB):
    stage = getattr(student, "lesson_stage", None) or "context_question"

    if stage == LESSON_COMPLETED_STAGE:
        return LESSON_COMPLETED_STAGE

    if stage in {"intro", "vocabulary", "grammar", "examples", "practice", "correction"}:
        return "short_explanation"

    if stage not in LESSON_STAGES:
        return "context_question"

    return stage


def is_lesson_completed(student: StudentDB):
    return get_lesson_stage(student) == LESSON_COMPLETED_STAGE


def advance_lesson_stage(student: StudentDB):
    current_stage = get_lesson_stage(student)

    if current_stage == LESSON_COMPLETED_STAGE:
        return

    current_index = LESSON_STAGES.index(current_stage)

    if current_index < len(LESSON_STAGES) - 1:
        student.lesson_stage = LESSON_STAGES[current_index + 1]
    else:
        student.lesson_stage = "conversation"


def mark_lesson_completed(student: StudentDB):
    if (student.current_lesson or 1) < 70:
        student.current_lesson = (student.current_lesson or 1) + 1

    student.lesson_stage = LESSON_COMPLETED_STAGE
    student.messages_in_current_lesson = 0


def reset_lesson_flow(student: StudentDB):
    student.lesson_stage = "context_question"
    student.messages_in_current_lesson = 0


def update_lesson_engagement(student: StudentDB):
    current_stage = get_lesson_stage(student)

    if current_stage == LESSON_COMPLETED_STAGE:
        return

    student.messages_in_current_lesson = (
        getattr(student, "messages_in_current_lesson", 0) or 0
    ) + 1
    student.engagement_minutes = (
        getattr(student, "engagement_minutes", 0) or 0
    ) + 2

    if current_stage == "challenge":
        mark_lesson_completed(student)
        return

    if (student.messages_in_current_lesson or 0) > 1:
        advance_lesson_stage(student)

def get_onboarding_notes(student: StudentDB):
    try:
        notes = json.loads(student.onboarding_notes or "[]")
    except json.JSONDecodeError:
        notes = []

    if not isinstance(notes, list):
        return []

    return notes


def add_onboarding_note(student: StudentDB, key: str, value: str):
    notes = get_onboarding_notes(student)
    notes.append(
        {
            "key": key,
            "value": value,
            "created_at": datetime.utcnow().isoformat()
        }
    )
    student.onboarding_notes = json.dumps(notes, ensure_ascii=False)


def get_latest_onboarding_note(student: StudentDB, key: str):
    notes = get_onboarding_notes(student)

    for note in reversed(notes):
        if note.get("key") == key:
            return note.get("value", "")

    return ""


def is_affirmative(message: str):
    text = (message or "").strip().lower()
    return any(
        word in text
        for word in ["sim", "quero", "pode", "vamos", "yes", "ok", "claro", "bora"]
    )


def is_negative(message: str):
    text = (message or "").strip().lower()
    return any(
        word in text
        for word in ["nao", "não", "prefiro nao", "agora nao", "no"]
    )


def looks_like_english_message(message: str):
    text = (message or "").strip().lower()

    if len(text.split()) < 3:
        return False

    portuguese_markers = [
        "voce", "você", "nao", "não", "quero", "aula", "ingles", "inglês",
        "porque", "obrigado", "obrigada", "comecar", "começar"
    ]

    if any(marker in text for marker in portuguese_markers):
        return False

    english_markers = [
        " i ", " i'm ", " my ", " you ", " are ", " is ", " want ", " need ",
        " like ", " have ", " study ", " english ", " hello ", " hi ",
        "good morning", "good afternoon", "good evening", "where are",
        "what is", "what's", "from brazil"
    ]

    padded_text = f" {text} "

    return any(marker in padded_text for marker in english_markers)


def can_offer_full_english_mode(student):
    return (student.level or "").strip() in {"Advanced", "Fluent"}


def normalize_person_name(value: str):
    text = (value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(
        char for char in text
        if not unicodedata.combining(char)
    )
    return re.sub(r"[^a-z\s]", "", text).strip()


def looks_like_name_correction(student: StudentDB, message: str):
    current_name = normalize_person_name(getattr(student, "name", "") or "")
    candidate_text = extract_name_candidate(message)

    if has_invalid_name_content(candidate_text):
        return False

    new_name = normalize_person_name(candidate_text)

    if not current_name or not new_name:
        return False

    words = new_name.split()

    if len(words) > 4:
        return False

    blocked_goal_words = {
        "viajar", "viagem", "trabalho", "negocios", "conversacao",
        "entrevista", "estudo", "estudar", "aprender", "ingles",
        "profissional", "faculdade", "escola"
    }

    if any(word in blocked_goal_words for word in words):
        return False

    full_similarity = SequenceMatcher(None, current_name, new_name).ratio()

    if full_similarity >= 0.72:
        return True

    current_words = current_name.split()

    return any(
        SequenceMatcher(None, old_word, new_word).ratio() >= 0.82
        for old_word in current_words
        for new_word in words
    )


def normalize_intent_text(value: str):
    text = (value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(
        char for char in text
        if not unicodedata.combining(char)
    )
    return text


def is_affirmative(message: str):
    text = normalize_intent_text(message)
    return any(
        re.search(pattern, text)
        for pattern in [
            r"\bsim\b",
            r"\byes\b",
            r"\bok\b",
            r"\bclaro\b",
            r"\bpode\b",
            r"\bquero\b",
            r"\bvamos\b",
            r"\bbora\b",
        ]
    )


def is_negative(message: str):
    text = normalize_intent_text(message)
    return any(
        re.search(pattern, text)
        for pattern in [
            r"\bnao\b",
            r"\bno\b",
            r"\bprefiro nao\b",
            r"\bagora nao\b",
            r"\bnunca\b",
        ]
    )


def is_unclear_yes_no(message: str):
    return not is_affirmative(message) and not is_negative(message)


def is_study_experience_affirmative(message: str):
    text = normalize_intent_text(message)
    return any(
        re.search(pattern, text)
        for pattern in [
            r"\bsim\b",
            r"\bja\b",
            r"\byes\b",
            r"\bum pouco\b",
            r"\bpouco\b",
            r"\balguns meses\b",
            r"\balguns anos\b",
        ]
    )


def is_unclear_study_experience(message: str):
    return not is_study_experience_affirmative(message) and not is_negative(message)


def wants_portuguese_mode(message: str):
    text = normalize_intent_text(message)
    return any(
        re.search(pattern, text)
        for pattern in [
            r"\bfale.*portugues\b",
            r"\bfalar.*portugues\b",
            r"\bvolta.*portugues\b",
            r"\bvoltar.*portugues\b",
            r"\bsomente.*portugues\b",
            r"\bso.*portugues\b",
            r"\bapenas.*portugues\b",
            r"\bnao.*ingles\b",
            r"\bem portugues\b",
        ]
    )


def wants_english_mode(message: str):
    text = normalize_intent_text(message)
    return any(
        re.search(pattern, text)
        for pattern in [
            r"\bfale.*ingles\b",
            r"\bfalar.*ingles\b",
            r"\bcontinue.*ingles\b",
            r"\bsomente.*ingles\b",
            r"\bso.*ingles\b",
            r"\bapenas.*ingles\b",
            r"\bin english\b",
        ]
    )


def wants_to_stop_assessment(message: str):
    text = normalize_intent_text(message)
    return any(
        re.search(pattern, text)
        for pattern in [
            r"\bpare.*teste\b",
            r"\bparar.*teste\b",
            r"\bcancelar.*teste\b",
            r"\bcancela.*teste\b",
            r"\bnao quero.*teste\b",
            r"\bsem teste\b",
            r"\bchega.*teste\b",
            r"\bstop.*test\b",
            r"\bcancel.*test\b",
        ]
    )


def is_off_topic_during_assessment(message: str):
    text = normalize_intent_text(message)

    if wants_portuguese_mode(text) or wants_english_mode(text) or wants_to_stop_assessment(text):
        return True

    if text in {
        "sim", "nao", "ok", "okay", "ta", "ta bom", "tá bom", "beleza",
        "entendi", "certo", "volta", "pare", "para", "parar", "stop"
    }:
        return True

    return any(
        re.search(pattern, text)
        for pattern in [
            r"\bme ajuda\b",
            r"\bme ajude\b",
            r"\bcomo fala\b",
            r"\bcomo digo\b",
            r"\bcomo dizer\b",
            r"\bcomo eu falo\b",
            r"\btenho uma duvida\b",
            r"\btenho uma pergunta\b",
            r"\bnao entendi\b",
            r"\bnao quero continuar\b",
            r"\bdeixa pra depois\b",
            r"\bdepois eu faco\b",
        ]
    )


def is_probable_learning_goal(message: str):
    text = normalize_intent_text(message)

    if len(text) < 3:
        return False

    if text in {"ok", "sim", "nao", "yes", "no"}:
        return False

    return True


def is_number_without_time_unit(message: str):
    text = normalize_intent_text(message)
    return bool(re.fullmatch(r"\d+", text))


def extract_name_candidate(message: str):
    text = (message or "").strip()
    cleaned = re.sub(
        r"(?i)^(meu nome e|meu nome é|me chamo|sou|corrigindo|correcao|correção|na verdade|quis dizer)\s*[:,-]?\s*",
        "",
        text
    ).strip()
    return cleaned or text


def has_invalid_name_content(message: str):
    raw_text = (message or "").strip()
    normalized_text = normalize_intent_text(raw_text)

    if re.search(r"\d", raw_text):
        return True

    blocked_words = {
        "oi", "ola", "hello", "hi", "bom", "dia", "boa", "tarde", "noite",
        "sim", "nao", "yes", "no", "ok", "quero", "aprender", "ingles",
        "viajar", "viagem", "trabalho", "estudar", "conversacao", "negocios",
        "teste", "testando", "asdf", "abc",
        "porra", "caralho", "merda", "bosta", "fdp", "puta", "puto",
        "cu", "cacete", "desgraca", "idiota", "burro",
    }

    words = re.findall(r"[a-z]+", normalized_text)

    return any(word in blocked_words for word in words)


def is_probable_person_name(message: str):
    candidate_text = extract_name_candidate(message)

    if has_invalid_name_content(candidate_text):
        return False

    candidate = normalize_person_name(candidate_text)

    if not candidate:
        return False

    words = candidate.split()

    if len(words) > 4:
        return False

    blocked_words = {
        "oi", "ola", "hello", "hi", "bom", "dia", "boa", "tarde", "noite",
        "sim", "nao", "yes", "no", "ok", "quero", "aprender", "ingles",
        "viajar", "trabalho", "estudar", "conversacao", "negocios"
    }

    if any(word in blocked_words for word in words):
        return False

    return all(len(word) >= 2 for word in words)


def evaluate_placement_test(student: StudentDB):
    client = get_openai_client()
    notes = get_onboarding_notes(student)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": """
You are an English placement test evaluator.

Analyze the student's onboarding notes and placement test answers.
The student may answer in Portuguese, English, or a mix.
If the student reports having no English contact or only knows isolated words, return Basic.
Do not punish the student for answering in Portuguese; infer level from evidence of English ability.

Return ONLY ONE level:

Basic
Basic 2
Intermediate
Advanced
Fluent
"""
            },
            {
                "role": "user",
                "content": json.dumps(notes, ensure_ascii=False)
            }
        ]
    )

    return response.choices[0].message.content.strip()


def evaluate_placement_test_details(student: StudentDB):
    client = get_openai_client()
    notes = get_onboarding_notes(student)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": """
You are an English placement test evaluator.

Analyze the student's onboarding notes and placement test answers.
The student may answer in Portuguese, English, or a mix.
If the student reports having no English contact or only knows isolated words, return Basic.

Return ONLY valid JSON with this shape:
{
  "level": "Basic | Basic 2 | Intermediate | Advanced | Fluent",
  "reason": "short explanation of why this level was chosen",
  "strengths": ["short strength 1", "short strength 2"],
  "mistakes": [
    {
      "original": "student sentence or phrase",
      "correction": "corrected version",
      "explanation": "short explanation"
    }
  ]
}

Keep reasons and explanations short.
If the chosen level is Basic, Basic 2, or Intermediate, write reason, strengths, and mistake explanations in Portuguese.
If the chosen level is Advanced or Fluent, write reason, strengths, and mistake explanations in English.
If there are no clear English mistakes because the student wrote very little, explain that the level is based on limited evidence.
"""
            },
            {
                "role": "user",
                "content": json.dumps(notes, ensure_ascii=False)
            }
        ]
    )

    content = response.choices[0].message.content.strip()

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return {
            "level": evaluate_placement_test(student),
            "reason": "I based this level on your answers during the quick test.",
            "strengths": [],
            "mistakes": []
        }

    level = data.get("level", "Basic")

    if level not in {"Basic", "Basic 2", "Intermediate", "Advanced", "Fluent"}:
        data["level"] = "Basic"

    return data


def evaluate_placement_test_details_fallback(student: StudentDB):
    notes = get_onboarding_notes(student)
    answers = [
        str(note.get("value", ""))
        for note in notes
        if str(note.get("key", "")).startswith("placement_answer_")
    ]
    combined = normalize_intent_text(" ".join(answers))
    word_count = count_answer_words(combined)

    if (
        not answers
        or "nao sei" in combined
        or "nao tenho" in combined
        or "nenhum conhecimento" in combined
        or "nada" == combined.strip()
    ):
        return {
            "level": "Basic",
            "reason": "Voce informou que nao tem conhecimento ou respondeu com pouca evidencia em ingles.",
            "strengths": ["Voce foi sincero sobre seu ponto de partida."],
            "mistakes": []
        }

    english_signals = len(re.findall(
        r"\b(i|am|my|name|from|like|want|study|work|travel|hello|hi|good)\b",
        combined
    ))

    if english_signals >= 8 and word_count >= 35:
        level = "Intermediate"
        reason = "Voce conseguiu usar varias palavras e ideias em ingles, mas ainda vamos confirmar com aulas guiadas."
    elif english_signals >= 3 and word_count >= 12:
        level = "Basic 2"
        reason = "Voce mostrou alguma base de vocabulario e frases simples em ingles."
    else:
        level = "Basic"
        reason = "Suas respostas mostram que e melhor comecar pelo basico e construir seguranca."

    return {
        "level": level,
        "reason": reason,
        "strengths": ["Voce conseguiu responder ao teste.", "Agora temos um ponto inicial para as aulas."],
        "mistakes": []
    }


def format_placement_feedback(details: dict, language: str):
    level = details.get("level", "Basic")
    reason = details.get("reason") or "I based this on your answers in the test."
    strengths = details.get("strengths") or []
    mistakes = details.get("mistakes") or []
    advanced_feedback = level in {"Advanced", "Fluent"}

    if language == "English" and advanced_feedback:
        lines = [
            "Thanks for answering. I have a clearer picture now.",
            "",
            f"Your current English level is: {level}",
            f"Why I chose this level: {reason}",
        ]

        if strengths:
            lines.append("")
            lines.append("What you did well:")
            lines.extend(f"- {item}" for item in strengths[:2])

        if mistakes:
            lines.append("")
            lines.append("A few corrections:")

            for mistake in mistakes[:2]:
                original = mistake.get("original", "")
                correction = mistake.get("correction", "")
                explanation = mistake.get("explanation", "")
                lines.append(f"- {original} -> {correction}")
                if explanation:
                    lines.append(f"  {explanation}")

        return "\n".join(lines)

    lines = [
        "Obrigado por responder. Agora ficou mais claro.",
        "",
        f"Seu nivel atual de ingles e: {level}",
        f"Por que escolhi esse nivel: {reason}",
    ]

    if strengths:
        lines.append("")
        lines.append("Pontos positivos:")
        lines.extend(f"- {item}" for item in strengths[:2])

    if mistakes:
        lines.append("")
        lines.append("Algumas correcoes:")

        for mistake in mistakes[:2]:
            original = mistake.get("original", "")
            correction = mistake.get("correction", "")
            explanation = mistake.get("explanation", "")
            lines.append(f"- {original} -> {correction}")
            if explanation:
                lines.append(f"  {explanation}")

    return "\n".join(lines)



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

        try:
            meta_error = response.json().get("error", {})
            error_message = meta_error.get("message", "Erro desconhecido da Meta")
            error_code = meta_error.get("code", response.status_code)
        except ValueError:
            error_message = response.text
            error_code = response.status_code

        raise HTTPException(
            status_code=502,
            detail=f"Erro ao enviar mensagem pelo WhatsApp Cloud API: {error_code} - {error_message}"
        )

    return response.json()


def send_whatsapp_video(
    phone: str,
    caption: str,
    media_id: str | None = None,
    link: str | None = None
):
    phone_number_id, access_token = get_meta_whatsapp_config()
    recipient_phone = normalize_whatsapp_phone_for_send(phone)

    url = f"https://graph.facebook.com/v23.0/{phone_number_id}/messages"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    video_payload = {
        "caption": caption
    }

    if media_id:
        video_payload["id"] = media_id
    elif link:
        video_payload["link"] = link
    else:
        raise HTTPException(
            status_code=500,
            detail="Video de introducao nao configurado"
        )

    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_phone,
        "type": "video",
        "video": video_payload
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=20
    )

    if response.status_code >= 400:
        print("Erro ao enviar video pela Meta:", response.text)
        print("Telefone recebido:", phone)
        print("Telefone usado no envio:", recipient_phone)

        try:
            meta_error = response.json().get("error", {})
            error_message = meta_error.get("message", "Erro desconhecido da Meta")
            error_code = meta_error.get("code", response.status_code)
        except ValueError:
            error_message = response.text
            error_code = response.status_code

        raise HTTPException(
            status_code=502,
            detail=f"Erro ao enviar video pelo WhatsApp Cloud API: {error_code} - {error_message}"
        )

    return response.json()


def send_whatsapp_reply(phone: str, reply):
    if isinstance(reply, dict) and reply.get("type") == "video":
        send_whatsapp_video(
            phone=phone,
            caption=reply.get("caption", ""),
            media_id=reply.get("media_id"),
            link=reply.get("link")
        )
        return

    send_whatsapp_message(phone, str(reply))


def get_reply_text(reply):
    if isinstance(reply, dict):
        return reply.get("caption", "")

    return str(reply)


INTRO_VIDEO_PATH = Path(
    os.getenv(
        "WINGO_INTRO_VIDEO_PATH",
        r"C:\Users\Computer\Desktop\WINGO\APRESENTAÇÃO WINGO.mp4"
    )
)

WINGO_INTRO_CAPTION = (
    "Oi!\n\n"
    "Eu sou o WINGO, seu professor de ingles do What's Up English.\n\n"
    "Vou te ajudar a aprender ingles de forma simples, pratica e no seu ritmo.\n\n"
    "LET'S GO..."
)

INTRO_VIDEO_CACHE_PATH = Path(".wingo_intro_video_media_id")


def resolve_intro_video_path():
    configured_path = os.getenv("WINGO_INTRO_VIDEO_PATH")

    if configured_path:
        return Path(configured_path)

    configured_dir = os.getenv("WINGO_INTRO_VIDEO_DIR")

    if not configured_dir:
        return None

    video_dir = Path(configured_dir)

    if not video_dir.exists():
        return None

    preferred_video = video_dir / "APRESENTA\u00c7\u00c3O WINGO.mp4"

    if preferred_video.exists():
        return preferred_video

    videos = sorted(video_dir.glob("*.mp4"))

    if not videos:
        return None

    return videos[0]


def get_cached_intro_video_media_id():
    configured_media_id = os.getenv("WINGO_INTRO_VIDEO_MEDIA_ID")

    if configured_media_id:
        return configured_media_id

    if INTRO_VIDEO_CACHE_PATH.exists():
        media_id = INTRO_VIDEO_CACHE_PATH.read_text(encoding="utf-8").strip()

        if media_id:
            return media_id

    return None


def cache_intro_video_media_id(media_id: str):
    INTRO_VIDEO_CACHE_PATH.write_text(media_id, encoding="utf-8")


def build_lesson_intro_video_reply(student: StudentDB):
    media_id = os.getenv("WINGO_LESSON_INTRO_VIDEO_MEDIA_ID")
    video_link = os.getenv("WINGO_LESSON_INTRO_VIDEO_LINK")

    if not media_id and not video_link:
        return None

    lesson = get_current_lesson(student)
    caption = (
        f"Vamos comecar nossa aula: {format_lesson_title(lesson)}.\n\n"
        "Assista esse video rapidinho e depois responda a proxima pergunta."
    )

    if media_id:
        return {
            "type": "video",
            "caption": caption,
            "media_id": media_id
        }

    return {
        "type": "video",
        "caption": caption,
        "link": video_link
    }


def build_intro_video_reply():
    media_id = get_cached_intro_video_media_id()
    video_link = os.getenv("WINGO_INTRO_VIDEO_LINK")

    if media_id:
        return {
            "type": "video",
            "caption": WINGO_INTRO_CAPTION,
            "media_id": media_id
        }

    if video_link:
        return {
            "type": "video",
            "caption": WINGO_INTRO_CAPTION,
            "link": video_link
        }

    intro_video_path = resolve_intro_video_path()

    if intro_video_path and intro_video_path.exists():
        media_id = upload_whatsapp_media(intro_video_path, "video/mp4")
        cache_intro_video_media_id(media_id)
        return {
            "type": "video",
            "caption": WINGO_INTRO_CAPTION,
            "media_id": media_id
        }

    return WINGO_INTRO_CAPTION


def upload_whatsapp_media(file_path: Path, mime_type: str):
    phone_number_id, access_token = get_meta_whatsapp_config()
    url = f"https://graph.facebook.com/v23.0/{phone_number_id}/media"

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    file_size_mb = file_path.stat().st_size / (1024 * 1024)

    with file_path.open("rb") as file:
        response = requests.post(
            url,
            headers=headers,
            data={"messaging_product": "whatsapp"},
            files={"file": (file_path.name, file, mime_type)},
            timeout=30
        )

    if response.status_code >= 400:
        print("Erro ao subir media na Meta:", response.text)
        print("Arquivo:", file_path)
        print("Tipo:", mime_type)
        print("Tamanho MB:", round(file_size_mb, 2))

        try:
            meta_error = response.json().get("error", {})
            error_message = meta_error.get("message", "Erro desconhecido da Meta")
            error_code = meta_error.get("code", response.status_code)
        except ValueError:
            error_message = response.text
            error_code = response.status_code

        raise HTTPException(
            status_code=502,
            detail=f"Erro ao subir media para o WhatsApp Cloud API: {error_code} - {error_message}"
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


def should_send_pronunciation_audio(question: str, answer: str):
    text = (question or "").lower()
    answer_text = (answer or "").lower()

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
        "manda audio",
        "mande audio",
        "manda um audio",
        "pode falar",
        "nao entendi",
        "não entendi",
        "dificuldade",
        "dificil entender",
        "difícil entender",
    )

    answer_triggers = (
        "repeat after me:",
        "repita comigo:",
    )

    return any(trigger in text for trigger in triggers) or any(
        trigger in answer_text for trigger in answer_triggers
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


def extract_english_phrases_for_audio(answer: str, limit: int = 3):
    quoted_phrases = re.findall(r'"([^"]+)"', answer or "")
    candidates = []

    for phrase in quoted_phrases:
        if re.search(r"[A-Za-z]", phrase) and not re.search(r"[À-ÿ]", phrase):
            candidates.append(phrase.strip())

    if not candidates:
        for line in (answer or "").splitlines():
            cleaned = line.strip(" -•0123456789.()")

            if not cleaned:
                continue

            if re.search(
                r"\b(am|is|are|hello|hi|good morning|my name|what's your name)\b",
                cleaned.lower()
            ):
                candidates.append(cleaned)

    unique_phrases = []

    for phrase in candidates:
        if phrase and phrase not in unique_phrases:
            unique_phrases.append(phrase)

    return unique_phrases[:limit]


def ensure_teacher_audio_prompt(student: StudentDB, answer: str):
    if "repeat after me:" in (answer or "").lower():
        return answer

    if get_lesson_stage(student) not in {
        "more_examples",
        "structure",
        "production",
        "conversation",
    }:
        return answer

    phrases = extract_english_phrases_for_audio(answer)

    if not phrases:
        lesson = get_current_lesson(student)

        if lesson["title"] == "Greetings":
            phrases = ["Hi.", "Hello.", "My name is Wingo."]

    if not phrases:
        return answer

    return (
        f"{answer}\n\n"
        "Repeat after me:\n"
        + "\n".join(phrases)
    )


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


def normalize_language_preference(value: str):
    text = (value or "").strip().lower()

    if text in {"2", "english", "ingles", "inglês"} or "engl" in text or "ingl" in text:
        return "English"

    if text in {"1", "portuguese", "portugues", "português"} or "port" in text:
        return "Portuguese"

    return "Adaptive"


def get_language_instruction(language: str, level: str = "Basic"):
    if language == "English":
        return (
            "Reply primarily in English. Do not switch to Portuguese unless the "
            "student explicitly asks for Portuguese or seems completely stuck."
        )

    if language == "Portuguese":
        return (
            "Use Portuguese as the main explanation language. Still include simple "
            "English practice sentences, but keep explanations in Portuguese."
        )

    normalized_level = (level or "").strip().lower()

    if "fluent" in normalized_level or "fluente" in normalized_level or "c2" in normalized_level:
        return "Use about 90% English and 10% Portuguese. Use Portuguese only if the student asks."

    if "advanced" in normalized_level or "avanc" in normalized_level or "c1" in normalized_level:
        return "Use about 80% English and 20% Portuguese. Use Portuguese only to clarify difficult points."

    if "upper" in normalized_level or "b2" in normalized_level:
        return "Use about 70% English and 30% Portuguese. Keep explanations concise."

    if "intermediate" in normalized_level or "a2" in normalized_level or "b1" in normalized_level:
        return "Use about 50% English and 50% Portuguese. Increase English gradually when the student responds well."

    return (
        "Use about 30% to 40% English and 60% to 70% Portuguese. Use very simple "
        "English words and short sentences. Do not force long English answers from beginners."
    )


def get_assessment_prompt(language: str):
    if language == "English":
        return (
            "Great!\n\n"
            "Now I will do a quick assessment to understand your current English level.\n\n"
            "Don't worry about mistakes. Answer as best as you can.\n\n"
            "Tell me what you already know in English. You can write words, short phrases, or a simple sentence."
        )

    return (
        "Otimo!\n\n"
        "Agora vou fazer uma avaliacao rapida para entender seu nivel atual de ingles.\n\n"
        "Nao se preocupe com erros. Pode responder em portugues, em ingles, ou misturado.\n\n"
        "Me diga:\n"
        "1. Voce ja estudou ingles antes?\n"
        "2. Quais palavras ou frases em ingles voce ja conhece?\n"
        "3. Se conseguir, escreva uma frase simples em ingles. Exemplo: My name is..."
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


def parse_day_period_time(value: str):
    text = (value or "").lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))

    if "manha" in text or "morning" in text:
        return "09:00"

    if "tarde" in text or "afternoon" in text:
        return "14:00"

    if "noite" in text or "night" in text or "evening" in text:
        return "19:00"

    return None


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
            lesson_time = parse_day_period_time(chunk)

        if not lesson_time:
            lesson_time = parse_clock_time(text)

        if not lesson_time:
            lesson_time = parse_day_period_time(text)

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


def today_key():
    return local_now().date().isoformat()


def has_started_lesson_today(student: StudentDB):
    return getattr(student, "last_lesson_date", None) == today_key()


def mark_lesson_started_today(student: StudentDB):
    student.last_lesson_date = today_key()


def get_seasonal_context(now: datetime | None = None):
    now = now or local_now()
    month_day = now.strftime("%m-%d")

    seasonal_dates = {
        "01-01": {
            "name": "New Year's Day",
            "theme": "goals, plans, resolutions, and fresh starts",
            "vocabulary": "goals, resolution, improve, habit, fresh start",
        },
        "02-14": {
            "name": "Valentine's Day",
            "theme": "relationships, affection, invitations, and kind messages",
            "vocabulary": "date, gift, flowers, couple, romantic",
        },
        "03-08": {
            "name": "International Women's Day",
            "theme": "respect, achievements, work, family, and appreciation",
            "vocabulary": "respect, achievement, equality, support, inspire",
        },
        "04-01": {
            "name": "April Fools' Day",
            "theme": "jokes, humor, surprises, and playful conversation",
            "vocabulary": "joke, prank, funny, surprise, kidding",
        },
        "05-01": {
            "name": "Labor Day",
            "theme": "jobs, routines, careers, meetings, and professional English",
            "vocabulary": "work, career, meeting, schedule, coworker",
        },
        "06-12": {
            "name": "Dia dos Namorados no Brasil",
            "theme": "dating, relationships, compliments, invitations, gifts, and feelings",
            "vocabulary": "date, crush, relationship, gift, compliment, miss you",
        },
        "09-07": {
            "name": "Brazilian Independence Day",
            "theme": "Brazil, culture, history, travel, and describing your country",
            "vocabulary": "independence, country, culture, flag, celebrate",
        },
        "10-12": {
            "name": "Children's Day in Brazil",
            "theme": "childhood, memories, family, games, and simple past",
            "vocabulary": "childhood, toy, game, memory, family",
        },
        "10-31": {
            "name": "Halloween",
            "theme": "costumes, stories, fear, parties, and describing scenes",
            "vocabulary": "costume, spooky, candy, party, ghost",
        },
        "11-20": {
            "name": "Black Consciousness Day in Brazil",
            "theme": "culture, identity, history, respect, and representation",
            "vocabulary": "identity, culture, history, respect, heritage",
        },
        "12-24": {
            "name": "Christmas Eve",
            "theme": "family, dinner, gifts, plans, and greetings",
            "vocabulary": "gift, dinner, family, celebrate, holiday",
        },
        "12-25": {
            "name": "Christmas",
            "theme": "family, gifts, gratitude, travel, and holiday greetings",
            "vocabulary": "Christmas, gift, grateful, trip, celebrate",
        },
        "12-31": {
            "name": "New Year's Eve",
            "theme": "plans, reflections, celebrations, future with going to and will",
            "vocabulary": "celebrate, countdown, midnight, plan, next year",
        },
    }

    seasonal = seasonal_dates.get(month_day)

    if not seasonal:
        return (
            "No major seasonal date today. Use everyday situations, the student's "
            "goal, and recent academic memory as the main theme."
        )

    return (
        f"Today is {seasonal['name']}. Prefer examples and mini-lessons connected "
        f"to {seasonal['theme']}. Useful vocabulary: {seasonal['vocabulary']}. "
        "Keep the theme natural and culturally sensitive; do not force romance or "
        "personal topics if the student's goal suggests work, travel, or studies."
    )


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

def generate_ai_answer(
    student: StudentDB,
    question: str,
    db: Session,
    ai_question: str | None = None
):
    level = getattr(student, "level", None) or "Basic"
    language = normalize_language_preference(
        getattr(student, "preferred_language", None) or "Portuguese"
    )
    language_instruction = get_language_instruction(language, level)
    goal = getattr(student, "learning_goal", None) or "Conversation"
    interests = getattr(student, "interests", None) or "not informed yet"
    lesson_stage = get_lesson_stage(student)
    lesson_mode = "bot_after_lesson" if lesson_stage == LESSON_COMPLETED_STAGE else "guided_lesson"
    engagement_minutes = getattr(student, "engagement_minutes", 0) or 0
    lesson_messages = getattr(student, "messages_in_current_lesson", 0) or 0
    learning_summary = get_recent_learning_summary(student.id, db)
    lesson_context = get_lesson_context(student)

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
You are WINGO from WhatsUp English, a friendly English tutor inside WhatsApp.

Student profile:
- Level: {level}
- Preferred language: {language}
- Learning goal: {goal}
- Interests: {interests}
- Current lesson stage: {lesson_stage}
- Current mode: {lesson_mode}
- Estimated engagement in lessons: {engagement_minutes} minutes
- Messages in current lesson: {lesson_messages}

Recent academic memory:
{learning_summary}

Structured course path:
{lesson_context}

Language rule:
- {language_instruction}

Wingo's personality:
- Friendly, patient, and motivating.
- Sound like a helpful tutor in a WhatsApp chat, not a formal school.
- Be simple, human, and encouraging.
- Celebrate small progress without exaggerating.
- Make the student feel comfortable making mistakes.
- Keep a light, positive tone.

Lesson guidance:
- Do not behave like a free open chat.
- Lead the student through the current structured lesson.
- Respect the current lesson stage and follow the micro-lesson flow below.
- Start from the current lesson topic unless the student asks a direct urgent question.
- If the student asks something unrelated, answer briefly and gently bring them back to the current lesson.
- Teach one small point at a time, then ask one practice question.
- If the student says "vamos comecar", "vamos começar", "start", or "let's start", begin the lesson topic directly. Do not ask "How are you today?" in this case.
- Do not jump to future lessons unless the student explicitly asks for a preview.
- Do not advance the course just because the student sent one answer; reinforce, correct, and practice first.
- If the student asks "what should I study?" or "start the class", begin the current lesson.

After-lesson BOT mode:
- If Current mode is bot_after_lesson, the guided class has already finished.
- In bot_after_lesson mode, do not continue the next structured lesson automatically.
- In bot_after_lesson mode, answer the student's personal English questions naturally, like a helpful tutor.
- If the student asks a curiosity such as how to order water, how to say a sentence, vocabulary, pronunciation, or travel phrase, answer that question and keep the conversation on that topic.
- If the student answers "sim", "yes", "ok", "ta bom", or similar in bot_after_lesson mode, treat it as a reply to your last assistant question, not as permission to start the next lesson.
- In bot_after_lesson mode, only start the next structured lesson if the student clearly asks: "vamos comecar", "proxima aula", "quero aula", "start lesson", or similar.
- In bot_after_lesson mode, you may mention that the next guided lesson is ready, but do not teach it unless the student asks or it is a scheduled class time.

Micro-lesson flow:
- Each lesson is a micro-lesson: 1 concept, 5 to 10 minutes, 10 to 15 WhatsApp messages.
- Do not send a long 60-minute class. The product experience is: learn one small thing now, get feedback, continue.
- Do not send all steps at once. Send only the current step.
- Do not show labels like "Etapa 1" unless the student asks for a summary.
- Current stage context_question: ask one simple question that naturally creates the need for the lesson. Use a question that belongs to the current lesson topic only.
- Current stage short_explanation: explain the concept briefly and give 1 bilingual example.
- Current stage more_examples: give 3 bilingual examples, English first and Portuguese meaning right after. Include "Repeat after me:" with 1 to 3 short English phrases.
- Current stage comprehension: ask what one example means. Example: What does "She is reading" mean?
- Current stage structure: show the formula clearly. Example: Subject + To Be + Verb + ING.
- Current stage exercise_1: ask a fill-in-the-blank exercise. Example: I ___ studying.
- Current stage exercise_2: ask a second fill-in-the-blank exercise. Example: She ___ reading.
- Current stage production: ask the student to translate or produce one full sentence. After the student writes it, ask for one short audio under 20 seconds.
- Current stage conversation: ask a real conversation question using the topic. Example: What are you doing right now?
- Current stage expansion: ask for only 2 personalized sentences about the student's life, interests, or surroundings.
- Current stage challenge: finish with one tiny mission, not another long exercise, and summarize what they learned.

Present Continuous example flow:
- Short explanation: We use Present Continuous for actions happening now. Example: I am studying English. Eu estou estudando ingles.
- More examples: She is reading. Ela esta lendo. He is working. Ele esta trabalhando. They are playing soccer. Eles estao jogando futebol.
- Structure: Subject + To Be + Verb + ING.
- Explain that -ING is added to the main verb: study -> studying, read -> reading, play -> playing.
- Explain am/is/are: I am, he/she/it is, you/we/they are.
- Mention simple spelling only when helpful: make -> making, run -> running.
- If the student answered the context question incorrectly, do not say "Muito bem" or "Great job". Say "Quase isso", show the corrected version, and then explain.

Greetings lesson requirements:
- Stay only on greetings and simple introductions.
- Do not mix in unrelated grammar like Present Continuous, routine, colors, or long personal sentences.
- Context question: ask "Como voce diria 'Ola' em ingles?"
- Accept "hello" and "hi" as correct answers.
- If the student writes "hello", do not say "Quase isso". Say it is correct and explain the difference between "Hi" and "Hello" simply.
- Examples should stay close to the topic:
  - Hi.
  - Hello.
  - Good morning.
  - What's your name?
  - My name is Ronan.
- Comprehension should ask meaning of one greeting or one introduction sentence.
- Structure should focus only on "My name is..." and "What's your name?"
- Exercises should be simple:
  - Complete: My name ___ Ronan.
  - Complete: ___ your name?
- Production should ask the student to introduce themselves with "My name is..."

Standard Wingo lesson model:
- The Micro-lesson flow above is mandatory and overrides this generic model.
- Follow this structure for each lesson, but deliver it step by step through conversation.
- Do not send the whole lesson at once.
- Never output all labels in one message: Warm-up, Vocabulary, Grammar, Examples, Practice, Correction, Challenge.
- Choose only the next step the student needs right now.
- Keep each WhatsApp message under 90 words whenever possible.
- Warm-up is only for scheduled class messages sent on the student's chosen days and times. Do not use a generic "How are you today?" when the student manually asks to start.
- 2. New Vocabulary: teach up to 10 useful words connected to the current lesson.
- 3. Grammar: give a clear explanation of the main structure. Include the formula, when to use it, common rules, and one important detail for the topic.
- 4. Examples: give 3 realistic examples.
- 5. Practice: ask questions and make the student answer using the lesson topic. Prefer text answers by default.
- 6. Correction: correct mistakes gently and show the improved sentence.
- 7. Challenge: finish with one tiny mission, such as "Write one sentence about now."
- In WhatsApp chat, usually send only one section or one exercise per message.
- After each student answer, decide whether to correct, give another practice item, or move to the next section.
- For grammar topics such as Present Continuous, do not be too shallow. Explain the structure, for example: subject + verb to be + verb-ing; mention that -ing is added to the main verb; include spelling notes when useful, such as make -> making and run -> running.
- After the explanation, ask only one practice question.

Personalization:
- Use the student's interests to create examples, short scenarios, and practice prompts.
- If the student likes games, use examples with playing, winning, losing, streaming, characters, missions, and teams.
- If the student likes music, use examples with listening, singing, playing instruments, concerts, bands, and lyrics.
- If the student likes movies or series, use examples with watching, characters, scenes, episodes, and stories.
- If the student mentions religion or church, be respectful and use neutral examples about community, routine, reading, music, and events. Do not debate beliefs.
- If the student likes technology, use examples with apps, AI, work, coding, devices, and online conversations.
- Combine the learning goal with interests. For example, travel + games can become "I am traveling to a gaming event."
- Do not force personalization in every sentence. Use it naturally.

Engagement:
- Make the student spend time practicing by asking one small answer at a time.
- Prefer short cycles: explain, example, ask, correct, ask again.
- After a few good answers, briefly show qualitative progress such as "Boa, voce esta praticando bem esse padrao." Do not mention message counts.
- Do not invent exact scores unless the system gives them. You may mention progress qualitatively.
- If the student seems tired or asks to stop, summarize what they learned and end kindly.

Audio control:
- Every micro-lesson should include at least one teacher audio and at least one student audio request.
- Prefer text practice by default, but do not skip audio completely.
- Do not ask for audio in every exercise.
- Suggest up to two short audio moments per lesson when useful: one for repeating model sentences and one for the student's own answer.
- When asking for audio, request one short voice note under 20 seconds.
- Use audio mainly for pronunciation, speaking confidence, or final speaking checks.
- If you want the system to send a teacher audio, write exactly "Repeat after me:" followed by 1 to 3 short English sentences.
- When teaching a new English phrase or model sentence, include a "Repeat after me:" block so the backend sends teacher audio.
- Use "Repeat after me:" up to two times per lesson, preferably after structure and near conversation or challenge.
- After sending a repeat prompt, ask the student to answer with a short audio only if pronunciation practice is useful.
- If the student sends many voice notes in sequence, correct briefly and guide them back to text practice.
- Do not ask for a voice note in the first lesson message.
- Do not ask for voice notes in challenges unless the student asked for speaking practice.

Teaching style:
- Be warm, direct, and encouraging.
- Keep the conversation natural, like a private tutor on WhatsApp.
- Adapt vocabulary and grammar to the student's level.
- Prefer short messages, but grammar explanations may use 120 to 180 words when needed for clarity.
- Follow the language rule above even if the conversation history used another language.
- Correct mistakes politely.
- Always show a corrected version when the student makes a mistake.
- Only invite the student to send a voice note if they explicitly ask for speaking or pronunciation practice.
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
            "content": ai_question or question
        }
    )

    client = get_openai_client()

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages
    )

    answer = response.choices[0].message.content
    answer = ensure_teacher_audio_prompt(student, answer)

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
    seasonal_context = get_seasonal_context()

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": """
You create a short WhatsApp English word-of-the-day challenge.

Rules:
- Use the student's level, memory, and seasonal context.
- If the seasonal context names a commemorative date or holiday, prefer a word connected to that theme.
- Keep it under 90 words.
- Include one useful English word, pronunciation hint, meaning in Portuguese,
  one example sentence, and one tiny challenge for the student to answer.
- Be warm and concise.
"""
            },
            {
                "role": "user",
                "content": f"Student: {student.name}\nLevel: {student.level}\nGoal: {student.learning_goal}\nSeasonal context:\n{seasonal_context}\nMemory:\n{learning_summary}"
            }
        ]
    )

    return response.choices[0].message.content.strip()


def generate_weekly_quiz(student: StudentDB, db: Session):
    client = get_openai_client()
    learning_summary = get_recent_learning_summary(student.id, db)
    seasonal_context = get_seasonal_context()

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
- If there is a relevant seasonal date or holiday, use it naturally in the writing or speaking prompts.
- Keep it under 140 words.
- Do not include the answers yet.
"""
            },
            {
                "role": "user",
                "content": f"Student: {student.name}\nLevel: {student.level}\nGoal: {student.learning_goal}\nSeasonal context:\n{seasonal_context}\nMemory:\n{learning_summary}"
            }
        ]
    )

    return response.choices[0].message.content.strip()


def generate_weekly_lesson(student: StudentDB, db: Session):
    client = get_openai_client()
    learning_summary = get_recent_learning_summary(student.id, db)
    seasonal_context = get_seasonal_context()
    lesson_context = get_lesson_context(student)
    interests = getattr(student, "interests", None) or "not informed yet"
    lesson_stage = get_lesson_stage(student)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": """
Create one short personalized English mini-lesson for WhatsApp.

Rules:
- Use the current structured lesson as the main lesson theme.
- Use the student's level, goal, recent academic memory, and seasonal context.
- If there is a relevant commemorative date or holiday this week, connect it lightly to the current lesson only if it fits naturally.
- Do NOT send the full lesson structure.
- Do NOT include labels like Warm-up, Vocabulary, Grammar, Examples, Practice, Correction Invitation, or Challenge.
- This message is for the student's scheduled class time, so a short warm-up is allowed.
- Do not always ask "How are you today?". Vary the opening and connect it to the lesson topic.
- Send only the first useful step of the lesson.
- Start with one friendly sentence, introduce the current topic, and ask one simple question connected to the topic.
- Use the student's interests naturally in the example or question when possible.
- Respect the current lesson stage.
- Keep it under 90 words.
- Wait for the student's answer before teaching vocabulary or grammar.
- Prefer text practice.
- Do not ask for audio or voice notes in this first lesson message.
- Do not use emojis.
"""
            },
            {
                "role": "user",
                "content": f"Student: {student.name}\nLevel: {student.level}\nGoal: {student.learning_goal}\nInterests: {interests}\nLesson stage: {lesson_stage}\nStructured lesson:\n{lesson_context}\nSeasonal context:\n{seasonal_context}\nMemory:\n{learning_summary}"
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

            if has_started_lesson_today(student):
                continue

            try:
                if not getattr(student, "lesson_stage", None):
                    student.lesson_stage = "context_question"
                mark_lesson_started_today(student)
                update_lesson_engagement(student)
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
    interests="",
    current_lesson=1,
    lesson_stage="context_question",
    engagement_minutes=0,
    messages_in_current_lesson=0,
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
        "interests": new_student.interests,
        "level": new_student.level,
        "assessment_completed": new_student.assessment_completed,
        "current_lesson": new_student.current_lesson,
        "lesson_stage": new_student.lesson_stage,
        "engagement_minutes": new_student.engagement_minutes,
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
            "interests": student.interests,
            "current_lesson": student.current_lesson,
            "lesson_stage": student.lesson_stage,
            "engagement_minutes": student.engagement_minutes or 0,
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
        interests="",
        current_lesson=1,
        lesson_stage="context_question",
        engagement_minutes=0,
        messages_in_current_lesson=0,
        current_stage=0,
        last_activity=now
    )

    db.add(student)
    db.commit()
    db.refresh(student)

    return student


def recover_student_flow(student: StudentDB, db: Session):
    if not (student.name or "").strip():
        student.current_stage = 2
        db.commit()
        return (
            "Tive um problema aqui. Vou retomar com você do ponto certo.\n\n"
            "Primeiro, qual e o seu nome?"
        )

    if not (student.learning_goal or "").strip() or student.learning_goal == "Conversation":
        student.current_stage = 3
        db.commit()
        return (
            "Tive um problema aqui. Vou retomar com você do ponto certo.\n\n"
            "Me conta com suas palavras: por que voce quer aprender ingles?"
        )

    if not (student.interests or "").strip():
        student.current_stage = 35
        db.commit()
        return (
            "Tive um problema aqui. Vou retomar com você do ponto certo.\n\n"
            "Me conta do que voce gosta para eu personalizar suas aulas."
        )

    if getattr(student, "assessment_completed", "No") != "Yes":
        student.current_stage = 4
        db.commit()
        return (
            "Tive um problema aqui. Vou retomar com você do ponto certo.\n\n"
            "Voce ja estudou ingles antes, mesmo que por pouco tempo?"
        )

    if getattr(student, "schedule_completed", "No") != "Yes":
        student.current_stage = 70
        db.commit()
        return (
            "Tive um problema aqui. Vou retomar com você do ponto certo.\n\n"
            "Quais dias e horarios voce prefere para suas aulas?"
        )

    student.current_stage = 7
    db.commit()
    return (
        "Tive um problema aqui. Vou retomar com você do ponto certo.\n\n"
        "Quando quiser continuar, me mande: vamos comecar."
    )


def process_whatsapp_message(phone: str, message: str, db: Session):
    student = get_or_create_whatsapp_student(phone, db)

    if student.current_stage == 999:
        student.last_activity = datetime.utcnow()
        db.commit()
        return recover_student_flow(student, db)

    if student.current_stage == 0:
        student.current_stage = 2
        student.last_activity = datetime.utcnow()
        db.commit()

        return [
            build_intro_video_reply(),
            "Primeiro, qual e o seu nome?"
        ]

    student.last_activity = datetime.utcnow()
    db.commit()

    if (
        student.current_stage not in {0, 2, 3, 35, 4, 5, 6, 50, 51, 52, 53, 54, 70, 80, 81, 999}
        and is_level_retest_request(message)
    ):
        student.assessment_completed = "No"
        student.current_stage = 50
        reset_lesson_flow(student)
        add_onboarding_note(student, "level_retest_requested", message)
        db.commit()

        questions = get_placement_questions(student.level)
        return (
            "Claro. Quando voce se sentir preparado, pode refazer o teste de nivel para ver sua evolucao.\n\n"
            "Vamos fazer agora: sao 5 perguntas curtas, uma por vez.\n\n"
            f"{questions[0]}"
        )

    if student.current_stage == 2:
        if not is_probable_person_name(message):
            return (
                "Quase la. Me diga apenas seu nome.\n\n"
                "Exemplo: Ronan"
            )

        student.name = extract_name_candidate(message)
        student.current_stage = 3
        db.commit()

        return (
            f"Prazer em conhecer voce, {student.name}!\n\n"
            "Me conta com suas palavras: por que voce quer aprender ingles?"
        )

    if student.current_stage == 3:
        if looks_like_name_correction(student, message):
            student.name = extract_name_candidate(message)
            db.commit()

            return (
                f"Obrigado, corrigi seu nome para {student.name}.\n\n"
                "Agora me conta com suas palavras: por que voce quer aprender ingles?"
            )

        if not is_probable_learning_goal(message):
            return (
                "Me conta um pouco melhor seu objetivo com o ingles.\n\n"
                "Pode escrever do seu jeito. Exemplo: quero viajar, trabalhar, conversar ou estudar fora."
            )

        student.learning_goal = message
        student.preferred_language = "Adaptive"
        add_onboarding_note(student, "learning_goal", message)
        student.current_stage = 35
        db.commit()

        return (
            "Legal. Para eu deixar suas aulas mais interessantes, me conta do que voce gosta.\n\n"
            "Pode ser musica, filmes, series, games, futebol, tecnologia, igreja, viagens, livros..."
        )

    if student.current_stage == 35:
        if not is_probable_learning_goal(message):
            return (
                "Me fala pelo menos um interesse seu.\n\n"
                "Exemplo: gosto de games, musica e filmes."
            )

        student.interests = message
        add_onboarding_note(student, "interests", message)
        student.current_stage = 4
        db.commit()

        return "Boa. Vou usar isso para personalizar exemplos e praticas. Voce ja estudou ingles antes, mesmo que por pouco tempo?"

    if student.current_stage == 4:
        add_onboarding_note(student, "studied_before", message)
        if is_negative(message):
            student.level = "Basic"
            student.current_lesson = get_start_lesson_for_level(student.level)
            reset_lesson_flow(student)
            student.assessment_completed = "Yes"
            student.current_stage = 70
            db.commit()

            lesson = get_current_lesson(student)

            return (
                "Sem problema. Vamos comecar bem do inicio e no seu ritmo.\n\n"
                "Entao seu nivel de ingles provavelmente e: Basic.\n\n"
                f"A primeira aula sera: {format_lesson_title(lesson)}.\n\n"
                "Quais dias e horarios voce prefere para suas aulas?"
            )

        if is_unclear_study_experience(message):
            return (
                "So para eu entender melhor: voce ja estudou ingles antes?\n\n"
                "Pode responder sim, nao ou um pouco."
            )

        student.current_stage = 5
        db.commit()

        return "Legal. E por quanto tempo voce estudou? Se souber, me diga tambem qual nivel voce acha que tem hoje."

    assessment_completed = getattr(student, "assessment_completed", "No")

    if student.current_stage == 5 and assessment_completed != "Yes":
        if is_number_without_time_unit(message):
            return (
                "Voce quis dizer meses ou anos?\n\n"
                "Exemplo: 5 meses, 5 anos, ou: acho que sou basico."
            )

        add_onboarding_note(student, "study_time_and_self_level", message)
        probable_level = estimate_level_from_study_history(message)
        student.level = probable_level
        student.current_stage = 81 if probable_level in {"Advanced", "Fluent"} else 6
        db.commit()

        if probable_level in {"Advanced", "Fluent"}:
            return (
                f"Perfeito. Entao seu nivel de ingles provavelmente e: {probable_level}.\n\n"
                "Voce quer continuar a aula em ingles?"
            )

        return (
            f"Perfeito. Entao seu nivel de ingles provavelmente e: {probable_level}.\n\n"
            "Para confirmar melhor, voce quer fazer um teste rapidinho agora? "
            "Sao 5 perguntas curtas, uma por vez."
        )

    if student.current_stage == 81 and assessment_completed != "Yes":
        if wants_portuguese_mode(message):
            student.preferred_language = "Portuguese"
            student.current_stage = 6
            db.commit()

            return (
                "Combinado. Vou falar em portugues com voce.\n\n"
                "Voce quer fazer um teste rapidinho de nivel agora? "
                "Sao 5 perguntas curtas, uma por vez."
            )

        if is_affirmative(message):
            student.preferred_language = "English"
            student.current_stage = 6
            db.commit()

            return (
                "Perfect. I will continue mainly in English.\n\n"
                "Would you like to take a quick level test now? "
                "It has 5 short questions, one at a time."
            )

        if is_negative(message):
            student.preferred_language = "Adaptive"
            student.current_stage = 6
            db.commit()

            return (
                "Combinado. Vou misturar portugues e ingles quando fizer sentido.\n\n"
                "Voce quer fazer um teste rapidinho de nivel agora? "
                "Sao 5 perguntas curtas, uma por vez."
            )

        return "Voce quer continuar a aula em ingles? Pode responder sim ou nao."

    if student.current_stage == 6 and assessment_completed != "Yes":
        if wants_portuguese_mode(message):
            student.preferred_language = "Portuguese"
            db.commit()

            return (
                "Combinado. Vou falar em portugues com voce.\n\n"
                "Voce quer fazer o teste rapidinho de nivel agora?"
            )

        if is_negative(message):
            student.level = "Basic"
            student.current_lesson = get_start_lesson_for_level(student.level)
            reset_lesson_flow(student)
            student.assessment_completed = "Yes"
            student.current_stage = 70
            db.commit()

            lesson = get_current_lesson(student)

            if normalize_language_preference(student.preferred_language) == "English":
                return (
                    "No problem. We will start calmly from your current base.\n\n"
                    f"The first lesson will be: {format_lesson_title(lesson)}.\n\n"
                    "Which days and times do you prefer for your classes?"
                )

            return (
                "Tudo bem. Vamos comecar com calma pelo basico.\n\n"
                f"A primeira aula sera: {format_lesson_title(lesson)}.\n\n"
                "Quais dias e horarios voce prefere para suas aulas?"
            )

        if is_unclear_yes_no(message):
            return (
                "Pode me responder com sim ou nao?\n\n"
                "Voce quer fazer o teste rapidinho de nivel agora?"
            )

        student.current_stage = 50
        db.commit()

        questions = get_placement_questions(student.level)
        return questions[0]

    if 50 <= student.current_stage <= 54 and assessment_completed != "Yes":
        question_index = student.current_stage - 50
        questions = get_placement_questions(student.level)
        answer_message = message

        if is_off_topic_during_assessment(answer_message):
            if wants_portuguese_mode(answer_message):
                student.preferred_language = "Portuguese"

            student.current_lesson = get_start_lesson_for_level(student.level)
            reset_lesson_flow(student)
            student.assessment_completed = "Yes"
            student.current_stage = 70
            db.commit()

            lesson = get_current_lesson(student)

            return (
                "Sem problema. Parei o teste por aqui.\n\n"
                f"Vou considerar por enquanto que seu nivel provavelmente e: {student.level}.\n\n"
                f"A primeira aula sera: {format_lesson_title(lesson)}.\n\n"
                "Quais dias e horarios voce prefere para suas aulas?"
            )

        if not is_valid_placement_answer(student.level, question_index, answer_message):
            return repeat_placement_question(student.level, question_index)

        add_onboarding_note(
            student,
            f"placement_answer_{question_index + 1}",
            answer_message
        )

        if question_index < len(questions) - 1:
            student.current_stage += 1
            db.commit()
            return questions[question_index + 1]

        try:
            placement_details = evaluate_placement_test_details(student)
        except Exception as error:
            print("Erro ao avaliar teste de nivel. Usando fallback:", error)
            placement_details = evaluate_placement_test_details_fallback(student)

        level = placement_details.get("level", "Basic")

        student.level = level
        student.current_lesson = get_start_lesson_for_level(level)
        reset_lesson_flow(student)
        student.assessment_completed = "Yes"
        student.current_stage = 70
        db.commit()

        lesson = get_current_lesson(student)
        feedback = format_placement_feedback(
            placement_details,
            normalize_language_preference(student.preferred_language)
        )
        advanced_feedback = level in {"Advanced", "Fluent"}

        if normalize_language_preference(student.preferred_language) == "English" and advanced_feedback:
            return [
                (
                    f"{feedback}\n\n"
                    f"I will prepare your first lesson: {format_lesson_title(lesson)}.\n\n"
                    "When you feel ready in the future, you can ask me to retake the level test."
                ),
                "Which days and times do you prefer for your classes?"
            ]

        return [
            (
                f"{feedback}\n\n"
                f"Vou preparar sua primeira aula: {format_lesson_title(lesson)}.\n\n"
                "Quando se sentir preparado no futuro, voce pode me pedir para refazer o teste de nivel."
            ),
            "Quais dias e horarios voce prefere para suas aulas?"
        ]

    if student.current_stage == 70:
        slots = parse_lesson_schedule(message)

        if len(slots) < 2:
            if normalize_language_preference(student.preferred_language) == "English":
                return (
                    "Send me two days and times for your classes.\n\n"
                    "You can write naturally. Example: Monday morning and Thursday night."
                )

            return (
                "Me mande dois dias e horarios para suas aulas.\n\n"
                "Pode escrever do seu jeito. Exemplo: segunda de manha e quinta a noite."
            )

        student.lesson_schedule = json.dumps(slots)
        student.schedule_completed = "Yes"
        student.current_stage = 7
        db.commit()

        if normalize_language_preference(student.preferred_language) == "English":
            return (
                "Great! Your weekly classes are scheduled for "
                f"{format_lesson_schedule(slots)}.\n\n"
                "In our first lesson, I will guide you step by step.\n\n"
                "When you feel you have improved, you can ask: retake level test.\n\n"
                "When you want to start, send me: let's start."
            )

        return (
            "Combinado! Suas aulas semanais ficaram em "
            f"{format_lesson_schedule(slots)}.\n\n"
            "Na nossa primeira aula, eu vou te guiar passo a passo.\n\n"
            "Quando sentir que evoluiu, voce pode pedir: refazer teste de nivel.\n\n"
            "Quando quiser comecar, me mande: vamos comecar."
        )

    if student.current_stage == 80:
        if is_affirmative(message):
            student.preferred_language = "English"
            student.current_stage = 7
            db.commit()

            return "Perfect. From now on, I will continue the class mainly in English."

        if is_negative(message):
            student.preferred_language = "Adaptive"
            student.current_stage = 7
            db.commit()

            return "Combinado. Vou continuar misturando portugues e ingles de acordo com seu nivel."

        return "Voce prefere continuar a aula em ingles? Pode responder sim ou nao."

    if student.current_stage == 7:
        requested_level = detect_requested_level_change(message)

        if requested_level:
            student.level = requested_level
            student.current_lesson = get_start_lesson_for_level(requested_level)
            reset_lesson_flow(student)
            student.preferred_language = (
                "Adaptive"
            )
            if requested_level in {"Advanced", "Fluent"}:
                student.current_stage = 80
            db.commit()

            lesson = get_current_lesson(student)

            if requested_level in {"Advanced", "Fluent"}:
                return (
                    f"Combinado. Mudei seu nivel para {requested_level}.\n\n"
                    f"Vamos seguir por: {format_lesson_title(lesson)}.\n\n"
                    "Quer continuar essa parte em ingles?"
                )

            return (
                f"Combinado. Mudei seu nivel para {requested_level}.\n\n"
                f"Vamos seguir por: {format_lesson_title(lesson)}.\n\n"
                "Vou explicar em portugues e colocar o ingles aos poucos, no seu ritmo."
            )

    if student.current_stage == 7 and is_lesson_completed(student):
        if is_lesson_start_request(message):
            if has_started_lesson_today(student):
                return (
                    "Por hoje ja fizemos uma aula guiada.\n\n"
                    "Para a beta, vou liberar 1 aula por dia para cada aluno. "
                    "Mas posso te ajudar com duvidas, frases, vocabulario ou revisao do que vimos hoje."
                )

            reset_lesson_flow(student)
            mark_lesson_started_today(student)
            db.commit()

            lesson = get_current_lesson(student)
            lesson_video = build_lesson_intro_video_reply(student)

            replies = [
                "Combinado! Vamos para a proxima aula.",
            ]

            if lesson_video:
                replies.append(lesson_video)

            if lesson["title"] == "Greetings":
                replies.append("Como voce diria 'Ola' em ingles?")
            else:
                replies.append(
                    f"Hoje vamos trabalhar: {format_lesson_title(lesson)}.\n\n"
                    "Primeiro, me diga uma coisa simples sobre esse tema com suas palavras."
                )

            return replies

        return generate_ai_answer(
            student=student,
            question=message,
            db=db,
            ai_question=(
                "[Internal instruction: the guided lesson is finished. "
                "Answer the student's current question in flexible tutor/BOT mode. "
                "Do not start the next structured lesson. If the student only says yes, continue the last free-help topic.]\n\n"
                f"Student message: {message}"
            )
        )

    if (
        student.current_stage == 7
        and can_offer_full_english_mode(student)
        and normalize_language_preference(student.preferred_language) != "English"
        and looks_like_english_message(message)
    ):
        student.current_stage = 80
        db.commit()

        return "Percebi que voce escreveu em ingles. Voce quer continuar a aula em ingles?"

    if student.current_stage == 7 and is_lesson_start_request(message):
        if has_started_lesson_today(student):
            return (
                "Por hoje ja fizemos uma aula guiada.\n\n"
                "Para a beta, vou liberar 1 aula por dia para cada aluno. "
                "Mas posso te ajudar com duvidas, frases, vocabulario ou revisao do que vimos hoje."
            )

        student.lesson_stage = "context_question"
        student.messages_in_current_lesson = 0
        mark_lesson_started_today(student)
        db.commit()

        lesson = get_current_lesson(student)
        lesson_video = build_lesson_intro_video_reply(student)

        if lesson["title"] == "Greetings":
            replies = [
                "Otimo! Vamos comecar!",
                "Como voce diria 'Ola' em ingles?"
            ]

            if lesson_video:
                replies.insert(1, lesson_video)

            return replies

        replies = [
            "Otimo! Vamos comecar!",
            "O que voce esta fazendo agora?"
        ]

        if lesson_video:
            replies.insert(1, lesson_video)

        return replies

    question_for_ai = None

    if student.current_stage == 7:
        update_lesson_engagement(student)
        db.commit()

        if get_lesson_stage(student) == "short_explanation":
            lesson = get_current_lesson(student)
            question_for_ai = (
                "[Internal instruction: use the student's last answer as the bridge into the lesson. "
                f"The current lesson topic is {lesson['title']}. Do not teach another topic. "
                "Explain only the current concept using that answer when possible. "
                "If the topic is Greetings, stay only with Hi, Hello, Good morning, What's your name?, and My name is. "
                "If the student answered correctly, say it is correct without saying 'Quase isso'. "
                "If the student answered incorrectly, say 'Quase isso' and correct gently.]\n\n"
                f"Student message: {message}"
            )

    return generate_ai_answer(
        student=student,
        question=message,
        db=db,
        ai_question=question_for_ai
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
Fluent
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
        message_id = incoming_message.get("id")
        message_type = incoming_message.get("type")

        if message_id:
            already_processed = db.query(ProcessedWebhookMessageDB).filter(
                ProcessedWebhookMessageDB.message_id == message_id
            ).first()

            if already_processed:
                print("Mensagem Meta ja processada:", message_id)
                return {"status": "ok"}

            db.add(
                ProcessedWebhookMessageDB(
                    message_id=message_id,
                    phone=phone
                )
            )
            db.commit()

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

        replies = reply if isinstance(reply, list) else [reply]

        for reply_message in replies:
            print("RESPOSTA:", get_reply_text(reply_message))
            send_whatsapp_reply(
                phone,
                reply_message
            )

        reply_text = "\n".join(get_reply_text(item) for item in replies)

        send_pronunciation_audio_if_needed(
            phone=phone,
            question=message,
            answer=reply_text
        )

    except Exception as e:
        print("Erro ao processar mensagem:", e)
        try:
            db.rollback()
            if "phone" in locals():
                student = db.query(StudentDB).filter(
                    StudentDB.phone == phone
                ).first()

                if student:
                    student.current_stage = 999
                    student.last_activity = datetime.utcnow()
                    db.commit()
                    print("Aluno marcado para recuperacao:", phone)
        except Exception as recovery_error:
            db.rollback()
            print("Erro ao marcar aluno para recuperacao:", recovery_error)

    return {"status": "ok"}
