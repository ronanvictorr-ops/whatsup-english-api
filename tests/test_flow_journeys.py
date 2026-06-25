import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import main
from database import Base
from models import ConversationDB, LessonSessionDB, StudentDB


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

        reply = self.send(student, "manda o áudio de novo")

        self.assertIn("vou repetir o áudio", reply)
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
            "Ótimo! Você chegou ao próximo nível de inglês. Quer áudio e exercícios?",
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
