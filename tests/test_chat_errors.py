import unittest
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from google.genai.errors import ClientError
from langchain_core.exceptions import ModelAuthenticationError

from app.routes.chat import router


class ChatErrorTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(router)
        app.state.vector_store = Mock()
        app.state.chat_model = Mock()
        self.client = TestClient(app)

    def assert_authentication_failure(self, error):
        with patch('app.routes.chat.query_user', side_effect=error):
            with self.assertLogs('app.routes.chat', level='ERROR') as logs:
                response = self.client.post('/chat', json={'message': 'Who is Nuur?'})
        self.assertEqual(response.status_code, 503)
        self.assertIn('could not authenticate', response.json()['detail'])
        self.assertNotIn('server-key-never-return', response.text)
        self.assertNotIn('server-key-never-return', '\n'.join(logs.output))
        self.assertIn('app/.env', '\n'.join(logs.output))

    def test_embedding_authentication_failure_is_not_a_generic_502(self):
        error = RuntimeError('Error embedding content: server-key-never-return')
        error.__cause__ = ClientError(401, {'error': {'message': 'API key not valid'}})
        self.assert_authentication_failure(error)

    def test_chat_authentication_failure_is_classified(self):
        self.assert_authentication_failure(ModelAuthenticationError('server-key-never-return'))

    def test_invalid_key_reported_as_400_is_also_classified(self):
        error = ClientError(400, {'error': {'message': 'API_KEY_INVALID server-key-never-return'}})
        self.assert_authentication_failure(error)

    def test_other_failures_keep_the_generic_response(self):
        with patch('app.routes.chat.query_user', side_effect=RuntimeError('private provider detail')):
            with self.assertLogs('app.routes.chat', level='ERROR'):
                response = self.client.post('/chat', json={'message': 'Who is Nuur?'})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()['detail'], 'The knowledge service is temporarily unavailable.')
        self.assertNotIn('private provider detail', response.text)


if __name__ == '__main__':
    unittest.main()
