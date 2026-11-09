import unittest
from unittest.mock import Mock

from langchain_core.documents import Document

from app.services.query import (
    GREETING_RESPONSES,
    UNSUPPORTED_LANGUAGE,
    detect_supported_language,
    query_user,
)


class GreetingTests(unittest.TestCase):
    def test_short_greetings_have_a_supported_language(self):
        for message, language in [("hi", "en"), (" Hello! ", "en"), ("ASC", "so"), ("Salaan!", "so")]:
            with self.subTest(message=message):
                self.assertEqual(detect_supported_language(message), language)

    def test_greetings_work_without_the_knowledge_service(self):
        store = Mock()
        model = Mock()
        for message, language in [("hi", "en"), ("salaan", "so")]:
            with self.subTest(message=message):
                self.assertEqual(query_user(message, store, model), GREETING_RESPONSES[language])
        store.similarity_search_with_score.assert_not_called()
        model.invoke.assert_not_called()

    def test_a_question_after_a_greeting_still_uses_sources(self):
        store = Mock()
        store.similarity_search_with_score.return_value = [
            (Document(page_content="Nuur develops software."), 0.9),
        ]
        model = Mock()
        model.invoke.return_value.content = "Nuur develops software."
        question = "Hello, who is Nuur?"
        self.assertEqual(query_user(question, store, model), "Nuur develops software.")
        store.similarity_search_with_score.assert_called_once_with(question, k=8)
        self.assertIn("Nuur develops software.", model.invoke.call_args.args[0][1].content)

    def test_identity_question_includes_summary_ranked_below_faq_chunks(self):
        store = Mock()
        matches = [
            (Document(page_content=f"FAQ fragment {index}: professional details."), 0.8 - index * 0.01)
            for index in range(7)
        ] + [(Document(page_content="PROFILE SUMMARY: Nuur is a software developer."), 0.70)]
        store.similarity_search_with_score.side_effect = lambda question, k: matches[:k]
        model = Mock()

        def answer_from_context(messages):
            text = messages[1].content
            return Mock(content="Nuur is a software developer." if "PROFILE SUMMARY" in text else "__OUT_OF_SCOPE__")

        model.invoke.side_effect = answer_from_context
        self.assertEqual(query_user("Who is Nuur?", store, model), "Nuur is a software developer.")

    def test_unsupported_language_does_not_query_sources(self):
        store = Mock()
        model = Mock()
        self.assertEqual(query_user("这是一个中文问题。", store, model), UNSUPPORTED_LANGUAGE)
        store.similarity_search_with_score.assert_not_called()
        model.invoke.assert_not_called()


if __name__ == "__main__":
    unittest.main()
