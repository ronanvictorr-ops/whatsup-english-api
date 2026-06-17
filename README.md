# WhatsUp English API

API desenvolvida com FastAPI para o projeto WhatsUp English.

O posicionamento comercial, planos beta e roadmap de produto estao em:

```text
PRODUCT.md
```

## Tecnologias utilizadas

* Python
* FastAPI
* SQLite
* SQLAlchemy
* Pydantic
* Bcrypt
* JWT Authentication
* Git
* GitHub

---

## Instalação

Clone o projeto:

```bash
git clone git@github.com:ronanvictorr-ops/whatsup-english-api.git
```

Entre na pasta:

```bash
cd whatsup-english-api
```

Crie o ambiente virtual:

```bash
python -m venv venv
```

Ative o ambiente virtual:

### Windows

```bash
venv\Scripts\activate
```

### Linux/Mac

```bash
source venv/bin/activate
```

Instale as dependências:

```bash
pip install fastapi uvicorn sqlalchemy bcrypt python-jose[cryptography] python-multipart
```

Execute a aplicação:

```bash
uvicorn main:app --reload
```

A documentação ficará disponível em:

http://127.0.0.1:8000/docs

---

## Deploy no Render

Use o projeto como Web Service no Render.

Build command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Variaveis de ambiente necessarias:

```env
DATABASE_URL=
SECRET_KEY=
OPENAI_API_KEY=
META_PHONE_NUMBER_ID=
META_ACCESS_TOKEN=
META_VERIFY_TOKEN=
WINGO_INTRO_VIDEO_MEDIA_ID=
LOCAL_TIMEZONE=America/Sao_Paulo
LOCAL_UTC_OFFSET_HOURS=-3
ACADEMIC_AUTOMATIONS_ENABLED=true
```

Depois do deploy, configure o webhook da Meta com:

```text
https://SEU-SERVICO.onrender.com/meta-webhook
```

O campo `messages` precisa estar inscrito no webhook do WhatsApp.

---

# Funcionalidades

## Cadastro de Alunos

### POST /register

Cadastra um novo aluno.

Exemplo:

```json
{
  "name": "Ronan",
  "email": "ronan@email.com",
  "password": "123456"
}
```

---

## Login

### POST /login

Realiza login e retorna um token JWT.

Exemplo:

```json
{
  "email": "ronan@email.com",
  "password": "123456"
}
```

Resposta:

```json
{
  "access_token": "TOKEN_JWT",
  "token_type": "bearer"
}
```

---

## Listar Alunos

### GET /students

Retorna todos os alunos cadastrados.

---

## Buscar Aluno por ID

### GET /students/{student_id}

Exemplo:

```bash
/students/1
```

---

## Quiz

### POST /quiz

Envia uma resposta para correção.

Exemplo:

```json
{
  "answer": "I am fine."
}
```

Resposta:

```json
{
  "correct": true,
  "score": 10
}
```

---

## Salvar Progresso

### POST /progress

Salva uma pontuação.

Exemplo:

```json
{
  "student_id": 1,
  "score": 10
}
```

---

## Listar Progresso

### GET /progress

Retorna todos os registros de progresso.

---

## Ranking

### GET /ranking

Retorna as pontuações em ordem decrescente.

---

## Usuário Autenticado

### GET /me

Rota protegida por JWT.

Retorna os dados presentes no token do usuário autenticado.

---

# Estrutura do Projeto

```text
whatsup-english-api/
│
├── main.py
├── models.py
├── database.py
├── whatsup.db
├── README.md
├── .gitignore
└── venv/
```

---

# Próximas Funcionalidades

* Chat com IA
* Histórico de Conversas
* Níveis de Inglês
* Dashboard do Aluno
* Estatísticas de Aprendizagem
* Deploy em Produção
* Integração com OpenAI

---

# Autor

Ronan Victor Cunha Santos

Projeto criado para o desenvolvimento da plataforma de ensino de inglês WhatsUp English.
