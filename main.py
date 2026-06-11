import token # IMPORTAÇÕES

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
import bcrypt
from jose import jwt
from datetime import datetime, timedelta    
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError  
from database import SessionLocal, engine, Base
from models import StudentDB, ProgressDB, ConversationDB
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

print("API KEY:", OPENAI_API_KEY)

client = OpenAI(
    api_key=OPENAI_API_KEY
)


Base.metadata.create_all(bind=engine) # CRIA TABELAS NO BANCO DE DADOS


app = FastAPI() # Inicializa a aplicação FastAPI
SECRET_KEY = "whatsup-english-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="login"
)

# MODELOS DE ENTRADA (PYDANTIC)


class Student(BaseModel): # Cadastro de aluno
    name: str
    email: str
    password: str


class Login(BaseModel): # Login
    email: str
    password: str

def create_access_token(data: dict):

    to_encode = data.copy()

    expire = datetime.utcnow() + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return encoded_jwt
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

class QuizAnswer(BaseModel): # Resposta do quiz
    answer: str



class Progress(BaseModel): # Salvar progresso
    student_id: int
    score: int


@app.post("/register") # CADASTRO DE ALUNOS
def register(student: Student):

    db: Session = SessionLocal()

    try:

        # Criptografa a senha
        hashed_password = bcrypt.hashpw(
            student.password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

        # Cria novo aluno
        new_student = StudentDB(
            name=student.name,
            email=student.email,
            password=hashed_password
        )

        db.add(new_student)
        db.commit()
        db.refresh(new_student)

        return {
            "message": "Aluno cadastrado com sucesso",
            "id": new_student.id,
            "name": new_student.name,
            "email": new_student.email
        }

    except Exception as e:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Erro ao cadastrar aluno: {str(e)}"
        )

    finally:
        db.close()



@app.post("/login") # LOGIN
def login(data: Login):

    db: Session = SessionLocal()

    try:

        student = db.query(StudentDB).filter(
            StudentDB.email == data.email
        ).first()

        if not student:
            raise HTTPException(
                status_code=404,
                detail="Aluno não encontrado"
            )

        # Verifica senha criptografada
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

    finally:
        db.close()



@app.get("/students") # LISTAR TODOS OS ALUNOS
def get_students():

    db: Session = SessionLocal()

    try:
        return db.query(StudentDB).all()

    finally:
        db.close()


@app.get("/students/{student_id}") # BUSCAR ALUNO POR ID
def get_student(student_id: int):

    db: Session = SessionLocal()

    try:

        student = db.query(StudentDB).filter(
            StudentDB.id == student_id
        ).first()

        if student is None:
            raise HTTPException(
                status_code=404,
                detail="Aluno não encontrado"
            )

        return student

    finally:
        db.close()



@app.post("/quiz") # QUIZ
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



@app.post("/progress") # SALVAR PROGRESSO
def save_progress(progress: Progress):

    db: Session = SessionLocal()

    try:

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

    finally:
        db.close()


@app.get("/progress") # LISTAR PROGRESSO
def get_progress():

    db: Session = SessionLocal()

    try:
        return db.query(ProgressDB).all()

    finally:
        db.close()


@app.get("/ranking") # RANKING
def ranking():

    db: Session = SessionLocal()

    try:

        ranking = (
            db.query(ProgressDB)
            .order_by(ProgressDB.score.desc())
            .all()
        )

        return ranking

    finally:
        db.close()

@app.get("/me")
def me(user = Depends(get_current_user)):

    return {
        "message": "Usuário autenticado",
        "user": user
    }
    
    
@app.get("/students/{student_id}/progress")
def get_student_progress(student_id: int):

    db: Session = SessionLocal()

    try:

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

    finally:
        db.close()

class Conversation(BaseModel):
    student_id: int
    question: str
    answer: str  



@app.post("/conversation") #SALVAR CONVERSAS
def save_conversation(conversation: Conversation):

    db: Session = SessionLocal()

    try:

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

    finally:
        db.close()



@app.get("/conversations") # LISTAR CONVERSAS
def get_conversations():

    db: Session = SessionLocal()

    try:
        return db.query(ConversationDB).all()

    finally:
        db.close()



@app.get("/students/{student_id}/conversations") #CONVERSAS DE ALUNOS
def get_student_conversations(student_id: int):

    db: Session = SessionLocal()

    try:

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
                    "question": c.question,
                    "answer": c.answer
                }
                for c in student.conversations
            ]
        }

    finally:
        db.close()

class ChatRequest(BaseModel):
    student_id: int
    question: str


# Resposta da IA

@app.post("/chat")
def chat(data: ChatRequest):

    db: Session = SessionLocal()

    try:

        student = db.query(StudentDB).filter(
            StudentDB.id == data.student_id
        ).first()

        if not student:
            raise HTTPException(
                status_code=404,
                detail="Aluno não encontrado"
            )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """
                    You are an English teacher.
                    Correct grammar mistakes.
                    Encourage conversation.
                    Answer in English.
                    """
                },
                {
                    "role": "user",
                    "content": data.question
                }
            ]
        )

        answer = response.choices[0].message.content

        conversation = ConversationDB(
            student_id=data.student_id,
            question=data.question,
            answer=answer
        )

        db.add(conversation)
        db.commit()
        db.refresh(conversation)

        return {
            "student": student.name,
            "question": data.question,
            "answer": answer
        }

    finally:
        db.close()