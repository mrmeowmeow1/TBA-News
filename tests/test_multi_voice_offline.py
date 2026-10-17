"""Offline checks: selected voice bytes, response MIME, permitted model IDs."""
import ast
from contextlib import nullcontext
from pathlib import Path
import hashlib
import logging
import re
import sys
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services import voice_service

class FakeResponse:
    def __init__(self, data, mimetype=None):
        self.data = data
        self.mimetype = mimetype
        self.headers = {}
    def get_json(self): return self.data
class Cache:
    def __init__(self): self.items = {}
    def get(self, k): return self.items.get(k)
    def set(self, k, v, ttl=0): self.items[k] = v
class Request:
    body = {'language':'hi', 'provider':'edge-swara'}
    def get_json(self, silent=True): return self.body
request = Request()
scope = {
    're':re,'hashlib':hashlib,'request':request,
    'jsonify':lambda **kw: FakeResponse(kw),'Response':FakeResponse,
    'id_lock':lambda *args: nullcontext(),
    'FEMALE_AUDIO_CACHE':Cache(),
    'app':type('App',(),{'logger':logging.getLogger('voice-tests')})(),
    'avatar_narration':lambda i: FakeResponse({'language':'hi-IN','fallback':False,'text':'यह खबर पढ़ी जा रही है।'})
}
tree=ast.parse((ROOT/'app.py').read_text())
for func in ('avatar_voice_service_sample','avatar_voice_service'):
    node = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==func)
    node.decorator_list=[]
    exec(compile(ast.Module(body=[node],type_ignores=[]),'app.py','exec'),scope)

class Tests(unittest.TestCase):
    def setUp(self):
        scope['FEMALE_AUDIO_CACHE']=Cache()
        request.body={'language':'hi','provider':'edge-swara'}
    def test_audio_format_checks(self):
        self.assertTrue(voice_service.valid_audio(b'ID3'+b'\0'*40, 'edge-swara'))
        self.assertTrue(voice_service.valid_audio(b'RIFF'+b'\0'*40, 'piper'))
        self.assertFalse(voice_service.valid_audio(b'RIFF'+b'\0'*40, 'edge-swara'))
        self.assertFalse(voice_service.valid_audio(b'ID3'+b'\0'*40, 'piper'))
        self.assertEqual(voice_service.audio_mime('edge-madhur'), 'audio/mpeg')
        self.assertEqual(voice_service.audio_mime('piper-rohan'), 'audio/wav')
    def test_swara_and_madhur_sample_as_mp3(self):
        calls=[]
        def synth(t,p):calls.append((t,p));return b'ID3'+b'\0'*100
        with patch.object(voice_service,'available',return_value={'edge-swara':True,'edge-madhur':True}),patch.object(voice_service,'synthesize_hindi',side_effect=synth):
            for name in ('edge-swara','edge-madhur'):
                request.body['provider']=name
                res=scope['avatar_voice_service_sample']()
                self.assertEqual(res.mimetype,'audio/mpeg')
                self.assertEqual(res.data[:3],b'ID3')
            self.assertEqual(len(calls),2)
            self.assertEqual(calls[1][1],'edge-madhur')
    def test_real_article_source_is_preserved(self):
        captured=[]
        request.body={'language':'hi','provider':'edge-madhur','text':'fake override'}
        with patch.object(voice_service,'available',return_value={'edge-madhur':True}),patch.object(voice_service,'synthesize_hindi',side_effect=lambda t,p:(captured.append(t) or b'ID3'+b'\0'*100)):
            res=scope['avatar_voice_service']('a'*20)
        self.assertEqual(res.mimetype,'audio/mpeg')
        self.assertEqual(res.headers['X-TBA-Voice'],'edge-madhur')
        self.assertNotIn('fake override',captured[0])
    def test_english_fallback_voice_switch_uses_distinct_audio_and_cache_keys(self):
        request.body={'language':'en','provider':'edge-swara'}
        synth=[]
        old=scope['avatar_narration']
        scope['avatar_narration']=lambda i: FakeResponse({'language':'en-IN','fallback':False,'text':'English summary from verified source.'})
        scope['FEMALE_AUDIO_CACHE']=Cache()
        try:
            def render(t,p,lang):
                synth.append((t,p,lang))
                return b'ID3'+b'\x00'*120
            with patch.object(voice_service,'available',return_value={'edge-swara':True,'edge-madhur':True}),patch.object(voice_service,'synthesize_speech',side_effect=render):
                response1=scope['avatar_voice_service']('a'*20)
                self.assertEqual(response1.headers['X-TBA-Voice'],'edge-swara')
                self.assertEqual(response1.headers['X-TBA-Language'],'en')
                request.body={'language':'en','provider':'edge-madhur'}
                response2=scope['avatar_voice_service']('a'*20)
                self.assertEqual(response2.headers['X-TBA-Voice'],'edge-madhur')
                self.assertEqual(response2.headers['X-TBA-Language'],'en')
                self.assertEqual(response2.headers['Cache-Control'],'no-store')
                self.assertEqual([x[1:] for x in synth],[('edge-swara','en'),('edge-madhur','en')])
                response3=scope['avatar_voice_service']('a'*20)
                self.assertEqual(len(synth),2,'same narrator should reuse server cache, not other narrator')
        finally:
            scope['avatar_narration']=old

    def test_english_edge_voices_map_to_distinct_speakers(self):
        from types import SimpleNamespace
        import asyncio
        seen=[]
        class Communicate:
            def __init__(self, text, voice, rate):seen.append(voice)
            async def stream(self):
                yield {'type':'audio','data':b'ID3'+b'\x00'*70}
        with patch.dict(sys.modules, {'edge_tts':SimpleNamespace(Communicate=Communicate)}):
            asyncio.run(voice_service._edge_mp3_async('Hello','edge-swara','en'))
            asyncio.run(voice_service._edge_mp3_async('Hello','edge-madhur','en'))
            asyncio.run(voice_service._edge_mp3_async('नमस्ते','edge-swara','hi'))
        self.assertEqual(seen,['en-IN-NeerjaNeural','en-IN-PrabhatNeural','hi-IN-SwaraNeural'])

    def test_disallow_unknown_provider(self):
        request.body={'language':'hi','provider':'fake'}
        _,status=scope['avatar_voice_service_sample']()
        self.assertEqual(status,400)
if __name__=='__main__':unittest.main(verbosity=2)
