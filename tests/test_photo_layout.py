import unittest
from photo_layout import photo_layout
from tones import TONES
class PhotoLayoutTests(unittest.TestCase):
    def test_explicit_positions_kept(self):
        body="도입\n\n[[photo:1]]\n\n감상\n\n[[photo:2]]\n\n마무리"
        self.assertEqual(photo_layout(body,2),body)
    def test_missing_photos_distributed_between_paragraphs(self):
        result=photo_layout("도입\n\n첫 장면\n\n두 번째 장면\n\n마무리",2)
        self.assertLess(result.index("[[photo:1]]"),result.index("마무리"))
        self.assertLess(result.index("[[photo:2]]"),result.index("마무리"))
    def test_duplicate_and_invalid_marker_removed_without_photo_loss(self):
        result=photo_layout("도입\n\n[[photo:1]]\n\n[[photo:1]]\n\n[[photo:99]]\n\n마무리",2)
        self.assertEqual(result.count("[[photo:1]]"),1)
        self.assertEqual(result.count("[[photo:2]]"),1)
        self.assertNotIn("[[photo:99]]",result)
    def test_lively_tone_is_available_without_inventing_identity(self):
        guide=TONES["밝고 자연스러운 일상 후기체"]
        self.assertIn("신상",guide)
        self.assertIn("만들어",guide)
