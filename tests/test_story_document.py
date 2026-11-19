import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import app
from story_document import parse,serialize,reconcile,read_documents,view,photo_ids,uid
from platform_writing import view as channel_view

class StoryDocumentTests(unittest.TestCase):
 def doc(self,body='Intro\n\n[[photo:2]]\n\nA view.\n\n[[photo:1]]'):
  return reconcile(body,['a'*32,'b'*32],'A title','reference')
 def test_legacy_import_preserves_original_and_resolves_photos_by_id(self):
  doc=self.doc();self.assertEqual(photo_ids(doc),['b'*32,'a'*32]);self.assertEqual(serialize(doc),doc['source']);self.assertEqual(doc['original']['body'],'Intro\n\n[[photo:2]]\n\nA view.\n\n[[photo:1]]')
 def test_caption_stays_with_image_after_normalization_adds_a_notice(self):
  doc=self.doc();photo=next(b for b in doc['blocks'] if b['type']=='photo');photo['caption']='My caption';doc['source']=serialize(doc)
  newer=reconcile('A disclosure.\n\n'+doc['source'],[], 'A title','reference',doc)
  self.assertEqual(next(b for b in newer['blocks'] if b['id']==photo['id'])['caption'],'My caption');self.assertEqual(newer['original'],doc['original'])
 def test_line_wrapping_preserves_photo_caption_membership(self):
  doc=self.doc();photo=next(b for b in doc['blocks'] if b['type']=='photo');photo['caption']='My caption';doc['source']=serialize(doc)
  updated=reconcile(doc['source'].replace('My caption','My\ncaption'),[], 'A title','reference',doc)
  self.assertEqual(next(b for b in updated['blocks'] if b['id']==photo['id'])['caption'],'My\ncaption')
 def test_view_excludes_unused_assets_and_keeps_doc_order(self):
  doc=self.doc();draft={'blog':doc['source'],'images':['a'*32,'b'*32,'c'*32],'blog_documents':{'naver':doc}}
  self.assertEqual(view(draft,'naver')['images'],['b'*32,'a'*32]);self.assertEqual(draft['images'],['a'*32,'b'*32,'c'*32])
 def test_stale_doc_cannot_override_a_new_body(self):
  doc=self.doc();self.assertEqual(view({'blog':'New body','images':[],'blog_documents':{'naver':doc}},'naver')['blog'],'New body')
 def test_tistory_uses_its_own_document(self):
  doc=self.doc();draft={'blog':'Naver remains','title':'Naver','tistory':doc['source'],'tistory_title':'Tistory','images':[],'blog_documents':{'tistory':doc}}
  result=channel_view(draft,'tistory');self.assertEqual(result['title'],'Tistory');self.assertEqual(result['images'],photo_ids(doc));self.assertEqual(draft['blog'],'Naver remains')
 def test_invalid_duplicate_photo_and_future_schema_rejected(self):
  doc=self.doc();doc['blocks'].append(copy.deepcopy(next(b for b in doc['blocks'] if b['type']=='photo')))
  with self.assertRaises(ValueError):read_documents({'naver':doc})
  with self.assertRaises(ValueError):read_documents({'naver':{'version':2}})
 def test_photo_removal_is_not_filled_back_into_explicit_doc(self):
  doc=self.doc();doc['blocks']=[b for b in doc['blocks'] if b['type']!='photo'];doc['source']=serialize(doc)
  self.assertEqual(view({'blog':doc['source'],'images':['a'*32],'blog_documents':{'naver':doc}},'naver')['images'],[])
 def test_heading_and_inline_anchor_preserve_surrounding_text(self):
  blocks=parse('Before [[photo:1]] after\n## Heading\nLast line',['a'*32]);self.assertEqual([b['type'] for b in blocks],['paragraph','photo','paragraph','heading','paragraph']);self.assertIn('Before',serialize({'blocks':blocks}));self.assertIn('Last line',serialize({'blocks':blocks}))

class DocumentSaveTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.patches=[patch.object(app,'DATA',self.root),patch.object(app,'MEDIA',self.root)]
  for p in self.patches:p.start()
  with app.db() as db:db.execute('CREATE TABLE drafts(id TEXT PRIMARY KEY,title TEXT,data TEXT,updated REAL)')
  for char in 'abc':(self.root/(char*32+'.jpg')).write_bytes(b'fixture')
 def tearDown(self):
  for p in self.patches:p.stop()
  self.temp.cleanup()
 def test_save_does_not_reinsert_deleted_photo_and_preserves_other_channel(self):
  doc=reconcile('Intro\n\n[[photo:1]]',['b'*32],'Title','reference');doc['undo']=[{'blocks':copy.deepcopy(doc['blocks']),'title':'Old title','template':'reference'}]
  draft=app.save_draft({'title':'Title','blog':doc['source'],'tistory':'Other blog','tistory_title':'Other title','instagram':'Keep me','images':['a'*32,'b'*32,'c'*32],'blog_documents':{'naver':doc},'editing_platform':'naver','selective_generation':True})
  self.assertEqual(photo_ids(draft['blog_documents']['naver']),['b'*32]);self.assertEqual(draft['instagram'],'Keep me');self.assertEqual(draft['tistory'],'Other blog');self.assertEqual(len(draft['blog_documents']['naver']['undo']),1)
  loaded=app.get_draft(draft['id']);self.assertEqual(channel_view(loaded,'naver')['images'],['b'*32]);self.assertEqual(loaded['images'],['a'*32,'b'*32,'c'*32])
 def test_missing_replacement_file_fails_before_overwriting_saved_draft(self):
  first=app.save_draft({'title':'Title','blog':'Original'})
  doc=reconcile('Changed\n\n[[photo:1]]',['f'*32],'Title','reference')
  with self.assertRaises(app.Problem):app.save_draft({**first,'blog':doc['source'],'blog_documents':{'naver':doc}})
  self.assertEqual(app.get_draft(first['id'])['blog'],'Original')

 def test_extension_payload_matches_document_photos_and_template(self):
  from extension_bridge import ExtensionBridge
  from naver_guard import NaverGuard
  (self.root/('b'*32+'.jpg')).write_bytes(b'CHOSEN')
  doc=reconcile('A review.\n\n[[photo:1]]',['b'*32],'Title','clean')
  saved=app.save_draft({'title':'Title','blog':doc['source'],'images':['a'*32,'b'*32,'c'*32],'template':'reference','blog_documents':{'naver':doc},'editing_platform':'naver','selective_generation':True})
  bridge=ExtensionBridge(self.root,NaverGuard(self.root/'naver.json'));ticket=bridge.create(saved);payload=bridge.redeem(ticket['code'])
  import base64
  self.assertEqual(payload['expected_photos'],1);self.assertEqual(base64.b64decode(payload['photos'][0]['base64']),b'CHOSEN');self.assertEqual(payload['body'],saved['blog']);self.assertEqual(payload['format']['align'],'left')
 def test_tistory_handoff_and_photo_mission_use_only_selected_images(self):
  from extension_bridge import ExtensionBridge,HandoffError
  from naver_guard import NaverGuard
  doc=reconcile('A review.\n\n[[photo:1]]',['c'*32],'Tistory','reference')
  saved=app.save_draft({'title':'Naver','blog':'Keep Naver','tistory_title':'Tistory','tistory':doc['source'],'images':['a'*32,'b'*32,'c'*32],'blog_documents':{'tistory':doc},'editing_platform':'tistory','selective_generation':True})
  bridge=ExtensionBridge(self.root,NaverGuard(self.root/'tistory.json'),channel='tistory');ticket=bridge.create(saved);self.assertEqual(ticket['photo_count'],1)
  payload=bridge.redeem(ticket['code']);self.assertEqual(payload['title'],'Tistory');self.assertEqual(payload['body'],saved['tistory'])
  other=ExtensionBridge(self.root,NaverGuard(self.root/'mission.json'),channel='tistory')
  with self.assertRaisesRegex(HandoffError,'사진'):other.create({**saved,'campaign_enabled':True,'campaign_min_photos':2,'disclosure':'experience'})
