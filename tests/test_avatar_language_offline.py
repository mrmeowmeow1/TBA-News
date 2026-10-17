"""Standalone avatar-language route tests. No Flask, internet or optional ML packages needed.

Run: python tests/test_avatar_language_offline.py
The route is taken from app.py's actual AST so the behaviour under test is not a rewrite.
"""
import ast
import hashlib
import time
from contextlib import nullcontext
import logging
import re
import threading
import unittest
import sys
import types
from pathlib import Path
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'app.py'
TREE = ast.parse(SOURCE.read_text())
FN = next(node for node in TREE.body if isinstance(node, ast.FunctionDef) and node.name == 'avatar_narration')
FN.decorator_list = []
SCOPE = {
    're': re,
    'hashlib': hashlib,
    'time': time,
    'id_lock': lambda *args: nullcontext(),
    'TRANSLATION_PROVIDER_LOCK': threading.Lock(),
    'TRANSLATION_COOLDOWNS': {'Google':0.0,'MyMemory':0.0},
    'LOCK': threading.RLock(),
    'KNOWN_URLS': {},
    'FEED_META': {},
    'app': types.SimpleNamespace(logger=logging.getLogger('test-avatar')),
    'jsonify': lambda *args, **kw: args[0] if args else kw,
}
exec(compile(ast.Module(body=[FN], type_ignores=[]), str(SOURCE), 'exec'), SCOPE)


class Cache:
    def __init__(self): self.data = {}
    def get(self, key): return self.data.get(key)
    def set(self, key, value, ttl=0): self.data[key] = value


class FakeRequest:
    path = '/api/avatar/narration/id'
    body = {}
    def get_json(self, silent=True): return self.body


class FakeResponse:
    def __init__(self, data): self.data = data
    def get_json(self): return self.data


