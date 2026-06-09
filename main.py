# ==========================================
# IMPORTAÇÕES
# ==========================================

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
import bcrypt

from database import SessionLocal, engine, Base
from models import StudentDB, ProgressDB

# Cria as tabelas do banco caso não existam
Base.metadata.create_all(bind=engine)

# Inicializa a aplicação FastAPI
app = FastAPI()


# ==========================================
# MODELOS DE ENTRADA (PYDANTIC)
# ==========================================

# Cadastro de aluno
class Student(BaseModel):
    name: str
    email: str
    password: str


# Login
class Login(BaseModel):
    email: str
    password: str


# Resposta do quiz
class QuizAnswer(BaseModel):
    answer: str


# Salvar progresso
class Progress(BaseModel):
    student_id: int
    score: int


# ==========================================
# CADASTRO DE ALUNOS
# ==========================================

@app.post("/register")
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


# ==========================================
# LOGIN
# ==========================================

@app.post("/login")
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

        return {
            "message": "Login realizado com sucesso",
            "student_id": student.id,
            "name": student.name
        }

    finally:
        db.close()


# ==========================================
# LISTAR TODOS OS ALUNOS
# ==========================================

@app.get("/students")
def get_students():

    db: Session = SessionLocal()

    try:
        return db.query(StudentDB).all()

    finally:
        db.close()


# ==========================================
# BUSCAR ALUNO POR ID
# ==========================================

@app.get("/students/{student_id}")
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


# ==========================================
# QUIZ
# ==========================================

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


# ==========================================
# SALVAR PROGRESSO
# ==========================================

@app.post("/progress")
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


# ==========================================
# LISTAR PROGRESSO
# ==========================================

@app.get("/progress")
def get_progress():

    db: Session = SessionLocal()

    try:
        return db.query(ProgressDB).all()

    finally:
        db.close()


# ==========================================
# RANKING
# ==========================================

@app.get("/ranking")
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
        