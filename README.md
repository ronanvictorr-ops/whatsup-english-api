# WhatsUp English API

Backend da plataforma WhatsUp English.

## Tecnologias

- Python
- FastAPI
- SQLite
- SQLAlchemy

## Funcionalidades

- Cadastro de alunos
- Listagem de alunos
- Busca por ID
- Quiz
- Progresso
- Ranking

## Executar o projeto

Criar ambiente virtual:

```bash
python -m venv venv
```

Ativar ambiente virtual:

```bash
venv\Scripts\activate
```

Instalar dependências:

```bash
pip install fastapi uvicorn sqlalchemy
```

Executar servidor:

```bash
uvicorn main:app --reload
```
