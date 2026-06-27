from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import re

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import inspect as inspect_database

from database import get_db
from wingo.rate_limit import client_identifier, enforce_rate_limit
from wingo.security import get_current_user, require_dashboard_admin


router = APIRouter()


@dataclass(frozen=True)
class _Route:
    method: str
    path: str
    endpoint: object
    kwargs: dict


class _DeferredRoutes:
    def __init__(self):
        self.items = []

    def _register(self, method, path, **kwargs):
        def decorator(endpoint):
            self.items.append(_Route(method, path, endpoint, kwargs))
            return endpoint
        return decorator

    def get(self, path, **kwargs):
        return self._register("GET", path, **kwargs)

    def post(self, path, **kwargs):
        return self._register("POST", path, **kwargs)

    def put(self, path, **kwargs):
        return self._register("PUT", path, **kwargs)

    def delete(self, path, **kwargs):
        return self._register("DELETE", path, **kwargs)


_routes = _DeferredRoutes()

# =========================
# STUDENTS
# =========================

@_routes.get("/plans")
def get_product_plans():
    return {
        "product": "WINGO Daily",
        "positioning": "10 minutos de ingles por dia no WhatsApp.",
        "value_proposition": (
            "Aulas curtas, personalizadas e diarias com correcao imediata, "
            "pratica por audio, memoria pedagogica e relatorio semanal."
        ),
        "plans": PRODUCT_PLANS,
    }


@_routes.get("/pedagogy")
def get_pedagogy_overview():
    return {
        "lesson_stages": LESSON_STAGES,
        "correction_rubric": CORRECTION_RUBRIC,
        "placement_rubric": PLACEMENT_RUBRIC,
        "pronunciation_rubric": PRONUNCIATION_RUBRIC,
        "spaced_review_intervals_days": SPACED_REVIEW_INTERVALS,
        "advancement_criteria": {
            level: get_advancement_criterion(level)
            for level in ["Basic", "Basic 2", "Intermediate", "Advanced", "Fluent"]
        },
    }


@_routes.get("/pedagogy/lessons")
def get_pedagogy_lessons():
    return [
        {
            **lesson,
            "design": get_lesson_design(lesson),
        }
        for lesson in CURRICULUM
    ]


@_routes.get("/pedagogy/lessons/{lesson_number}")
def get_pedagogy_lesson(lesson_number: int):
    lesson = CURRICULUM_BY_NUMBER.get(lesson_number)

    if not lesson:
        raise HTTPException(
            status_code=404,
            detail="Aula nao encontrada"
        )

    return {
        **lesson,
        "design": get_lesson_design(lesson),
    }


