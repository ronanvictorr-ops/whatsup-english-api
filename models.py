from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
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

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )
