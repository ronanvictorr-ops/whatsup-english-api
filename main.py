import os
from datetime import datetime, timedelta
import requests
import bcrypt
from dotenv import load_dotenv
from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    Response,
)
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from openai import OpenAI
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import Base, SessionLocal, engine
from models import ConversationDB, ProgressDB, StudentDB




# =========================
# CONFIGURAÇÕES INICIAIS
# =========================

load_dotenv()

Base.metadata.create_all(bind=engine)

app = FastAPI()

SECRET_KEY = os.getenv("SECRET_KEY", "whatsup-english-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


# =========================
# DATABASE
# =========================

def get_db():
    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


# =========================
# OPENAI
# =========================

def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="OPENAI_API_KEY não configurada no arquivo .env"
        )

    return OpenAI(api_key=api_key)


# =========================
# WHATSAPP CLOUD API / META
# =========================

def normalize_whatsapp_phone_for_send(phone: str):
    digits = "".join(char for char in phone if char.isdigit())

    # A Meta as vezes envia wa_id brasileiro sem o nono digito, mas a lista de
    # destinatarios de teste pode ficar cadastrada com o nono digito.
    if digits.startswith("55") and len(digits) == 12:
        ddd = digits[2:4]
        local_number = digits[4:]

        if not local_number.startswith("9"):
            return f"55{ddd}9{local_number}"

    return digits


def send_whatsapp_message(phone: str, text: str):
    phone_number_id = os.getenv("META_PHONE_NUMBER_ID")
    access_token = os.getenv("META_ACCESS_TOKEN")
    recipient_phone = normalize_whatsapp_phone_for_send(phone)

    if not phone_number_id or not access_token:
        raise HTTPException(
            status_code=500,
            detail="META_PHONE_NUMBER_ID ou META_ACCESS_TOKEN nao configurado no .env"
        )

    url = f"https://graph.facebook.com/v23.0/{phone_number_id}/messages"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_phone,
        "type": "text",
        "text": {
            "body": text
        }
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=20
    )

    if response.status_code >= 400:
        print("Erro ao enviar mensagem pela Meta:", response.text)
        print("Telefone recebido:", phone)
        print("Telefone usado no envio:", recipient_phone)
        raise HTTPException(
            status_code=502,
            detail="Erro ao enviar mensagem pelo WhatsApp Cloud API"
        )

    return response.json()


# =========================
# PYDANTIC MODELS
# =========================

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


class Conversation(BaseModel):
    student_id: int
    question: str
    answer: str


class ChatRequest(BaseModel):
    student_id: int
    question: str


class AssessmentRequest(BaseModel):
    student_id: int
    answer: str


# =========================
# AUTH
# =========================

def create_access_token(data: dict):
    to_encode = data.copy()

    expire = datetime.utcnow() + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    to_encode.update({"exp": expire})

    return jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM
    )


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


