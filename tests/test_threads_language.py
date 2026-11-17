import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import app
from writing_quality import disclose,review,caption_facts

class ThreadsLanguageTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.patch=patch.object(app,'DATA',Path(self.temp.name));self.patch.start()
  with app.db() as db:db.execute('CREATE TABLE drafts(id TEXT PRIMARY KEY,title TEXT,data TEXT,updated REAL)')
 def tearDown(self):self.patch.stop();self.temp.cleanup()
 def test_legacy_defaults_and_roundtrip(self):
  old=app.save_draft({'title':'제목','blog':'본문'})
  self.assertEqual(old['language'],'ko');self.assertEqual(old['threads'],'')
  saved=app.save_draft({**old,'language':'en','threads_tone':'witty','threads':"Turns out a quiet coffee break was all I needed."})
  self.assertEqual(app.get_draft(saved['id'])['threads'],saved['threads'])
 def test_limit_and_english_disclosure(self):
  for body in [{'threads':'a'*501},{'threads':'a'*490,'disclosure':'paid','language':'en'},{'language':'invalid'},{'threads_tone':'invalid'}]:
   with self.subTest(body=body),self.assertRaises(app.Problem):app.save_draft(body)
  saved=app.save_draft({'language':'en','threads':'A little coffee break.','disclosure':'paid'})
  self.assertTrue(saved['threads'].startswith('Paid partnership.'))
  self.assertEqual(app.save_draft(saved)['threads'],saved['threads'])
 def test_english_facts_are_not_appended_in_korean(self):
  body={'language':'en','instagram':'A coffee break.','facts':'창가에 앉았어요.','facts_translation':'I sat by the window.','facts_translation_source':'창가에 앉았어요.'}
  saved=app.save_draft(body)
  self.assertIn('I sat by the window.',saved['instagram']);self.assertNotIn('창가',saved['instagram'])
  changed=app.save_draft({**saved,'facts':'온천이 좋았어요.'})
  self.assertEqual(caption_facts(changed),'');self.assertNotIn('온천',changed['instagram'])
  self.assertTrue(any('필수 메모' in c['message'] for c in review(changed)))
 def test_threads_review_does_not_require_a_blog_title_or_photos(self):
  checks=review({'threads':'가끔은 커피 한 잔이면 충분하더라.','review_channel':'threads'})
  self.assertFalse(any(item['level']=='error' for item in checks))
 def test_generation_guides_every_channel_and_english_style_pass(self):
  facts='창가에 앉았어요.'
  answer={'title':'A quiet coffee break','blog':"I'd happily spend a quiet afternoon by this window. No rushing, just a little room to breathe.",'instagram':'A quiet coffee break.','threads':"A good window seat makes a coffee break feel like a tiny holiday.",'facts_translation':'I sat by the window.'}
  response={'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(answer)}]}]}
  events=[]
  with patch.dict(os.environ,{'OPENAI_API_KEY':'test'}),patch.object(app,'remote',return_value=response) as remote:
   generated=app.generate({'prompt':'카페 후기','facts':facts,'language':'en','threads_tone':'witty','tone':'밝고 자연스러운 일상 후기체','images':[]},lambda message,stage:events.append(stage))
  self.assertEqual(generated['threads'],answer['threads'])
  self.assertNotIn('창가',generated['instagram']);self.assertIn('I sat by the window.',generated['instagram'])
  self.assertEqual(generated['blog'],answer['blog'])
  self.assertEqual(remote.call_count,2)
  for call in remote.call_args_list:self.assertIn('OUTPUT LANGUAGE: ENGLISH',call.args[1]['instructions'])
  self.assertIn('threads_tone',remote.call_args_list[0].args[1]['instructions'])
  self.assertEqual(events,[1,2,3,4])
  self.assertIn('lang="en"',app.blog_html(generated))
