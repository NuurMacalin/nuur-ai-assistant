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
        store.similarity_search_with_score.assert_called_once_with(question, k=4)
        self.assertIn("Nuur develops software.", model.invoke.call_args.args[0][1].content)

    def test_unsupported_language_does_not_query_sources(self):
        store = Mock()
        model = Mock()
        self.assertEqual(query_user("这是一个中文问题。", store, model), UNSUPPORTED_LANGUAGE)
        store.similarity_search_with_score.assert_not_called()
        model.invoke.assert_not_called()


if __name__ == "__main__":
    unittest.main()
