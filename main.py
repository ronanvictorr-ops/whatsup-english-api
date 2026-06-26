import asyncio
import json
import os
import re
import tempfile
import unicodedata
from time import perf_counter
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
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from database import Base, SessionLocal, engine, get_db
from pedagogy import (
    CORRECTION_RUBRIC,
    PLACEMENT_RUBRIC,
    PRONUNCIATION_RUBRIC,
    SPACED_REVIEW_INTERVALS,
    build_pedagogical_context,
    get_advancement_criterion,
    get_lesson_design,
    get_placement_rubric_text,
)
from models import (
    ConversationDB,
    LearningRecordDB,
    LessonSessionDB,
    OperationalMetricDB,
    OutboundDeliveryDB, PersonalNoteDB,
    PronunciationAttemptDB,
    ProcessedWebhookMessageDB,
    ProgressDB,
    StudentDB,
    StateTransitionDB,
)
from wingo.flows.router import resolve_flow
from wingo.states import (
    ConversationState,
    infer_recovery_state,
    restore_student,
    snapshot_student,
    state_name,
)
from wingo.observability import audit_transition, log_event, record_metric
from wingo.idempotency import (
    claim_inbound_message,
    complete_inbound_message,
    fail_inbound_message,
    send_reply_once,
)
from wingo.retries import call_with_retry, http_get_with_retry, http_post_with_retry
from wingo.personal_memory import (
    get_recent_personal_notes_summary,
    save_personal_notes_if_needed,
)
from wingo.pronunciation import (
    assess_pronunciation,
    build_pronunciation_feedback,
    extract_reference_text,
)
from wingo.phones import (
    mask_phone,
    normalize_whatsapp_phone as normalize_whatsapp_phone_for_send,
    whatsapp_phone_variants,
)
from wingo.security import (
    create_access_token,
    get_current_user,
    meta_signature_required,
    require_dashboard_admin,
    require_student_access,
    validate_security_configuration,
    verify_meta_webhook_signature,
)
from wingo.webhook import (
    WebhookDependencies,
    configure_webhook,
    receive_message,
    router as webhook_router,
    verify_webhook,
)
from wingo.automations import (
    acquire_automation_lock,
    build_weekly_progress_report,
    configure_automations,
    generate_daily_word_challenge,
    generate_weekly_lesson,
    generate_weekly_quiz,
    release_automation_lock,
    send_daily_word_challenges,
    send_scheduled_lessons,
    send_weekly_progress_reports,
    send_weekly_quizzes,
)
from wingo.api import configure_api, router as api_router


def run_academic_automations_once(db: Session, now: datetime) -> None:
    """Compatibility facade for callers that patch automation steps in main."""
    send_scheduled_lessons(db, now)
    send_daily_word_challenges(db, now)
    send_weekly_quizzes(db, now)
    send_weekly_progress_reports(db, now)




# =========================
# CONFIGURAÇÕES INICIAIS
# =========================

load_dotenv()

app = FastAPI()

DASHBOARD_DIR = Path(__file__).resolve().parent / "dashboard"
SALES_DIR = Path(__file__).resolve().parent / "sales"
app.mount(
    "/dashboard-assets",
    StaticFiles(directory=DASHBOARD_DIR),
    name="dashboard-assets",
)
app.mount(
    "/sales-assets",
    StaticFiles(directory=SALES_DIR),
    name="sales-assets",
)

validate_security_configuration()


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
WEEKLY_REPORT_DAY = os.getenv("WEEKLY_REPORT_DAY", "Friday")
WEEKLY_REPORT_TIME = os.getenv("WEEKLY_REPORT_TIME", "18:00")

PRODUCT_PLANS = [
    {
        "id": "individual_beta",
        "name": "Aluno Individual Beta",
        "price_brl": 29.90,
        "billing": "monthly",
        "audience": "Aluno final",
        "limits": {
            "students": 1,
            "guided_lessons_per_day": 1,
        },
        "features": [
            "1 aula guiada por dia",
            "Aulas de 5 a 10 minutos",
            "Pratica por texto",
            "Pratica por audio",
            "Correcao imediata",
            "Memoria pedagogica",
            "Teste de nivel inicial",
            "Relatorio semanal",
            "Suporte em horario comercial",
        ],
        "beta_offer": "7 dias gratis ou R$19,90 por mes durante 3 meses para fundadores",
    },
    {
        "id": "teacher_partner_beta",
        "name": "Professor Parceiro Beta",
        "price_brl": 99.00,
        "billing": "monthly",
        "audience": "Professor independente",
        "limits": {
            "students": 10,
            "guided_lessons_per_day": 1,
        },
        "features": [
            "Ate 10 alunos",
            "Painel do professor",
            "Progresso por aluno",
            "Relatorio por aluno",
            "Memoria pedagogica por aluno",
            "Comandos de controle do aluno",
            "Acompanhamento humano opcional",
        ],
        "beta_offer": "Plano para professores validarem o WINGO com uma turma pequena",
    },
    {
        "id": "school_beta",
        "name": "Escola Beta",
        "price_range_brl": "299.00-599.00",
        "billing": "monthly",
        "audience": "Escolas pequenas e cursos livres",
        "limits": {
            "students": "30-100",
            "guided_lessons_per_day": 1,
        },
        "features": [
            "Painel da escola",
            "Relatorios semanais",
            "Acompanhamento por turma",
            "Indicadores de engajamento",
            "Suporte prioritario",
            "Personalizacao com nome da escola",
        ],
        "beta_offer": "Recomendado somente depois da validacao com alunos e professores",
    },
]


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
            r"\bvamos (?:para|pra|ter|fazer).*aula\b",
            r"\bpodemos (?:comecar|iniciar|antecipar).*aula\b",
            r"\bquero (?:comecar|iniciar|antecipar).*aula\b",
            r"\baula agora\b",
            r"\b(?:seguir|segue|continue|continuar|retomar).*aula guiada\b",
            r"\baula guiada\b",
            r"\bvamos (?:seguir|continuar).*aula\b",
            r"^guiada$",
            r"^guiana$",
            r"^agora$",
        ]
    )


def is_lesson_schedule_question(message: str):
    text = normalize_intent_text(message)
    return any(
        re.search(pattern, text)
        for pattern in [
            r"\bque horas.*aula\b",
            r"\bqual.*horario.*aula\b",
            r"\bquando.*aula\b",
            r"\bhorario.*aula\b",
        ]
    )


def is_schedule_change_request(message: str):
    text = normalize_intent_text(message)
    return any(
        re.search(pattern, text)
        for pattern in [
            r"\bmudar.*horario\b",
            r"\btrocar.*horario\b",
            r"\balterar.*horario\b",
            r"\bremarcar.*aula\b",
            r"\breagendar.*aula\b",
        ]
    )


def is_exercise_request(message: str):
    text = normalize_intent_text(message)
    return any(
        re.search(pattern, text)
        for pattern in [
            r"\bexercici[oa]s?\b",
            r"\bexercise\b",
            r"\bquiz\b",
            r"\bpraticar\b",
            r"\bpractice\b",
            r"\bfazer questoes\b",
            r"\bfazer perguntas\b",
        ]
    )


def is_next_lesson_question(message: str):
    text = normalize_intent_text(message)
    return any(
        re.search(pattern, text)
        for pattern in [
            r"\bqual.*proxima aula\b",
            r"\bo que.*proxima aula\b",
            r"\bo que.*vamos aprender.*proxim\b",
            r"\bqual.*proximo tema\b",
            r"\baula de amanha\b",
            r"\bnext lesson\b",
            r"\bwhat.*learn next\b",
        ]
    )


