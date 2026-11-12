import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import check_live_site as c  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
REL = 'rel="nofollow sponsored noopener"'
GOOD = (
    '<html><head><script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-8158546915072061"></script></head><body>'
    '<div class="hero-shop">'
    f'<a class="btn" href="https://www.amazon.co.jp?&amp;tag=magonoteinnov-22" {REL}>Amazonでお買い物 <span>PR</span></a>'
    f'<a class="btn" href="https://rpx.a8.net/svt/ejp?a8mat=3HC21T+C6SIE2+2HOM+BW8O1&amp;rakuten=y" {REL}>楽天市場でお買い物 <span>PR</span></a>'
    '</div>'
    '<section class="top-ad"><div><ins class="adsbygoogle" data-ad-client="ca-pub-8158546915072061" data-ad-slot="2417620558"></ins></div></section>'
    '<a href="articles/a.html">記事</a></body></html>'
)


class CheckLiveSiteTest(unittest.TestCase):
    def test_good(self):
        errors, links = c.check_top_html(GOOD, 't')
        self.assertEqual(errors, [])
        self.assertEqual(links, ['articles/a.html'])

    def test_missing_rakuten(self):
        bad = GOOD.replace('a8mat=3HC21T+C6SIE2+2HOM+BW8O1', 'x')
        errors, _ = c.check_top_html(bad, 't')
        self.assertTrue(any('楽天' in e for e in errors))

    def test_missing_amazon_tag(self):
        errors, _ = c.check_top_html(GOOD.replace('tag=magonoteinnov-22', 'tag=other-22'), 't')
        self.assertTrue(any('Amazon' in e for e in errors))

    def test_rel_required(self):
        errors, _ = c.check_top_html(GOOD.replace(REL, 'rel="noopener"', 1), 't')
        self.assertTrue(any('rel=' in e for e in errors))

    def test_two_ad_units(self):
        dup = GOOD.replace('</div></section>', '<ins class="adsbygoogle" data-ad-client="ca-pub-8158546915072061" data-ad-slot="2417620558"></ins></div></section>')
        errors, _ = c.check_top_html(dup, 't')
        self.assertTrue(any('1個' in e for e in errors))

    def test_no_ad_unit(self):
        errors, _ = c.check_top_html(GOOD.replace('class="top-ad"', 'class="x"'), 't')
        self.assertTrue(any('top-ad' in e for e in errors))

    def test_repository_index(self):
        errors, links = c.check_top_html((ROOT / 'index.html').read_text(encoding='utf-8'), 'index.html')
        self.assertEqual(errors, [])
        self.assertTrue(links)


if __name__ == '__main__':
    unittest.main()
