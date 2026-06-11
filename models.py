from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime
)

from sqlalchemy.orm import relationship
from datetime import datetime

from database import Base


# ==========================================
# ALUNOS
# ==========================================

class StudentDB(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)

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

    # Um aluno possui vários progressos
    progresses = relationship(
        "ProgressDB",
        back_populates="student"
    )

    # Um aluno possui várias conversas
    conversations = relationship(
        "ConversationDB",
        back_populates="student"
    )


# ==========================================
# PROGRESSO
# ==========================================

class ProgressDB(Base):
    __tablename__ = "progress"

    id = Column(Integer, primary_key=True, index=True)

    student_id = Column(
        Integer,
        ForeignKey("students.id")
    )

    score = Column(Integer)

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    # Cada progresso pertence a um aluno
    student = relationship(
        "StudentDB",
        back_populates="progresses"
    )


# ==========================================
# CONVERSAS COM IA
# ==========================================

class ConversationDB(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)

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

    # Cada conversa pertence a um aluno
    student = relationship(
        "StudentDB",
        back_populates="conversations"
    )