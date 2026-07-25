"""IDs read out of LinkedIn URLs."""
import unittest

from linkedin_bots.messaging.adapters.selenium.linkedin_ids import photo_id_from_src, thread_id_from_url

PHOTO_SRC = ("https://media.licdn.com/dms/image/v2/D4D03AQFeIgpwF-N4zg/"
             "profile-displayphoto-scale_100_100/B4DZk2I6.SGQAc-/0/1757549934615"
             "?e=1784160000&v=beta&t=QAujsPGottE0BHzJ4UHRH6Sz8V_nhODEe_-iDPrvXNQ")


class IdParsingTest(unittest.TestCase):
    def test_photo_id_ignores_the_rotating_signature(self):
        self.assertEqual(photo_id_from_src(PHOTO_SRC), "D4D03AQFeIgpwF-N4zg")

    def test_placeholder_photo_has_no_id(self):
        for src in (None, "", "data:image/gif;base64,R0lGOD",
                    "https://static.licdn.com/aero-v1/sc/h/ghost-person.svg"):
            self.assertIsNone(photo_id_from_src(src))

    def test_thread_id_from_url(self):
        self.assertEqual(
            thread_id_from_url("https://www.linkedin.com/messaging/thread/"
                               "2-YWY1NmU1ZjctNDkyNS00NjdkXzEwMA==/"),
            "2-YWY1NmU1ZjctNDkyNS00NjdkXzEwMA==")
        self.assertIsNone(thread_id_from_url("https://www.linkedin.com/feed/"))
