import copy,json,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import app
import story_library as library
import reusable_kits as kits
from extension_bridge import ExtensionBridge
from naver_guard import NaverGuard

class LibraryTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.media=self.root/'media';self.media.mkdir();self.patches=[patch.object(app,'DATA',self.root),patch.object(app,'MEDIA',self.media)]
  for item in self.patches:item.start()
  self.mid='a'*32;Image.new('RGB',(400,300),'red').save(self.media/(self.mid+'.jpg'))
  with app.db() as conn:conn.executescript("CREATE TABLE drafts(id TEXT PRIMARY KEY,title TEXT,data TEXT,updated REAL);CREATE TABLE attempts(id TEXT PRIMARY KEY,draft_id TEXT,state TEXT,result TEXT,created REAL);"+app.THREADS_SCHEMA)
 def tearDown(self):
  for item in reversed(self.patches):item.stop()
  self.temp.cleanup()
 def draft(self,**extra):return app.save_draft({'title':'카페 기록','blog':'크림이 고소했던 라떼 이야기예요.','tistory':'','instagram':'창가에서 마신 라떼예요.','threads':'오늘의 작은 이야기','images':[self.mid],'selected_platforms':['naver','instagram','threads'],'selective_generation':True,'editing_platform':'naver',**extra})
 def card(self,did):return library.story_card(app.db,app.draft_summary,did)
 def review(self,draft,platform='naver'):return library.mark_review(app.db,{'id':draft['id'],'updated':draft['updated'],'platform':platform,'confirmed':True})
 def test_saved_draft_is_not_automatically_reviewed(self):
  draft=self.draft();card=self.card(draft['id']);self.assertEqual(card['state'],'draft');self.assertFalse(card['channel_states']['naver']['reviewed'])
 def test_review_is_channel_scoped(self):
  draft=self.draft();self.review(draft);states=self.card(draft['id'])['channel_states'];self.assertTrue(states['naver']['reviewed']);self.assertFalse(states['instagram']['reviewed'])
 def test_review_invalidates_only_changed_channel(self):
  draft=self.draft();self.review(draft);new=app.save_draft({**draft,'threads':'다른 스레드 이야기','editing_platform':'threads'});self.assertTrue(self.card(new['id'])['channel_states']['naver']['reviewed'])
  new=app.save_draft({**new,'blog':new['blog']+' 새 문장.','editing_platform':'naver'});self.assertFalse(self.card(new['id'])['channel_states']['naver']['reviewed'])
 def test_photo_frame_changes_invalidate_instagram_review(self):
  draft=self.draft(channel_media={'instagram':{'images':[self.mid],'frame':'portrait'}});self.review(draft,'instagram');new=app.save_draft({**draft,'channel_media':{'instagram':{'images':[self.mid],'frame':'square'}}});self.assertFalse(self.card(new['id'])['channel_states']['instagram']['reviewed'])
 def test_same_content_after_undo_can_use_its_review(self):
  draft=self.draft();self.review(draft);new=app.save_draft({**draft,'blog':draft['blog']+' 임시 문장.'});new=app.save_draft({**new,'blog':draft['blog']});self.assertTrue(self.card(new['id'])['channel_states']['naver']['reviewed'])
 def test_review_rejects_stale_version_or_unconfirmed(self):
  draft=self.draft();new=app.save_draft({**draft,'blog':draft['blog']+' 수정.'})
  with self.assertRaises(FileExistsError):self.review(draft)
  with self.assertRaises(ValueError):library.mark_review(app.db,{'id':new['id'],'updated':new['updated'],'platform':'naver','confirmed':False})
 def test_cannot_forge_review_through_save(self):
  draft=self.draft(channel_reviews={'naver':{'reviewed':True}});self.assertFalse(self.card(draft['id'])['channel_states']['naver']['reviewed']);self.assertNotIn('channel_reviews',draft)
 def test_invalid_body_or_missing_instagram_photo_blocks_review(self):
  draft=self.draft(images=[],channel_media={'instagram':{'images':[]}})
  with self.assertRaisesRegex(ValueError,'사진'):self.review(draft,'instagram')
  draft=self.draft(blog='')
  with self.assertRaises(ValueError):self.review(draft)
 def test_campaign_manual_conditions_must_be_checked(self):
  draft=self.draft(campaign_enabled=True,disclosure='experience',campaign_manual_checks=[{'id':'b'*20,'text':'지도 확인','quote':'지도 첨부'}])
  with self.assertRaisesRegex(ValueError,'직접 확인'):self.review(draft)
  report=app.campaign_report(draft,'naver');draft=app.save_draft({**draft,'campaign_manual_state':{'naver':{'b'*20:report['fingerprint']}}});self.assertTrue(self.review(draft)['confirmed'])
 def test_published_snapshot_matches_current_content(self):
  draft=self.draft()
  with app.db() as conn:
   conn.execute('INSERT INTO attempts VALUES(?,?,?,?,?)',('f'*32,draft['id'],'published','{}',time.time()));library.record_publish(conn,'f'*32,draft,'instagram')
  self.assertEqual(self.card(draft['id'])['channel_states']['instagram']['state'],'published')
  new=app.save_draft({**draft,'instagram':'다른 캡션이에요.','editing_platform':'instagram'});self.assertEqual(self.card(new['id'])['channel_states']['instagram']['state'],'changed')
 def test_old_publication_without_snapshot_is_not_current_publication(self):
  draft=self.draft()
  with app.db() as conn:conn.execute('INSERT INTO attempts VALUES(?,?,?,?,?)',('f'*32,draft['id'],'published','{}',time.time()))
  state=self.card(draft['id'])['channel_states']['instagram'];self.assertEqual(state['state'],'changed');self.assertIn('이전',state['label'])
 def test_unresolved_attempt_stays_visible_after_edit(self):
  draft=self.draft()
  with app.db() as conn:conn.execute('INSERT INTO attempts VALUES(?,?,?,?,?)',('e'*32,draft['id'],'uncertain','{}',time.time()))
  new=app.save_draft({**draft,'instagram':'새 캡션','editing_platform':'instagram'});self.assertEqual(self.card(new['id'])['channel_states']['instagram']['state'],'attention')
 def test_alias_star_and_archive_do_not_change_post_content(self):
  draft=self.draft();first=library.update_meta(app.db,{'id':draft['id'],'revision':0,'changes':{'label':'주말 카페 이야기','starred':True}});self.assertEqual(first['revision'],1);self.assertEqual(app.get_draft(draft['id'])['title'],'카페 기록');self.assertEqual(self.card(draft['id'])['story_title'],'주말 카페 이야기')
  library.update_meta(app.db,{'id':draft['id'],'revision':1,'changes':{'archived':True}});self.assertEqual(library.page(app.db,app.draft_summary)['total'],0);self.assertEqual(self.card(draft['id'])['meta']['archived'],True);self.assertEqual(library.page(app.db,app.draft_summary,{'scope':'archived'})['total'],1)
  library.update_meta(app.db,{'id':draft['id'],'revision':2,'changes':{'archived':False}});self.assertEqual(library.page(app.db,app.draft_summary)['total'],1)
 def test_metadata_stale_window_preserves_first_change(self):
  draft=self.draft();library.update_meta(app.db,{'id':draft['id'],'revision':0,'changes':{'label':'첫 이름'}})
  with self.assertRaises(FileExistsError):library.update_meta(app.db,{'id':draft['id'],'revision':0,'changes':{'label':'낡은 이름'}})
  self.assertEqual(self.card(draft['id'])['story_title'],'첫 이름')
 def test_open_marker_is_independent_of_metadata_revision(self):
  draft=self.draft();library.opened(app.db,draft['id']);meta=library.update_meta(app.db,{'id':draft['id'],'revision':0,'changes':{'starred':True}});self.assertGreater(meta['last_opened'],0)
 def test_search_and_channel_state_filters(self):
  draft=self.draft(prompt='부산 여행 기록',facts='마시멜로가 좋았어요.');self.review(draft)
  self.assertEqual(library.page(app.db,app.draft_summary,{'q':'부산'})['total'],1);self.assertEqual(library.page(app.db,app.draft_summary,{'q':'마시멜로'})['total'],1)
  self.assertEqual(library.page(app.db,app.draft_summary,{'platform':'naver','state':'ready'})['total'],1);self.assertEqual(library.page(app.db,app.draft_summary,{'platform':'instagram','state':'ready'})['total'],0)
 def test_pagination_and_pinned_first(self):
  drafts=[self.draft(title='이야기 '+str(i)) for i in range(25)];library.update_meta(app.db,{'id':drafts[0]['id'],'revision':0,'changes':{'starred':True}});first=library.page(app.db,app.draft_summary,{'limit':24});second=library.page(app.db,app.draft_summary,{'limit':24,'offset':24});self.assertEqual(first['items'][0]['id'],drafts[0]['id']);self.assertTrue(first['has_more']);self.assertEqual(len(second['items']),1);self.assertFalse(set(x['id'] for x in first['items'])&set(x['id'] for x in second['items']))
 def test_notes_only_ideas_and_safe_summary(self):
  draft=self.draft(blog='',instagram='',threads='',facts='다음에 쓸 산책 기록',prompt='',selected_platforms=['naver']);card=self.card(draft['id']);self.assertEqual(card['state'],'idea');self.assertIn('산책',card['excerpt']);self.assertNotIn('blog',card);self.assertNotIn('facts',card);self.assertNotIn('channel_media',card)
 def test_one_damaged_record_does_not_break_other_cards(self):
  good=self.draft()
  with app.db() as conn:conn.execute('INSERT INTO drafts VALUES(?,?,?,?)',('d'*32,'읽기 확인','{broken',time.time()))
  result=library.page(app.db,app.draft_summary);self.assertEqual(result['total'],2);bad=next(c for c in result['items'] if c['id']=='d'*32);self.assertTrue(bad['damaged']);self.assertEqual(bad['state'],'attention');self.assertEqual(self.card(good['id'])['title'],'카페 기록')
  with self.assertRaises(app.Problem):app.get_draft('d'*32)
 def test_structurally_damaged_draft_cannot_break_the_editor(self):
  with app.db() as conn:conn.execute('INSERT INTO drafts VALUES(?,?,?,?)',('c'*32,'형식 확인',json.dumps({'blog':{'bad':'body'},'images':[]}),time.time()))
  self.assertTrue(self.card('c'*32)['damaged'])
  with self.assertRaises(app.Problem):app.get_draft('c'*32)
 def test_actual_selected_photo_is_used_when_prepared_pool_changed(self):
  second='b'*32;Image.new('RGB',(300,400),'blue').save(self.media/(second+'.jpg'));draft=self.draft(images=[second],editing_platform='instagram',channel_media={'instagram':{'images':[self.mid]}});self.assertEqual(self.card(draft['id'])['thumbnail'],self.mid)
 def test_text_only_channel_does_not_show_prepared_photo_as_its_thumbnail(self):
  draft=self.draft(editing_platform='threads',threads_include_images=False);card=self.card(draft['id']);self.assertEqual(card['thumbnail'],'');self.assertEqual(card['photo_count'],0)
 def test_handoff_is_persisted_but_never_called_publication(self):
  draft=self.draft();bridge=ExtensionBridge(self.media,NaverGuard(self.root/'guard.json'),record_report=lambda token,item,state,count:library.record_handoff(app.db,'naver',token,item,state,count));ticket=bridge.create(draft);delivery=bridge.redeem(ticket['code']);bridge.report(delivery['report_token'],'ready',1);bridge.report(delivery['report_token'],'ready',1);state=self.card(draft['id'])['channel_states']['naver'];self.assertEqual(state['state'],'handed_off');self.assertNotEqual(state['label'],'발행 완료')
  with app.db() as conn:self.assertEqual(conn.execute('SELECT COUNT(*) FROM handoff_events').fetchone()[0],1)
 def test_removed_channel_prose_does_not_hide_its_publication_record(self):
  draft=self.draft(instagram='',selected_platforms=['naver'])
  with app.db() as conn:conn.execute('INSERT INTO attempts VALUES(?,?,?,?,?)',('f'*32,draft['id'],'published','{}',time.time()))
  state=self.card(draft['id'])['channel_states']['instagram'];self.assertEqual(state['state'],'changed');self.assertIn('원고 없음',state['label'])
 def test_legacy_guard_only_proves_an_earlier_input(self):
  draft=self.draft();result=library.story_card(app.db,app.draft_summary,draft['id'],legacy_handoffs={'naver':{draft['id']}});state=result['channel_states']['naver'];self.assertEqual(state['state'],'draft');self.assertIn('이전 편집기 입력',state['label']);self.assertFalse(state['reviewed'])
 def test_invalid_filter_metadata_and_page_are_rejected(self):
  for params in ({'state':'made-up'},{'platform':'facebook'},{'limit':500},{'offset':-1},{'q':'x'*201}):
   with self.subTest(params=params),self.assertRaises(ValueError):library.page(app.db,app.draft_summary,params)
  draft=self.draft()
  for changes in ({'starred':'yes'},{'label':'x'*81},{'token':'secret'}):
   with self.subTest(changes=changes),self.assertRaises(ValueError):library.update_meta(app.db,{'id':draft['id'],'revision':0,'changes':changes})


