import asyncio
import json
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from database import SessionLocal, engine
from models import LearningRecordDB, LessonSessionDB, StudentDB
from wingo.retries import call_with_retry


_DEPENDENCY_NAMES = (
    "ACADEMIC_AUTOMATIONS_ENABLED",
    "DAILY_WORD_TIME",
    "WEEKLY_QUIZ_DAY",
    "WEEKLY_QUIZ_TIME",
    "WEEKLY_REPORT_DAY",
    "WEEKLY_REPORT_TIME",
    "build_scheduled_lesson_invitation",
    "current_week_key",
    "format_lesson_title",
    "generate_ai_answer",
    "get_current_lesson",
    "get_language_instruction",
    "get_lesson_context",
    "get_lesson_stage",
    "get_openai_client",
    "get_recent_learning_summary",
    "get_seasonal_context",
    "get_student_lesson_schedule",
    "has_started_lesson_today",
    "has_time_arrived",
    "local_now",
    "normalize_language_preference",
    "send_whatsapp_message",
)


def configure_automations(resolve):
    for name in _DEPENDENCY_NAMES:
        globals()[name] = resolve(name)

def generate_daily_word_challenge(student: StudentDB, db: Session):
    client = get_openai_client()
    learning_summary = get_recent_learning_summary(student.id, db)
    seasonal_context = get_seasonal_context()

    response = call_with_retry(client.chat.completions.create, operation="chat_completion",
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

    response = call_with_retry(client.chat.completions.create, operation="chat_completion",
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


def build_weekly_progress_report(student: StudentDB, db: Session):
    week_start = local_now().date() - timedelta(days=7)
    recent_sessions = (
        db.query(LessonSessionDB)
        .filter(
            LessonSessionDB.student_id == student.id,
            LessonSessionDB.started_at >= datetime.combine(week_start, datetime.min.time())
        )
        .order_by(LessonSessionDB.started_at.desc())
        .all()
    )
    recent_records = (
        db.query(LearningRecordDB)
        .filter(
            LearningRecordDB.student_id == student.id,
            LearningRecordDB.created_at >= datetime.combine(week_start, datetime.min.time())
        )
        .order_by(LearningRecordDB.created_at.desc())
        .limit(5)
        .all()
    )
    completed = [session for session in recent_sessions if session.status == "completed"]
    learned_topics = []

    for session in completed:
        if session.lesson_title and session.lesson_title not in learned_topics:
            learned_topics.append(session.lesson_title)

    improvement = "participacao nas aulas"

    if recent_records:
        improvement = recent_records[0].topic or recent_records[0].skill or improvement

    next_lesson = get_current_lesson(student)
    topics_text = ", ".join(learned_topics[:4]) if learned_topics else "primeiras praticas com o WINGO"

    return (
        f"Resumo da semana - WINGO\n\n"
        f"Aulas feitas: {len(completed)}\n"
        f"Tempo estimado praticado: {student.engagement_minutes or 0} min\n"
        f"XP atual: {student.xp or 0}\n"
        f"Topicos trabalhados: {topics_text}\n"
        f"Principal evolucao: {improvement}\n"
        f"Proximo foco: {format_lesson_title(next_lesson)}\n\n"
        "Quando sentir que evoluiu, voce pode mandar: refazer teste de nivel."
    )


def send_weekly_progress_reports(db: Session, now: datetime):
    if now.strftime("%A") != WEEKLY_REPORT_DAY:
        return

    if not has_time_arrived(now, WEEKLY_REPORT_TIME):
        return

    week_key = current_week_key(now)
    students = db.query(StudentDB).filter(
        StudentDB.assessment_completed == "Yes"
    ).all()

    for student in students:
        if getattr(student, "last_weekly_report_week", None) == week_key:
            continue

        try:
            send_whatsapp_message(
                student.phone,
                build_weekly_progress_report(student, db)
            )

            student.last_weekly_report_week = week_key
            db.commit()
        except Exception as error:
            db.rollback()
            print("Erro ao enviar relatorio semanal:", student.id, error)


def generate_weekly_lesson(student: StudentDB, db: Session):
    client = get_openai_client()
    learning_summary = get_recent_learning_summary(student.id, db)
    seasonal_context = get_seasonal_context()
    lesson_context = get_lesson_context(student)
    interests = getattr(student, "interests", None) or "not informed yet"
    lesson_stage = get_lesson_stage(student)
    level = getattr(student, "level", None) or "Basic"
    language = normalize_language_preference(
        getattr(student, "preferred_language", None) or "Portuguese"
    )
    language_instruction = get_language_instruction(language, level)

    response = call_with_retry(client.chat.completions.create, operation="chat_completion",
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": f"""
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
- Language preference: {language}.
- Mandatory language rule: {language_instruction}
- Keep this same language choice throughout the guided lesson. Do not switch languages unexpectedly.
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
                student.current_stage = 82
                message = build_scheduled_lesson_invitation(student, db, now)
                send_whatsapp_message(student.phone, message)

                sent_keys.append(lesson_key)
                student.last_lesson_keys = json.dumps(sent_keys[-20:])
                db.commit()
            except Exception as error:
                db.rollback()
                print("Erro ao enviar aula agendada:", student.id, error)


AUTOMATION_LOCK_ID = 846_204_711


def acquire_automation_lock(db: Session) -> bool:
    if engine.dialect.name != "postgresql":
        return True
    return bool(
        db.execute(
            text("SELECT pg_try_advisory_lock(:lock_id)"),
            {"lock_id": AUTOMATION_LOCK_ID},
        ).scalar()
    )


def release_automation_lock(db: Session) -> None:
    if engine.dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_unlock(:lock_id)"),
            {"lock_id": AUTOMATION_LOCK_ID},
        )


def run_academic_automations_once(db: Session, now: datetime) -> None:
    send_scheduled_lessons(db, now)
    send_daily_word_challenges(db, now)
    send_weekly_quizzes(db, now)
    send_weekly_progress_reports(db, now)


async def academic_automation_loop():
    while True:
        db = SessionLocal()
        lock_acquired = False

        try:
            lock_acquired = acquire_automation_lock(db)
            if lock_acquired:
                run_academic_automations_once(db, local_now())
        except Exception as error:
            print("Erro nas automacoes academicas:", error)
        finally:
            if lock_acquired:
                try:
                    release_automation_lock(db)
                except Exception as error:
                    print("Erro ao liberar lock das automacoes:", error)
            db.close()

        await asyncio.sleep(60)


async def start_academic_automations():
    if not ACADEMIC_AUTOMATIONS_ENABLED:
        print("Automacoes academicas desativadas por ACADEMIC_AUTOMATIONS_ENABLED=false")
        return

    asyncio.create_task(academic_automation_loop())
