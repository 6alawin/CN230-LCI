import io
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError

from app.rag import generate_answer

SETTINGS = SimpleNamespace(gemini_api_key='test-key', gemini_generation_model='gemini-test')
HITS = [{'source_code': 'SRC-22', 'entity_id': 42, 'content': 'ใช้ก๊าซธรรมชาติ'}]

def response(answer):
    content = json.dumps({'candidates':[{'content':{'parts':[{'text':answer}]}}]}).encode()
    return io.BytesIO(content)

class RagTest(unittest.TestCase):
    @patch('app.rag.urlopen')
    def test_valid_citation(self, request):
        request.return_value = response('พบการใช้ก๊าซ [SRC-22 / exchange 42]')
        answer, message = generate_answer('ใช้เชื้อเพลิงอะไร', HITS, SETTINGS)
        self.assertIn('SRC-22', answer)
        self.assertIsNone(message)

    @patch('app.rag.urlopen')
    def test_rejects_fabricated_citation(self, request):
        request.return_value = response('ข้อมูลอื่น [SRC-21 / exchange 999]')
        answer, message = generate_answer('คำถาม', HITS, SETTINGS)
        self.assertIsNone(answer)
        self.assertIn('อ้างอิง', message)

    @patch('app.rag.urlopen')
    def test_rejects_unknown_id_inside_group(self, request):
        request.return_value = response('ผล [SRC-22 / exchange 42, 999]')
        answer, message = generate_answer('คำถาม', HITS, SETTINGS)
        self.assertIsNone(answer)
        self.assertIn('อ้างอิง', message)

    @patch('app.rag.urlopen')
    def test_quota_exhaustion_preserves_search(self, request):
        request.side_effect = HTTPError('https://example.invalid',429,'quota',{},None)
        answer, message = generate_answer('คำถาม', HITS, SETTINGS)
        self.assertIsNone(answer)
        self.assertIn('โควตา', message)

if __name__ == '__main__':
    unittest.main()