# =========================
# AI SERVICE
# =========================

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
"""
        }
    ]

    for conversation in reversed(history):
        messages.append(
            {
                "role": "user",
                "content": conversation.question
            }
        )

        messages.append(
            {
                "role": "assistant",
                "content": conversation.answer
            }
        )

    messages.append(
        {
            "role": "user",
            "content": question
        }
    )

    client = get_openai_client()

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages
    )

    answer = response.choices[0].message.content

    conversation = ConversationDB(
        student_id=student.id,
        question=question,
        answer=answer
    )

    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return answer


# =========================
# STUDENTS
# =========================

@app.post("/register")
def register(student: Student, db: Session = Depends(get_db)):

    existing_student = db.query(StudentDB).filter(
        StudentDB.email == student.email
    ).first()

    if existing_student:
        raise HTTPException(
            status_code=400,
            detail="Este email já está cadastrado."
        )

    existing_phone = db.query(StudentDB).filter(
        StudentDB.phone == student.phone
    ).first()

    if existing_phone:
        raise HTTPException(
            status_code=400,
            detail="Este telefone já está cadastrado."
        )

    hashed_password = bcrypt.hashpw(
        student.password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    new_student = StudentDB(
    name=student.name,
    email=student.email,
    password=hashed_password,
    phone=student.phone,
    preferred_language=student.preferred_language,
    learning_goal=student.learning_goal,
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
        "level": new_student.level,
        "assessment_completed": new_student.assessment_completed,
        "current_stage": new_student.current_stage,
        "last_activity": new_student.last_activity
    }


@app.get("/students")
def get_students(db: Session = Depends(get_db)):
    return db.query(StudentDB).all()


@app.get("/students/{student_id}")
def get_student(student_id: int, db: Session = Depends(get_db)):
    student = db.query(StudentDB).filter(
        StudentDB.id == student_id
    ).first()

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Aluno não encontrado"
        )

    return student


# =========================
# LOGIN
# =========================

@app.post("/login")
def login(data: Login, db: Session = Depends(get_db)):
    student = db.query(StudentDB).filter(
        StudentDB.email == data.email
    ).first()

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Aluno não encontrado"
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


@app.get("/me")
def me(user=Depends(get_current_user)):
    return {
        "message": "Usuário autenticado",
        "user": user
    }


# =========================
# QUIZ
# =========================

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


# =========================
# PROGRESS
# =========================

@app.post("/progress")
def save_progress(progress: Progress, db: Session = Depends(get_db)):
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


@app.get("/progress")
def get_progress(db: Session = Depends(get_db)):
    return db.query(ProgressDB).all()


@app.get("/students/{student_id}/progress")
def get_student_progress(student_id: int, db: Session = Depends(get_db)):
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


@app.get("/ranking")
def ranking(db: Session = Depends(get_db)):
    return (
        db.query(ProgressDB)
        .order_by(ProgressDB.score.desc())
        .all()
    )


# =========================
# CONVERSATIONS
# =========================

@app.post("/conversation")
def save_conversation(
    conversation: Conversation,
    db: Session = Depends(get_db)
):
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


@app.get("/conversations")
def get_conversations(db: Session = Depends(get_db)):
    return db.query(ConversationDB).all()


@app.get("/students/{student_id}/conversations")
def get_student_conversations(
    student_id: int,
    db: Session = Depends(get_db)
):
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
                "question": conversation.question,
                "answer": conversation.answer
            }
            for conversation in student.conversations
        ]
    }


# =========================
# CHAT IA
# =========================

@app.post("/chat")
def chat(data: ChatRequest, db: Session = Depends(get_db)):
    student = db.query(StudentDB).filter(
        StudentDB.id == data.student_id
    ).first()

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Aluno não encontrado"
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

    student = db.query(StudentDB).filter(
        StudentDB.phone == phone
    ).first()

    if student:
        student.last_activity = now
        db.commit()
        db.refresh(student)
        return student

    hashed_password = bcrypt.hashpw(
        os.urandom(32),
        bcrypt.gensalt()
    ).decode("utf-8")

    student = StudentDB(
        name="",
        email=f"{phone}@whatsapp.local",
        password=hashed_password,
        phone=phone,
        preferred_language="Portuguese",
        learning_goal="Conversation",
        current_stage=0,
        last_activity=now
    )

    db.add(student)
    db.commit()
    db.refresh(student)

    return student


def process_whatsapp_message(phone: str, message: str, db: Session):
    student = get_or_create_whatsapp_student(phone, db)

    if student.current_stage == 0:
        student.current_stage = 2
        student.last_activity = datetime.utcnow()
        db.commit()

        return (
            "Ola!\n\n"
            "Eu sou o Ronan AI, professor virtual do WhatsUp English.\n\n"
            "Vou te ajudar a aprender ingles de forma simples, pratica e no seu ritmo.\n\n"
            "Let's Bora!\n\n"
            "Primeiro, qual e o seu nome?"
        )

    student.last_activity = datetime.utcnow()
    db.commit()

    if student.current_stage == 2:
        student.name = message
        student.current_stage = 3
        db.commit()

        return (
            f"Prazer em conhecer voce, {student.name}!\n\n"
            "Qual e o seu principal objetivo com o ingles?\n\n"
            "1. Viagens\n"
            "2. Trabalho\n"
            "3. Negocios\n"
            "4. Conversacao\n"
            "5. Entrevistas de emprego\n"
            "6. Estudos\n"
            "7. Outro"
        )

    if student.current_stage == 3:
        student.learning_goal = message
        student.current_stage = 4
        db.commit()

        return (
            "Perfeito!\n\n"
            "Agora me diga:\n\n"
            "Voce prefere continuar nossas conversas em:\n\n"
            "Portugues\n"
            "Ingles\n"
            "Os dois"
        )

    if student.current_stage == 4:
        student.preferred_language = message
        student.current_stage = 5
        db.commit()

        return (
            "Otimo!\n\n"
            "Agora vou fazer uma avaliacao rapida para entender seu nivel atual de ingles.\n\n"
            "Nao se preocupe com erros. Responda da melhor forma que conseguir.\n\n"
            "Como voce se apresentaria em ingles para alguem que acabou de conhecer?"
        )

    assessment_completed = getattr(student, "assessment_completed", "No")

    if student.current_stage == 5 and assessment_completed != "Yes":
        client = get_openai_client()

        assessment_response = client.chat.completions.create(
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
"""
                },
                {
                    "role": "user",
                    "content": message
                }
            ]
        )

        level = assessment_response.choices[0].message.content.strip()

        student.level = level
        student.assessment_completed = "Yes"
        student.current_stage = 6
        db.commit()

        return (
            f"Excelente!\n\n"
            f"Seu nivel atual de ingles e: {level}\n\n"
            "Agora ja podemos comecar sua pratica personalizada.\n\n"
            "Me envie uma frase em ingles ou diga o que voce gostaria de praticar hoje."
        )

    return generate_ai_answer(
        student=student,
        question=message,
        db=db
    )