def detect_language_switch_request(message: str):
    text = normalize_intent_text(message)

    english_patterns = [
        r"^(?:english|ingles)$",
        r"\benglish only\b",
        r"\bonly english\b",
        r"\bspeak (?:only )?english\b",
        r"\bcontinue in english\b",
        r"\blesson in english\b",
        r"\b(?:mudar|trocar|alterar).*(?:idioma|lingua).*(?:english|ingles)\b",
        r"\b(?:mudar|trocar|alterar).*para.*(?:english|ingles)\b",
        r"\bem ingles\b",
        r"\b(?:fale|fala|continue|aula).*somente.*ingles\b",
        r"\b(?:fale|fala|continue|aula).*so em ingles\b",
        r"\bsomente em ingles\b",
    ]
    portuguese_patterns = [
        r"^(?:portuguese|portugues)$",
        r"\bportuguese only\b",
        r"\bonly portuguese\b",
        r"\bspeak (?:only )?portuguese\b",
        r"\bcontinue in portuguese\b",
        r"\b(?:mudar|trocar|alterar).*(?:idioma|lingua).*(?:portuguese|portugues)\b",
        r"\b(?:mudar|trocar|alterar).*para.*(?:portuguese|portugues)\b",
        r"\bem portugues\b",
        r"\b(?:fale|fala|continue|aula).*somente.*portugues\b",
        r"\b(?:fale|fala|continue|aula).*so em portugues\b",
        r"\bsomente em portugues\b",
    ]

    if any(re.search(pattern, text) for pattern in english_patterns):
        return "English"

    if any(re.search(pattern, text) for pattern in portuguese_patterns):
        return "Portuguese"

    return None


def is_ready_for_lesson(message: str):
    text = normalize_intent_text(message)
    return (
        is_affirmative(message)
        or is_lesson_start_request(message)
        or any(
            re.search(pattern, text)
            for pattern in [
                r"\bestou pront[oa]\b",
                r"\bestou disponivel\b",
                r"\bpode mandar\b",
                r"\bpode comecar\b",
            ]
        )
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


def detect_control_command(message: str):
    text = normalize_intent_text(message)

    command_patterns = [
        ("reset", [r"\breiniciar\b", r"\bresetar\b", r"\bcomecar de novo\b", r"\bcomeçar de novo\b", r"\bzerar\b"]),
        ("status", [r"\bstatus\b", r"\bonde estou\b", r"\bem que etapa\b"]),
        ("progress", [r"\bmeu progresso\b", r"\bprogresso\b", r"\bminha evolucao\b", r"\bminha evolução\b"]),
        ("weekly_report", [r"\brelatorio semanal\b", r"\brelatorio da semana\b", r"\bresumo da semana\b"]),
        ("review", [r"\brevisar aula\b", r"\brevisao\b", r"\brevisão\b", r"\brevisar\b"]),
        ("pause", [r"\bpausar aulas\b", r"\bpausar\b", r"\bdar um tempo\b"]),
        ("resume", [r"\bretomar aulas\b", r"\bvoltar aulas\b", r"\bcontinuar aulas\b", r"\bvamos continuar\b"]),
        ("support", [r"\bsuporte\b", r"\bfalar com suporte\b", r"\bhumano\b", r"\bprofessor humano\b"]),
        ("help", [r"\bajuda\b", r"\bcomandos\b", r"\bo que posso fazer\b"]),
    ]

    for command, patterns in command_patterns:
        if any(re.search(pattern, text) for pattern in patterns):
            return command

    return None


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
    stage = get_lesson_stage(student)
    pedagogical_context = build_pedagogical_context(
        lesson=lesson,
        level=getattr(student, "level", "Basic"),
        stage=stage,
    )

    next_lesson_text = "This is the final lesson."

    if next_lesson:
        next_lesson_text = (
            f"Next topic: {next_lesson['title']}."
        )

    return (
        f"Current structured lesson:\n"
        f"- Topic ({lesson['level']}): {lesson['title']}\n"
        f"- Focus: {lesson['focus']}\n"
        f"- {next_lesson_text}\n\n"
        f"{pedagogical_context}"
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


def get_active_lesson_session(student: StudentDB, db: Session):
    return (
        db.query(LessonSessionDB)
        .filter(
            LessonSessionDB.student_id == student.id,
            LessonSessionDB.status == "started"
        )
        .order_by(LessonSessionDB.id.desc())
        .first()
    )


def start_lesson_session(student: StudentDB, db: Session, mode: str = "guided"):
    active_session = get_active_lesson_session(student, db)

    if active_session:
        return active_session

    lesson = get_current_lesson(student)
    lesson_design = get_lesson_design(lesson)
    session = LessonSessionDB(
        student_id=student.id,
        lesson_number=student.current_lesson or lesson["number"],
        lesson_title=lesson["title"],
        mode=mode,
        status="started",
        messages_count=student.messages_in_current_lesson or 0,
        summary=(
            f"Objetivo: {lesson_design['objective']} "
            f"Can-do: {lesson_design['can_do']}"
        )
    )

    db.add(session)
    return session


def complete_active_lesson_session(student: StudentDB, db: Session):
    active_session = get_active_lesson_session(student, db)

    if not active_session:
        return

    lesson = get_current_lesson(student)
    active_session.status = "completed"
    active_session.completed_at = datetime.utcnow()
    active_session.messages_count = student.messages_in_current_lesson or 0
    active_session.summary = (
        f"Aula concluida: {format_lesson_title(lesson)}. "
        f"Foco: {lesson['focus']}."
    )


def get_latest_lesson_session(student: StudentDB, db: Session):
    return (
        db.query(LessonSessionDB)
        .filter(LessonSessionDB.student_id == student.id)
        .order_by(LessonSessionDB.id.desc())
        .first()
    )


def get_latest_completed_lesson_session(student: StudentDB, db: Session):
    return (
        db.query(LessonSessionDB)
        .filter(
            LessonSessionDB.student_id == student.id,
            LessonSessionDB.status == "completed"
        )
        .order_by(LessonSessionDB.id.desc())
        .first()
    )


def build_post_lesson_feedback_message(student: StudentDB, db: Session):
    session = get_latest_completed_lesson_session(student, db)

    if not session:
        return None

    lesson_focus = session.summary or f"Voce praticou {session.lesson_title}."
    records = get_recent_learning_records(student.id, db, limit=3)
    review_lines = []

    for record in records:
        if record.corrected_text:
            review_lines.append(f"- {record.corrected_text[:90]}")

    review_text = "\n".join(review_lines) if review_lines else "- Uma frase curta usando o tema da aula."
    next_hook = build_next_lesson_preview(student, db, closing_hook=True)

    body = (
        "Fechamento da aula de hoje:\n\n"
        f"Hoje voce aprendeu: {lesson_focus}\n\n"
        "Sua missao: me mandar amanha uma frase comecando com "
        "'Yesterday I...' ou usando uma frase da aula.\n\n"
        "Ponto para guardar:\n"
        f"{review_text}\n\n"
        "Proximo passo:\n"
        f"{next_hook}\n\n"
        "Boa aula. Pequeno passo, mas passo real.\n\n"
        "De 0 a 10, quanto essa aula te ajudou hoje?\n\n"
        "Se preferir, toque em uma opcao para seguir agora:"
    )

    return {"type": "buttons", "body": body, "buttons": [
        {"id": "post_lesson:review", "title": "Revisar"},
        {"id": "post_lesson:practice", "title": "Praticar conversa"},
        {"id": "post_lesson:next_preview", "title": "Ver proxima"},
    ]}


def get_next_lesson_for_preview(student: StudentDB):
    current_lesson = get_current_lesson(student)

    if is_lesson_completed(student):
        return current_lesson

    return CURRICULUM_BY_NUMBER.get(current_lesson["number"] + 1)


def build_next_lesson_preview(
    student: StudentDB,
    db: Session,
    closing_hook: bool = False,
):
    next_lesson = get_next_lesson_for_preview(student)

    if not next_lesson:
        return (
            "Voce chegou ao final da trilha atual. O proximo passo sera uma revisao personalizada."
        )

    design = get_lesson_design(next_lesson)
    language = normalize_language_preference(student.preferred_language)
    response_language = "English" if language == "English" else "Portuguese"
    interests = getattr(student, "interests", None) or "not informed"

    try:
        client = get_openai_client()
        response = call_with_retry(client.chat.completions.create, operation="chat_completion",
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"Write a short preview in {response_language} for the student's next English lesson. "
                        "Explain the theme, what the student will learn, and one practical situation where it helps. "
                        "Finish with a curiosity hook that creates interest, but do not start teaching the lesson. "
                        "Use 45 to 70 words, no labels, no exercise, and no question requiring an answer."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Lesson: {next_lesson['title']}\n"
                        f"Focus: {next_lesson['focus']}\n"
                        f"Objective: {design['objective']}\n"
                        f"Can do: {design['can_do']}\n"
                        f"Student goal: {student.learning_goal}\n"
                        f"Student interests: {interests}\n"
                        f"This is an end-of-lesson hook: {closing_hook}"
                    ),
                },
            ],
        )
        preview = response.choices[0].message.content.strip()
    except Exception as error:
        print("Erro ao gerar previa da proxima aula:", error)
        if response_language == "English":
            preview = (
                f"Next lesson: {next_lesson['title']}. We will explore {next_lesson['focus'].lower()} "
                "and use it in a practical conversation. There is one useful pattern waiting for you."
            )
        else:
            preview = (
                f"Na proxima aula, vamos estudar {next_lesson['title']}. "
                "Voce vai entender o tema em uma situacao pratica e descobrir um novo padrao para conversar melhor."
            )

    heading = "Next lesson" if response_language == "English" else "Proxima aula"
    return f"{heading}: {next_lesson['title']}\n\n{preview}"


