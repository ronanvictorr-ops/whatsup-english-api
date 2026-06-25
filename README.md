<div align="center">
  <img src="dashboard/whatsup-english-logo.jpg" alt="WhatsUp English" width="420">

  # WINGO | WhatsUp English

  **Inglês no seu ritmo. Pelo WhatsApp, com IA.**

  Professor virtual de inglês com aulas curtas, prática por texto e áudio,
  correção imediata e acompanhamento de progresso.

  ![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
  ![FastAPI](https://img.shields.io/badge/FastAPI-0.136-009688?logo=fastapi&logoColor=white)
  [![CI](https://github.com/ronanvictorr-ops/whatsup-english-api/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ronanvictorr-ops/whatsup-english-api/actions/workflows/ci.yml)
  ![Tests](https://img.shields.io/badge/tests-74%20passing-16a34a)
  ![Status](https://img.shields.io/badge/status-beta-f59e0b)
</div>

## Sobre o produto

O **WINGO** transforma o WhatsApp em uma experiência diária e personalizada de aprendizagem de inglês. Em vez de funcionar como um chatbot aberto, ele conduz o aluno por uma jornada pedagógica estruturada, com onboarding, avaliação de nível, aulas, escrita, quizzes e prática de pronúncia.

> **10 minutos de inglês por dia no WhatsApp.**

O projeto está em fase beta e já reúne a experiência conversacional, o painel visual do aluno/professor, a página comercial e a base operacional necessária para testes com usuários reais.

## O que já funciona

- Onboarding e avaliação inicial de nível.
- Currículo progressivo com 70 aulas estruturadas.
- Aulas guiadas e personalizadas por nível, objetivo e interesses.
- Exercícios de escrita, quizzes e correção com IA.
- Prática por áudio com transcrição.
- Avaliação acústica de pronúncia com Azure AI Speech.
- Memória pedagógica e memória de relacionamento por aluno.
- Agenda de aulas e automações acadêmicas.
- Relatório semanal e acompanhamento de progresso.
- Painel responsivo para aluno e professor em `/dashboard`.
- Página de vendas responsiva em `/`.
- Autenticação com JWT e acesso administrativo protegido.
- Saúde, métricas e auditoria operacional.

## Confiabilidade do webhook

O webhook da Meta foi projetado para evitar perda de estado e respostas duplicadas:

- Máquina de estados com transições explícitas.
- Idempotência de entrada por `message_id`.
- Chave independente para cada mensagem de saída.
- Retentativas controladas para Meta e OpenAI.
- Snapshot e restauração do estado quando a entrega falha.
- Retomada de mensagens com falha sem excluir o aluno.
- Cadência humanizada entre múltiplas respostas, com indicador de digitação quando disponível.
- Auditoria das decisões e transições.
- Métricas de volume, erros, latência, tentativas, tokens e custo estimado.

## Arquitetura

```mermaid
flowchart LR
    A[Aluno no WhatsApp] --> B[Meta Cloud API]
    B --> C[Webhook FastAPI]
    C --> D[Idempotência e auditoria]
    D --> E[Máquina de estados]
    E --> F[Fluxos pedagógicos]
    F --> G[OpenAI]
    F --> H[Azure AI Speech]
    E --> I[(PostgreSQL / SQLite)]
    C --> J[Painel e operações]
```

Os fluxos conversacionais ficam separados por responsabilidade:

```text
wingo/flows/
├── onboarding.py
├── assessment.py
├── lesson.py
├── writing.py
├── quiz.py
├── bot.py
└── router.py
```

## Tecnologias

- Python 3.11+
- FastAPI e Uvicorn
- SQLAlchemy
- PostgreSQL em produção e SQLite no desenvolvimento
- OpenAI API
- Azure AI Speech
- WhatsApp Cloud API (Meta)
- JWT e bcrypt
- HTML, CSS e JavaScript
- Render

## Executando localmente

### 1. Clone o repositório

```bash
git clone git@github.com:ronanvictorr-ops/whatsup-english-api.git
cd whatsup-english-api
```

### 2. Crie e ative o ambiente virtual

```bash
python -m venv venv
```

Windows:

```powershell
.\venv\Scripts\Activate.ps1
```

Linux ou macOS:

```bash
source venv/bin/activate
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 4. Configure o ambiente

Crie um arquivo `.env` na raiz. Use apenas as variáveis necessárias para o ambiente em que estiver trabalhando:

```env
DATABASE_URL=sqlite:///./whatsup.db
SECRET_KEY=troque-por-uma-chave-longa-e-aleatoria

OPENAI_API_KEY=
OPENAI_TTS_MODEL=gpt-4o-mini-tts
OPENAI_TTS_VOICE=alloy
OPENAI_TRANSCRIBE_MODEL=whisper-1

AZURE_SPEECH_KEY=
AZURE_SPEECH_REGION=brazilsouth

META_PHONE_NUMBER_ID=
META_ACCESS_TOKEN=
META_VERIFY_TOKEN=
META_APP_SECRET=
META_SIGNATURE_REQUIRED=true

DASHBOARD_ADMIN_TOKEN=
LOCAL_TIMEZONE=America/Sao_Paulo
LOCAL_UTC_OFFSET_HOURS=-3
ACADEMIC_AUTOMATIONS_ENABLED=true

RATE_LIMIT_ENABLED=true
RATE_LIMIT_LOGIN_REQUESTS=10
RATE_LIMIT_LOGIN_WINDOW_SECONDS=300
RATE_LIMIT_REGISTER_REQUESTS=5
RATE_LIMIT_REGISTER_WINDOW_SECONDS=3600
RATE_LIMIT_CHAT_REQUESTS=30
RATE_LIMIT_CHAT_WINDOW_SECONDS=60
RATE_LIMIT_ASSESSMENT_REQUESTS=10
RATE_LIMIT_ASSESSMENT_WINDOW_SECONDS=300
RATE_LIMIT_WEBHOOK_REQUESTS=60
RATE_LIMIT_WEBHOOK_WINDOW_SECONDS=60
```

Nunca envie o `.env`, tokens ou chaves de API para o GitHub.

## Rate limiting

O WINGO possui protecao de volume no proprio codigo para reduzir abuso e
loops: cadastro, login, chat, avaliacao de pronuncia e webhook passam por
janelas deslizantes em memoria. Em producao, mantenha `RATE_LIMIT_ENABLED=true`.

As variaveis `RATE_LIMIT_<ESCOPO>_REQUESTS` e
`RATE_LIMIT_<ESCOPO>_WINDOW_SECONDS` permitem ajustar cada escopo sem mudar o
codigo. Os escopos atuais sao `LOGIN`, `REGISTER`, `CHAT`, `ASSESSMENT` e
`WEBHOOK`.

### 5. Inicie a aplicação

```bash
# terminal 1: API e webhook
uvicorn main:app --reload

# terminal 2: aulas, desafios e relatórios agendados
python worker.py
```

O servidor web não executa automações em background. O `worker.py` é o único
processo responsável pelo agendamento; o advisory lock do PostgreSQL continua
protegendo contra execução duplicada durante reinícios ou sobreposição.

Principais endereços locais:

| Recurso | URL |
|---|---|
| Página de vendas | `http://127.0.0.1:8000/` |
| Painel | `http://127.0.0.1:8000/dashboard` |
| Swagger | `http://127.0.0.1:8000/docs` |
| Saúde operacional | `http://127.0.0.1:8000/ops/health` |

## Configurando o WhatsApp

No painel da Meta, configure o webhook com a URL pública da aplicação:

```text
https://SEU-DOMINIO/meta-webhook
```

Use em `META_VERIFY_TOKEN` o mesmo token informado na configuração da Meta e inscreva o campo `messages`. Durante o desenvolvimento, a aplicação local precisa ser exposta por um túnel HTTPS.

`META_APP_SECRET` deve receber a chave secreta do aplicativo configurado na Meta. Em produção, a assinatura `X-Hub-Signature-256` é obrigatória; webhooks sem assinatura válida são rejeitados.

## Avaliação de pronúncia

Com `AZURE_SPEECH_KEY` e `AZURE_SPEECH_REGION` configurados, o WINGO utiliza o Azure AI Speech para calcular notas acústicas de precisão, fluência, completude e prosódia, além de identificar palavras e fonemas que precisam de atenção.

Sem essas credenciais, o áudio ainda pode ser transcrito, mas o sistema informa que a avaliação acústica não está disponível. Ele não cria pontuações fictícias.

## Testes

A suíte cobre as transições de estado, os fluxos pedagógicos, idempotência, retentativas, recuperação do webhook, painel e avaliação de pronúncia.

```bash
python -m unittest discover -s tests -v
```

## Migrações de banco

O esquema é versionado com Alembic. A aplicação não cria nem altera tabelas
durante a importação; no Render, `alembic upgrade head` é executado antes do
Uvicorn pelo `Procfile`.

```bash
# aplicar todas as migrações pendentes
alembic upgrade head

# conferir a versão instalada
alembic current

# criar uma nova migração a partir dos models
alembic revision --autogenerate -m "descricao da mudanca"

# voltar uma versão (migrações posteriores à baseline)
alembic downgrade -1
```

A primeira revisão é uma baseline não destrutiva: ela adota bancos existentes
e cria o esquema completo em instalações novas. Por segurança, o downgrade da
baseline não apaga tabelas históricas; revisões seguintes devem sempre declarar
`upgrade()` e `downgrade()` reversíveis.

Estado atual: **74 testes aprovados**, incluindo validações de arquitetura,
worker, fluxos pedagógicos, webhook, idempotência, segurança, painel e
pronúncia, além de rate limiting. O mesmo conjunto é executado automaticamente
no GitHub Actions.

## Endpoints principais

| Área | Endpoints |
|---|---|
| Autenticação | `POST /register`, `POST /login`, `GET /me` |
| Aprendizagem | `POST /chat`, `POST /assessment`, `POST /quiz` |
| Progresso | `GET /progress`, `GET /ranking`, `GET /students/{id}/learning-records` |
| Agenda | `GET/POST /students/{id}/lesson-schedule` |
| Painel | `GET /dashboard/api/student`, `GET /dashboard/api/teacher` |
| Operações | `GET /ops/health`, `GET /ops/metrics`, `GET /ops/state-transitions` |
| WhatsApp | `GET/POST /meta-webhook` |

A especificação completa e interativa está disponível em `/docs` durante a execução.

## Estrutura do projeto

```text
whatsup-english-api/
├── .github/workflows/ci.yml # CI de testes e migrações
├── dashboard/              # Painel do aluno e professor
├── sales/                  # Página comercial
├── tests/                  # Testes automatizados
├── wingo/
│   ├── api.py                # Rotas HTTP e endpoints
│   ├── automations.py        # Rotinas acadêmicas agendadas
│   ├── flows/              # Fluxos da jornada pedagógica
│   ├── idempotency.py      # Garantias de entrada e saída
│   ├── observability.py    # Eventos e métricas
│   ├── phones.py            # Normalização de telefones
│   ├── pronunciation.py    # Integração acústica com Azure
│   ├── rate_limit.py       # Limites de volume por escopo
│   ├── retries.py          # Retentativas de serviços externos
│   ├── security.py          # JWT, autorização e assinatura Meta
│   ├── states.py            # Máquina de estados
│   └── webhook.py           # Entrada e entrega confiável do WhatsApp
├── migrations/              # Versões Alembic do banco
├── alembic.ini
├── database.py
├── main.py
├── models.py
├── pedagogy.py
├── worker.py                # Processo separado de automações
├── PRODUCT.md
└── requirements.txt
```

## Deploy no Render

Crie um **Web Service** usando:

Build command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT
```

### Worker de automações

O processo separado já está implementado e testado, com este start command:

```bash
python worker.py
```

**Situação atual:** a ativação do serviço separado no Render foi adiada para
evitar custo adicional. A produção permanece na versão anterior, que mantém as
automações dentro do processo web. Não promova a versão modular para produção
antes de criar um Background Worker ou adaptar o comando para um Cron Job.

Quando ativado, o Web Service e o worker devem compartilhar as mesmas variáveis
de ambiente, incluindo `DATABASE_URL`, credenciais Meta/OpenAI e
`ACADEMIC_AUTOMATIONS_ENABLED=true`. Não configure o worker como uma segunda
instância web.

Em produção, configure `DATABASE_URL` com PostgreSQL e cadastre as demais variáveis no painel do Render. Não armazene segredos no repositório.

## CI/CD e proteção de deploy

O workflow [`.github/workflows/ci.yml`](.github/workflows/ci.yml) está ativo e executa em
pull requests e pushes para `main`/`feature-login`. Ele instala as dependências
com Python 3.12.8, compila o projeto, aplica Alembic em banco limpo, executa a
suíte completa de 74 testes e confirma que o banco chegou ao `head`.

Para tornar a proteção efetiva:

1. No GitHub, proteja `main` em **Settings > Branches** e exija o status
   **Tests and migrations** antes do merge.
2. No Render, altere Auto-Deploy para **After CI Checks Pass** nos dois serviços.
3. Faça o Render acompanhar `main`; `feature-login` deve deixar de ser branch de
   deploy depois da transição.

Sem essas configurações externas, o workflow informa falhas, mas GitHub e Render
ainda podem aceitar ou implantar um commit reprovado.

## Próximos passos

- Validar a avaliação de pronúncia com áudios reais e diferentes sotaques.
- Medir retenção diária e conclusão de aulas no beta.
- Implementar revisão espaçada automática.
- Adicionar sistema de pagamento e assinatura.
- Estruturar suporte humano e operação do beta.

O planejamento comercial e pedagógico detalhado está em [`PRODUCT.md`](PRODUCT.md).

## Autor

Desenvolvido por **Ronan Victor Cunha Santos**.

Projeto em desenvolvimento para validação beta da plataforma WhatsUp English.
