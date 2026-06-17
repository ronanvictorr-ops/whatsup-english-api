LESSON_STAGE_OBJECTIVES = {
    "context_question": "Diagnose what the student already understands about the topic.",
    "short_explanation": "Teach one clear concept with one bilingual example.",
    "more_examples": "Give three realistic examples and model pronunciation.",
    "comprehension": "Check if the student understands meaning before production.",
    "structure": "Show the sentence pattern or grammar formula clearly.",
    "exercise_1": "Practice one controlled answer with high chance of success.",
    "exercise_2": "Practice a second controlled answer with a small variation.",
    "production": "Make the student create a full sentence.",
    "conversation": "Use the structure in a real conversation question.",
    "expansion": "Connect the topic to the student's life or interests.",
    "challenge": "Close the lesson with a tiny mission and summarize progress.",
}


LEVEL_EXERCISE_STYLE = {
    "Basic": {
        "english_ratio": "30-40%",
        "exercise_type": "translation, fill-in-the-blank, one short sentence",
        "feedback": "Portuguese explanation with simple English examples",
        "advance_when": "student can understand one example and produce one short guided sentence",
    },
    "Basic 2": {
        "english_ratio": "40-50%",
        "exercise_type": "short answers, simple routine sentences, guided mini-dialogues",
        "feedback": "Portuguese explanation with more English prompts",
        "advance_when": "student can produce two simple sentences with minor support",
    },
    "Intermediate": {
        "english_ratio": "55-70%",
        "exercise_type": "sentence transformation, short answers, personal examples",
        "feedback": "mixed Portuguese and English, focusing on grammar and naturalness",
        "advance_when": "student can answer a personal question using the target structure",
    },
    "Advanced": {
        "english_ratio": "85-100%",
        "exercise_type": "opinion, storytelling, nuance, correction of naturalness",
        "feedback": "English feedback with concise correction notes",
        "advance_when": "student can explain ideas clearly with few blocking mistakes",
    },
    "Fluent": {
        "english_ratio": "100%",
        "exercise_type": "debate, nuance, idiomatic language, precision",
        "feedback": "English feedback focused on sophistication and style",
        "advance_when": "student can sustain a natural discussion and refine expression",
    },
}


PLACEMENT_RUBRIC = {
    "Basic": {
        "evidence": [
            "student knows isolated words or no English",
            "student cannot form independent sentences yet",
            "student needs Portuguese support most of the time",
        ],
        "start_lesson": 1,
    },
    "Basic 2": {
        "evidence": [
            "student can write simple memorized sentences",
            "student uses basic vocabulary about self, routine, likes, food, places",
            "student makes frequent grammar errors but meaning is often clear",
        ],
        "start_lesson": 11,
    },
    "Intermediate": {
        "evidence": [
            "student can answer personal questions in short paragraphs",
            "student can use present, past, or future with some mistakes",
            "student can describe experiences or plans",
        ],
        "start_lesson": 21,
    },
    "Advanced": {
        "evidence": [
            "student can explain opinions and abstract ideas",
            "student uses connectors and varied vocabulary",
            "student needs correction mostly for precision and naturalness",
        ],
        "start_lesson": 51,
    },
    "Fluent": {
        "evidence": [
            "student communicates naturally across complex topics",
            "student handles nuance, debate, storytelling, and negotiation",
            "student needs refinement, not basic instruction",
        ],
        "start_lesson": 61,
    },
}


CORRECTION_RUBRIC = {
    "meaning": "Did the student communicate the intended idea?",
    "grammar": "Did the student use the target structure correctly?",
    "vocabulary": "Did the student choose useful and natural words?",
    "pronunciation": "If audio was sent, was the phrase understandable and confident?",
    "independence": "Did the student answer without needing too much prompting?",
}


PRONUNCIATION_RUBRIC = {
    "understandability": "Could the spoken phrase be transcribed and understood?",
    "target_phrase": "Did the student attempt the requested phrase or answer?",
    "rhythm": "Does the phrase seem complete and natural from the transcription?",
    "confidence": "Is the answer clear enough to repeat and improve?",
    "safety_rule": "Do not claim phonetic certainty unless the system has explicit speech-analysis data.",
}


SPACED_REVIEW_INTERVALS = [1, 3, 7, 14, 30]


