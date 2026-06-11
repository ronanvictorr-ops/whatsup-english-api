import html
import os
from datetime import datetime, timedelta

import bcrypt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Form, HTTPException, Response
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from openai import OpenAI
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import Base, SessionLocal, engine
from models import ConversationDB, ProgressDB, StudentDB


load_dotenv()

Base.metadata.create_all(bind=engine)

app = FastAPI()

SECRET_KEY = os.getenv("SECRET_KEY", "whatsup-english-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="OPENAI_API_KEY não configurada no arquivo .env",
        )

    return OpenAI(api_key=api_key)


def twilio_message(message: str):
    escaped_message = html.escape(message)
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{escaped_message}</Message>
</Response>"""

    return Response(content=twiml, media_type="application/xml")


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


class AssessmentRequest(BaseModel):
    student_id: int
    answer: str


class Conversation(BaseModel):
    student_id: int
    question: str
    answer: str


class ChatRequest(BaseModel):
    student_id: int
    question: str


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})

    return jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )

        return payload

    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Token inválido",
        )


def generate_ai_answer(student: StudentDB, question: str, db: Session):
    level = getattr(student, "level", None) or "Basic"
    language = getattr(student, "preferred_language", None) or "Portuguese"
    goal = getattr(student, "learning_goal", None) or "Conversation"

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
- Preferred language for explanations: {language}
- Learning goal: {goal}

Teaching style:
- Be warm, direct, and encouraging.
- Keep the conversation natural, like a private tutor on WhatsApp.
- Adapt vocabulary and grammar to the student's level.
- Prefer short messages. Stay under 120 words.
- Use English for practice, but explain in the preferred language when helpful.
- Correct mistakes politely.
- Always show a corrected version when the student makes a mistake.
- Ask one simple follow-up question to keep the student practicing.
- Do not overwhelm the student with long grammar theory.

Brand voice:
- You can occasionally use the slogan "Let's Bora!".
""",
        }
    ]

    for conversation in reversed(history):
        messages.append(
            {
                "role": "user",
                "content": conversation.question,
            }
        )

        messages.append(
            {
                "role": "assistant",
                "content": conversation.answer,
            }
        )

    messages.append(
        {
            "role": "user",
            "content": question,
        }
    )

    client = get_openai_client()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
    )

    answer = response.choices[0].message.content

    conversation = ConversationDB(
        student_id=student.id,
        question=question,
        answer=answer,
    )

    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return answer


@app.post("/register")
def register(student: Student, db: Session = Depends(get_db)):
    try:
        hashed_password = bcrypt.hashpw(
            student.password.encode("utf-8"),
            bcrypt.gensalt(),
        ).decode("utf-8")

        new_student = StudentDB(
            name=student.name,
            email=student.email,
            password=hashed_password,
            phone=student.phone,
            preferred_language=student.preferred_language,
            learning_goal=student.learning_goal,
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
        }

    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Erro ao cadastrar aluno: {str(e)}",
        )


@app.post("/login")
def login(data: Login, db: Session = Depends(get_db)):
    student = db.query(StudentDB).filter(
        StudentDB.email == data.email,
    ).first()

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Aluno não encontrado",
        )

    if not bcrypt.checkpw(
        data.password.encode("utf-8"),
        student.password.encode("utf-8"),
    ):
        raise HTTPException(
            status_code=401,
            detail="Senha incorreta",
        )

    token = create_access_token(
        {
            "student_id": student.id,
            "email": student.email,
        }
    )

    return {
        "access_token": token,
        "token_type": "bearer",
    }


@app.get("/students")
def get_students(db: Session = Depends(get_db)):
    return db.query(StudentDB).all()


@app.get("/students/{student_id}")
def get_student(student_id: int, db: Session = Depends(get_db)):
    student = db.query(StudentDB).filter(
        StudentDB.id == student_id,
    ).first()

    if student is None:
        raise HTTPException(
            status_code=404,
            detail="Aluno não encontrado",
        )

    return student


