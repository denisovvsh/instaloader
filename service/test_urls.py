import unittest

from service.urls import UrlParseError, is_instagram_media_url, parse_instagram_url


class ParseInstagramUrlTest(unittest.TestCase):
    def test_reel(self):
        r = parse_instagram_url("https://www.instagram.com/reel/B_K4CykAOtf/")
        self.assertEqual(r["shortcode"], "B_K4CykAOtf")
        self.assertEqual(r["kind"], "reel")

    def test_reels_and_query(self):
        r = parse_instagram_url("https://www.instagram.com/reels/AbCdEfGhIjK/?igsh=abc")
        self.assertEqual(r["shortcode"], "AbCdEfGhIjK")

    def test_p_and_tv(self):
        self.assertEqual(parse_instagram_url("https://instagram.com/p/B_K4CykAOtf")["kind"], "p")
        self.assertEqual(parse_instagram_url("https://www.instagram.com/tv/B_K4CykAOtf/")["kind"], "tv")

    def test_share(self):
        r = parse_instagram_url("https://www.instagram.com/share/reel/B_K4CykAOtf/")
        self.assertEqual(r["shortcode"], "B_K4CykAOtf")
        r2 = parse_instagram_url("https://www.instagram.com/share/B_K4CykAOtf")
        self.assertEqual(r2["shortcode"], "B_K4CykAOtf")

    def test_instagr_am(self):
        r = parse_instagram_url("https://instagr.am/p/B_K4CykAOtf/")
        self.assertEqual(r["shortcode"], "B_K4CykAOtf")

    def test_l_instagram_unwrap(self):
        inner = "https://www.instagram.com/reel/B_K4CykAOtf/"
        r = parse_instagram_url("https://l.instagram.com/?u=" + inner)
        self.assertEqual(r["shortcode"], "B_K4CykAOtf")

    def test_stories_rejected(self):
        with self.assertRaises(UrlParseError) as ctx:
            parse_instagram_url("https://www.instagram.com/stories/someone/123")
        self.assertEqual(ctx.exception.error_code, "invalid_url")
        self.assertFalse(is_instagram_media_url("https://www.instagram.com/stories/someone/123"))

    def test_not_instagram(self):
        with self.assertRaises(UrlParseError):
            parse_instagram_url("https://example.com/reel/abc")


if __name__ == "__main__":
    unittest.main()
