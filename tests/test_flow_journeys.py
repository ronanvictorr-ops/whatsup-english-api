import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import main
from database import Base
from models import ConversationDB, LearningRecordDB, LessonSessionDB, PersonalNoteDB, StudentDB


class FlowJourneyTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def create_student(self, stage=0, **overrides):
        values = {
            "phone": "5511988888888",
            "email": "journey@whatsapp.local",
            "password": "test",
            "name": "Journey Student",
            "level": "Basic",
            "preferred_language": "Portuguese",
            "assessment_completed": "No",
            "learning_goal": "Conversation",
            "interests": "travel",
            "onboarding_notes": "[]",
            "current_lesson": 1,
            "lesson_stage": "context_question",
            "messages_in_current_lesson": 0,
            "current_stage": stage,
            "schedule_completed": "No",
            "xp": 0,
        }
        values.update(overrides)
        student = StudentDB(**values)
        self.db.add(student)
        self.db.commit()
        self.db.refresh(student)
        return student

    def send(self, student, message):
        reply = main.process_whatsapp_message(student.phone, message, self.db)
        self.db.refresh(student)
        return reply

    def test_onboarding_happy_path_reaches_lesson(self):
        student = self.create_student(stage=0, name="", interests="")

        replies = self.send(student, "oi")
        self.assertEqual(student.current_stage, 2)
        self.assertIsInstance(replies, list)
        self.assertEqual(len(replies), 3)
        self.assertIn("primeiro contato", replies[1].lower())
        self.assertIn("nome", replies[2].lower())

        invalid_reply = self.send(student, "sim")
        self.assertEqual(student.current_stage, 2)
        self.assertIn("nome", invalid_reply.lower())

        self.send(student, "Ronan")
        self.assertEqual(student.current_stage, 3)
        self.assertEqual(student.name, "Ronan")

        self.send(student, "Quero aprender ingles para viajar e trabalhar")
        self.assertEqual(student.current_stage, 35)

        self.send(student, "Gosto de musica, filmes e tecnologia")
        self.assertEqual(student.current_stage, 4)
        self.assertIn("musica", student.interests.lower())

        self.send(student, "nao")
        self.assertEqual(student.current_stage, 70)
        self.assertEqual(student.assessment_completed, "Yes")

        invalid_schedule = self.send(student, "qualquer hora")
        self.assertEqual(student.current_stage, 70)
        self.assertIn("horario", invalid_schedule.lower())

        self.send(student, "todos os dias as 19h")
        self.assertEqual(student.current_stage, 7)
        self.assertEqual(student.schedule_completed, "Yes")
        self.assertIn("19:00", student.lesson_schedule)

    def test_assessment_five_answers_persist_level_and_advance(self):
        student = self.create_student(stage=6)
        self.send(student, "sim")
        self.assertEqual(student.current_stage, 50)

        placement = {
            "level": "Intermediate",
            "summary": "Good functional English.",
            "strengths": ["Clear ideas"],
            "improvements": ["Verb tense"],
        }
        with patch.object(main, "is_valid_placement_answer", return_value=True), patch.object(
            main, "evaluate_placement_test_details", return_value=placement
        ):
            for expected_stage in (51, 52, 53, 54):
                self.send(student, "This is a complete English answer.")
                self.assertEqual(student.current_stage, expected_stage)
            final_reply = self.send(student, "I would travel and practice every day.")

        self.assertEqual(student.current_stage, 70)
        self.assertEqual(student.assessment_completed, "Yes")
        self.assertEqual(student.level, "Intermediate")
        self.assertIsInstance(final_reply, list)
        self.assertEqual(len(final_reply), 2)
        self.assertIn("placement_answer_5", student.onboarding_notes)

    def test_lesson_start_creates_session_and_keeps_guided_state(self):
        student = self.create_student(
            stage=7,
            assessment_completed="Yes",
            schedule_completed="Yes",
        )

        reply = self.send(student, "vamos comecar")

        session = self.db.query(LessonSessionDB).filter_by(student_id=student.id).one()
        self.assertEqual(student.current_stage, 7)
        self.assertEqual(student.lesson_stage, "context_question")
        self.assertIsNotNone(student.last_lesson_date)
        self.assertEqual(session.status, "started")
        self.assertIsInstance(reply, list)
        self.assertTrue(reply)

    def test_writing_feedback_is_saved_and_can_return_to_quiz(self):
        student = self.create_student(stage=84, assessment_completed="Yes")
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs: None))
        )
        fake_response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="I worked yesterday. Good correction."))]
        )

        with patch.object(main, "get_openai_client", return_value=fake_client), patch.object(
            main, "call_with_retry", return_value=fake_response
        ):
            reply = self.send(student, "I work yesterday")

        exchange = self.db.query(ConversationDB).filter_by(student_id=student.id).one()
        self.assertEqual(student.current_stage, 84)
        self.assertIn("worked", reply)
        self.assertEqual(exchange.question, "I work yesterday")
        self.assertIn("worked", exchange.answer)

        quiz = self.send(student, "quero exercicios")
        self.assertEqual(student.current_stage, 7)
        self.assertEqual(quiz["type"], "buttons")

    def test_quiz_wrong_answer_then_three_correct_answers_add_xp(self):
        student = self.create_student(stage=7, assessment_completed="Yes")

        retry = self.send(
            student,
            "__button__:quiz:past_work_en:wrong:work::work",
        )
        self.assertEqual(student.xp, 0)
        self.assertEqual(retry["type"], "buttons")
        self.assertIn("Try again", retry["body"])

        first = self.send(
            student,
            "__button__:quiz:past_work_en:correct:worked::worked",
        )
        second = self.send(
            student,
            "__button__:quiz:past_travel_en:correct:traveled::traveled",
        )
        third = self.send(
            student,
            "__button__:quiz:past_cook_en:correct:cooked::cooked",
        )

        self.assertEqual(student.xp, 6)
        self.assertEqual(first[1]["type"], "buttons")
        self.assertEqual(second[1]["type"], "buttons")
        self.assertEqual(third[1]["type"], "buttons")
        self.assertIn("writing", third[1]["buttons"][0]["id"])

        writing_prompt = self.send(
            student,
            "__button__:practice:writing:en::Practice writing",
        )
        self.assertEqual(student.current_stage, 84)
        self.assertIn("duas frases curtas", writing_prompt)

    def test_explicit_topic_request_overrides_recent_past_simple_quiz(self):
        student = self.create_student(
            stage=7,
            assessment_completed="Yes",
            schedule_completed="Yes",
            lesson_stage="completed",
        )
        self.db.add(
            ConversationDB(
                student_id=student.id,
                question="quero exercicios",
                answer="Vamos praticar o Past Simple.",
            )
        )
        self.db.commit()

        with patch.object(
            main, "generate_ai_answer", return_value="Vamos praticar o futuro."
        ) as answer:
            reply = self.send(student, "Vamos praticar future")

        self.assertEqual(reply, "Vamos praticar o futuro.")
        instruction = answer.call_args.kwargs["ai_question"]
        self.assertIn("Future: will and going to", instruction)
        self.assertIn("Do not continue Past Simple", instruction)

    def test_quiz_menu_accepts_topic_choice(self):
        student = self.create_student(stage=7, assessment_completed="Yes")

        prompt = self.send(
            student,
            "__button__:practice:choose_topic:pt::Escolher tema",
        )

        self.assertIn("Qual tema", prompt)

    def test_more_quizzes_rotates_the_deterministic_block(self):
        student = self.create_student(stage=7, assessment_completed="Yes", xp=6)

        second_block = self.send(
            student,
            "__button__:practice:more_quiz:pt::Mais quizzes",
        )
        student.xp = 12
        self.db.commit()
        first_block = self.send(
            student,
            "__button__:practice:more_quiz:pt::Mais quizzes",
        )

        self.assertIn("homework last night", second_block["body"])
        self.assertIn("on a project", first_block["body"])
        self.assertNotEqual(second_block["body"], first_block["body"])

    def test_audio_can_be_replayed_from_recent_practice(self):
        student = self.create_student(
            stage=7,
            assessment_completed="Yes",
            schedule_completed="Yes",
            lesson_stage="completed",
        )
        self.db.add(
            ConversationDB(
                student_id=student.id,
                question="Como digo isso?",
                answer="Repeat after me:\nI am studying English.",
            )
        )
        self.db.commit()

        reply = self.send(student, "manda o audio de novo")

        self.assertIn("vou repetir", main.normalize_intent_text(reply))
        self.assertIn("I am studying English", reply)

    def test_chat_abbreviations_are_normalized_for_intents(self):
        normalized = main.normalize_intent_text("vc qro praticar agr, blz? pfv")

        self.assertEqual(
            normalized,
            "voce quero praticar agora, beleza? por favor",
        )

    def test_english_sentence_does_not_change_adaptive_reply_language(self):
        student = self.create_student(
            stage=7,
            level="Intermediate",
            preferred_language="Adaptive",
            assessment_completed="Yes",
        )

        self.assertEqual(
            main.get_quiz_interface_language(student, "I studied English yesterday."),
            "pt",
        )
        instruction = main.get_language_instruction("Adaptive", "Intermediate")
        self.assertIn("Use Portuguese", instruction)
        self.assertIn("Only conduct the conversation in English after an explicit", instruction)

    def test_visible_portuguese_is_polished_before_delivery(self):
        polished = main.polish_portuguese_text(
            "Otimo! Voce chegou ao proximo nivel de ingles. Quer audio e exercicios?"
        )

        self.assertEqual(
            polished,
            "\u00d3timo! Voc\u00ea chegou ao pr\u00f3ximo n\u00edvel de ingl\u00eas. Quer \u00e1udio e exerc\u00edcios?",
        )

    def test_bot_mode_answers_without_changing_state(self):
        student = self.create_student(
            stage=7,
            assessment_completed="Yes",
            lesson_stage="completed",
            xp=12,
        )

        with patch.object(main, "generate_ai_answer", return_value="A concise tutor answer.") as answer:
            reply = self.send(student, "What is the difference between do and make?")

        self.assertEqual(reply, "A concise tutor answer.")
        self.assertEqual(student.current_stage, 7)
        self.assertEqual(student.lesson_stage, "completed")
        self.assertEqual(student.xp, 12)
        answer.assert_called_once()

    def test_post_lesson_feedback_uses_choice_buttons(self):
        student = self.create_student(
            stage=7,
            assessment_completed="Yes",
            lesson_stage="completed",
        )
        self.db.add(
            LessonSessionDB(
                student_id=student.id,
                lesson_number=1,
                lesson_title="Greetings",
                status="completed",
                summary="Aula concluida: Greetings.",
            )
        )
        self.db.commit()

        with patch.object(main, "build_next_lesson_preview", return_value="Proxima aula: Introductions"):
            reply = main.build_post_lesson_feedback_message(student, self.db)

        self.assertEqual(reply["type"], "buttons")
        self.assertIn("Fechamento da aula", reply["body"])
        self.assertIn("Hoje voce aprendeu", reply["body"])
        self.assertIn("Sua missao", reply["body"])
        self.assertIn("Proximo passo", reply["body"])
        self.assertIn("Pequeno passo, mas passo real", reply["body"])
        self.assertEqual(
            [button["id"] for button in reply["buttons"]],
            ["post_lesson:review", "post_lesson:practice", "post_lesson:next_preview"],
        )

    def test_return_choice_buttons_are_handled_without_free_text_guessing(self):
        student = self.create_student(
            stage=7,
            assessment_completed="Yes",
            schedule_completed="Yes",
            lesson_stage="completed",
        )

        review = self.send(student, "__button__:return:review::Revisar")
        topic = self.send(student, "__button__:return:topic::Mudar tema")

        self.assertIn("Vamos revisar", review)
        self.assertIn("Greetings", review)

    def test_smart_return_prompt_continues_unfinished_lesson(self):
        student = self.create_student(
            stage=7,
            assessment_completed="Yes",
            schedule_completed="Yes",
            lesson_stage="short_explanation",
        )

        prompt = main.build_smart_return_prompt(student, self.db)

        self.assertEqual(prompt["type"], "buttons")
        self.assertIn("continuar a aula atual", prompt["body"])
        self.assertEqual(
            [button["id"] for button in prompt["buttons"]],
            ["return:continue", "return:review", "return:practice"],
        )

    def test_smart_return_prompt_prioritizes_recent_error(self):
        student = self.create_student(
            stage=7,
            assessment_completed="Yes",
            schedule_completed="Yes",
            lesson_stage="completed",
        )
        self.db.add(
            LearningRecordDB(
                student_id=student.id,
                skill="grammar",
                topic="Past Simple",
                original_text="I go yesterday",
                corrected_text="I went yesterday.",
                explanation="Use went for the past of go.",
            )
        )
        self.db.commit()

        prompt = main.build_smart_return_prompt(student, self.db)

        self.assertIn("I went yesterday.", prompt["body"])
        self.assertEqual(prompt["buttons"][0]["id"], "return:review")

    def test_smart_return_prompt_uses_personal_memory_when_no_error(self):
        student = self.create_student(
            stage=7,
            assessment_completed="Yes",
            schedule_completed="Yes",
            lesson_stage="completed",
        )
        self.db.add(
            PersonalNoteDB(
                student_id=student.id,
                category="travel",
                note="o aluno ia viajar para a Bahia",
            )
        )
        self.db.commit()
        self.db.refresh(student)

        prompt = main.build_smart_return_prompt(student, self.db)

        self.assertIn("Bahia", prompt["body"])
        self.assertEqual(prompt["buttons"][0]["id"], "return:personal")

    def test_post_lesson_practice_button_starts_tiny_conversation(self):
        student = self.create_student(
            stage=7,
            assessment_completed="Yes",
            schedule_completed="Yes",
            lesson_stage="completed",
        )

        with patch.object(main, "generate_ai_answer", return_value="Pergunta curta.") as answer:
            reply = self.send(student, "__button__:post_lesson:practice::Praticar conversa")

        self.assertEqual(reply, "Pergunta curta.")
        self.assertIn("post-lesson button", answer.call_args.kwargs["ai_question"])

    def test_short_time_request_switches_to_two_minute_micro_lesson(self):
        student = self.create_student(
            stage=7,
            assessment_completed="Yes",
            schedule_completed="Yes",
        )
        self.db.add(
            ConversationDB(
                student_id=student.id,
                question="vamos praticar",
                answer="Example: I cooked dinner yesterday.",
            )
        )
        self.db.commit()

        with patch.object(main, "generate_ai_answer", return_value="Microaula curta.") as answer:
            reply = self.send(student, "hoje nao posso muito, so 2 min")

        self.assertEqual(reply, "Microaula curta.")
        ai_question = answer.call_args.kwargs["ai_question"]
        self.assertIn("2-minute micro-lesson", ai_question)
        self.assertIn("I cooked dinner yesterday", ai_question)

    def test_more_quiz_avoids_recent_first_example(self):
        student = self.create_student(
            stage=7,
            assessment_completed="Yes",
            schedule_completed="Yes",
        )
        self.db.add(
            ConversationDB(
                student_id=student.id,
                question="quiz anterior",
                answer="Yesterday, I ___ on a project. Work -> worked.",
            )
        )
        self.db.commit()

        reply = self.send(student, "__button__:practice:more_quiz:pt::Mais quizzes")

        self.assertEqual(reply["type"], "buttons")
        self.assertIn("They ___ their homework", reply["body"])
        self.assertNotIn("Yesterday, I ___ on a project", reply["body"])

    def test_stuck_basic_student_gets_reformulation_example_and_hint_button(self):
        student = self.create_student(
            stage=7,
            assessment_completed="Yes",
            schedule_completed="Yes",
            current_lesson=1,
            lesson_stage="context_question",
        )

        reply = self.send(student, "nao entendi")

        self.assertEqual(reply["type"], "buttons")
        self.assertIn("Vou reformular", reply["body"])
        self.assertIn("Exemplo: Hello.", reply["body"])
        self.assertEqual(reply["buttons"][0]["id"], "lesson:hint")
        self.assertEqual(reply["buttons"][0]["title"], "Me de uma dica")

    def test_greetings_context_answer_is_handled_without_ai_fallback(self):
        student = self.create_student(
            stage=7,
            assessment_completed="Yes",
            schedule_completed="Yes",
            current_lesson=1,
            lesson_stage="context_question",
        )

        with patch.object(main, "generate_ai_answer") as answer:
            reply = self.send(student, "Hello")

        answer.assert_not_called()
        self.assertIn("esta correto", reply)
        self.assertIn("Hi e mais casual", reply)

    def test_greetings_intro_sequence_completes_without_recovery_loop(self):
        student = self.create_student(
            stage=7,
            assessment_completed="Yes",
            schedule_completed="Yes",
            current_lesson=1,
            lesson_stage="context_question",
        )

        with patch.object(main, "generate_ai_answer") as answer:
            hello_reply = self.send(student, "Hello")
            name_reply = self.send(student, "My name is Ana")
            question_reply = self.send(student, "What's your name?")
            final_reply = self.send(student, "My name is Ronan")

        answer.assert_not_called()
        all_replies = "\n".join([hello_reply, name_reply, question_reply, final_reply])
        self.assertNotIn("Tive um problema", all_replies)
        self.assertIn("Hi e mais casual", hello_reply)
        self.assertIn("funciona para se apresentar", name_reply)
        self.assertIn("What's your name", question_reply)
        self.assertIn("Hoje voce praticou", final_reply)
        self.assertEqual(student.lesson_stage, "completed")
        self.assertEqual(student.messages_in_current_lesson, 0)
        self.assertEqual(student.xp, 10)

    def test_greetings_active_session_resume_does_not_repeat_recovery_message(self):
        student = self.create_student(
            stage=7,
            assessment_completed="Yes",
            schedule_completed="Yes",
            current_lesson=1,
            lesson_stage="short_explanation",
            messages_in_current_lesson=1,
        )
        self.db.add(
            LessonSessionDB(
                student_id=student.id,
                lesson_number=1,
                lesson_title="Greetings",
                status="started",
            )
        )
        self.db.add(
            ConversationDB(
                student_id=student.id,
                question="Hello",
                answer="Muito bem! Hello esta correto.",
            )
        )
        self.db.commit()

        with patch.object(main, "generate_ai_answer") as answer:
            reply = self.send(student, "Vamos comecar")

        answer.assert_not_called()
        self.assertNotIn("Tive um problema", reply)
        self.assertIn("Meu nome e Ana", reply)
        self.assertEqual(student.lesson_stage, "short_explanation")

    def test_hint_button_gives_short_guided_hint(self):
        student = self.create_student(
            stage=7,
            assessment_completed="Yes",
            schedule_completed="Yes",
            lesson_stage="context_question",
        )

        with patch.object(main, "generate_ai_answer") as answer:
            reply = self.send(student, "__button__:lesson:hint::Me de uma dica")

        answer.assert_not_called()
        self.assertIn("Dica curta", reply)
        self.assertIn("Hello", reply)

    def test_plain_hint_text_does_not_fall_into_recovery_loop(self):
        student = self.create_student(
            stage=7,
            assessment_completed="Yes",
            schedule_completed="Yes",
            current_lesson=1,
            lesson_stage="more_examples",
        )

        with patch.object(main, "generate_ai_answer") as answer:
            reply = self.send(student, "Me de uma dica")

        answer.assert_not_called()
        self.assertNotIn("Tive um problema", reply)
        self.assertIn("What's your name", reply)

    def test_basic_levels_always_use_portuguese_guidance(self):
        for level in ("Basic", "Basic 2"):
            instruction = main.get_language_instruction("English", level)
            self.assertIn("Portuguese", instruction)
            self.assertIn("English only", instruction)

    def test_basic_student_cannot_switch_guidance_to_english(self):
        student = self.create_student(
            stage=7,
            level="Basic 2",
            preferred_language="English",
            assessment_completed="Yes",
        )

        reply = self.send(student, "continue somente em ingles")

        self.assertEqual(student.preferred_language, "Portuguese")
        self.assertIn("portugues", main.normalize_intent_text(reply))
        self.assertIn("exemplos e exercicios", main.normalize_intent_text(reply))

    def test_basic_quiz_interface_stays_in_portuguese(self):
        student = self.create_student(
            stage=7,
            level="Basic",
            preferred_language="English",
            assessment_completed="Yes",
        )

        self.assertEqual(main.get_quiz_interface_language(student, "I want exercises"), "pt")

    def test_explicit_language_request_exits_confirmation_state(self):
        student = self.create_student(
            stage=80,
            level="Advanced",
            preferred_language="Adaptive",
            assessment_completed="Yes",
        )

        reply = self.send(student, "portugues")

        self.assertEqual(student.current_stage, 7)
        self.assertEqual(student.preferred_language, "Portuguese")
        self.assertIn("continuar de onde paramos", main.normalize_intent_text(reply))

    def test_english_exercise_answer_does_not_reopen_language_confirmation(self):
        student = self.create_student(
            stage=80,
            level="Advanced",
            preferred_language="Adaptive",
            assessment_completed="Yes",
        )

        self.send(student, "nao")
        self.assertEqual(student.current_stage, 7)

        with patch.object(main, "generate_ai_answer", return_value="Correcao da atividade."):
            reply = self.send(student, "I studied English yesterday.")

        self.assertEqual(student.current_stage, 7)
        self.assertNotIn("continuar a aula em ingles", main.normalize_intent_text(reply))


if __name__ == "__main__":
    unittest.main()