def save_lesson_feedback_if_expected(student: StudentDB, message: str, db: Session):
    session = get_latest_completed_lesson_session(student, db)

    if not session or session.feedback_rating is not None:
        return None

    match = re.search(r"\b(10|[0-9])\b", message or "")

    if not match:
        return None

    rating = int(match.group(1))
    session.feedback_rating = rating
    session.feedback_text = message
    student.xp = (student.xp or 0) + 5
    db.commit()

    if rating >= 8:
        return "Obrigado pelo feedback. Fico feliz que a aula ajudou. Amanha continuamos no seu ritmo."

    return (
        "Obrigado por ser sincero. Vou usar isso para deixar a proxima aula mais clara e mais pratica.\n\n"
        "Se quiser, me diga em uma frase o que posso melhorar."
    )


def mark_lesson_completed(student: StudentDB, db: Session = None):
    if db:
        complete_active_lesson_session(student, db)

    if (student.current_lesson or 1) < 70:
        student.current_lesson = (student.current_lesson or 1) + 1

    student.lesson_stage = LESSON_COMPLETED_STAGE
    student.messages_in_current_lesson = 0


def reset_lesson_flow(student: StudentDB):
    student.lesson_stage = "context_question"
    student.messages_in_current_lesson = 0


def update_lesson_engagement(student: StudentDB, db: Session = None):
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
        mark_lesson_completed(student, db)
        return

    if (student.messages_in_current_lesson or 0) >= 1:
        advance_lesson_stage(student)


def get_recent_relevant_lesson_answer(student: StudentDB, db: Session):
    conversations = (
        db.query(ConversationDB)
        .filter(ConversationDB.student_id == student.id)
        .order_by(ConversationDB.id.desc())
        .limit(12)
        .all()
    )

    fallback = None

    for conversation in conversations:
        candidate = (conversation.question or "").strip()

        if not candidate or is_lesson_start_request(candidate):
            continue

        if is_lesson_schedule_question(candidate) or is_schedule_change_request(candidate):
            continue

        if normalize_intent_text(candidate) in {"sim", "nao", "ok", "okay", "agora"}:
            continue

        if looks_like_english_message(candidate):
            return candidate

        if fallback is None:
            fallback = candidate

    return fallback


def save_guided_exchange(student: StudentDB, question: str, answer: str, db: Session):
    db.add(
        ConversationDB(
            student_id=student.id,
            question=question,
            answer=answer,
        )
    )
    db.commit()


def get_quiz_interface_language(student: StudentDB, message: str = ""):
    if is_basic_level(getattr(student, "level", None)):
        return "pt"

    preference = normalize_language_preference(student.preferred_language)
    if preference == "English":
        return "en"
    return "pt"


def build_past_simple_work_quiz(prefix: str = "", language: str = "en"):
    instruction = "Complete the sentence:" if language == "en" else "Complete a frase:"
    body = (
        f"{prefix}\n\n" if prefix else ""
    ) + f"{instruction}\n\nYesterday, I ___ on a project."
    return {
        "type": "buttons",
        "body": body,
        "buttons": [
            {"id": f"quiz:past_work_{language}:wrong:work", "title": "work"},
            {"id": f"quiz:past_work_{language}:correct:worked", "title": "worked"},
            {"id": f"quiz:past_work_{language}:wrong:working", "title": "working"},
        ],
    }


def build_past_simple_travel_quiz(prefix: str = "", language: str = "en"):
    instruction = "Complete the sentence:" if language == "en" else "Complete a frase:"
    body = (
        f"{prefix}\n\n" if prefix else ""
    ) + f"{instruction}\n\nLast summer, I ___ to the beach."
    return {
        "type": "buttons",
        "body": body,
        "buttons": [
            {"id": f"quiz:past_travel_{language}:wrong:travel", "title": "travel"},
            {"id": f"quiz:past_travel_{language}:correct:traveled", "title": "traveled"},
            {"id": f"quiz:past_travel_{language}:wrong:traveling", "title": "traveling"},
        ],
    }


def build_past_simple_cook_quiz(prefix: str = "", language: str = "en"):
    instruction = "Complete the sentence:" if language == "en" else "Complete a frase:"
    body = (
        f"{prefix}\n\n" if prefix else ""
    ) + f"{instruction}\n\nHe ___ dinner yesterday."
    return {
        "type": "buttons",
        "body": body,
        "buttons": [
            {"id": f"quiz:past_cook_{language}:correct:cooked", "title": "cooked"},
            {"id": f"quiz:past_cook_{language}:wrong:cook", "title": "cook"},
            {"id": f"quiz:past_cook_{language}:wrong:cooking", "title": "cooking"},
        ],
    }


def build_past_simple_finish_quiz(prefix: str = "", language: str = "en"):
    instruction = "Complete the sentence:" if language == "en" else "Complete a frase:"
    body = (f"{prefix}\n\n" if prefix else "") + f"{instruction}\n\nThey ___ their homework last night."
    return {
        "type": "buttons",
        "body": body,
        "buttons": [
            {"id": f"quiz:past_finish_{language}:wrong:finish", "title": "finish"},
            {"id": f"quiz:past_finish_{language}:correct:finished", "title": "finished"},
            {"id": f"quiz:past_finish_{language}:wrong:finishing", "title": "finishing"},
        ],
    }


def build_past_simple_watch_quiz(prefix: str = "", language: str = "en"):
    instruction = "Complete the sentence:" if language == "en" else "Complete a frase:"
    body = (f"{prefix}\n\n" if prefix else "") + f"{instruction}\n\nWe ___ a movie yesterday."
    return {
        "type": "buttons",
        "body": body,
        "buttons": [
            {"id": f"quiz:past_watch_{language}:wrong:watch", "title": "watch"},
            {"id": f"quiz:past_watch_{language}:correct:watched", "title": "watched"},
            {"id": f"quiz:past_watch_{language}:wrong:watching", "title": "watching"},
        ],
    }