class KitTests(unittest.TestCase):
 setUp=LibraryTests.setUp
 tearDown=LibraryTests.tearDown
 draft=LibraryTests.draft
 def save(self,kind,settings,name='자주 쓰는 설정'):return kits.save(app.db,{'kind':kind,'name':name,'settings':settings})
 def test_tags_normalize_and_merge_without_duplicates(self):
  kit=self.save('tags',{'hashtags':'#카페, 일상, CAFE, cafe'});self.assertEqual(kit['settings']['hashtags'],'#카페 #일상 #CAFE')
  result=kits.preview(app.db,{'id':kit['id'],'revision':kit['revision'],'current':{'hashtags':'#기존 #카페'},'groups':['tags']});self.assertEqual(result['patch']['hashtags'],'#기존 #카페 #일상 #CAFE')
 def test_tags_replace_is_explicit(self):
  kit=self.save('tags',{'hashtags':'#새태그'});result=kits.preview(app.db,{'id':kit['id'],'revision':1,'current':{'hashtags':'#원래태그'},'groups':['tags'],'tag_mode':'replace'});self.assertEqual(result['patch']['hashtags'],'#새태그')
 def test_tag_overflow_blocks_without_changing_draft(self):
  draft=self.draft();kit=self.save('tags',{'hashtags':' '.join('#new'+str(i) for i in range(30))})
  with self.assertRaises(ValueError):kits.preview(app.db,{'id':kit['id'],'revision':1,'current':{'hashtags':'#기존'},'groups':['tags']})
  self.assertEqual(app.get_draft(draft['id'])['blog'],draft['blog'])
 def test_place_requires_new_confirmation_each_time(self):
  kit=self.save('brand',{'campaign_brand':'카페','selected_place':{'name':'같은 이름 카페','address':'서울 성동구 정확한 주소'}});request={'id':kit['id'],'revision':1,'current':{'campaign_brand':'원래 업체','selected_place':None},'groups':['place']}
  with self.assertRaisesRegex(ValueError,'주소'):kits.preview(app.db,request)
  result=kits.preview(app.db,{**request,'place_confirmed':True});self.assertEqual(result['patch']['selected_place']['address'],'서울 성동구 정확한 주소');self.assertNotIn('campaign_brand',result['patch'])
 def test_campaign_requires_new_confirmation(self):
  kit=self.save('campaign',{'title_keywords':'카페','campaign_min_chars':2000});request={'id':kit['id'],'revision':1,'current':{'campaign_max_chars':0},'groups':['length']}
  with self.assertRaises(ValueError):kits.preview(app.db,request)
  result=kits.preview(app.db,{**request,'conditions_confirmed':True});self.assertTrue(result['patch']['campaign_enabled']);self.assertEqual(result['patch']['campaign_min_chars'],2000);self.assertNotIn('title_keywords',result['patch'])
 def test_reuse_never_copies_prose_benefits_dates_or_exact_claims(self):
  for field in ('blog','images','facts','campaign_benefit','disclosure','required_phrases','campaign_brief','campaign_manual_state'):
   with self.subTest(field=field),self.assertRaises(ValueError):self.save('campaign',{'body_keywords':'카페',field:'previous visit'})
 def test_conflicting_saved_conditions_or_combined_conditions_are_blocked(self):
  with self.assertRaises(ValueError):self.save('campaign',{'campaign_min_chars':2000,'campaign_max_chars':1000})
  kit=self.save('campaign',{'body_keywords':'카페'});
  with self.assertRaises(ValueError):kits.preview(app.db,{'id':kit['id'],'revision':1,'current':{'campaign_forbidden':'카페'},'groups':['keywords'],'conditions_confirmed':True})
 def test_empty_settings_are_not_saved(self):
  for kind in ('brand','tags','campaign'):
   with self.subTest(kind=kind),self.assertRaises(ValueError):self.save(kind,{})
 def test_archive_and_restore_preserve_settings(self):
  kit=self.save('tags',{'hashtags':'#카페'});result=kits.archive(app.db,{'id':kit['id'],'revision':1});self.assertEqual(kits.list_kits(app.db),[]);old=kits.list_kits(app.db,True)[0];self.assertEqual(old['settings'],kit['settings']);restored=kits.save(app.db,{**old,'revision':result['revision']});self.assertFalse(restored['archived']);self.assertEqual(len(kits.list_kits(app.db)),1)
 def test_multi_window_update_and_preview_conflicts(self):
  kit=self.save('tags',{'hashtags':'#카페'});new=kits.save(app.db,{**kit,'name':'수정한 이름'})
  with self.assertRaises(FileExistsError):kits.save(app.db,{**kit,'name':'오래된 수정'})
  with self.assertRaises(FileExistsError):kits.preview(app.db,{'id':kit['id'],'revision':1,'current':{'hashtags':''},'groups':['tags']})
  self.assertEqual(kits.list_kits(app.db)[0]['name'],new['name'])
 def test_no_saved_story_is_mutated_by_kit_apply_preview(self):
  draft=self.draft();original=app.get_draft(draft['id']);kit=self.save('campaign',{'body_keywords':'카페','hashtags':'#일상'});result=kits.preview(app.db,{'id':kit['id'],'revision':1,'groups':['keywords','tags'],'conditions_confirmed':True,'current':{'hashtags':'#기존'}});self.assertEqual(app.get_draft(draft['id']),original);self.assertNotIn('disclosure',result['patch']);self.assertNotIn('required_phrases',result['patch'])
 def test_unselected_or_unknown_fields_cannot_enter_preview(self):
  kit=self.save('tags',{'hashtags':'#일상'})
  for extra in ({'groups':[]},{'groups':['unknown']},{'current':{'token':'private'}},{'tag_mode':'silent'}):
   with self.subTest(extra=extra),self.assertRaises(ValueError):kits.preview(app.db,{'id':kit['id'],'revision':1,'groups':['tags'],'current':{'hashtags':''},**extra})

if __name__=='__main__':unittest.main()
