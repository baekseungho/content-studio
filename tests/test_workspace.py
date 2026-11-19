"""Workspace selections survive save/reload without changing channel content."""
import tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import app

class WorkspaceDraftTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.data=patch.object(app,'DATA',Path(self.temp.name));self.data.start()
  with app.db() as db:db.execute('CREATE TABLE drafts(id TEXT PRIMARY KEY,title TEXT,data TEXT,updated REAL)')
 def tearDown(self):self.data.stop();self.temp.cleanup()
 def test_roundtrip_keeps_selected_channels_and_step(self):
  saved=app.save_draft({'selected_platforms':['naver','instagram'],'workspace_step':3,'selective_generation':True,'editing_platform':'naver','title':'A moment','blog':'A quiet afternoon.','instagram':'My existing caption.'})
  loaded=app.get_draft(saved['id']);self.assertEqual(loaded['selected_platforms'],['naver','instagram']);self.assertEqual(loaded['workspace_step'],3);self.assertEqual(loaded['instagram'],'My existing caption.')
 def test_empty_selection_is_a_valid_unfinished_story(self):
  saved=app.save_draft({'selected_platforms':[],'prompt':'A memory to finish later.','workspace_step':1})
  self.assertEqual(app.get_draft(saved['id'])['selected_platforms'],[])
 def test_legacy_story_infers_channels_without_requiring_new_metadata(self):
  saved=app.save_draft({'threads':'A small thought.'});self.assertEqual(saved['selected_platforms'],['threads']);self.assertEqual(saved['workspace_step'],2)
 def test_invalid_destinations_are_rejected(self):
  for value in ('naver',[None],['unknown'],[{}],['naver']*5):
   with self.subTest(value=value),self.assertRaises(app.Problem):app.save_draft({'selected_platforms':value})
 def test_repeated_destinations_are_normalized_and_invalid_step_is_safe(self):
  saved=app.save_draft({'selected_platforms':['instagram','instagram'],'workspace_step':True})
  self.assertEqual(saved['selected_platforms'],['instagram']);self.assertEqual(saved['workspace_step'],1)