def build_past_simple_play_quiz(prefix: str = "", language: str = "en"):
    instruction = "Complete the sentence:" if language == "en" else "Complete a frase:"
    body = (f"{prefix}\n\n" if prefix else "") + f"{instruction}\n\nShe ___ soccer on Saturday."
    return {
        "type": "buttons",
        "body": body,
        "buttons": [
            {"id": f"quiz:past_play_{language}:wrong:play", "title": "play"},
            {"id": f"quiz:past_play_{language}:correct:played", "title": "played"},
            {"id": f"quiz:past_play_{language}:wrong:playing", "title": "playing"},
        ],
    }


def build_practice_mode_choice(language: str = "pt"):
    if language == "en":
        body = "We have completed a good number of quizzes. Would you like to practice writing now?"
        writing_title = "Practice writing"
        quiz_title = "More quizzes"
        topic_title = "Choose a topic"
    else:
        body = "Ja fizemos uma quantidade significativa de quizzes. Vamos praticar escrita agora?"
        writing_title = "Praticar escrita"
        quiz_title = "Mais quizzes"
        topic_title = "Escolher tema"

    return {
        "type": "buttons",
        "body": body,
        "buttons": [
            {"id": f"practice:writing:{language}", "title": writing_title},
            {"id": f"practice:more_quiz:{language}", "title": quiz_title},
            {"id": f"practice:choose_topic:{language}", "title": topic_title},
        ],
    }


def parse_practice_button_message(message: str):
    match = re.fullmatch(
        r"__button__:practice:(writing|more_quiz|choose_topic):(pt|en)::(.+)",
        message or "",
        flags=re.DOTALL,
    )
    if not match:
        return None
    return {"choice": match.group(1), "language": match.group(2)}


def parse_quiz_button_message(message: str):
    match = re.fullmatch(
        r"__button__:(quiz:[^:]+:(?:correct|wrong):[^:]+)::(.+)",
        message or "",
        flags=re.DOTALL,
    )

    if not match:
        return None

    button_id = match.group(1)
    title = match.group(2).strip()
    parts = button_id.split(":", 3)
    return {
        "quiz_id": parts[1],
        "is_correct": parts[2] == "correct",
        "value": parts[3],
        "title": title,
    }


def build_quiz_retry(quiz_id: str):
    language = "pt" if quiz_id.endswith("_pt") else "en"
    base_quiz_id = re.sub(r"_(?:pt|en)$", "", quiz_id)

    if base_quiz_id == "past_work":
        return build_past_simple_work_quiz(
            (
                "Not quite. We need the Past Simple because the action happened yesterday. Try again."
                if language == "en"
                else "Quase. Precisamos do Past Simple porque a acao aconteceu ontem. Tente novamente."
            ),
            language,
        )

    if base_quiz_id == "past_travel":
        return build_past_simple_travel_quiz(
            (
                "Not quite. 'Last summer' shows a finished time in the past. Try again."
                if language == "en"
                else "Quase. 'Last summer' indica um momento concluido no passado. Tente novamente."
            ),
            language,
        )

    if base_quiz_id == "past_cook":
        return build_past_simple_cook_quiz(
            (
                "Not quite. 'Yesterday' asks for the Past Simple. Try again."
                if language == "en"
                else "Quase. 'Yesterday' pede o Past Simple. Tente novamente."
            ),
            language,
        )

    if base_quiz_id == "past_finish":
        return build_past_simple_finish_quiz(
            "Not quite. 'Last night' asks for the Past Simple. Try again."
            if language == "en"
            else "Quase. 'Last night' pede o Past Simple. Tente novamente.",
            language,
        )

    if base_quiz_id == "past_watch":
        return build_past_simple_watch_quiz(
            "Not quite. The action finished yesterday. Try again."
            if language == "en"
            else "Quase. A acao terminou ontem. Tente novamente.",
            language,
        )

    if base_quiz_id == "past_play":
        return build_past_simple_play_quiz(
            "Not quite. Saturday is a finished past time here. Try again."
            if language == "en"
            else "Quase. Aqui, Saturday indica um momento concluido no passado. Tente novamente.",
            language,
        )

    return None


def build_quiz_correct_reply(quiz_id: str, student: StudentDB, db: Session):
    language = "pt" if quiz_id.endswith("_pt") else "en"
    base_quiz_id = re.sub(r"_(?:pt|en)$", "", quiz_id)
    student.xp = (student.xp or 0) + 2
    db.commit()

    if base_quiz_id == "past_work":
        return [
            (
                "Correct! Work is a regular verb: work -> worked."
                if language == "en"
                else "Correto! Work e um verbo regular: work -> worked."
            ),
            build_past_simple_travel_quiz(
                "Question 2 of 3" if language == "en" else "Pergunta 2 de 3",
                language,
            ),
        ]

    if base_quiz_id == "past_travel":
        return [
            (
                "Correct! Travel is regular: travel -> traveled."
                if language == "en"
                else "Correto! Travel e regular: travel -> traveled."
            ),
            build_past_simple_cook_quiz(
                "Question 3 of 3" if language == "en" else "Pergunta 3 de 3",
                language,
            ),
        ]

    if base_quiz_id == "past_cook":
        return [
            "Correct! Cook becomes cooked in the Past Simple."
            if language == "en"
            else "Correto! Cook se transforma em cooked no Past Simple.",
            build_practice_mode_choice(language),
        ]

    if base_quiz_id == "past_finish":
        return [
            "Correct! Finish becomes finished."
            if language == "en"
            else "Correto! Finish se transforma em finished.",
            build_past_simple_watch_quiz(
                "Question 2 of 3" if language == "en" else "Pergunta 2 de 3",
                language,
            ),
        ]

    if base_quiz_id == "past_watch":
        return [
            "Correct! Watch becomes watched."
            if language == "en"
            else "Correto! Watch se transforma em watched.",
            build_past_simple_play_quiz(
                "Question 3 of 3" if language == "en" else "Pergunta 3 de 3",
                language,
            ),
        ]

    if base_quiz_id == "past_play":
        return [
            "Correct! Play becomes played."
            if language == "en"
            else "Correto! Play se transforma em played.",
            build_practice_mode_choice(language),
        ]

    return "Correct!"


def generate_writing_practice_feedback(student: StudentDB, message: str, db: Session):
    language = normalize_language_preference(student.preferred_language)
    response_language = "English" if language == "English" else "Portuguese"
    client = get_openai_client()
    response = call_with_retry(client.chat.completions.create, operation="chat_completion",
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are WINGO correcting a short Past Simple writing exercise. "
                    f"Reply in {response_language}. First show the corrected English sentence, "
                    "then explain one important correction briefly, and ask for one new Past Simple "
                    "sentence about yesterday. Do not change topics and do not use multiple choice."
                ),
            },
            {"role": "user", "content": message},
        ],
    )
    answer = response.choices[0].message.content.strip()
    save_guided_exchange(student, message, answer, db)
    return answer


def has_recent_past_simple_context(student: StudentDB, message: str, db: Session):
    text = normalize_intent_text(message)

    if "past simple" in text or "simple past" in text or "passado simples" in text:
        return True

    if get_current_lesson(student)["title"] == "Past Simple":
        return True

    recent = (
        db.query(ConversationDB)
        .filter(ConversationDB.student_id == student.id)
        .order_by(ConversationDB.id.desc())
        .limit(4)
        .all()
    )
    recent_text = " ".join(
        f"{item.question or ''} {item.answer or ''}"
        for item in recent
    )
    normalized_recent = normalize_intent_text(recent_text)
    return any(
        marker in normalized_recent
        for marker in ["past simple", "simple past", "passado simples"]
    )