# =========================
# ASSESSMENT
# =========================

@app.post("/assessment")
def assessment(data: AssessmentRequest, db: Session = Depends(get_db)):
    student = db.query(StudentDB).filter(
        StudentDB.id == data.student_id
    ).first()

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Aluno não encontrado"
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
"""
            },
            {
                "role": "user",
                "content": data.answer
            }
        ]
    )

    level = response.choices[0].message.content.strip()

    student.level = level
    student.assessment_completed = "Yes"

    db.commit()

    return {
        "student": student.name,
        "level": level
    }


@app.get("/meta-webhook")
def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):

    if (
        hub_mode == "subscribe"
        and hub_verify_token == os.getenv("META_VERIFY_TOKEN")
    ):
        return Response(
            content=hub_challenge,
            media_type="text/plain"
        )

    raise HTTPException(
        status_code=403,
        detail="Verification failed"
    )
@app.post("/meta-webhook")
async def receive_message(
    request: Request,
    db: Session = Depends(get_db)
):
    data = await request.json()

    print("WEBHOOK META")
    print(data)

    try:
        value = data["entry"][0]["changes"][0]["value"]

        if "messages" not in value:
            return {"status": "ok"}

        incoming_message = value["messages"][0]
        phone = incoming_message["from"]
        message = incoming_message.get("text", {}).get("body", "").strip()

        if not message:
            send_whatsapp_message(
                phone,
                "Por enquanto consigo responder mensagens de texto. Me envie uma frase ou pergunta por escrito."
            )
            return {"status": "ok"}

        print("TELEFONE:", phone)
        print("TELEFONE ENVIO:", normalize_whatsapp_phone_for_send(phone))
        print("MENSAGEM:", message)

        reply = process_whatsapp_message(
            phone=phone,
            message=message,
            db=db
        )

        send_whatsapp_message(
            phone,
            reply
        )

    except Exception as e:
        print("Erro ao processar mensagem:", e)

    return {"status": "ok"}