class AvatarTests(unittest.TestCase):
    def setUp(self):
        self.ident = 'a' * 20
        self.request = FakeRequest()
        self.request.body = {'language':'en'}
        SCOPE['request'] = self.request
        SCOPE['KNOWN_URLS'] = {self.ident: ('https://news.example/article', 1)}
        SCOPE['FEED_META'] = {self.ident: {'title':'Scientists announce solar power breakthrough', 'source':'Example News'}}
        self.article_cache = Cache()
        self.hindi_cache = Cache()
        SCOPE['ARTICLE_CACHE'] = self.article_cache
        SCOPE['HINDI_CACHE'] = self.hindi_cache
        SCOPE['article'] = lambda ident: FakeResponse({'summary_type':'unavailable'})
        SCOPE['TRANSLATION_COOLDOWNS'].update({'Google':0.0,'MyMemory':0.0})

    def call(self): return SCOPE['avatar_narration'](self.ident)

    def test_english_returns_200_without_translation(self):
        self.article_cache.set(self.ident, {'summary_type':'article', 'summary': 'Researchers have announced a breakthrough in clean solar energy. New materials may improve efficiency and reduce costs substantially.'})
        with patch.dict(sys.modules, {'deep_translator': None}):
            result = self.call()
        self.assertEqual(result['language'], 'en-IN')
        self.assertFalse(result['fallback'])
        self.assertEqual(result['source_type'], 'article')
        self.assertIn('Researchers', result['text'])
        self.assertEqual(result['translation'], 'not_required')

    def test_english_headline_only_instead_of_422(self):
        result = self.call()
        self.assertEqual(result['source_type'], 'headline')
        self.assertIn('complete article text is not available', result['text'])
        self.assertIn('Headline only', result['notice'])
        self.assertEqual(result['language'], 'en-IN')

    def test_english_even_if_article_extraction_busy(self):
        SCOPE['article'] = lambda ident: ({'error':'Busy'}, 503)
        self.assertEqual(self.call()['source_type'], 'headline')

    def test_english_short_description_uses_headline(self):
        self.article_cache.set(self.ident, {'summary_type':'description','summary':'Too short.'})
        self.assertEqual(self.call()['source_type'], 'headline')

    def test_english_description_keeps_source_limit(self):
        self.article_cache.set(self.ident, {'summary_type':'description','summary':'Scientists report promising solar power advances that could eventually improve renewable energy generation.'})
        result = self.call()
        self.assertEqual(result['source_type'], 'description')
        self.assertIn('publisher-provided description', result['notice'])

    def test_hindi_unavailable_falls_back_to_english(self):
        self.request.body = {'language':'hi'}
        with patch.dict(sys.modules, {'deep_translator': None}):
            result = self.call()
        self.assertTrue(result['fallback'])
        self.assertEqual(result['language'], 'en-IN')
        self.assertEqual(result['requested_language'], 'hi')
        self.assertIn('unavailable', result['notice'])

    def test_hindi_translation_success(self):
        self.request.body = {'language':'hi'}
        class Translator:
            def __init__(self, **kw): pass
            def translate(self, chunk): return 'यह आज की समाचार रिपोर्ट है।'
        with patch.dict(sys.modules, {'deep_translator':types.SimpleNamespace(GoogleTranslator=Translator, MyMemoryTranslator=Translator)}):
            result = self.call()
        self.assertEqual(result['language'], 'hi-IN')
        self.assertFalse(result['fallback'])
        self.assertIn('समाचार', result['text'])
        self.assertEqual(len(self.hindi_cache.data), 1)

    def test_mymemory_uses_supported_language_names_after_google_rate_limit(self):
        self.request.body = {'language': 'hi'}
        calls = []
        class Google:
            def __init__(self, **kwargs): calls.append(('google_init', kwargs))
            def translate(self, chunk):
                calls.append(('google', chunk))
                raise RuntimeError('TooManyRequests: 429')
        class Memory:
            def __init__(self, **kwargs):
                calls.append(('memory_init', kwargs))
                if kwargs != {'source': 'english', 'target':'hindi'}:
                    raise ValueError('Unsupported language')
            def translate(self, chunk):
                calls.append(('memory', chunk))
                return 'यह एक समाचार रिपोर्ट है।'
        stub = types.SimpleNamespace(GoogleTranslator=Google, MyMemoryTranslator=Memory)
        with patch.dict(sys.modules, {'deep_translator':stub}):
            result = self.call()
        self.assertEqual(result['language'], 'hi-IN')
        self.assertEqual(result['translation_provider'], 'MyMemory')
        self.assertTrue(any(c[0]=='memory_init' for c in calls))
        self.assertGreater(SCOPE['TRANSLATION_COOLDOWNS']['Google'], time.time())
        with patch.dict(sys.modules, {'deep_translator':stub}):
            result2 = self.call()
        self.assertEqual(result2, result)
        self.assertEqual(sum(c[0]=='google' for c in calls), 1)  # one 429, no repeat

    def test_both_providers_fail_then_cached_fallback(self):
        self.request.body = {'language': 'hi'}
        calls = []
        class Failing:
            def __init__(self, **kwargs): pass
            def translate(self, chunk):
                calls.append(chunk)
                raise RuntimeError('Service down')
        stub = types.SimpleNamespace(GoogleTranslator=Failing, MyMemoryTranslator=Failing)
        with patch.dict(sys.modules, {'deep_translator':stub}):
            result = self.call()
            result2 = self.call()
        self.assertEqual(len(calls), 2)  # Google + MyMemory once each
        self.assertEqual(result2, result)
        self.assertTrue(result['fallback'])
        self.assertEqual(result['language'], 'en-IN')
        self.assertEqual(result['translation'], 'unavailable')

    def test_long_mymemory_narration_is_clearly_labeled_shortened(self):
        self.request.body = {'language': 'hi'}
        self.article_cache.set(self.ident, {'summary_type':'article', 'summary': 'This is a long news sentence explaining the details. ' * 40})
        class Memory:
            def __init__(self, **kwargs): pass
            def translate(self, chunk):
                self_len = len(chunk)
                assert self_len <= 400
                return 'यह हिंदी समाचार है।'
        SCOPE['TRANSLATION_COOLDOWNS']['Google'] = time.time() + 600
        stub = types.SimpleNamespace(GoogleTranslator=Memory, MyMemoryTranslator=Memory)
        with patch.dict(sys.modules, {'deep_translator':stub}):
            result = self.call()
        self.assertEqual(result['language'], 'hi-IN')
        self.assertIn('opening part', result['notice'])

    def test_bad_language_is_400(self):
        self.request.body = {'language':'fr'}
        self.assertEqual(self.call()[1], 400)

    def test_invalid_id_is_400(self):
        self.assertEqual(SCOPE['avatar_narration']('invalid')[1], 400)

    def test_expired_story_is_404(self):
        SCOPE['KNOWN_URLS'] = {}
        self.assertEqual(self.call()[1], 404)

    def test_no_verified_title_or_text_is_422(self):
        SCOPE['FEED_META'][self.ident]['title'] = ''
        self.assertEqual(self.call()[1], 422)

    def test_legacy_endpoint_defaults_hindi(self):
        self.request.path = '/api/avatar/hindi/id'
        self.request.body = {}
        with patch.dict(sys.modules, {'deep_translator': None}):
            self.assertEqual(self.call()['requested_language'], 'hi')

if __name__ == '__main__': unittest.main(verbosity=2)
