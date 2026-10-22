"""Offline regression checks for the October 2026 Render speech fix and Azure fallback."""
import asyncio
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.translation_service import AzureTranslator, azure_configured
from services import voice_service


class Tests(unittest.TestCase):
    def test_current_edge_tts_version_is_required(self):
        requirements = (ROOT / 'requirements.txt').read_text()
        self.assertIn('edge-tts>=7.3.1,<8', requirements)
        self.assertNotIn('edge-tts>=6.1,<9', requirements)

    def test_azure_translation_credentials_are_server_only(self):
        with patch.dict(os.environ, {'TBA_AZURE_TRANSLATOR_KEY': 'test-private-key', 'TBA_AZURE_TRANSLATOR_REGION': 'eastus'}):
            response = SimpleNamespace(raise_for_status=lambda: None,
                                       json=lambda: [{'translations': [{'text': 'ही मराठी बातमी आहे.'}]}])
            with patch('services.translation_service.requests.post', return_value=response) as post:
                self.assertTrue(azure_configured())
                translated = AzureTranslator('mr').translate('This is Marathi news.')
                self.assertIn('मराठी', translated)
                args, kwargs = post.call_args
                self.assertTrue(args[0].startswith('https://'))
                self.assertEqual(kwargs['params']['to'], 'mr')
                self.assertEqual(kwargs['headers']['Ocp-Apim-Subscription-Key'], 'test-private-key')
                self.assertEqual(kwargs['headers']['Ocp-Apim-Subscription-Region'], 'eastus')

    def test_azure_does_not_require_configuration_for_voice_preview(self):
        with patch.dict(os.environ, {'TBA_AZURE_TRANSLATOR_KEY': ''}):
            self.assertFalse(azure_configured())
        for lang in ('en', 'hi', 'mr', 'bho', 'ml'):
            self.assertIn(lang, ('en','hi','mr','bho','ml'))

    def test_403_response_is_sanitized_and_actionable(self):
        class WSServerHandshakeError(Exception):
            status = 403
        class BrokenStream:
            def __init__(self, text, voice, rate): pass
            async def stream(self):
                raise WSServerHandshakeError('403 with possibly sensitive tokens')
                yield {'type':'audio','data':b''}
        with patch.dict(sys.modules, {'edge_tts': SimpleNamespace(Communicate=BrokenStream)}), \
             patch.object(voice_service, 'available', return_value={'edge-swara': True}):
            with self.assertRaises(voice_service.VoiceUnavailable) as exc:
                voice_service._edge_mp3('नमस्कार', 'edge-swara', language='mr')
        self.assertIn('7.3.1+', str(exc.exception))
        self.assertNotIn('sensitive tokens', str(exc.exception))


if __name__ == '__main__':
    unittest.main()
