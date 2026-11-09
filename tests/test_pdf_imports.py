import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
from uuid import uuid4

from langchain_core.documents import Document
from qdrant_client import QdrantClient, models

from app.config import Settings
from app.index import index_directory, index_pdf


class PdfImportTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.pdfs = self.root / 'pdfs'
        self.pdfs.mkdir()
        self.storage = self.root / 'qdrant'
        self.settings = Settings(google_api_key='test-only-key', qdrant_collection='test_collection')
        self.embeddings = Mock()
        self.embeddings.embed_documents.side_effect = lambda texts: [[0.1, 0.2, 0.3] for _ in texts]
        for patcher in (
            patch('app.index.create_qdrant_client', side_effect=self.client),
            patch('app.index.create_embeddings', return_value=self.embeddings),
            patch('app.index.load_pdf_documents', side_effect=lambda path: [
                Document(page_content=path.read_text(), metadata={'source': path.name, 'page': 0})
            ]),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def client(self, *_):
        return QdrantClient(path=str(self.storage))

    def pdf(self, name, text):
        path = self.pdfs / name
        path.write_text(text)
        return path

    def count(self):
        with closing(self.client()) as client:
            return client.count('test_collection', exact=True).count

    def test_adding_a_second_pdf_preserves_the_first(self):
        first = self.pdf('first.pdf', 'Nuur is a developer.')
        second = self.pdf('second.pdf', 'Nuur builds useful systems.')
        self.assertEqual(index_pdf(self.settings, first, append=True), 1)
        self.assertEqual(index_pdf(self.settings, second, append=True), 1)
        self.assertEqual(self.count(), 2)

    def test_repeated_import_does_not_call_google_or_duplicate_points(self):
        pdf = self.pdf('first.pdf', 'Nuur is a developer.')
        index_pdf(self.settings, pdf, append=True)
        self.embeddings.reset_mock()
        self.assertEqual(index_pdf(self.settings, pdf, append=True), 0)
        self.embeddings.embed_documents.assert_not_called()
        self.assertEqual(self.count(), 1)

    def test_renaming_an_identical_pdf_does_not_duplicate_points(self):
        first = self.pdf('first.pdf', 'Nuur is a developer.')
        renamed = self.pdf('renamed.pdf', 'Nuur is a developer.')
        index_pdf(self.settings, first, append=True)
        self.assertEqual(index_pdf(self.settings, renamed, append=True), 0)
        self.assertEqual(self.count(), 1)

    def test_old_windows_source_metadata_is_recognized(self):
        pdf = self.pdf('sample.pdf', 'Nuur is a developer.')
        with closing(self.client()) as client:
            client.create_collection('test_collection', vectors_config=models.VectorParams(size=3, distance=models.Distance.COSINE))
            client.upsert('test_collection', points=[models.PointStruct(
                id=str(uuid4()), vector=[0.1, 0.2, 0.3],
                payload={'page_content': 'Nuur is a developer.', 'metadata': {
                    'source': r'C:\xampp\htdocs\fastapi_llm\app\data\sample.pdf', 'page': 0,
                }},
            )])
        self.assertEqual(index_pdf(self.settings, pdf, append=True), 0)
        self.embeddings.embed_documents.assert_not_called()
        self.assertEqual(self.count(), 1)

    def test_partial_import_resumes_only_missing_chunks(self):
        pdf = self.pdf('large.pdf', 'A long synthetic profile with factual details. ' * 80)
        original_count = index_pdf(self.settings, pdf, append=True)
        self.assertGreater(original_count, 1)
        with closing(self.client()) as client:
            points, _ = client.scroll('test_collection', limit=100)
            client.delete('test_collection', points_selector=models.PointIdsList(points=[points[0].id]))
        self.embeddings.reset_mock()
        self.assertEqual(index_pdf(self.settings, pdf, append=True), 1)
        self.assertEqual(len(self.embeddings.embed_documents.call_args.args[0]), 1)
        self.assertEqual(self.count(), original_count)

    def test_dimension_mismatch_does_not_write_data(self):
        pdf = self.pdf('first.pdf', 'Nuur is a developer.')
        with closing(self.client()) as client:
            client.create_collection('test_collection', vectors_config=models.VectorParams(size=2, distance=models.Distance.COSINE))
        with self.assertRaisesRegex(ValueError, 'dimensions'):
            index_pdf(self.settings, pdf, append=True)
        self.assertEqual(self.count(), 0)

    def test_default_named_vector_collection_accepts_new_pdf(self):
        pdf = self.pdf('first.pdf', 'Nuur is a developer.')
        with closing(self.client()) as client:
            client.create_collection('test_collection', vectors_config={'': models.VectorParams(size=3, distance=models.Distance.COSINE)})
        self.assertEqual(index_pdf(self.settings, pdf, append=True), 1)
        self.assertEqual(self.count(), 1)

    def test_directory_imports_all_pdfs_once(self):
        self.pdf('first.pdf', 'Nuur is a developer.')
        self.pdf('second.PDF', 'Nuur builds useful systems.')
        self.pdf('notes.txt', 'This file is not a PDF.')
        self.assertEqual(index_directory(self.settings, self.pdfs), 2)
        self.assertEqual(index_directory(self.settings, self.pdfs), 0)
        self.assertEqual(self.count(), 2)

    def test_empty_directory_on_first_deployment_has_clear_instructions(self):
        with self.assertRaisesRegex(FileNotFoundError, 'Upload your private PDF'):
            index_directory(self.settings, self.pdfs)

    def test_empty_directory_does_not_remove_existing_knowledge(self):
        pdf = self.pdf('first.pdf', 'Nuur is a developer.')
        index_pdf(self.settings, pdf, append=True)
        empty = self.root / 'empty'
        empty.mkdir()
        self.assertEqual(index_directory(self.settings, empty), 0)
        self.assertEqual(self.count(), 1)


if __name__ == '__main__':
    unittest.main()
