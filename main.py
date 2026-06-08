# ==========================================
# IMPORTAÇÕES
# ==========================================

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import SessionLocal, engine, Base
from models import StudentDB, ProgressDB

# Cria as tabelas do banco caso não existam
Base.metadata.create_all(bind=engine)

# Inicializa a aplicação FastAPI
app = FastAPI()


# ==========================================
# MODELOS DE ENTRADA (PYDANTIC)
# ==========================================

# Dados necessários para cadastrar um aluno
class Student(BaseModel):
    name: str
    email: str


# Dados enviados pelo aluno ao responder um quiz
class QuizAnswer(BaseModel):
    answer: str


# Dados necessários para salvar uma pontuação
class Progress(BaseModel):
    student_id: int
    score: int


# ==========================================
# CADASTRO DE ALUNOS
# ==========================================

@app.post("/register")
def register(student: Student):
    """
    Cadastra um novo aluno no banco de dados.
    """

    db: Session = SessionLocal()

    try:
        new_student = StudentDB(
            name=student.name,
            email=student.email
        )

        db.add(new_student)
        db.commit()
        db.refresh(new_student)

        return {
            "message": "Aluno salvo com sucesso",
            "id": new_student.id,
            "name": new_student.name,
            "email": new_student.email
        }

    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Erro ao salvar aluno: {str(e)}"
        )

    finally:
        db.close()


# ==========================================
# LISTAR TODOS OS ALUNOS
# ==========================================

@app.get("/students")
def get_students():
    """
    Retorna todos os alunos cadastrados.
    """

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
    """
    Busca um aluno específico pelo ID.
    """

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
# QUIZ DE INGLÊS
# ==========================================

@app.post("/quiz")
def quiz(data: QuizAnswer):
    """
    Corrige uma resposta de quiz.
    """

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
# SALVAR PROGRESSO DO ALUNO
# ==========================================

@app.post("/progress")
def save_progress(progress: Progress):
    """
    Salva uma pontuação no histórico do aluno.
    """

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
# LISTAR TODO O PROGRESSO
# ==========================================

@app.get("/progress")
def get_progress():
    """
    Retorna todas as pontuações registradas.
    """

    db: Session = SessionLocal()

    try:
        return db.query(ProgressDB).all()

    finally:
        db.close()


# ==========================================
# RANKING DE PONTUAÇÕES
# ==========================================

@app.get("/ranking")
def ranking():
    """
    Retorna as maiores pontuações primeiro.
    """

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
        