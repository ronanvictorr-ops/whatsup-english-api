def get_openai_text(response):
    try:
        content = response.choices[0].message.content
    except (AttributeError, IndexError, TypeError) as error:
        raise RuntimeError("Resposta da OpenAI sem conteudo de texto.") from error

    text = str(content or "").strip()

    if not text:
        raise RuntimeError("Resposta da OpenAI vazia.")

    return text


def build_ai_unavailable_reply(
    language: str,
    level: str,
    lesson_title: str,
    is_basic_level: bool,
):
    if language == "English" and not is_basic_level:
        return (
            "I had a temporary issue with the smart correction, but we can keep practicing.\n\n"
            f"Let's stay with {lesson_title}. Send one short English sentence, or answer: "
            "What do you like?"
        )

    return (
        "A correcao inteligente ficou instavel agora, mas a aula nao precisa parar.\n\n"
        f"Vamos continuar com {lesson_title}. Escreva uma frase curta em ingles, ou responda:\n\n"
        "What do you like?\n\n"
        "Exemplo: I like music."
    )


def build_writing_practice_fallback(response_language: str):
    if response_language == "English":
        return (
            "I could not generate the full smart correction right now, but we can keep practicing.\n\n"
            "Write one new Past Simple sentence about yesterday.\n\n"
            "Example: I studied English yesterday."
        )

    return (
        "Nao consegui gerar a correcao inteligente completa agora, mas vamos continuar a pratica.\n\n"
        "Escreva uma nova frase no Past Simple sobre ontem.\n\n"
        "Exemplo: I studied English yesterday."
    )
