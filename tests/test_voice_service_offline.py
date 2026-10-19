"""Test the actual WAV endpoint logic without Flask, Piper, network or model weights."""
import ast
import hashlib
import logging
import re
from pathlib import Path
import sys
from contextlib import nullcontext
from unittest.mock import patch
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from services import voice_service

TREE=ast.parse((ROOT/'app.py').read_text())
FN=next(n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name=='avatar_voice_service')
FN.decorator_list=[]
class FakeResponse:
 def __init__(self,data,mimetype=None):self.data=data;self.mimetype=mimetype;self.headers={}
 def get_json(self):return self.data
class Cache:
 def __init__(self):self.contents={}
 def get(self,key):return self.contents.get(key)
 def set(self,key,value,ttl=0):self.contents[key]=value
class Request:
 body={'language':'hi','provider':'piper'}
 def get_json(self,silent=True):return self.body

request=Request()
SCOPE={'re':re,'hashlib':hashlib,'request':request,'jsonify':lambda **kw:FakeResponse(kw),
 'Response':FakeResponse,'id_lock':lambda *args:nullcontext(),
 'FEMALE_AUDIO_CACHE':Cache(),'app':type('App',(),{'logger':logging.getLogger('test-wav')})(),
 'restore_story':lambda article_id:False,
 'avatar_narration':lambda ident:FakeResponse({'language':'hi-IN','fallback':False,'text':'यह एक सत्यापित हिंदी समाचार का संक्षिप्त विवरण है।'})}
exec(compile(ast.Module(body=[FN],type_ignores=[]),str(ROOT/'app.py'),'exec'),SCOPE)
SAMPLE_FN=next(n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name=='avatar_voice_service_sample')
SAMPLE_FN.decorator_list=[]
exec(compile(ast.Module(body=[SAMPLE_FN],type_ignores=[]),str(ROOT/'app.py'),'exec'),SCOPE)

class Tests(unittest.TestCase):
 def setUp(self):
  SCOPE['FEMALE_AUDIO_CACHE']=Cache()
  request.body={'language':'hi','provider':'piper'}
  self.ident='a'*20
  SCOPE['avatar_narration']=lambda ident:FakeResponse({'language':'hi-IN','fallback':False,'text':'यह एक सत्यापित हिंदी समाचार का संक्षिप्त विवरण है।'})
 def invoke(self):return SCOPE['avatar_voice_service'](self.ident)
 def test_wav_is_generated_and_cached(self):
  voices=[]
  with patch.object(voice_service,'available',return_value={'piper':True}),patch.object(voice_service,'synthesize_hindi',side_effect=lambda t,p:(voices.append((t,p)) or b'RIFF____WAVE')):
   a=self.invoke();b=self.invoke()
  self.assertEqual(a.mimetype,'audio/wav')
  self.assertEqual(a.data,b.data)
  self.assertEqual(len(voices),1)
  self.assertEqual(a.headers['X-TBA-Voice'],'piper')
 def test_missing_voice_is_503(self):
  with patch.object(voice_service,'available',return_value={'piper':False}):
   r,status=self.invoke()
  self.assertEqual(status,503)
  self.assertIn('not available',r.data['error'])
 def test_english_fallback_not_passed_to_hindi_model(self):
  SCOPE['avatar_narration']=lambda ident:FakeResponse({'language':'en-IN','fallback':True,'text':'English fallback'})
  with patch.object(voice_service,'available',return_value={'piper':True}),patch.object(voice_service,'synthesize_hindi') as synth:
   _,status=self.invoke()
   synth.assert_not_called()
  self.assertEqual(status,422)
 def test_invalid_id_is_400(self):
  with patch.object(voice_service,'available',return_value={'piper':True}):
   r,status=SCOPE['avatar_voice_service']('not-a-valid-id')
  self.assertEqual(status,400)
 def test_client_text_cannot_override_source(self):
  request.body={'language':'hi','provider':'piper','text':'fake invented news claims'}
  outputs=[]
  with patch.object(voice_service,'available',return_value={'piper':True}),patch.object(voice_service,'synthesize_hindi',side_effect=lambda t,p:(outputs.append(t) or b'RIFF____WAVE')):
   self.invoke()
  self.assertNotIn('fake invented',outputs[0])
 def test_voice_sample_bypasses_translation_and_is_cached(self):
  wave_calls=[]
  SCOPE['avatar_narration']=lambda ident: (_ for _ in ()).throw(AssertionError('Sample must not translate news'))
  with patch.object(voice_service,'available',return_value={'piper':True}), patch.object(voice_service,'synthesize_hindi',side_effect=lambda t,p:(wave_calls.append((t,p)) or b'RIFF____WAVE')):
   a=SCOPE['avatar_voice_service_sample']()
   b=SCOPE['avatar_voice_service_sample']()
  self.assertEqual(a.mimetype,'audio/wav')
  self.assertEqual(a.data,b.data)
  self.assertEqual(len(wave_calls),1)
  self.assertIn('नमस्कार',wave_calls[0][0])
 def test_piper_and_parler_provider_guard(self):
  request.body={'language':'hi','provider':'unknown'}
  _,status=self.invoke()
  self.assertEqual(status,400)
 def test_empty_script_guard(self):
  SCOPE['avatar_narration']=lambda ident:FakeResponse({'language':'hi-IN','fallback':False,'text':'No Hindi characters present'})
  with patch.object(voice_service,'available',return_value={'piper':True}):
   _,status=self.invoke()
  self.assertEqual(status,422)
if __name__=='__main__': unittest.main(verbosity=2)
