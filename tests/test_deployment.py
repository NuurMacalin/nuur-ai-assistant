import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.documents import Document

from app.config import Settings
from app.index import index_pdf
from app.routes.health import router


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(router)
        app.state.settings = Settings(google_api_key="test-only-key")
        self.qdrant = Mock()
        app.state.qdrant_client = self.qdrant
        self.client = TestClient(app)

    def test_existing_index_is_ready(self):
        self.qdrant.get_collection.return_value = SimpleNamespace(points_count=13)
        response = self.client.get('/ready')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['knowledge_base'], 'indexed')

    def test_empty_index_is_not_ready(self):
        self.qdrant.get_collection.return_value = SimpleNamespace(points_count=0)
        self.assertEqual(self.client.get('/ready').status_code, 503)

    def test_storage_errors_do_not_leak_provider_details(self):
        self.qdrant.get_collection.side_effect = RuntimeError('private connection details')
        response = self.client.get('/ready')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private connection details', response.text)
        self.assertEqual(self.client.get('/health').status_code, 200)


class IndexingTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(google_api_key='test-only-key', qdrant_collection='test_collection')
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.pdf = Path(self.directory.name) / 'sample.pdf'
        self.pdf.write_bytes(b'synthetic PDF fixture')
        self.client = Mock()
        self.client.collection_exists.return_value = False
        self.documents = [Document(page_content='A synthetic document.', metadata={'page': 0})]

    def test_existing_collection_is_preserved_without_google_calls(self):
        self.client.collection_exists.return_value = True
        self.client.count.return_value = SimpleNamespace(count=13)
        with patch('app.index.create_qdrant_client', return_value=self.client):
            with patch('app.index.create_embeddings') as embeddings:
                self.assertEqual(index_pdf(self.settings, self.pdf), 13)
        embeddings.assert_not_called()
        self.client.upsert.assert_not_called()
        self.client.create_collection.assert_not_called()
        self.client.close.assert_called_once()

    def test_initial_index_uses_configured_collection_and_matching_payload(self):
        embeddings = Mock()
        embeddings.embed_documents.return_value = [[0.1, 0.2, 0.3]]
        with patch('app.index.create_qdrant_client', return_value=self.client):
            with patch('app.index.load_pdf_documents', return_value=self.documents):
                with patch('app.index.create_embeddings', return_value=embeddings):
                    self.assertEqual(index_pdf(self.settings, self.pdf), 1)
        self.assertEqual(self.client.create_collection.call_args.kwargs['collection_name'], 'test_collection')
        upsert = self.client.upsert.call_args
        self.assertEqual(upsert.args[0], 'test_collection')
        self.assertEqual(upsert.kwargs['points'][0].payload['page_content'], 'A synthetic document.')
        self.assertEqual(upsert.kwargs['points'][0].vector, [0.1, 0.2, 0.3])

    def test_embedding_failure_does_not_create_or_clear_a_collection(self):
        embeddings = Mock()
        embeddings.embed_documents.side_effect = RuntimeError('Provider failure')
        with patch('app.index.create_qdrant_client', return_value=self.client):
            with patch('app.index.load_pdf_documents', return_value=self.documents):
                with patch('app.index.create_embeddings', return_value=embeddings):
                    with self.assertRaises(RuntimeError):
                        index_pdf(self.settings, self.pdf)
        self.client.create_collection.assert_not_called()
        self.client.delete_collection.assert_not_called()
        self.client.upsert.assert_not_called()


class SettingsTests(unittest.TestCase):
    def test_credentials_are_not_in_configuration_repr(self):
        settings = Settings(google_api_key='private-google-key', qdrant_api_key='private-qdrant-key')
        self.assertNotIn('private-google-key', repr(settings))
        self.assertNotIn('private-qdrant-key', repr(settings))

    def test_environment_model_selection_is_used(self):
        with patch('app.config.load_environment'):
            with patch.dict('os.environ', {'GOOGLE_API_KEY': 'test-key', 'GEMINI_CHAT_MODEL': 'configured-model', 'QDRANT_COLLECTION': 'configured-collection'}, clear=True):
                settings = Settings.from_environment()
        self.assertEqual(settings.chat_model, 'configured-model')
        self.assertEqual(settings.qdrant_collection, 'configured-collection')

    def test_missing_key_fails_with_configuration_instructions(self):
        with self.assertRaisesRegex(RuntimeError, 'GOOGLE_API_KEY'):
            Settings(google_api_key='').require_google_key()


if __name__ == '__main__':
    unittest.main()