TOPIC_OBJECTIVES = {
    "Greetings": {
        "objective": "Greet someone and introduce yourself.",
        "can_do": "I can say hello, ask a name, and say my name.",
        "target_language": ["Hi.", "Hello.", "Good morning.", "What's your name?", "My name is..."],
        "controlled_exercises": [
            "Complete: My name ___ Ronan.",
            "Complete: ___ your name?",
            "Translate: Oi, meu nome e Ronan.",
        ],
        "speaking_task": "Send a short audio saying: Hi, my name is [your name].",
    },
    "Present Continuous": {
        "objective": "Talk about actions happening now.",
        "can_do": "I can say what I or another person is doing right now.",
        "target_language": ["I am studying.", "She is reading.", "They are playing soccer."],
        "controlled_exercises": [
            "Complete: I ___ studying.",
            "Complete: She ___ reading.",
            "Translate: Eu estou estudando ingles.",
        ],
        "speaking_task": "Send a short audio answering: What are you doing right now?",
    },
    "Restaurant Conversation": {
        "objective": "Order food or drink politely.",
        "can_do": "I can ask for food or water politely in English.",
        "target_language": ["Can I have water, please?", "I would like a coffee.", "The bill, please."],
        "controlled_exercises": [
            "Complete: Can I have ___, please?",
            "Translate: Eu gostaria de agua.",
            "Answer: What would you like?",
        ],
        "speaking_task": "Send a short audio ordering one item politely.",
    },
}


def normalize_level(level: str):
    if level in LEVEL_EXERCISE_STYLE:
        return level

    if level and "advanced" in level.lower():
        return "Advanced"

    if level and "fluent" in level.lower():
        return "Fluent"

    if level and "intermediate" in level.lower():
        return "Intermediate"

    if level and "basic 2" in level.lower():
        return "Basic 2"

    return "Basic"


def build_default_lesson_design(lesson: dict):
    focus = lesson.get("focus", "")
    title = lesson.get("title", "English")

    return {
        "objective": f"Use {title} in a practical WhatsApp conversation.",
        "can_do": f"I can understand and use basic language about {title}.",
        "target_language": [item.strip() for item in focus.split(";") if item.strip()][:5],
        "controlled_exercises": [
            f"Write one short sentence using: {title}.",
            f"Translate one useful phrase connected to: {focus}.",
            f"Answer one simple question about: {title}.",
        ],
        "speaking_task": f"Send a short audio using one phrase from {title}.",
    }


def get_lesson_design(lesson: dict):
    return TOPIC_OBJECTIVES.get(
        lesson.get("title", ""),
        build_default_lesson_design(lesson)
    )


def get_level_pedagogy(level: str):
    return LEVEL_EXERCISE_STYLE[normalize_level(level)]


def build_pedagogical_context(lesson: dict, level: str, stage: str):
    design = get_lesson_design(lesson)
    level_style = get_level_pedagogy(level)
    stage_objective = LESSON_STAGE_OBJECTIVES.get(stage, "Continue the guided lesson.")

    return (
        "Pedagogical design:\n"
        f"- Lesson objective: {design['objective']}\n"
        f"- Can-do statement: {design['can_do']}\n"
        f"- Current stage objective: {stage_objective}\n"
        f"- Target language: {', '.join(design['target_language']) or lesson.get('focus', '')}\n"
        f"- Controlled exercises: {' | '.join(design['controlled_exercises'])}\n"
        f"- Speaking task: {design['speaking_task']}\n"
        f"- Level English ratio: {level_style['english_ratio']}\n"
        f"- Exercise style: {level_style['exercise_type']}\n"
        f"- Feedback style: {level_style['feedback']}\n"
        f"- Advancement criterion: {level_style['advance_when']}\n"
        f"- Correction rubric: meaning, grammar, vocabulary, pronunciation, independence\n"
        f"- Pronunciation rubric: understandability, target phrase, rhythm, confidence\n"
        f"- Spaced review intervals in days: {', '.join(str(day) for day in SPACED_REVIEW_INTERVALS)}"
    )


def get_advancement_criterion(level: str):
    return get_level_pedagogy(level)["advance_when"]


def get_placement_rubric_text():
    lines = ["Placement rubric:"]

    for level, data in PLACEMENT_RUBRIC.items():
        lines.append(f"- {level}: " + "; ".join(data["evidence"]))

    return "\n".join(lines)