@_routes.post("/register")
def register(student: Student, request: Request, db: Session = Depends(get_db)):
    enforce_rate_limit(
        "register",
        client_identifier(request),
        default_limit=5,
        default_window_seconds=3600,
    )

    if len(student.password) < 8:
        raise HTTPException(
            status_code=400,
            detail="A senha precisa ter pelo menos 8 caracteres.",
        )

    canonical_phone = normalize_whatsapp_phone_for_send(student.phone)
    if not canonical_phone:
        raise HTTPException(status_code=400, detail="Telefone invalido.")

    existing_student = db.query(StudentDB).filter(
        StudentDB.email == student.email
    ).first()

    if existing_student:
        raise HTTPException(
            status_code=400,
            detail="Este email ja esta cadastrado."
        )

    existing_phone = db.query(StudentDB).filter(
        StudentDB.phone.in_(whatsapp_phone_variants(student.phone))
    ).first()

    if existing_phone:
        raise HTTPException(
            status_code=400,
            detail="Este telefone ja esta cadastrado."
        )

    hashed_password = bcrypt.hashpw(
        student.password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    new_student = StudentDB(
    name=student.name,
    email=student.email,
    password=hashed_password,
    phone=canonical_phone,
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


@_routes.get("/students")
def get_students(
    db: Session = Depends(get_db),
    admin: bool = Depends(require_dashboard_admin),
):
    return db.query(StudentDB).all()


@_routes.get("/students-dashboard")
def get_students_dashboard(
    db: Session = Depends(get_db),
    admin: bool = Depends(require_dashboard_admin),
):
    students = db.query(StudentDB).order_by(StudentDB.id.desc()).all()
    return [build_dashboard_student(student, db) for student in students]


@_routes.get("/students/{student_id}")
def get_student(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    require_student_access(student_id, current_user)
    student = db.query(StudentDB).filter(
        StudentDB.id == student_id
    ).first()

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Aluno nao encontrado"
        )

    return {
        "id": student.id,
        "name": student.name,
        "email": student.email,
        "phone": student.phone,
        "level": student.level,
        "preferred_language": student.preferred_language,
        "learning_goal": student.learning_goal,
        "current_lesson": student.current_lesson,
        "lesson_stage": student.lesson_stage,
        "xp": student.xp or 0,
        "streak_days": student.streak_days or 0,
    }


# =========================
# LOGIN
# =========================

@_routes.post("/login")
def login(data: Login, request: Request, db: Session = Depends(get_db)):
    login_identity = f"{client_identifier(request)}:{data.email.strip().lower()}"
    enforce_rate_limit(
        "login",
        login_identity,
        default_limit=10,
        default_window_seconds=300,
    )
    student = db.query(StudentDB).filter(
        StudentDB.email == data.email
    ).first()

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Aluno nao encontrado"
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


@_routes.get("/me")
def me(user=Depends(get_current_user)):
    return {
        "message": "Usuario autenticado",
        "user": user
    }


# =========================
# QUIZ
# =========================

@_routes.post("/quiz")
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

@_routes.post("/progress")
def save_progress(
    progress: Progress,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    require_student_access(progress.student_id, current_user)
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


@_routes.get("/progress")
def get_progress(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    student_id = int(current_user["student_id"])
    return db.query(ProgressDB).filter(ProgressDB.student_id == student_id).all()


@_routes.get("/students/{student_id}/progress")
def get_student_progress(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    require_student_access(student_id, current_user)
    student = db.query(StudentDB).filter(
        StudentDB.id == student_id
    ).first()

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Aluno nao encontrado"
        )

    return {
        "student": student.name,
        "scores": [
            progress.score
            for progress in student.progresses
        ]
    }


@_routes.get("/ranking")
def ranking(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
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
            "level": student.level,
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

@_routes.post("/conversation")
def save_conversation(
    conversation: Conversation,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    require_student_access(conversation.student_id, current_user)
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


@_routes.get("/conversations")
def get_conversations(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    student_id = int(current_user["student_id"])
    return db.query(ConversationDB).filter(
        ConversationDB.student_id == student_id
    ).all()


@_routes.get("/students/{student_id}/conversations")
def get_student_conversations(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    require_student_access(student_id, current_user)
    student = db.query(StudentDB).filter(
        StudentDB.id == student_id
    ).first()

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Aluno nao encontrado"
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

@_routes.get("/students/{student_id}/learning-records")
def get_student_learning_records(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    require_student_access(student_id, current_user)
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


@_routes.post("/learning-records")
def create_learning_record(
    record: LearningRecord,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    require_student_access(record.student_id, current_user)
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

@_routes.post("/chat")
def chat(
    data: ChatRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    require_student_access(data.student_id, current_user)
    enforce_rate_limit(
        "chat",
        str(current_user["student_id"]),
        default_limit=30,
        default_window_seconds=60,
    )
    student = db.query(StudentDB).filter(
        StudentDB.id == data.student_id
    ).first()

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Aluno nao encontrado"
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
    canonical_phone = normalize_whatsapp_phone_for_send(phone)

    student = db.query(StudentDB).filter(
        StudentDB.phone == canonical_phone
    ).first()

    if not student:
        student = db.query(StudentDB).filter(
            StudentDB.phone.in_(whatsapp_phone_variants(phone))
        ).order_by(StudentDB.id.asc()).first()

    if student:
        if student.phone != canonical_phone:
            canonical_owner = db.query(StudentDB).filter(
                StudentDB.phone == canonical_phone,
                StudentDB.id != student.id,
            ).first()
            if not canonical_owner:
                student.phone = canonical_phone
        db.commit()
        db.refresh(student)
        return student

    hashed_password = bcrypt.hashpw(
        os.urandom(32),
        bcrypt.gensalt()
    ).decode("utf-8")

    student = StudentDB(
        name="",
        email=f"{canonical_phone}@whatsapp.local",
        password=hashed_password,
        phone=canonical_phone,
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


def get_learning_mode_label(student: StudentDB):
    if student.current_stage == 999:
        return "recuperacao"

    if student.current_stage in {0, 2, 3, 35, 4, 5, 6, 70, 81}:
        return "onboarding"

    if 50 <= (student.current_stage or 0) <= 54:
        return "teste de nivel"

    if student.current_stage == 7 and is_lesson_completed(student):
        return "modo BOT"

    if student.current_stage == 7:
        return "aula guiada"

    if student.current_stage == 80:
        return "escolha de idioma"

    if student.current_stage == 82:
        return "aguardando confirmacao da aula"

    if student.current_stage == 83:
        return "revisao antes da aula"

    if student.current_stage == 84:
        return "pratica de escrita"

    return "conversa"


def get_recent_learning_records(student_id: int, db: Session, limit: int = 3):
    return (
        db.query(LearningRecordDB)
        .filter(LearningRecordDB.student_id == student_id)
        .order_by(LearningRecordDB.id.desc())
        .limit(limit)
        .all()
    )


def get_completed_lessons_count(student_id: int, db: Session):
    return (
        db.query(LessonSessionDB)
        .filter(
            LessonSessionDB.student_id == student_id,
            LessonSessionDB.status == "completed"
        )
        .count()
    )


DASHBOARD_STAGE_LABELS = {
    "context_question": "Pergunta de contexto",
    "short_explanation": "Explicacao curta",
    "more_examples": "Mais exemplos",
    "comprehension": "Compreensao",
    "structure": "Estrutura",
    "exercise_1": "Primeiro exercicio",
    "exercise_2": "Segundo exercicio",
    "production": "Producao",
    "conversation": "Conversacao",
    "expansion": "Expansao",
    "challenge": "Desafio final",
    "completed": "Aula concluida",
}


def build_dashboard_student(student: StudentDB, db: Session):
    lesson = get_current_lesson(student)
    lesson_stage = get_lesson_stage(student)
    schedule = get_student_lesson_schedule(student)
    latest_session = get_latest_lesson_session(student, db)
    recent_records = get_recent_learning_records(student.id, db, limit=3)
    pronunciation_attempts = (
        db.query(PronunciationAttemptDB)
        .filter(PronunciationAttemptDB.student_id == student.id)
        .order_by(PronunciationAttemptDB.id.desc())
        .limit(5)
        .all()
    )
    completed_lessons = get_completed_lessons_count(student.id, db)
    rated_sessions = [
        session.feedback_rating
        for session in student.lesson_sessions
        if session.feedback_rating is not None
    ]
    average_rating = (
        round(sum(rated_sessions) / len(rated_sessions), 1)
        if rated_sessions
        else None
    )
    stage_index = (
        len(LESSON_STAGES)
        if lesson_stage == LESSON_COMPLETED_STAGE
        else LESSON_STAGES.index(lesson_stage)
    )
    mode = get_learning_mode_label(student)

    return {
        "id": student.id,
        "name": student.name,
        "phone": student.phone,
        "level": student.level,
        "current_stage": student.current_stage,
        "learning_mode": mode,
        "learning_mode_label": mode.replace("BOT", "Bot").capitalize(),
        "current_lesson": format_lesson_title(lesson),
        "lesson_stage": lesson_stage,
        "lesson_stage_label": DASHBOARD_STAGE_LABELS.get(lesson_stage, lesson_stage),
        "lesson_progress_percent": round(
            min(100, ((stage_index + 1) / len(LESSON_STAGES)) * 100)
        ),
        "completed_lessons": completed_lessons,
        "schedule": format_lesson_schedule(schedule) if schedule else None,
        "learning_goal": student.learning_goal,
        "interests": student.interests,
        "engagement_minutes": student.engagement_minutes or 0,
        "xp": student.xp or 0,
        "streak_days": student.streak_days or 0,
        "average_lesson_rating": average_rating,
        "latest_lesson_session": {
            "lesson_title": latest_session.lesson_title,
            "status": latest_session.status,
            "teacher_audio_sent": latest_session.teacher_audio_sent,
            "student_audio_requested": latest_session.student_audio_requested,
            "feedback_rating": latest_session.feedback_rating,
            "started_at": latest_session.started_at,
            "completed_at": latest_session.completed_at,
        } if latest_session else None,
        "last_activity": student.last_activity,
        "recent_learning_records": [
            {
                "topic": record.topic,
                "original_text": record.original_text,
                "corrected_text": record.corrected_text,
                "explanation": record.explanation,
            }
            for record in recent_records
        ],
        "pronunciation_attempts": [
            {
                "reference_text": attempt.reference_text,
                "transcript": attempt.transcript,
                "provider": attempt.provider,
                "status": attempt.status,
                "accuracy_score": attempt.accuracy_score,
                "fluency_score": attempt.fluency_score,
                "completeness_score": attempt.completeness_score,
                "prosody_score": attempt.prosody_score,
                "pronunciation_score": attempt.pronunciation_score,
                "feedback": attempt.feedback,
                "created_at": attempt.created_at,
            }
            for attempt in pronunciation_attempts
        ],
    }


def build_status_message(student: StudentDB, db: Session):
    lesson = get_current_lesson(student)
    mode = get_learning_mode_label(student)
    schedule = get_student_lesson_schedule(student)
    schedule_text = format_lesson_schedule(schedule) if schedule else "ainda nao definido"

    return (
        f"Status do WINGO\n\n"
        f"Nome: {student.name or 'ainda nao informado'}\n"
        f"Nivel: {student.level or 'Not Assessed'}\n"
        f"Modo atual: {mode}\n"
        f"Aula atual: {format_lesson_title(lesson)}\n"
        f"Etapa da aula: {get_lesson_stage(student)}\n"
        f"Aulas concluidas: {get_completed_lessons_count(student.id, db)}\n"
        f"XP: {student.xp or 0}\n"
        f"Horarios: {schedule_text}"
    )


def build_progress_message(student: StudentDB, db: Session):
    records = get_recent_learning_records(student.id, db)
    completed_lessons = get_completed_lessons_count(student.id, db)
    conversations_count = (
        db.query(ConversationDB)
        .filter(ConversationDB.student_id == student.id)
        .count()
    )
    sessions = (
        db.query(LessonSessionDB)
        .filter(LessonSessionDB.student_id == student.id)
        .all()
    )
    rated_sessions = [
        session.feedback_rating
        for session in sessions
        if session.feedback_rating is not None
    ]
    audio_lessons = [
        session for session in sessions
        if session.teacher_audio_sent == "Yes" or session.student_audio_requested == "Yes"
    ]
    average_rating = (
        round(sum(rated_sessions) / len(rated_sessions), 1)
        if rated_sessions
        else None
    )

    lines = [
        "Seu progresso ate agora:",
        "",
        f"Nivel atual: {student.level or 'Not Assessed'}",
        f"Aulas concluidas: {completed_lessons}",
        f"Mensagens praticadas: {conversations_count}",
        f"Aulas com pratica oral: {len(audio_lessons)}",
        f"Tempo estimado de pratica: {student.engagement_minutes or 0} min",
        f"XP: {student.xp or 0}",
    ]

    if average_rating is not None:
        lines.append(f"Sua nota media das aulas: {average_rating}/10")

    if records:
        lines.append("")
        lines.append("Ultimos pontos para revisar:")

        for record in records:
            topic = record.topic or record.skill or "ingles"
            corrected = record.corrected_text or record.original_text or ""
            lines.append(f"- {topic}: {corrected[:80]}")
    else:
        lines.append("")
        lines.append("Ainda nao tenho erros recorrentes salvos. Vamos construir isso nas proximas aulas.")

    lines.append("")
    lines.append("Quando sentir que evoluiu, mande: refazer teste de nivel.")

    return "\n".join(lines)


def build_review_message(student: StudentDB, db: Session):
    records = get_recent_learning_records(student.id, db, limit=5)
    lesson = get_current_lesson(student)

    if not records:
        return (
            f"Vamos revisar sua aula atual: {format_lesson_title(lesson)}.\n\n"
            f"Foco: {lesson['focus']}\n\n"
            "Me mande uma frase usando esse tema, e eu corrijo para voce."
        )

    lines = [
        "Vamos revisar alguns pontos importantes:",
        "",
    ]

    for record in records[:3]:
        if record.original_text and record.corrected_text:
            lines.append(f"- Voce escreveu: {record.original_text}")
            lines.append(f"  Melhor: {record.corrected_text}")
        elif record.corrected_text:
            lines.append(f"- Revise: {record.corrected_text}")

        if record.explanation:
            lines.append(f"  Dica: {record.explanation}")

    lines.append("")
    lines.append("Agora tente criar uma frase curta usando uma dessas correcoes.")

    return "\n".join(lines)


def get_latest_personal_note(student: StudentDB):
    notes = list(getattr(student, "personal_notes", []) or [])
    if not notes:
        return None
    return sorted(notes, key=lambda note: note.id or 0, reverse=True)[0]


def build_smart_return_prompt(student: StudentDB, db: Session):
    lesson = get_current_lesson(student)
    recent_records = get_recent_learning_records(student.id, db, limit=1)
    latest_note = get_latest_personal_note(student)

    if student.current_stage == 7 and not is_lesson_completed(student):
        return {
            "type": "buttons",
            "body": (
                "Que bom que voce voltou. Podemos continuar a aula atual "
                f"({format_lesson_title(lesson)}), revisar um ponto recente "
                "ou fazer uma pratica rapidinha de 2 minutos."
            ),
            "buttons": [
                {"id": "return:continue", "title": "Continuar aula"},
                {"id": "return:review", "title": "Revisar"},
                {"id": "return:practice", "title": "Mini pratica"},
            ],
        }

    if recent_records:
        record = recent_records[0]
        point = record.corrected_text or record.explanation or record.topic or "um ponto recente"
        return {
            "type": "buttons",
            "body": (
                "Que bom que voce voltou. Antes de seguir, vale revisar este ponto: "
                f"{point[:140]}\n\nO que prefere fazer agora?"
            ),
            "buttons": [
                {"id": "return:review", "title": "Revisar erro"},
                {"id": "return:practice", "title": "Mini pratica"},
                {"id": "return:continue", "title": "Continuar aula"},
            ],
        }

    if latest_note:
        return {
            "type": "buttons",
            "body": (
                "Que bom que voce voltou. Lembrei de uma coisa que voce comentou: "
                f"{latest_note.note[:140]}\n\nQuer me contar como foi ou prefere ir direto "
                "para a aula?"
            ),
            "buttons": [
                {"id": "return:personal", "title": "Contar agora"},
                {"id": "return:continue", "title": "Continuar aula"},
                {"id": "return:practice", "title": "Mini pratica"},
            ],
        }

    return {
        "type": "buttons",
        "body": (
            "Que bom que voce voltou. Tenho uma pratica de 2 minutos pronta para aquecer, "
            "mas tambem posso continuar a aula ou mudar de tema."
        ),
        "buttons": [
            {"id": "return:practice", "title": "Mini pratica"},
            {"id": "return:continue", "title": "Continuar aula"},
            {"id": "return:topic", "title": "Mudar tema"},
        ],
    }


def reset_student_for_beta(student: StudentDB, db: Session):
    db.query(ConversationDB).filter(ConversationDB.student_id == student.id).delete()
    db.query(LearningRecordDB).filter(LearningRecordDB.student_id == student.id).delete()
    db.query(ProgressDB).filter(ProgressDB.student_id == student.id).delete()
    db.query(LessonSessionDB).filter(LessonSessionDB.student_id == student.id).delete()

    student.name = ""
    student.level = "Not Assessed"
    student.preferred_language = "Portuguese"
    student.assessment_completed = "No"
    student.learning_goal = "Conversation"
    student.interests = ""
    student.onboarding_notes = "[]"
    student.current_lesson = 1
    student.lesson_stage = "context_question"
    student.engagement_minutes = 0
    student.messages_in_current_lesson = 0
    student.current_stage = 2
    student.xp = 0
    student.streak_days = 0
    student.lesson_schedule = None
    student.schedule_completed = "No"
    student.last_daily_word_date = None
    student.last_weekly_quiz_week = None
    student.last_lesson_date = None
    student.last_lesson_keys = "[]"
    student.last_activity = datetime.utcnow()
    db.commit()


def handle_control_command(student: StudentDB, message: str, db: Session):
    command = detect_control_command(message)

    if command == "reset":
        reset_student_for_beta(student, db)
        return [
            "Combinado. Reiniciei seu cadastro no WINGO para comecarmos do zero.",
            "Primeiro, qual e o seu nome?"
        ]

    if command == "status":
        return build_status_message(student, db)

    if command == "progress":
        return build_progress_message(student, db)

    if command == "weekly_report":
        return build_weekly_progress_report(student, db)

    if command == "review":
        return build_review_message(student, db)

    if command == "pause":
        student.schedule_completed = "Paused"
        db.commit()
        return (
            "Tudo bem. Pausei suas aulas automaticas por enquanto.\n\n"
            "Quando quiser voltar, me mande: vamos continuar."
        )

    if command == "resume":
        if (
            getattr(student, "schedule_completed", "No") == "Paused"
            and get_student_lesson_schedule(student)
        ):
            student.schedule_completed = "Yes"
            student.current_stage = 7
            db.commit()
            return (
                "Combinado. Suas aulas automaticas voltaram.\n\n"
                "Quando quiser uma revisao agora, mande: revisar aula."
            )

        if getattr(student, "schedule_completed", "No") == "Paused":
            student.current_stage = 70
            db.commit()
            return "Combinado. Qual horario voce prefere para receber sua aula diaria?"

        return None

    if command == "support":
        return (
            "Claro. Vou avisar o suporte humano.\n\n"
            "Enquanto isso, me diga em uma frase o que aconteceu para eu registrar melhor."
        )

    if command == "help":
        return (
            "Voce pode me mandar:\n\n"
            "- status\n"
            "- meu progresso\n"
            "- relatorio semanal\n"
            "- revisar aula\n"
            "- refazer teste de nivel\n"
            "- mudar para nivel basico/intermediario/avancado\n"
            "- mudar horario\n"
            "- pausar aulas\n"
            "- reiniciar\n"
            "- suporte"
        )

    return None


def parse_choice_button_message(message: str):
    match = re.fullmatch(
        r"__button__:(return|post_lesson|lesson):(continue|review|practice|personal|topic|next_preview|hint)::(.+)",
        message or "",
        flags=re.DOTALL,
    )
    if not match:
        return None
    return {
        "context": match.group(1),
        "choice": match.group(2),
        "title": match.group(3).strip(),
    }


def is_lesson_hint_request(message: str):
    text = normalize_intent_text(message)
    return text in {
        "me de uma dica",
        "me da uma dica",
        "dica",
        "hint",
        "help",
        "me ajuda",
    }


def build_lesson_hint_reply(student: StudentDB, message: str, db: Session):
    lesson = get_current_lesson(student)
    stage = get_lesson_stage(student)

    if lesson["title"] == "Greetings":
        hints = {
            "context_question": (
                "Dica curta: para dizer 'Ola' em ingles, voce pode usar Hello.\n\n"
                "Agora tente escrever so a palavra em ingles."
            ),
            "short_explanation": (
                "Dica curta: comece com My name is e depois coloque o nome.\n\n"
                "Exemplo: My name is Ana.\n\n"
                "Agora tente escrever a frase completa."
            ),
            "more_examples": (
                "Dica curta: para perguntar o nome, comece com What.\n\n"
                "A pergunta completa e: What's your name?\n\n"
                "Agora tente escrever em ingles."
            ),
            "comprehension": (
                "Dica curta: responda com My name is + seu nome.\n\n"
                "Exemplo: My name is Ana.\n\n"
                "Agora responda usando seu nome real."
            ),
        }
        reply = hints.get(stage) or (
            "Dica curta: nesta aula usamos Hello, What's your name? e My name is...\n\n"
            "Tente responder com uma frase bem curta em ingles."
        )
        db.add(
            ConversationDB(
                student_id=student.id,
                question=message,
                answer=reply,
            )
        )
        db.commit()
        return reply

    return generate_ai_answer(
        student=student,
        question=message,
        db=db,
        ai_question=(
            "[Internal instruction: the student tapped a hint button because they are stuck. "
            f"The current lesson is {lesson['title']} and the current stage is {stage}. "
            "Give one short hint in Portuguese, one tiny English example, and ask the same exercise "
            "again in simpler words. Do not give the full answer unless the current exercise is only "
            "a greeting. Keep it under 70 words.]"
        ),
    )


def handle_choice_button(student: StudentDB, button_choice: dict, db: Session):
    choice = button_choice["choice"]

    if choice == "hint":
        return build_lesson_hint_reply(student, button_choice["title"], db)

    if choice == "review":
        return build_review_message(student, db)

    if choice == "topic":
        return (
            "Combinado. Qual tema voce quer praticar agora?\n\n"
            "Pode ser: viagem, trabalho, futuro, entrevista ou pronuncia."
        )

    if choice == "next_preview":
        return build_next_lesson_preview(student, db)

    if choice == "practice":
        return generate_ai_answer(
            student=student,
            question=button_choice["title"],
            db=db,
            ai_question=(
                "[Internal instruction: the student tapped a post-lesson button to practice "
                "conversation. Start a tiny conversation practice connected to the student's "
                "level, interests, and recent lesson. Ask exactly one short question. For Basic "
                "students, explain in Portuguese and keep the English sentence simple.]"
            ),
        )

    if choice == "personal":
        return generate_ai_answer(
            student=student,
            question=button_choice["title"],
            db=db,
            ai_question=(
                "[Internal instruction: the student tapped a return button to talk about "
                "a saved personal memory. Use the personal relationship memory naturally. "
                "Ask one warm follow-up question, then gently connect back to English "
                "practice. For Basic students, speak mainly in Portuguese.]"
            ),
        )

    if choice == "continue":
        if student.current_stage == 7 and is_lesson_completed(student):
            return start_guided_lesson(student, db, mode="manual")

        if student.current_stage == 7:
            resumed_answer = resume_stuck_guided_lesson(
                student,
                "continuar aula guiada",
                db,
            )
            if resumed_answer is not None:
                return resumed_answer

            return generate_ai_answer(
                student=student,
                question=button_choice["title"],
                db=db,
                ai_question=(
                    "[Internal instruction: the student tapped a return button to continue "
                    "the current guided lesson. Continue from the saved lesson stage. Do not "
                    "restart onboarding and do not open a free chat. Ask exactly one next "
                    "practice question.]"
                ),
            )

        return recover_student_flow(student, db)

    return None


def recover_student_flow(student: StudentDB, db: Session):
    if not (student.name or "").strip():
        student.current_stage = 2
        db.commit()
        return (
            "Tive um problema aqui. Vou retomar com voce do ponto certo.\n\n"
            "Primeiro, qual e o seu nome?"
        )

    if not (student.learning_goal or "").strip() or student.learning_goal == "Conversation":
        student.current_stage = 3
        db.commit()
        return (
            "Tive um problema aqui. Vou retomar com voce do ponto certo.\n\n"
            "Me conta com suas palavras: por que voce quer aprender ingles?"
        )

    if not (student.interests or "").strip():
        student.current_stage = 35
        db.commit()
        return (
            "Tive um problema aqui. Vou retomar com voce do ponto certo.\n\n"
            "Me conta do que voce gosta para eu personalizar suas aulas."
        )

    if getattr(student, "assessment_completed", "No") != "Yes":
        student.current_stage = 4
        db.commit()
        return (
            "Tive um problema aqui. Vou retomar com voce do ponto certo.\n\n"
            "Voce ja estudou ingles antes, mesmo que por pouco tempo?"
        )

    if getattr(student, "schedule_completed", "No") != "Yes":
        student.current_stage = 70
        db.commit()
        return (
            "Tive um problema aqui. Vou retomar com voce do ponto certo.\n\n"
            "Qual horario voce prefere para receber sua aula diaria?"
        )

    student.current_stage = 7
    db.commit()
    return (
        "Tive um problema aqui. Vou retomar com voce do ponto certo.\n\n"
        "Quando quiser continuar, me mande: vamos comecar."
    )


def extract_explicit_practice_topic(message: str):
    text = normalize_intent_text(message)
    patterns = [
        r"^(?:vamos\s+)?(?:praticar|treinar|estudar|aprender|revisar)\s+(?:o\s+|a\s+|sobre\s+|tema\s+)?(.+)$",
        r"^(?:quero|gostaria de)\s+(?:praticar|treinar|estudar|aprender|revisar)\s+(?:o\s+|a\s+|sobre\s+|tema\s+)?(.+)$",
        r"^(?:let'?s\s+)?(?:practice|study|learn|review)\s+(?:the\s+|about\s+)?(.+)$",
    ]

    for pattern in patterns:
        match = re.match(pattern, text)
        if not match:
            continue

        topic = match.group(1).strip(" .!?,-")
        if topic in {"", "agora", "ingles", "english", "exercicios", "exercicio", "quiz"}:
            return None

        aliases = {
            "future": "Future: will and going to",
            "futuro": "Future: will and going to",
            "past simple": "Past Simple",
            "simple past": "Past Simple",
            "passado simples": "Past Simple",
            "present continuous": "Present Continuous",
            "presente continuo": "Present Continuous",
            "present simple": "Present Simple",
            "presente simples": "Present Simple",
        }
        return aliases.get(topic, topic)

    return None


def is_audio_replay_request(message: str):
    text = normalize_intent_text(message)
    return any(
        re.search(pattern, text)
        for pattern in [
            r"\baudio.*(?:de novo|novamente|outra vez)\b",
            r"\b(?:repete|repetir|reproduz|reproduzir|manda|mande).*(?:audio|som)\b",
            r"\b(?:toca|tocar).*(?:de novo|novamente|outra vez)\b",
        ]
    )


def build_audio_replay(student: StudentDB, db: Session):
    recent = (
        db.query(ConversationDB)
        .filter(ConversationDB.student_id == student.id)
        .order_by(ConversationDB.id.desc())
        .limit(12)
        .all()
    )
    for conversation in recent:
        phrases = extract_english_phrases_for_audio(conversation.answer or "")
        if phrases:
            return (
                "Claro, vou repetir o audio da ultima frase praticada.\n\n"
                "Repeat after me:\n" + "\n".join(phrases[:3])
            )

    return "Claro. Qual frase em ingles voce quer que eu repita em audio?"


def is_short_time_request(message: str):
    text = normalize_intent_text(message)
    return any(
        phrase in text
        for phrase in {
            "so 2 min",
            "so dois min",
            "tenho 2 min",
            "tenho dois min",
            "rapidinho",
            "rapido",
            "hoje nao posso muito",
            "nao posso muito hoje",
            "pouco tempo",
            "estou sem tempo",
            "to sem tempo",
            "correndo",
            "bem rapido",
        }
    )


def is_stuck_lesson_answer(message: str):
    text = normalize_intent_text(message)
    if not text:
        return True

    exact_stuck_markers = {
        "???",
        "?",
    }
    stuck_markers = {
        "nao sei",
        "n sei",
        "sei la",
        "nao entendi",
        "n entendi",
        "entendi nada",
        "to confuso",
        "estou confuso",
        "confuso",
        "como assim",
        "me ajuda",
        "ajuda",
        "help",
        "dica",
        "hint",
    }
    return text in exact_stuck_markers or text in stuck_markers or any(marker in text for marker in stuck_markers)


def build_stuck_lesson_recovery(student: StudentDB, db: Session):
    lesson = get_current_lesson(student)
    stage = get_lesson_stage(student)

    if lesson["title"] == "Greetings":
        example = "Exemplo: Hello."
        reformulated = "Vamos bem simples: como voce diria 'Ola' em ingles?"
    elif lesson["title"] == "Past Simple":
        example = "Exemplo: Yesterday I studied."
        reformulated = "Agora tente uma frase curta sobre ontem com 'Yesterday I...'"
    elif stage == "production":
        example = "Exemplo: I am studying English."
        reformulated = "Tente montar uma frase curta em ingles com a ideia da aula."
    else:
        example = f"Exemplo ligado a {lesson['title']}: I practice every day."
        reformulated = "Vamos simplificar: responda com uma frase curta em ingles."

    return {
        "type": "buttons",
        "body": (
            "Sem problema. Vou reformular.\n\n"
            f"{reformulated}\n\n"
            f"{example}\n\n"
            "Pode tentar do seu jeito. Se quiser, toque no botao de dica."
        ),
        "buttons": [
            {"id": "lesson:hint", "title": "Me de uma dica"},
        ],
    }


def build_greetings_context_reply(
    student: StudentDB,
    message: str,
    db: Session,
    answered_stage: str,
):
    if get_current_lesson(student)["title"] != "Greetings":
        return None

    normalized = normalize_intent_text(message)

    def save_and_return(answer: str):
        db.add(
            ConversationDB(
                student_id=student.id,
                question=message,
                answer=answer,
            )
        )
        db.commit()
        return answer

    if answered_stage == "context_question":
        if normalized not in {"hello", "hi", "hey", "good morning"}:
            return None

        return save_and_return(
            f"Muito bem! \"{message.strip()}\" esta correto.\n\n"
            "Hi e mais casual. Hello tambem esta certo e funciona bem para cumprimentar alguem.\n\n"
            "Agora vamos dar mais um passo: como voce diria em ingles \"Meu nome e Ana\"?"
        )

    if answered_stage == "short_explanation":
        if not (
            normalized.startswith("my name is ")
            or normalized.startswith("my name s ")
            or normalized.startswith("i am ")
            or normalized.startswith("i m ")
        ):
            return None

        return save_and_return(
            f"Perfeito! \"{message.strip()}\" funciona para se apresentar.\n\n"
            "A estrutura principal e: My name is + nome.\n\n"
            "Agora pratique a pergunta: como voce pergunta \"Qual e o seu nome?\" em ingles?"
        )

    if answered_stage in {"more_examples", "comprehension"}:
        name_questions = {
            "what is your name",
            "what is your name?",
            "whats your name",
            "whats your name?",
            "what s your name",
            "what s your name?",
            "what is you name",
            "what is you name?",
            "what your name",
            "what your name?",
        }
        if normalized in name_questions:
            return save_and_return(
                "Muito bem! A forma natural e: What's your name?\n\n"
                "Agora responda essa pergunta usando seu nome real:\n\n"
                "What's your name?"
            )
        if normalized.startswith("my name is ") or normalized.startswith("i am "):
            student.lesson_stage = LESSON_COMPLETED_STAGE
            student.messages_in_current_lesson = 0
            student.xp = (student.xp or 0) + 10
            return save_and_return(
                f"Excelente! \"{message.strip()}\" esta correto.\n\n"
                "Hoje voce praticou cumprimentos e apresentacao em ingles: Hello, Hi, "
                "What's your name? e My name is...\n\n"
                "Sua missao: me mandar amanha uma frase comecando com \"My name is...\" "
                "ou cumprimentar alguem com \"Hello\".\n\n"
                "Quando quiser seguir, me mande: proxima aula."
            )

    if answered_stage in {
        "structure",
        "exercise_1",
        "exercise_2",
        "production",
        "conversation",
        "expansion",
        "challenge",
    } and (normalized.startswith("my name is ") or normalized.startswith("i am ")):
        student.lesson_stage = LESSON_COMPLETED_STAGE
        student.messages_in_current_lesson = 0
        student.xp = (student.xp or 0) + 10
        return save_and_return(
            f"Boa! \"{message.strip()}\" esta correto.\n\n"
            "Aula de cumprimentos concluida. Voce ja consegue cumprimentar e se apresentar em ingles.\n\n"
            "Missao curta: amanha me mande \"Hello, my name is...\" com seu nome."
        )

    if answered_stage in {"more_examples", "comprehension", "structure"}:
        return save_and_return(
            "Quase. Vamos manter bem simples.\n\n"
            "Para perguntar o nome: What's your name?\n"
            "Para responder: My name is Ana.\n\n"
            "Agora tente responder: What's your name?"
        )

    return None


def build_greetings_resume_reply(student: StudentDB, db: Session):
    if get_current_lesson(student)["title"] != "Greetings" or is_lesson_completed(student):
        return None

    active_session = (
        db.query(LessonSessionDB)
        .filter(
            LessonSessionDB.student_id == student.id,
            LessonSessionDB.status == "started",
        )
        .order_by(LessonSessionDB.id.desc())
        .first()
    )
    if not active_session:
        return None

    student.current_stage = 7
    stage = get_lesson_stage(student)

    if stage == "context_question":
        db.commit()
        return build_lesson_opening_replies(student, db)

    prompts = {
        "short_explanation": (
            "Vamos retomar do ponto certo.\n\n"
            "Voce ja praticou o cumprimento. Agora me responda:\n\n"
            "Como voce diria em ingles \"Meu nome e Ana\"?"
        ),
        "more_examples": (
            "Vamos retomar do ponto certo.\n\n"
            "Agora pratique a pergunta: como voce pergunta \"Qual e o seu nome?\" em ingles?"
        ),
        "comprehension": (
            "Vamos retomar do ponto certo.\n\n"
            "Responda essa pergunta usando seu nome real:\n\n"
            "What's your name?"
        ),
        "structure": (
            "Vamos retomar do ponto certo.\n\n"
            "Para perguntar o nome: What's your name?\n"
            "Para responder: My name is Ana.\n\n"
            "Agora tente responder: What's your name?"
        ),
    }
    reply = prompts.get(stage)

    if not reply:
        return None

    db.add(
        ConversationDB(
            student_id=student.id,
            question="resume:greetings",
            answer=reply,
        )
    )
    db.commit()
    return reply


def get_recent_example_context(student: StudentDB, db: Session, limit: int = 8):
    recent = (
        db.query(ConversationDB)
        .filter(ConversationDB.student_id == student.id)
        .order_by(ConversationDB.id.desc())
        .limit(limit)
        .all()
    )
    snippets = []
    for conversation in recent:
        text = f"{conversation.question or ''} {conversation.answer or ''}"
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            snippets.append(text[:180])

    if not snippets:
        return "No recent examples saved yet."

    return "\n".join(f"- {snippet}" for snippet in snippets[:5])


def build_short_time_micro_lesson(student: StudentDB, message: str, db: Session):
    student.current_stage = 7
    db.commit()
    return generate_ai_answer(
        student=student,
        question=message,
        db=db,
        ai_question=(
            "[Internal instruction: the student said they have very little time. "
            "Switch to a 2-minute micro-lesson. Do not send a full lesson, do not ask "
            "multiple questions, and do not start a long explanation. Send at most 70 words. "
            "Use exactly: one warm acknowledgement, one tiny useful English example, and "
            "one short exercise for the student to answer. For Basic students, explain mainly "
            "in Portuguese. Avoid repeating any recent examples listed below.]\n\n"
            f"Recent examples to avoid:\n{get_recent_example_context(student, db)}\n\n"
            f"Student message: {message}"
        ),
    )


def build_varied_past_simple_quiz(student: StudentDB, prefix: str, language: str, db: Session):
    recent = get_recent_example_context(student, db).lower()
    if any(token in recent for token in ("yesterday, i ___ on a project", "work -> worked", "worked")):
        return build_past_simple_finish_quiz(prefix, language)
    completed_blocks = ((student.xp or 0) // 6) % 2
    if completed_blocks == 1:
        return build_past_simple_finish_quiz(prefix, language)
    return build_past_simple_work_quiz(prefix, language)


def process_whatsapp_message(phone: str, message: str, db: Session):
    student = get_or_create_whatsapp_student(phone, db)
    if (
        is_basic_level(getattr(student, "level", None))
        and normalize_language_preference(student.preferred_language) != "Portuguese"
    ):
        student.preferred_language = "Portuguese"
        db.commit()

    choice_button = parse_choice_button_message(message)
    if choice_button:
        choice_reply = handle_choice_button(student, choice_button, db)
        if choice_reply:
            return choice_reply

    practice_choice = parse_practice_button_message(message)

    if practice_choice and is_basic_level(getattr(student, "level", None)):
        practice_choice["language"] = "pt"

    if practice_choice:
        if practice_choice["choice"] == "choose_topic":
            if practice_choice["language"] == "en":
                return "Which topic would you like to practice? For example: future, travel, work, or pronunciation."
            return "Qual tema voce quer praticar? Por exemplo: futuro, viagem, trabalho ou pronuncia."

        if practice_choice["choice"] == "writing":
            student.current_stage = 84
            db.commit()
            if practice_choice["language"] == "en":
                return "Great. Write two short sentences about what you did yesterday."
            return "Otimo. Escreva duas frases curtas em ingles sobre o que voce fez ontem."

        student.current_stage = 7
        db.commit()
        prefix = "New quiz block - Question 1 of 3" if practice_choice["language"] == "en" else "Novo bloco de quizzes - Pergunta 1 de 3"
        return build_varied_past_simple_quiz(student, prefix, practice_choice["language"], db)

    quiz_answer = parse_quiz_button_message(message)

    if quiz_answer:
        message = quiz_answer["title"]

        if not quiz_answer["is_correct"]:
            retry = build_quiz_retry(quiz_answer["quiz_id"])
            if retry:
                return retry

        return build_quiz_correct_reply(
            quiz_answer["quiz_id"],
            student,
            db,
        )

    if student.current_stage != 0:
        student.last_activity = datetime.utcnow()
        db.commit()

        if (
            is_short_time_request(message)
            and getattr(student, "assessment_completed", "No") == "Yes"
            and getattr(student, "schedule_completed", "No") == "Yes"
        ):
            return build_short_time_micro_lesson(student, message, db)

        command_reply = handle_control_command(student, message, db)
        if command_reply:
            return command_reply

        requested_language = detect_language_switch_request(message)
        if (
            requested_language
            and getattr(student, "assessment_completed", "No") == "Yes"
            and student.current_stage in {7, 80, 82, 83, 84}
        ):
            student.current_stage = 7

            if requested_language == "English" and is_basic_level(student.level):
                student.preferred_language = "Portuguese"
                db.commit()
                return (
                    "Nos niveis basicos, vou explicar e orientar sempre em portugues para ficar mais facil.\n\n"
                    "O ingles continua nos exemplos e exercicios, e eu vou aumentar aos poucos conforme voce evoluir."
                )

            student.preferred_language = requested_language
            db.commit()

            if requested_language == "English":
                return "Combinado. A partir de agora, vou conduzir a aula em ingles. Vamos continuar de onde paramos."

            return "Combinado. A partir de agora, vou explicar em portugues. Vamos continuar de onde paramos."

        feedback_reply = save_lesson_feedback_if_expected(student, message, db)
        if feedback_reply:
            return feedback_reply

        if (
            student.current_stage in {7, 82, 83, 84}
            and is_next_lesson_question(message)
        ):
            return build_next_lesson_preview(student, db)

        if (
            student.current_stage == 7
            and not is_lesson_completed(student)
            and is_lesson_hint_request(message)
        ):
            return build_lesson_hint_reply(student, message, db)

        if (
            student.current_stage == 7
            and not is_lesson_completed(student)
            and is_stuck_lesson_answer(message)
        ):
            return build_stuck_lesson_recovery(student, db)

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
            (
                "Bem-vindo(a)! Esse e nosso primeiro contato, entao vou te guiar "
                "passo a passo."
            ),
            "Primeiro, qual e o seu nome?"
        ]

    student.last_activity = datetime.utcnow()
    db.commit()

    if (
        student.current_stage not in {0, 2, 3, 35, 4, 5, 6, 50, 51, 52, 53, 54, 70, 80, 81, 82, 83, 84, 999}
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
                "Qual horario voce prefere para receber sua aula diaria?"
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
                    "What time would you like to receive your daily lesson?"
                )

            return (
                "Tudo bem. Vamos comecar com calma pelo basico.\n\n"
                f"A primeira aula sera: {format_lesson_title(lesson)}.\n\n"
                "Qual horario voce prefere para receber sua aula diaria?"
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
                "Qual horario voce prefere para receber sua aula diaria?"
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
                "What time would you like to receive your daily lesson?"
            ]

        return [
            (
                f"{feedback}\n\n"
                f"Vou preparar sua primeira aula: {format_lesson_title(lesson)}.\n\n"
                "Quando se sentir preparado no futuro, voce pode me pedir para refazer o teste de nivel."
            ),
            "Qual horario voce prefere para receber sua aula diaria?"
        ]

    if student.current_stage == 70:
        slots = parse_lesson_schedule(message)

        if not slots:
            if normalize_language_preference(student.preferred_language) == "English":
                return (
                    "What time would you like to receive your daily lesson?\n\n"
                    "Example: every day at 7 PM."
                )

            return (
                "Qual horario voce prefere para receber sua aula diaria?\n\n"
                "Pode responder, por exemplo: todos os dias as 19h."
            )

        student.lesson_schedule = json.dumps(slots)
        student.schedule_completed = "Yes"
        student.current_stage = 7
        db.commit()

        if normalize_language_preference(student.preferred_language) == "English":
            return (
                "Great! Your classes are scheduled for "
                f"{format_lesson_schedule(slots)}.\n\n"
                "In our first lesson, I will guide you step by step.\n\n"
                "When you feel you have improved, you can ask: retake level test.\n\n"
                "When you want to start, send me: let's start."
            )

        return (
            "Combinado! Suas aulas ficaram em "
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

    if student.current_stage == 82:
        if is_ready_for_lesson(message):
            return start_guided_lesson(student, db, mode="scheduled")

        if is_negative(message) or normalize_intent_text(message) in {
            "mais tarde", "agora nao", "nao posso", "estou ocupado", "estou ocupada"
        }:
            student.current_stage = 7
            db.commit()
            return (
                "Sem problema. Nao vou iniciar a aula agora.\n\n"
                "Quando estiver disponivel hoje, me mande: vamos para nossa aula."
            )

        return "Voce esta disponivel para a aula de hoje? Pode responder sim ou dizer que prefere mais tarde."

    if student.current_stage == 83:
        student.current_stage = 7
        db.commit()
        return [
            "Boa! Revisao concluida. Agora vamos para o conteudo novo de hoje.",
            *build_lesson_opening_replies(student, db),
        ]

    if student.current_stage == 84:
        if is_exercise_request(message):
            student.current_stage = 7
            db.commit()
            language = get_quiz_interface_language(student, message)
            prefix = "New quiz block - Question 1 of 3" if language == "en" else "Novo bloco de quizzes - Pergunta 1 de 3"
            return build_past_simple_finish_quiz(prefix, language)

        return generate_writing_practice_feedback(student, message, db)

    if student.current_stage == 7:
        if is_audio_replay_request(message):
            return build_audio_replay(student, db)

        requested_topic = extract_explicit_practice_topic(message)
        if requested_topic:
            return generate_ai_answer(
                student=student,
                question=message,
                db=db,
                ai_question=(
                    "[Internal instruction: the student explicitly chose a new practice topic. "
                    f"Switch immediately to this topic: {requested_topic}. "
                    "Do not continue Past Simple or the previous quiz unless that is the chosen topic. "
                    "Acknowledge the topic, give one fresh level-appropriate example that does not "
                    "repeat recent conversation examples, then ask exactly one short exercise about it. "
                    "Use Portuguese guidance for Basic and Basic 2 students.]\n\n"
                    f"Recent examples to avoid:\n{get_recent_example_context(student, db)}\n\n"
                    f"Student message: {message}"
                ),
            )

        if is_exercise_request(message) and has_recent_past_simple_context(
            student,
            message,
            db,
        ):
            quiz_language = get_quiz_interface_language(student, message)
            intro = (
                "Let's practice the Past Simple. Choose the correct answer. Question 1 of 3"
                if quiz_language == "en"
                else "Vamos praticar o Past Simple. Escolha a resposta correta. Pergunta 1 de 3"
            )
            return build_varied_past_simple_quiz(student, intro, quiz_language, db)

        if is_schedule_change_request(message):
            student.current_stage = 70
            db.commit()
            return (
                "Claro. Qual sera o novo horario da sua aula diaria?\n\n"
                "Exemplo: todos os dias as 19h."
            )

        requested_level = detect_requested_level_change(message)

        if requested_level:
            student.level = requested_level
            student.current_lesson = get_start_lesson_for_level(requested_level)
            reset_lesson_flow(student)
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

    if student.current_stage == 7 and is_lesson_schedule_question(message):
        slots = get_student_lesson_schedule(student)
        if slots:
            return (
                f"Suas aulas estao programadas para {format_lesson_schedule(slots)}.\n\n"
                "Se quiser antecipar a aula de hoje, pode dizer: vamos para nossa aula agora."
            )
        return "Voce ainda nao definiu um horario. Me diga que horas prefere receber sua aula diaria."

    if student.current_stage == 7 and is_lesson_start_request(message):
        greetings_resume = build_greetings_resume_reply(student, db)

        if greetings_resume is not None:
            return greetings_resume

        resumed_answer = resume_stuck_guided_lesson(student, message, db)

        if resumed_answer is not None:
            return resumed_answer

    if student.current_stage == 7 and is_lesson_completed(student):
        if is_lesson_start_request(message):
            return start_guided_lesson(student, db, mode="manual")

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

    if student.current_stage == 7 and is_lesson_start_request(message):
        return start_guided_lesson(student, db, mode="manual")

    question_for_ai = None
    lesson_was_completed = is_lesson_completed(student)

    if student.current_stage == 7:
        if is_mixed_language_message(message):
            return generate_ai_answer(
                student=student,
                question=message,
                db=db,
                ai_question=(
                    "[Internal instruction: the student mixed Portuguese and English while answering "
                    "the current guided exercise. Do not advance the lesson stage. Infer the intended "
                    "English sentence and help reconstruct it. Reply naturally with: a brief encouraging "
                    "sentence in Portuguese; a separate line beginning 'Em ingles:' with the complete "
                    "English sentence; one short correction tip; and ask the student to write the complete "
                    "English sentence again. Do not discuss the sentence topic as free chat. Ask no other question.]\n\n"
                    f"Student's mixed sentence: {message}"
                )
            )

        answered_lesson_stage = get_lesson_stage(student)
        update_lesson_engagement(student, db)
        db.commit()

        greetings_reply = build_greetings_context_reply(
            student,
            message,
            db,
            answered_lesson_stage,
        )
        if greetings_reply:
            return greetings_reply

        deterministic_reply = build_deterministic_guided_reply(
            student,
            message,
            db,
        )

        if deterministic_reply:
            return deterministic_reply

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

        if quiz_answer and quiz_answer["is_correct"]:
            question_for_ai = (
                "[Internal instruction: the student selected the correct answer from an interactive "
                f"exercise: {quiz_answer['title']!r}. Congratulate briefly, explain why it is correct "
                "in one sentence, and continue with exactly one next step from the current guided lesson. "
                "Do not enter BOT mode and do not repeat the same multiple-choice question.]"
            )

    answer = generate_ai_answer(
        student=student,
        question=message,
        db=db,
        ai_question=question_for_ai
    )

    if student.current_stage == 7 and not lesson_was_completed and is_lesson_completed(student):
        feedback_message = build_post_lesson_feedback_message(student, db)

        if feedback_message:
            return [answer, feedback_message]

    return answer




@_routes.get("/students/{student_id}/lesson-schedule")
def get_student_lesson_schedule_endpoint(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    require_student_access(student_id, current_user)
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
        "weekly_report_day": WEEKLY_REPORT_DAY,
        "weekly_report_time": WEEKLY_REPORT_TIME,
    }


@_routes.post("/students/{student_id}/lesson-schedule")
def update_student_lesson_schedule(
    student_id: int,
    schedule: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    require_student_access(student_id, current_user)
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
            detail="Informe um horario. Exemplo: todos os dias as 19h"
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

@_routes.post("/assessment")
def assessment(
    data: AssessmentRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    require_student_access(data.student_id, current_user)
    enforce_rate_limit(
        "assessment",
        str(current_user["student_id"]),
        default_limit=10,
        default_window_seconds=300,
    )
    student = db.query(StudentDB).filter(
        StudentDB.id == data.student_id
    ).first()

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Aluno nao encontrado"
        )

    client = get_openai_client()

    response = call_with_retry(client.chat.completions.create, operation="chat_completion",
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
    allowed_levels = {"Basic", "Basic 2", "Intermediate", "Advanced", "Fluent"}
    if level not in allowed_levels:
        raise HTTPException(status_code=502, detail="Nivel invalido retornado pela avaliacao")

    student.level = level
    student.assessment_completed = "Yes"

    db.commit()

    return {
        "student": student.name,
        "level": level
    }


@_routes.get("/ops/health")
def operational_health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    since = datetime.utcnow() - timedelta(minutes=15)
    stale_before = datetime.utcnow() - timedelta(minutes=5)
    recent_errors = db.query(OperationalMetricDB).filter(
        OperationalMetricDB.status == "error",
        OperationalMetricDB.created_at >= since,
    ).count()
    failed_deliveries = db.query(OutboundDeliveryDB).filter(
        OutboundDeliveryDB.status == "failed",
        OutboundDeliveryDB.created_at >= since,
    ).count()
    stuck_inbound = db.query(ProcessedWebhookMessageDB).filter(
        ProcessedWebhookMessageDB.status == "processing",
        ProcessedWebhookMessageDB.created_at < stale_before,
    ).count()
    stuck_outbound = db.query(OutboundDeliveryDB).filter(
        OutboundDeliveryDB.status == "sending",
        OutboundDeliveryDB.created_at < stale_before,
    ).count()
    degraded = any((recent_errors, failed_deliveries, stuck_inbound, stuck_outbound))
    return {
        "status": "degraded" if degraded else "ok",
        "database": "ok",
        "pronunciation_assessment": (
            "azure_acoustic"
            if os.getenv("AZURE_SPEECH_KEY") and os.getenv("AZURE_SPEECH_REGION")
            else "transcription_only"
        ),
        "errors_last_15_minutes": recent_errors,
        "failed_deliveries_last_15_minutes": failed_deliveries,
        "stuck_inbound_messages": stuck_inbound,
        "stuck_outbound_deliveries": stuck_outbound,
    }


@_routes.get("/ops/metrics")
def operational_metrics(
    hours: int = Query(24, ge=1, le=720),
    db: Session = Depends(get_db),
    admin: bool = Depends(require_dashboard_admin),
):
    since = datetime.utcnow() - timedelta(hours=hours)
    rows = (
        db.query(
            OperationalMetricDB.service,
            OperationalMetricDB.operation,
            OperationalMetricDB.status,
            func.count(OperationalMetricDB.id),
            func.avg(OperationalMetricDB.latency_ms),
            func.sum(OperationalMetricDB.input_tokens),
            func.sum(OperationalMetricDB.output_tokens),
            func.sum(OperationalMetricDB.estimated_cost_usd),
        )
        .filter(OperationalMetricDB.created_at >= since)
        .group_by(
            OperationalMetricDB.service,
            OperationalMetricDB.operation,
            OperationalMetricDB.status,
        )
        .all()
    )
    return {
        "period_hours": hours,
        "metrics": [
            {
                "service": row[0],
                "operation": row[1],
                "status": row[2],
                "count": row[3],
                "average_latency_ms": round(float(row[4] or 0), 2),
                "input_tokens": int(row[5] or 0),
                "output_tokens": int(row[6] or 0),
                "estimated_cost_usd": round(float(row[7] or 0), 6),
            }
            for row in rows
        ],
    }


@_routes.get("/ops/state-transitions")
def recent_state_transitions(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    admin: bool = Depends(require_dashboard_admin),
):
    transitions = (
        db.query(StateTransitionDB)
        .order_by(StateTransitionDB.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "student_id": item.student_id,
            "message_id": item.message_id,
            "previous_state": item.previous_state,
            "next_state": item.next_state,
            "flow": item.flow,
            "decision": item.decision,
            "message": item.message_excerpt,
            "created_at": item.created_at,
        }
        for item in transitions
    ]


@_routes.post("/ops/reset-testers")
def reset_all_testers(
    db: Session = Depends(get_db),
    admin: bool = Depends(require_dashboard_admin),
):
    tables = [
        "pronunciation_attempts",
        "personal_notes",
        "learning_records",
        "progress",
        "lesson_sessions",
        "conversations",
        "state_transitions",
        "processed_webhook_messages",
        "outbound_deliveries",
        "operational_metrics",
        "students",
    ]
    existing_tables = set(inspect_database(db.bind).get_table_names())
    preparer = db.bind.dialect.identifier_preparer
    before = {
        table: db.execute(
            text(f"SELECT COUNT(*) FROM {preparer.quote(table)}")
        ).scalar()
        for table in tables
        if table in existing_tables
    }
    for table in tables:
        if table in existing_tables:
            db.execute(text(f"DELETE FROM {preparer.quote(table)}"))
    db.commit()
    return {
        "status": "ok",
        "message": "Todos os dados de alunos/testers foram apagados.",
        "deleted": before,
        "skipped_missing_tables": [
            table for table in tables if table not in existing_tables
        ],
    }


@_routes.get("/dashboard", include_in_schema=False)
def dashboard_page():
    return FileResponse(DASHBOARD_DIR / "index.html")


@_routes.get("/", include_in_schema=False)
def sales_page():
    return FileResponse(SALES_DIR / "index.html")


@_routes.get("/dashboard/api/student")
def dashboard_student(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    student_id = current_user.get("student_id")
    student = db.query(StudentDB).filter(StudentDB.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Aluno nao encontrado")
    return build_dashboard_student(student, db)


@_routes.get("/dashboard/api/teacher")
def dashboard_teacher(
    db: Session = Depends(get_db),
    admin: bool = Depends(require_dashboard_admin),
):
    students = db.query(StudentDB).order_by(StudentDB.last_activity.desc()).all()
    active_since = datetime.utcnow() - timedelta(days=7)
    active_students = db.query(StudentDB).filter(
        StudentDB.last_activity >= active_since
    ).count()
    completed_lessons = db.query(LessonSessionDB).filter(
        LessonSessionDB.status == "completed"
    ).count()
    total_xp = db.query(func.sum(StudentDB.xp)).scalar() or 0
    return {
        "summary": {
            "total_students": len(students),
            "active_students": active_students,
            "completed_lessons": completed_lessons,
            "total_xp": int(total_xp),
        },
        "students": [build_dashboard_student(student, db) for student in students],
    }


@_routes.get("/dashboard/api/operations")
def dashboard_operations(
    db: Session = Depends(get_db),
    admin: bool = Depends(require_dashboard_admin),
):
    return {
        "health": operational_health(db),
        "metrics": operational_metrics(
            hours=24,
            db=db,
            admin=True,
        )["metrics"],
        "transitions": recent_state_transitions(
            limit=12,
            db=db,
            admin=True,
        ),
    }


_DEPENDENCY_NAMES = ('AssessmentRequest', 'CORRECTION_RUBRIC', 'CURRICULUM', 'CURRICULUM_BY_NUMBER', 'ChatRequest', 'Conversation', 'ConversationDB', 'DAILY_WORD_TIME', 'DASHBOARD_DIR', 'FileResponse', 'HTTPException', 'LESSON_COMPLETED_STAGE', 'LESSON_STAGES', 'LearningRecord', 'LearningRecordDB', 'LessonSessionDB', 'Login', 'OperationalMetricDB', 'OutboundDeliveryDB', 'PLACEMENT_RUBRIC', 'PRODUCT_PLANS', 'PRONUNCIATION_RUBRIC', 'ProcessedWebhookMessageDB', 'Progress', 'ProgressDB', 'PronunciationAttemptDB', 'QuizAnswer', 'SALES_DIR', 'SPACED_REVIEW_INTERVALS', 'Session', 'StateTransitionDB', 'Student', 'StudentDB', 'WEEKLY_QUIZ_DAY', 'WEEKLY_QUIZ_TIME', 'WEEKLY_REPORT_DAY', 'WEEKLY_REPORT_TIME', 'add_onboarding_note', 'bcrypt', 'build_deterministic_guided_reply', 'build_intro_video_reply', 'build_lesson_opening_replies', 'build_next_lesson_preview', 'build_past_simple_finish_quiz', 'build_past_simple_work_quiz', 'build_post_lesson_feedback_message', 'build_quiz_correct_reply', 'build_quiz_retry', 'build_weekly_progress_report', 'calculate_learning_xp', 'call_with_retry', 'create_access_token', 'datetime', 'detect_control_command', 'detect_language_switch_request', 'detect_requested_level_change', 'estimate_level_from_study_history', 'evaluate_placement_test_details', 'evaluate_placement_test_details_fallback', 'extract_english_phrases_for_audio', 'extract_name_candidate', 'format_lesson_schedule', 'format_lesson_title', 'format_placement_feedback', 'func', 'generate_ai_answer', 'generate_writing_practice_feedback', 'get_advancement_criterion', 'get_current_lesson', 'get_latest_lesson_session', 'get_lesson_design', 'get_lesson_stage', 'get_openai_client', 'get_placement_questions', 'get_quiz_interface_language', 'get_start_lesson_for_level', 'get_student_lesson_schedule', 'has_recent_past_simple_context', 'is_affirmative', 'is_basic_level', 'is_exercise_request', 'is_lesson_completed', 'is_lesson_schedule_question', 'is_lesson_start_request', 'is_level_retest_request', 'is_mixed_language_message', 'is_negative', 'is_next_lesson_question', 'is_number_without_time_unit', 'is_off_topic_during_assessment', 'is_probable_learning_goal', 'is_probable_person_name', 'is_ready_for_lesson', 'is_schedule_change_request', 'is_unclear_study_experience', 'is_unclear_yes_no', 'is_valid_placement_answer', 'json', 'looks_like_name_correction', 'normalize_intent_text', 'normalize_language_preference', 'normalize_whatsapp_phone_for_send', 'os', 'parse_lesson_schedule', 'parse_practice_button_message', 'parse_quiz_button_message', 'repeat_placement_question', 'require_student_access', 'reset_lesson_flow', 'resume_stuck_guided_lesson', 'save_lesson_feedback_if_expected', 'start_guided_lesson', 'text', 'timedelta', 'update_lesson_engagement', 'wants_portuguese_mode', 'whatsapp_phone_variants')
_EXPORTED_NAMES = ('assessment', 'build_dashboard_student', 'build_progress_message', 'build_review_message', 'build_smart_return_prompt', 'build_status_message', 'chat', 'create_learning_record', 'dashboard_operations', 'dashboard_page', 'dashboard_student', 'dashboard_teacher', 'get_completed_lessons_count', 'get_conversations', 'get_learning_mode_label', 'get_or_create_whatsapp_student', 'get_pedagogy_lesson', 'get_pedagogy_lessons', 'get_pedagogy_overview', 'get_product_plans', 'get_progress', 'get_recent_learning_records', 'get_student', 'get_student_conversations', 'get_student_learning_records', 'get_student_lesson_schedule_endpoint', 'get_student_progress', 'get_students', 'get_students_dashboard', 'handle_control_command', 'login', 'me', 'operational_health', 'operational_metrics', 'process_whatsapp_message', 'quiz', 'ranking', 'recent_state_transitions', 'recover_student_flow', 'register', 'reset_student_for_beta', 'sales_page', 'save_conversation', 'save_progress', 'update_student_lesson_schedule')
_DYNAMIC_CALLABLES = {
    "call_with_retry",
    "evaluate_placement_test_details",
    "generate_ai_answer",
    "get_openai_client",
    "is_valid_placement_answer",
}


def configure_api(dependencies: Mapping[str, object]):
    dependency_names = set(_DEPENDENCY_NAMES)
    provided_names = set(dependencies)
    missing_names = sorted(dependency_names - provided_names)
    if missing_names:
        raise RuntimeError(
            "Missing API dependencies: " + ", ".join(missing_names)
        )

    for name in _DEPENDENCY_NAMES:
        if name in _DYNAMIC_CALLABLES:
            provider = dependencies[name]
            globals()[name] = (
                lambda *args, _provider=provider, **kwargs:
                _provider()(*args, **kwargs)
            )
        else:
            globals()[name] = dependencies[name]

    if not router.routes:
        for route in _routes.items:
            router.add_api_route(
                route.path,
                route.endpoint,
                methods=[route.method],
                **route.kwargs,
            )

    return {name: globals()[name] for name in _EXPORTED_NAMES}