@app.post("/quiz")
def quiz(data: QuizAnswer):
    correct_answer = "I am fine."

    if data.answer.strip().lower() == correct_answer.lower():
        return {
            "correct": True,
            "score": 10,
        }

    return {
        "correct": False,
        "score": 0,
    }


@app.post("/progress")
def save_progress(progress: Progress, db: Session = Depends(get_db)):
    new_progress = ProgressDB(
        student_id=progress.student_id,
        score=progress.score,
    )

    db.add(new_progress)
    db.commit()
    db.refresh(new_progress)

    return {
        "message": "Progresso salvo",
        "id": new_progress.id,
    }


@app.get("/progress")
def get_progress(db: Session = Depends(get_db)):
    return db.query(ProgressDB).all()


@app.get("/ranking")
def ranking(db: Session = Depends(get_db)):
    return (
        db.query(ProgressDB)
        .order_by(ProgressDB.score.desc())
        .all()
    )


@app.get("/me")
def me(user=Depends(get_current_user)):
    return {
        "message": "Usuário autenticado",
        "user": user,
    }


@app.get("/students/{student_id}/progress")
def get_student_progress(student_id: int, db: Session = Depends(get_db)):
    student = db.query(StudentDB).filter(
        StudentDB.id == student_id,
    ).first()

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Aluno não encontrado",
        )

    return {
        "student": student.name,
        "scores": [
            progress.score
            for progress in student.progresses
        ],
    }


@app.post("/conversation")
def save_conversation(conversation: Conversation, db: Session = Depends(get_db)):
    new_conversation = ConversationDB(
        student_id=conversation.student_id,
        question=conversation.question,
        answer=conversation.answer,
    )

    db.add(new_conversation)
    db.commit()
    db.refresh(new_conversation)

    return {
        "message": "Conversa salva com sucesso",
        "id": new_conversation.id,
    }


@app.get("/conversations")
def get_conversations(db: Session = Depends(get_db)):
    return db.query(ConversationDB).all()


@app.get("/students/{student_id}/conversations")
def get_student_conversations(student_id: int, db: Session = Depends(get_db)):
    student = db.query(StudentDB).filter(
        StudentDB.id == student_id,
    ).first()

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Aluno não encontrado",
        )

    return {
        "student": student.name,
        "conversations": [
            {
                "question": conversation.question,
                "answer": conversation.answer,
            }
            for conversation in student.conversations
        ],
    }


@app.post("/chat")
def chat(data: ChatRequest, db: Session = Depends(get_db)):
    student = db.query(StudentDB).filter(
        StudentDB.id == data.student_id,
    ).first()

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Aluno não encontrado",
        )

    answer = generate_ai_answer(
        student=student,
        question=data.question,
        db=db,
    )

    return {
        "student": student.name,
        "question": data.question,
        "answer": answer,
    }


@app.post("/whatsapp")
def whatsapp_webhook(
    Body: str = Form(...),
    From: str = Form(...),
    db: Session = Depends(get_db),
):
    phone = From.replace("whatsapp:", "")

    student = db.query(StudentDB).filter(
        StudentDB.phone == phone,
    ).first()

    if not student:
        return twilio_message(
            "Olá! Ainda não encontrei seu cadastro. Cadastre este número no WhatsUp English para começar."
        )

    answer = generate_ai_answer(
        student=student,
        question=Body,
        db=db,
    )

    return twilio_message(answer)


@app.post("/assessment")
def assessment(data: AssessmentRequest, db: Session = Depends(get_db)):
    student = db.query(StudentDB).filter(
        StudentDB.id == data.student_id,
    ).first()

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Aluno não encontrado",
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
""",
            },
            {
                "role": "user",
                "content": data.answer,
            },
        ],
    )

    level = response.choices[0].message.content.strip()

    student.level = level
    student.assessment_completed = "Yes"

    db.commit()

    return {
        "student": student.name,
        "level": level,
    }