def build_deterministic_guided_reply(student: StudentDB, answer: str, db: Session):
    lesson = get_current_lesson(student)
    stage = get_lesson_stage(student)

    if lesson["title"] != "Past Simple" or stage != "short_explanation":
        return None

    language = normalize_language_preference(student.preferred_language)

    if language == "English":
        explanation = (
            f"Great! \"{answer.strip()}\" is a correct Past Simple sentence.\n\n"
            "Studied is the past form of study. Because study ends in consonant + y, "
            "we change y to i and add -ed:\n\n"
            "study -> studied\n\n"
            "We use the Past Simple for finished actions."
        )
        reply = build_past_simple_work_quiz(explanation, "en")
    else:
        explanation = (
            f"Muito bem! \"{answer.strip()}\" e uma frase correta no Past Simple.\n\n"
            "Studied e o passado de study. Como study termina em consoante + y, "
            "trocamos y por i e acrescentamos -ed:\n\n"
            "study -> studied\n\n"
            "Usamos o Past Simple para acoes que ja terminaram."
        )
        reply = build_past_simple_work_quiz(explanation, "pt")

    save_guided_exchange(student, answer, reply["body"], db)
    return reply


def resume_stuck_guided_lesson(student: StudentDB, message: str, db: Session):
    active_session = get_active_lesson_session(student, db)

    if not active_session:
        return None

    previous_answer = get_recent_relevant_lesson_answer(student, db)
    student.current_stage = 7

    if is_lesson_completed(student):
        student.lesson_stage = "short_explanation" if previous_answer else "context_question"
        student.messages_in_current_lesson = 1 if previous_answer else 0
    elif previous_answer and get_lesson_stage(student) == "context_question":
        student.lesson_stage = "short_explanation"
        student.messages_in_current_lesson = max(
            student.messages_in_current_lesson or 0,
            1,
        )

    db.commit()

    if not previous_answer:
        return build_lesson_opening_replies(student, db)

    deterministic_reply = build_deterministic_guided_reply(
        student,
        previous_answer,
        db,
    )

    if deterministic_reply:
        return deterministic_reply

    lesson = get_current_lesson(student)
    return generate_ai_answer(
        student=student,
        question=message,
        db=db,
        ai_question=(
            "[Internal instruction: recover the active guided lesson now. "
            f"The current topic is {lesson['title']}. "
            f"The student's last relevant lesson answer was: {previous_answer!r}. "
            "Use that exact answer as the bridge: acknowledge or correct it, explain the next small point, "
            "and ask exactly one exercise from the current structured lesson. "
            "Do not discuss the answer's subject as free chat. Do not enter BOT mode. "
            "Follow the student's stored language preference.]"
        )
    )

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
        " like ", " have ", " study ", " studied ", " worked ", " played ",
        " yesterday ", " don't ", " dont ", " english ", " hello ", " hi ",
        "good morning", "good afternoon", "good evening", "where are",
        "what is", "what's", "from brazil"
    ]

    padded_text = f" {text} "

    return any(marker in padded_text for marker in english_markers)


def is_mixed_language_message(message: str):
    normalized = normalize_intent_text(message)
    tokens = set(re.findall(r"[a-z']+", normalized))

    if len(tokens) < 2:
        return False

    portuguese_tokens = {
        "eu", "voce", "nao", "sim", "ontem", "hoje", "amanha", "estou",
        "sou", "fui", "era", "estudei", "trabalhei", "joguei", "gosto",
        "quero", "tenho", "fiz", "com", "para", "porque", "mas", "meu",
        "minha", "uma", "um", "aula", "ingles", "aprendendo",
    }
    english_tokens = {
        "i", "you", "he", "she", "we", "they", "am", "is", "are", "was",
        "were", "did", "do", "studied", "study", "worked", "work", "played",
        "play", "went", "go", "like", "want", "have", "yesterday", "today",
        "tomorrow", "english", "learning", "learn", "my", "the", "a", "an",
    }

    return bool(tokens & portuguese_tokens) and bool(tokens & english_tokens)


def can_offer_full_english_mode(student):
    return (student.level or "").strip() in {"Advanced", "Fluent"}


def is_basic_level(level: str | None):
    normalized = (level or "").strip().lower()
    return normalized == "basic" or "basic 2" in normalized or "a1" in normalized


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
    abbreviations = {
        "vc": "voce",
        "vcs": "voces",
        "q": "que",
        "qdo": "quando",
        "qnd": "quando",
        "qro": "quero",
        "qr": "quero",
        "n": "nao",
        "nn": "nao",
        "naum": "nao",
        "blz": "beleza",
        "tb": "tambem",
        "tbm": "tambem",
        "pq": "porque",
        "pqe": "porque",
        "pf": "por favor",
        "pfv": "por favor",
        "hj": "hoje",
        "agr": "agora",
        "dps": "depois",
        "cmg": "comigo",
    }
    text = re.sub(
        r"\b[a-z0-9]+\b",
        lambda match: abbreviations.get(match.group(0), match.group(0)),
        text,
    )
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

    response = call_with_retry(client.chat.completions.create, operation="chat_completion",
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": f"""
You are an English placement test evaluator.

Analyze the student's onboarding notes and placement test answers.
The student may answer in Portuguese, English, or a mix.
If the student reports having no English contact or only knows isolated words, return Basic.
Do not punish the student for answering in Portuguese; infer level from evidence of English ability.

Use this rubric:
{get_placement_rubric_text()}

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

    response = call_with_retry(client.chat.completions.create, operation="chat_completion",
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": f"""
You are an English placement test evaluator.

Analyze the student's onboarding notes and placement test answers.
The student may answer in Portuguese, English, or a mix.
If the student reports having no English contact or only knows isolated words, return Basic.

Use this rubric:
{get_placement_rubric_text()}

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

def get_meta_whatsapp_config():
    phone_number_id = os.getenv("META_PHONE_NUMBER_ID")
    access_token = os.getenv("META_ACCESS_TOKEN")

    if not phone_number_id or not access_token:
        raise HTTPException(
            status_code=500,
            detail="META_PHONE_NUMBER_ID ou META_ACCESS_TOKEN nao configurado no .env"
        )

    return phone_number_id, access_token


def polish_portuguese_text(value: str) -> str:
    text = str(value or "")
    normalized = f" {normalize_intent_text(text)} "
    portuguese_markers = (
        " voce ", " voces ", " nao ", " portugues ", " ingles ", " aula ",
        " vamos ", " quero ", " qual ", " obrigado ", " obrigada ",
        " praticar ", " exercicio ", " exercicios ", " nivel ", " horario ",
        " pronuncia ", " otimo ", " otima ", " proximo ", " proxima ",
    )
    if not any(marker in normalized for marker in portuguese_markers):
        return text

    replacements = {
        "voce": "você",
        "voces": "vocês",
        "nao": "não",
        "portugues": "português",
        "ingles": "inglês",
        "audio": "áudio",
        "pronuncia": "pronúncia",
        "nivel": "nível",
        "niveis": "níveis",
        "horario": "horário",
        "horarios": "horários",
        "otimo": "ótimo",
        "otima": "ótima",
        "proximo": "próximo",
        "proxima": "próxima",
        "avaliacao": "avaliação",
        "correcao": "correção",
        "exercicio": "exercício",
        "exercicios": "exercícios",
        "facil": "fácil",
        "dificil": "difícil",
        "tambem": "também",
        "amanha": "amanhã",
        "acao": "ação",
        "acoes": "ações",
        "licao": "lição",
        "basico": "básico",
        "basicos": "básicos",
        "rapida": "rápida",
        "concluido": "concluído",
        "sera": "será",
    }
    pattern = re.compile(
        r"\b(" + "|".join(sorted(replacements, key=len, reverse=True)) + r")\b",
        flags=re.IGNORECASE,
    )

    def replace(match):
        original = match.group(0)
        replacement = replacements[original.lower()]
        if original.isupper():
            return replacement.upper()
        if original[:1].isupper():
            return replacement[:1].upper() + replacement[1:]
        return replacement

    return pattern.sub(replace, text)


def send_whatsapp_message(phone: str, text: str):
    phone_number_id, access_token = get_meta_whatsapp_config()
    recipient_phone = normalize_whatsapp_phone_for_send(phone)

    url = f"https://graph.facebook.com/v23.0/{phone_number_id}/messages"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    text = polish_portuguese_text(text)
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_phone,
        "type": "text",
        "text": {
            "body": text
        }
    }

    response = http_post_with_retry(
        url,
        headers=headers,
        json=payload,
        timeout=20
    )

    if response.status_code >= 400:
        print("Erro ao enviar mensagem pela Meta:", response.text)
        print("Destinatario da Meta:", mask_phone(recipient_phone))

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


def send_whatsapp_buttons(phone: str, body: str, buttons: list[dict]):
    phone_number_id, access_token = get_meta_whatsapp_config()
    recipient_phone = normalize_whatsapp_phone_for_send(phone)
    url = f"https://graph.facebook.com/v23.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    body = polish_portuguese_text(body)
    visible_buttons = [
        {**button, "title": polish_portuguese_text(str(button["title"]))}
        for button in buttons
    ]
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_phone,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body[:1024]},
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {
                            "id": str(button["id"])[:256],
                            "title": str(button["title"])[:20],
                        },
                    }
                    for button in visible_buttons[:3]
                ]
            },
        },
    }
    response = http_post_with_retry(
        url,
        headers=headers,
        json=payload,
        timeout=20,
    )

    if response.status_code >= 400:
        print("Erro ao enviar botoes pela Meta:", response.text)
        try:
            meta_error = response.json().get("error", {})
            error_message = meta_error.get("message", "Erro desconhecido da Meta")
            error_code = meta_error.get("code", response.status_code)
        except ValueError:
            error_message = response.text
            error_code = response.status_code

        raise HTTPException(
            status_code=502,
            detail=f"Erro ao enviar botoes pelo WhatsApp Cloud API: {error_code} - {error_message}",
        )

    return response.json()


