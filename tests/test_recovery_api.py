"""Result inspection is read-only and never leaks private job metadata."""
import unittest,urllib.request
from unittest.mock import patch
import app
import test_writing_api as writing_api
class RecoveryAPITests(unittest.TestCase):
 call=writing_api.WritingAPITests.call
 setUp=writing_api.WritingAPITests.setUp
 tearDown=writing_api.WritingAPITests.tearDown
 def test_unknown_job_has_distinct_recovery_code_without_creating_work(self):
  with patch.object(app,'remote',side_effect=AssertionError('Unexpected AI')):
   status,result=self.call('/api/jobs/'+'f'*32)
  self.assertEqual(status,200);self.assertEqual(result['code'],'job_missing');self.assertEqual(result['state'],'failed');self.assertFalse(app.JOBS)
 def test_result_can_be_read_again_without_consuming_or_restarting_it(self):
  job='c'*32;app.JOBS[job]={'state':'done','result':{'threads':'기존 요청 결과'},'_kind':'writing','_created':1,'_finished':2}
  with patch.object(app,'remote',side_effect=AssertionError('Unexpected AI')):
   first=self.call('/api/jobs/'+job);second=self.call('/api/jobs/'+job)
  self.assertEqual(first,second);self.assertEqual(first[1],{'state':'done','result':{'threads':'기존 요청 결과'}});self.assertEqual(len(app.JOBS),1)
 def test_help_assets_are_served_locally_without_caching_or_ai(self):
  with patch.object(app,'remote',side_effect=AssertionError('Unexpected AI')):
   for name in ('generation-recovery.js','workspace-help.js','workspace-help.css'):
    with self.subTest(name=name),urllib.request.urlopen(self.base+'/'+name) as response:
     self.assertEqual(response.status,200);self.assertIn('no-store',response.headers['Cache-Control']);self.assertTrue(response.read())
  self.assertFalse(app.JOBS)
