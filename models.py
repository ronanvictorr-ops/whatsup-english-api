from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String
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

    progresses = relationship(
        "ProgressDB",
        back_populates="student"
    )

    conversations = relationship(
        "ConversationDB",
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
    