def send_whatsapp_typing_indicator(message_id: str):
    phone_number_id, access_token = get_meta_whatsapp_config()
    url = f"https://graph.facebook.com/v23.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
        "typing_indicator": {"type": "text"},
    }

    response = http_post_with_retry(
        url,
        headers=headers,
        json=payload,
        timeout=8,
        operation="meta_typing_indicator",
        attempts=1,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Meta typing indicator failed: {response.status_code}")

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
        "caption": polish_portuguese_text(caption)
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

    response = http_post_with_retry(
        url,
        headers=headers,
        json=payload,
        timeout=20
    )

    if response.status_code >= 400:
        print("Erro ao enviar video pela Meta:", response.text)
        print("Destinatario da Meta:", mask_phone(recipient_phone))

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
        return send_whatsapp_video(
            phone=phone,
            caption=reply.get("caption", ""),
            media_id=reply.get("media_id"),
            link=reply.get("link")
        )

    if isinstance(reply, dict) and reply.get("type") == "buttons":
        return send_whatsapp_buttons(
            phone=phone,
            body=reply.get("body", ""),
            buttons=reply.get("buttons", []),
        )

    return send_whatsapp_message(phone, str(reply))


def get_reply_text(reply):
    if isinstance(reply, dict):
        return polish_portuguese_text(reply.get("caption") or reply.get("body", ""))

    return polish_portuguese_text(str(reply))


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
        response = http_post_with_retry(
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

    response = http_post_with_retry(
        url,
        headers=headers,
        json=payload,
        timeout=20
    )

    if response.status_code >= 400:
        print("Erro ao enviar audio pela Meta:", response.text)
        print("Destinatario da Meta:", mask_phone(recipient_phone))
        raise HTTPException(
            status_code=502,
            detail="Erro ao enviar audio pelo WhatsApp Cloud API"
        )

    return response.json()


def should_send_pronunciation_audio(question: str, answer: str):
    text = normalize_intent_text(question)
    answer_text = normalize_intent_text(answer)

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
        "audio de novo",
        "audio novamente",
        "repete o audio",
        "repetir o audio",
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

    response = call_with_retry(client.chat.completions.create, operation="chat_completion",
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
    speech = call_with_retry(client.audio.speech.create, operation="text_to_speech",
        model=os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts"),
        voice=os.getenv("OPENAI_TTS_VOICE", "alloy"),
        input=text,
        response_format="mp3",
    )

    audio_path = Path(tempfile.gettempdir()) / f"whatsup_audio_{os.urandom(8).hex()}.mp3"
    speech.write_to_file(audio_path)

    return audio_path


def send_pronunciation_audio_if_needed(
    phone: str,
    question: str,
    answer: str,
    student: StudentDB = None,
    db: Session = None
):
    try:
        audio_text = build_pronunciation_audio_text(question, answer)
    except Exception as error:
        print("Erro ao preparar audio do professor:", error)
        return

    if not audio_text:
        return

    try:
        audio_path = generate_pronunciation_audio_file(audio_text)
    except Exception as error:
        print("Erro ao gerar audio do professor:", error)
        return

    try:
        media_id = upload_whatsapp_media(audio_path, "audio/mpeg")
        send_whatsapp_audio(phone, media_id)

        if student and db:
            session = get_active_lesson_session(student, db) or get_latest_lesson_session(student, db)

            if session:
                session.teacher_audio_sent = "Yes"
                db.commit()
    except Exception as error:
        if db:
            db.rollback()
        print("Erro ao enviar audio do professor:", error)
    finally:
        try:
            audio_path.unlink(missing_ok=True)
        except OSError:
            pass


def mark_student_audio_request_if_needed(student: StudentDB, answer: str, db: Session):
    if not student or not db:
        return

    answer_text = normalize_intent_text(answer or "")
    audio_terms = (
        "audio",
        "voice note",
        "nota de voz",
        "grave",
        "gravar",
        "manda uma mensagem de voz",
        "mande uma mensagem de voz",
    )

    if not any(term in answer_text for term in audio_terms):
        return

    session = get_active_lesson_session(student, db) or get_latest_lesson_session(student, db)

    if not session:
        return

    session.student_audio_requested = "Yes"
    db.commit()


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

    response = http_get_with_retry(
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

    response = http_get_with_retry(
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
        transcript = call_with_retry(client.audio.transcriptions.create, operation="transcription",
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


def get_expected_pronunciation_reference(student: StudentDB, db: Session):
    session = get_active_lesson_session(student, db) or get_latest_lesson_session(student, db)
    if not session or session.student_audio_requested != "Yes":
        return None, session

    conversations = (
        db.query(ConversationDB)
        .filter(ConversationDB.student_id == student.id)
        .order_by(ConversationDB.id.desc())
        .limit(8)
        .all()
    )
    for conversation in conversations:
        reference_text = extract_reference_text(conversation.answer)
        if reference_text:
            return reference_text, session
    return None, session


def evaluate_expected_pronunciation(
    student: StudentDB,
    audio_path: Path,
    transcript: str,
    message_id: str | None,
    db: Session,
):
    if message_id:
        existing = db.query(PronunciationAttemptDB).filter(
            PronunciationAttemptDB.message_id == message_id
        ).first()
        if existing:
            return existing.feedback

    reference_text, session = get_expected_pronunciation_reference(student, db)
    if not reference_text:
        return None

    try:
        result = assess_pronunciation(audio_path, reference_text)
        error = None
    except Exception as assessment_error:
        log_event(
            "pronunciation_assessment_failed",
            student_id=student.id,
            message_id=message_id,
            error=str(assessment_error),
        )
        result = {
            "provider": "azure",
            "status": "acoustic_error",
            "accuracy_score": None,
            "fluency_score": None,
            "completeness_score": None,
            "prosody_score": None,
            "pronunciation_score": None,
            "words": [],
        }
        error = str(assessment_error)[:1000]

    feedback = build_pronunciation_feedback(result, reference_text, transcript)
    db.add(
        PronunciationAttemptDB(
            student_id=student.id,
            message_id=message_id,
            provider=result.get("provider"),
            status=result.get("status"),
            reference_text=reference_text,
            transcript=transcript,
            accuracy_score=result.get("accuracy_score"),
            fluency_score=result.get("fluency_score"),
            completeness_score=result.get("completeness_score"),
            prosody_score=result.get("prosody_score"),
            pronunciation_score=result.get("pronunciation_score"),
            word_details=json.dumps(result.get("words") or [], ensure_ascii=False),
            feedback=feedback,
            error=error,
        )
    )
    if session:
        session.student_audio_requested = "No"
    db.commit()
    return feedback


def normalize_language_preference(value: str):
    text = (value or "").strip().lower()

    if text in {"2", "english", "ingles", "inglês"} or "engl" in text or "ingl" in text:
        return "English"

    if text in {"1", "portuguese", "portugues", "português"} or "port" in text:
        return "Portuguese"

    return "Adaptive"


def get_language_instruction(language: str, level: str = "Basic"):
    if is_basic_level(level):
        return (
            "Always write instructions, explanations, questions, corrections, and feedback in Portuguese. "
            "Use English only for the exact word, phrase, example, or exercise the student is practicing. "
            "Immediately explain unfamiliar English in Portuguese. Never switch the conversation to English "
            "just because the student answered in English or requested English-only mode."
        )

    if language == "English":
        return (
            "The student explicitly requested English. Reply primarily in English, but switch "
            "to Portuguese if the student asks for clarification or seems completely stuck."
        )

    return (
        "Use Portuguese for all instructions, explanations, questions, corrections, and feedback. "
        "Use English only inside the exact examples and exercises being practiced. Do not switch "
        "the conversation to English merely because the student wrote an English sentence. Only "
        "conduct the conversation in English after an explicit language request."
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
    match = re.search(
        r"\b(\d{1,2})(?:(?::|h)(\d{2})?)?(?:\s*horas?)?\b",
        (value or "").lower()
    )

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

        if len(slots) == 7:
            break

    if not slots:
        daily_time = parse_clock_time(text) or parse_day_period_time(text)

        if daily_time:
            return [
                {"day": day_index, "time": daily_time}
                for day_index in range(7)
            ]

    return slots


def format_lesson_schedule(slots):
    if len(slots) == 7:
        times = {slot.get("time") for slot in slots}
        days = {slot.get("day") for slot in slots}
        if len(times) == 1 and days == set(range(7)):
            return f"todos os dias as {next(iter(times))}"

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


def build_scheduled_lesson_invitation(student: StudentDB, db: Session, now: datetime):
    if now.hour < 12:
        greeting = "Bom dia"
    elif now.hour < 18:
        greeting = "Boa tarde"
    else:
        greeting = "Boa noite"

    lesson = get_current_lesson(student)
    first_name = (student.name or "").strip().split(" ")[0]
    name_suffix = f", {first_name}" if first_name else ""
    previous_session = get_latest_completed_lesson_session(student, db)
    review_note = ""

    if previous_session:
        review_note = (
            f" Antes de comecar {format_lesson_title(lesson)}, "
            f"vamos fazer uma revisao rapida de {previous_session.lesson_title}."
        )

    return (
        f"{greeting}{name_suffix}! Chegou o horario da nossa aula de hoje.\n\n"
        f"Voce esta pronto e disponivel para comecar agora?{review_note}"
    )


def build_previous_lesson_review(student: StudentDB, db: Session):
    previous_session = get_latest_completed_lesson_session(student, db)

    if not previous_session:
        return "Esta e nossa primeira aula guiada, entao vamos direto ao ponto de hoje."

    records = get_recent_learning_records(student.id, db, limit=2)
    review_items = []

    for record in records:
        if record.corrected_text:
            review_items.append(f"- {record.corrected_text[:100]}")

    if not review_items:
        review_items.append(f"- Tema anterior: {previous_session.lesson_title}")

    return (
        "Antes, uma revisao bem rapida da ultima aula:\n"
        + "\n".join(review_items)
        + "\n\nEscolha uma dessas frases e me diga o que ela significa."
    )


def build_lesson_opening_replies(student: StudentDB, db: Session):
    lesson = get_current_lesson(student)
    lesson_video = build_lesson_intro_video_reply(student)
    replies = []

    if lesson_video:
        replies.append(lesson_video)

    if lesson["title"] == "Greetings":
        replies.append("Hoje vamos aprender cumprimentos. Como voce diria 'Ola' em ingles?")
    else:
        replies.append(generate_weekly_lesson(student, db))

    return replies


def start_guided_lesson(student: StudentDB, db: Session, mode: str):
    if has_started_lesson_today(student):
        return (
            "Por hoje ja fizemos uma aula guiada.\n\n"
            "Mas posso revisar o conteudo, tirar uma duvida ou praticar uma frase com voce."
        )

    previous_session = get_latest_completed_lesson_session(student, db)
    reset_lesson_flow(student)
    mark_lesson_started_today(student)
    start_lesson_session(student, db, mode=mode)
    student.current_stage = 83 if previous_session else 7
    db.commit()

    if previous_session:
        return build_previous_lesson_review(student, db)
    return build_lesson_opening_replies(student, db)


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

    response = call_with_retry(client.chat.completions.create, operation="chat_completion",
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
    personal_memory = get_recent_personal_notes_summary(student.id, db)
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

Personal relationship memory:
{personal_memory}

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
- In guided_lesson mode, every student message is first an answer to the current exercise.
- Example: if the lesson asks what the student did yesterday and they answer "I studied Python", teach the Past Simple in that sentence. Never start a free conversation about Python.
- Do not ask what project, hobby, subject, movie, game, or activity the student means unless that question is explicitly the current lesson exercise.
- If an internal instruction says the student explicitly selected a practice topic, that topic has priority over the current lesson and recent history.
- Never redirect an explicit topic request back to Past Simple or another previous topic.
- For topic practice, inspect the recent conversation and use new verbs, situations, and example sentences. Do not recycle an earlier exercise unless the student is correcting it.

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
- Use personal relationship memory naturally and sparingly, like a tutor who remembers the student. Do not say you have a database or saved memory.
- If a saved personal event may have happened recently, you may ask one warm follow-up question, then return to the lesson.
- Do not repeatedly mention the same personal fact in every message.
- Every guided lesson should include at least one example or exercise connected to the student's interests, unless the student has not shared interests yet.
- If the student has no interests saved, ask one quick preference question after the current exercise, not before finishing the required lesson step.
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
- Ask for one short voice note near production or conversation stage, unless the student already sent audio in this lesson or seems confused.

Teaching style:
- Be warm, direct, and encouraging.
- Keep the conversation natural, like a private tutor on WhatsApp.
- Adapt vocabulary and grammar to the student's level.
- Prefer short messages, but grammar explanations may use 120 to 180 words when needed for clarity.
- Follow the language rule above even if the conversation history used another language.
- Correct mistakes politely.
- Always show a corrected version when the student makes a mistake.
- Invite the student to send audio only at the planned speaking moment or when the student asks for pronunciation help.
- If the user's message starts with "[Voice note transcription]", treat it as something the student spoke aloud. Correct the English naturally and encourage them to repeat the improved version.
- For voice notes, evaluate pronunciation only from available evidence: if the transcription is clear, say the audio was understandable; if the transcription seems incomplete, ask for a slower short repetition. Do not pretend to know exact phonetic details that were not measured.
- Voice-note feedback should mention: clarity, target phrase, rhythm/confidence, and one small improvement.
- Use the recent academic memory to review recurring mistakes naturally, but do not mention database records.
- When a student repeats an old mistake, briefly remind them of the corrected pattern.
- Ask one simple follow-up question to keep the student practicing.
- Do not overwhelm the student with long grammar theory.
- Understand common Brazilian chat abbreviations and informal writing, such as vc, vcs, q, qro, n, nn, blz, tbm, pq, pfv, hj, agr, and dps. Infer the intended meaning naturally instead of asking the student to write formally.
- Write every Portuguese word with correct accents and punctuation. Never imitate unaccented or abbreviated Portuguese in the tutor response.

Brand voice:
- You can occasionally use the slogan "Let's Bora!".
"""
        }
    ]

    if lesson_mode == "bot_after_lesson":
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

    response = call_with_retry(client.chat.completions.create, operation="chat_completion",
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

    save_personal_notes_if_needed(
        student=student,
        message=question,
        db=db,
        get_openai_client=get_openai_client,
        call_with_retry=call_with_retry,
    )

    return answer


api_dependencies = {
        "AssessmentRequest": AssessmentRequest,
        "CORRECTION_RUBRIC": CORRECTION_RUBRIC,
        "CURRICULUM": CURRICULUM,
        "CURRICULUM_BY_NUMBER": CURRICULUM_BY_NUMBER,
        "ChatRequest": ChatRequest,
        "Conversation": Conversation,
        "ConversationDB": ConversationDB,
        "DAILY_WORD_TIME": DAILY_WORD_TIME,
        "DASHBOARD_DIR": DASHBOARD_DIR,
        "FileResponse": FileResponse,
        "HTTPException": HTTPException,
        "LESSON_COMPLETED_STAGE": LESSON_COMPLETED_STAGE,
        "LESSON_STAGES": LESSON_STAGES,
        "LearningRecord": LearningRecord,
        "LearningRecordDB": LearningRecordDB,
        "LessonSessionDB": LessonSessionDB,
        "Login": Login,
        "OperationalMetricDB": OperationalMetricDB,
        "OutboundDeliveryDB": OutboundDeliveryDB,
        "PLACEMENT_RUBRIC": PLACEMENT_RUBRIC,
        "PRODUCT_PLANS": PRODUCT_PLANS,
        "PRONUNCIATION_RUBRIC": PRONUNCIATION_RUBRIC,
        "PersonalNoteDB": PersonalNoteDB,
        "ProcessedWebhookMessageDB": ProcessedWebhookMessageDB,
        "Progress": Progress,
        "ProgressDB": ProgressDB,
        "PronunciationAttemptDB": PronunciationAttemptDB,
        "QuizAnswer": QuizAnswer,
        "SALES_DIR": SALES_DIR,
        "SPACED_REVIEW_INTERVALS": SPACED_REVIEW_INTERVALS,
        "Session": Session,
        "StateTransitionDB": StateTransitionDB,
        "Student": Student,
        "StudentDB": StudentDB,
        "WEEKLY_QUIZ_DAY": WEEKLY_QUIZ_DAY,
        "WEEKLY_QUIZ_TIME": WEEKLY_QUIZ_TIME,
        "WEEKLY_REPORT_DAY": WEEKLY_REPORT_DAY,
        "WEEKLY_REPORT_TIME": WEEKLY_REPORT_TIME,
        "add_onboarding_note": add_onboarding_note,
        "bcrypt": bcrypt,
        "build_deterministic_guided_reply": build_deterministic_guided_reply,
        "build_intro_video_reply": build_intro_video_reply,
        "build_lesson_opening_replies": build_lesson_opening_replies,
        "build_next_lesson_preview": build_next_lesson_preview,
        "build_past_simple_finish_quiz": build_past_simple_finish_quiz,
        "build_past_simple_work_quiz": build_past_simple_work_quiz,
        "build_post_lesson_feedback_message": build_post_lesson_feedback_message,
        "build_quiz_correct_reply": build_quiz_correct_reply,
        "build_quiz_retry": build_quiz_retry,
        "build_weekly_progress_report": build_weekly_progress_report,
        "calculate_learning_xp": calculate_learning_xp,
        "call_with_retry": lambda: call_with_retry,
        "create_access_token": create_access_token,
        "datetime": datetime,
        "detect_control_command": detect_control_command,
        "detect_language_switch_request": detect_language_switch_request,
        "detect_requested_level_change": detect_requested_level_change,
        "estimate_level_from_study_history": estimate_level_from_study_history,
        "evaluate_placement_test_details": lambda: evaluate_placement_test_details,
        "evaluate_placement_test_details_fallback": evaluate_placement_test_details_fallback,
        "extract_english_phrases_for_audio": extract_english_phrases_for_audio,
        "extract_name_candidate": extract_name_candidate,
        "format_lesson_schedule": format_lesson_schedule,
        "format_lesson_title": format_lesson_title,
        "format_placement_feedback": format_placement_feedback,
        "func": func,
        "generate_ai_answer": lambda: generate_ai_answer,
        "generate_writing_practice_feedback": generate_writing_practice_feedback,
        "get_advancement_criterion": get_advancement_criterion,
        "get_current_lesson": get_current_lesson,
        "get_latest_lesson_session": get_latest_lesson_session,
        "get_lesson_design": get_lesson_design,
        "get_lesson_stage": get_lesson_stage,
        "get_openai_client": lambda: get_openai_client,
        "get_placement_questions": get_placement_questions,
        "get_quiz_interface_language": get_quiz_interface_language,
        "get_start_lesson_for_level": get_start_lesson_for_level,
        "get_student_lesson_schedule": get_student_lesson_schedule,
        "has_recent_past_simple_context": has_recent_past_simple_context,
        "is_affirmative": is_affirmative,
        "is_basic_level": is_basic_level,
        "is_exercise_request": is_exercise_request,
        "is_lesson_completed": is_lesson_completed,
        "is_lesson_schedule_question": is_lesson_schedule_question,
        "is_lesson_start_request": is_lesson_start_request,
        "is_level_retest_request": is_level_retest_request,
        "is_mixed_language_message": is_mixed_language_message,
        "is_negative": is_negative,
        "is_next_lesson_question": is_next_lesson_question,
        "is_number_without_time_unit": is_number_without_time_unit,
        "is_off_topic_during_assessment": is_off_topic_during_assessment,
        "is_probable_learning_goal": is_probable_learning_goal,
        "is_probable_person_name": is_probable_person_name,
        "is_ready_for_lesson": is_ready_for_lesson,
        "is_schedule_change_request": is_schedule_change_request,
        "is_unclear_study_experience": is_unclear_study_experience,
        "is_unclear_yes_no": is_unclear_yes_no,
        "is_valid_placement_answer": lambda: is_valid_placement_answer,
        "json": json,
        "looks_like_name_correction": looks_like_name_correction,
        "normalize_intent_text": normalize_intent_text,
        "normalize_language_preference": normalize_language_preference,
        "normalize_whatsapp_phone_for_send": normalize_whatsapp_phone_for_send,
        "os": os,
        "parse_lesson_schedule": parse_lesson_schedule,
        "parse_practice_button_message": parse_practice_button_message,
        "parse_quiz_button_message": parse_quiz_button_message,
        "repeat_placement_question": repeat_placement_question,
        "require_student_access": require_student_access,
        "reset_lesson_flow": reset_lesson_flow,
        "resume_stuck_guided_lesson": resume_stuck_guided_lesson,
        "save_lesson_feedback_if_expected": save_lesson_feedback_if_expected,
        "start_guided_lesson": start_guided_lesson,
        "text": text,
        "timedelta": timedelta,
        "update_lesson_engagement": update_lesson_engagement,
        "wants_portuguese_mode": wants_portuguese_mode,
        "whatsapp_phone_variants": whatsapp_phone_variants,
}
globals().update(configure_api(api_dependencies))
app.include_router(api_router)
configure_automations(resolve=lambda name: globals()[name])
configure_webhook(WebhookDependencies(resolve=lambda name: globals()[name]))
app.include_router(webhook_router)
