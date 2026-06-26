from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text
)

from sqlalchemy.orm import relationship

from database import Base


# ==========================================
# ALUNOS
# ==========================================

class StudentDB(Base):
    __tablename__ = "students"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    name = Column(String)

    email = Column(
        String,
        unique=True,
        index=True
    )

    password = Column(String)

    phone = Column(
        String,
        unique=True,
        index=True,
        nullable=False
    )

    level = Column(
        String,
        default="Not Assessed"
    )

    preferred_language = Column(
        String,
        default="Portuguese"
    )

    assessment_completed = Column(
        String,
        default="No"
    )

    learning_goal = Column(
        String,
        default="Conversation"
    )

    interests = Column(
        Text,
        default=""
    )

    onboarding_notes = Column(
        Text,
        default="[]"
    )

    current_lesson = Column(
        Integer,
        default=1
    )

    lesson_stage = Column(
        String,
        default="context_question"
    )

    engagement_minutes = Column(
        Integer,
        default=0
    )

    messages_in_current_lesson = Column(
        Integer,
        default=0
    )

    current_stage = Column(
        Integer,
        default=0
    )

    canonical_state = Column(String)

    last_activity = Column(
        DateTime,
        nullable=True
    )

    xp = Column(
        Integer,
        default=0
    )

    streak_days = Column(
        Integer,
        default=0
    )

    lesson_schedule = Column(
        Text,
        nullable=True
    )

    schedule_completed = Column(
        String,
        default="No"
    )

    last_daily_word_date = Column(String)

    last_weekly_quiz_week = Column(String)

    last_weekly_report_week = Column(String)

    last_lesson_date = Column(String)

    last_lesson_keys = Column(
        Text,
        default="[]"
    )

    progresses = relationship(
        "ProgressDB",
        back_populates="student"
    )

    conversations = relationship(
        "ConversationDB",
        back_populates="student"
    )

    learning_records = relationship(
        "LearningRecordDB",
        back_populates="student"
    )

    personal_notes = relationship(
        "PersonalNoteDB",
        back_populates="student"
    )

    lesson_sessions = relationship(
        "LessonSessionDB",
        back_populates="student"
    )


# ==========================================
# PROGRESSO
# ==========================================

class ProgressDB(Base):
    __tablename__ = "progress"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    student_id = Column(
        Integer,
        ForeignKey("students.id")
    )

    score = Column(Integer)

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    student = relationship(
        "StudentDB",
        back_populates="progresses"
    )


# ==========================================
# CONVERSAS COM IA
# ==========================================

class ConversationDB(Base):
    __tablename__ = "conversations"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    student_id = Column(
        Integer,
        ForeignKey("students.id")
    )

    question = Column(String)

    answer = Column(String)

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    student = relationship(
        "StudentDB",
        back_populates="conversations"
    )
    

# ==========================================
# MEMORIA PEDAGOGICA
# ==========================================

class LearningRecordDB(Base):
    __tablename__ = "learning_records"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    student_id = Column(
        Integer,
        ForeignKey("students.id")
    )

    skill = Column(String)

    topic = Column(String)

    original_text = Column(Text)

    corrected_text = Column(Text)

    explanation = Column(Text)

    source = Column(
        String,
        default="chat"
    )

    xp_awarded = Column(
        Integer,
        default=0
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    student = relationship(
        "StudentDB",
        back_populates="learning_records"
    )


class PersonalNoteDB(Base):
    __tablename__ = "personal_notes"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    student_id = Column(
        Integer,
        ForeignKey("students.id"),
        index=True,
        nullable=False
    )

    category = Column(
        String,
        default="life"
    )

    note = Column(
        Text,
        nullable=False
    )

    source_message = Column(Text)

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    student = relationship(
        "StudentDB",
        back_populates="personal_notes"
    )


class PronunciationAttemptDB(Base):
    __tablename__ = "pronunciation_attempts"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), index=True, nullable=False)
    message_id = Column(String, unique=True, index=True)
    provider = Column(String, default="transcription_only")
    status = Column(String, default="completed", index=True)
    reference_text = Column(Text)
    transcript = Column(Text)
    accuracy_score = Column(Float)
    fluency_score = Column(Float)
    completeness_score = Column(Float)
    prosody_score = Column(Float)
    pronunciation_score = Column(Float)
    word_details = Column(Text, default="[]")
    feedback = Column(Text)
    error = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ==========================================
# SESSOES DE AULA
# ==========================================

class LessonSessionDB(Base):
    __tablename__ = "lesson_sessions"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    student_id = Column(
        Integer,
        ForeignKey("students.id")
    )

    lesson_number = Column(Integer)

    lesson_title = Column(String)

    mode = Column(
        String,
        default="guided"
    )

    status = Column(
        String,
        default="started"
    )

    messages_count = Column(
        Integer,
        default=0
    )

    summary = Column(Text)

    feedback_rating = Column(Integer)

    feedback_text = Column(Text)

    teacher_audio_sent = Column(
        String,
        default="No"
    )

    student_audio_requested = Column(
        String,
        default="No"
    )

    started_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    completed_at = Column(DateTime)

    student = relationship(
        "StudentDB",
        back_populates="lesson_sessions"
    )


# ==========================================
# MENSAGENS PROCESSADAS DO WEBHOOK
# ==========================================

class ProcessedWebhookMessageDB(Base):
    __tablename__ = "processed_webhook_messages"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    message_id = Column(
        String,
        unique=True,
        index=True,
        nullable=False
    )

    phone = Column(String)

    status = Column(String, default="processing")

    attempts = Column(Integer, default=1)

    last_error = Column(Text)

    completed_at = Column(DateTime)

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


class StateTransitionDB(Base):
    __tablename__ = "state_transitions"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), index=True)
    message_id = Column(String, index=True)
    previous_state = Column(String, nullable=False)
    next_state = Column(String, nullable=False)
    flow = Column(String)
    decision = Column(String)
    message_excerpt = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class OutboundDeliveryDB(Base):
    __tablename__ = "outbound_deliveries"

    id = Column(Integer, primary_key=True, index=True)
    idempotency_key = Column(String, unique=True, index=True, nullable=False)
    phone = Column(String, index=True)
    message_type = Column(String)
    payload_excerpt = Column(Text)
    status = Column(String, default="pending", index=True)
    attempts = Column(Integer, default=0)
    meta_message_id = Column(String)
    last_error = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)


class OperationalMetricDB(Base):
    __tablename__ = "operational_metrics"

    id = Column(Integer, primary_key=True, index=True)
    service = Column(String, index=True)
    operation = Column(String, index=True)
    status = Column(String, index=True)
    latency_ms = Column(Float, default=0)
    attempts = Column(Integer, default=1)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    estimated_cost_usd = Column(Float, default=0)
    error_type = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
