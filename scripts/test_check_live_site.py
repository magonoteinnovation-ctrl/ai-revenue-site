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
    + ''.join(
        f'<section class="top-ad"><div><ins class="adsbygoogle" data-ad-client="ca-pub-8158546915072061" data-ad-slot="{s}"></ins></div></section>'
        for s in ('2417620558', '6646146776', '4873900109', '2323758388')
    ) +
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
        dup = GOOD.replace('</div></section>', '<ins class="adsbygoogle" data-ad-client="ca-pub-8158546915072061" data-ad-slot="2417620558"></ins></div></section>', 1)
        errors, _ = c.check_top_html(dup, 't')
        self.assertTrue(any('1個' in e for e in errors))

    def test_no_ad_unit(self):
        errors, _ = c.check_top_html(GOOD.replace('class="top-ad"', 'class="x"', 1), 't')
        self.assertTrue(any('top-ad' in e for e in errors))

    def test_expected_slots_and_max(self):
        self.assertEqual([s for s, _ in c.TOP_AD_SLOTS], ['2417620558', '6646146776', '4873900109', '2323758388'])
        self.assertLessEqual(len(c.TOP_AD_SLOTS), c.MAX_TOP_ADS)
        self.assertEqual(c.MAX_TOP_ADS, 4)

    def test_old_layout_single_slot_fails(self):
        # 旧構成（1枠だけ）のままでは新しい3枠が足りないと判定する
        old = GOOD
        for s in ('6646146776', '4873900109', '2323758388'):
            old = old.replace(f'<section class="top-ad"><div><ins class="adsbygoogle" data-ad-client="ca-pub-8158546915072061" data-ad-slot="{s}"></ins></div></section>', '')
        errors, _ = c.check_top_html(old, 't')
        for s in ('6646146776', '4873900109', '2323758388'):
            self.assertTrue(any(s in e for e in errors), s)

    def test_missing_new_slot(self):
        errors, _ = c.check_top_html(GOOD.replace('data-ad-slot="4873900109"', 'data-ad-slot="9999999999"'), 't')
        self.assertTrue(any('4873900109' in e for e in errors))

    def test_fifth_ad_exceeds_max(self):
        extra = GOOD.replace('</body>', '<section class="top-ad"><ins class="adsbygoogle" data-ad-client="ca-pub-8158546915072061" data-ad-slot="1111111111"></ins></section></body>')
        errors, _ = c.check_top_html(extra, 't')
        self.assertTrue(any('最大4個' in e for e in errors))

    def test_ad_outside_top_ad_section(self):
        moved = GOOD.replace('<section class="top-ad"><div><ins class="adsbygoogle" data-ad-client="ca-pub-8158546915072061" data-ad-slot="2323758388"></ins></div></section>',
                             '<div class="article"><ins class="adsbygoogle" data-ad-client="ca-pub-8158546915072061" data-ad-slot="2323758388"></ins></div>')
        errors, _ = c.check_top_html(moved, 't')
        self.assertTrue(any('外' in e for e in errors))

    def test_wrong_order(self):
        swapped = GOOD.replace('data-ad-slot="6646146776"', 'data-ad-slot="TMP"').replace('data-ad-slot="2323758388"', 'data-ad-slot="6646146776"').replace('data-ad-slot="TMP"', 'data-ad-slot="2323758388"')
        errors, _ = c.check_top_html(swapped, 't')
        self.assertTrue(any('並び順' in e for e in errors))

    def test_wrong_client(self):
        bad = GOOD.replace('data-ad-client="ca-pub-8158546915072061" data-ad-slot="2323758388"', 'data-ad-client="ca-pub-0000000000000000" data-ad-slot="2323758388"')
        errors, _ = c.check_top_html(bad, 't')
        self.assertTrue(any('運営者ID' in e for e in errors))

    def test_loader_script_once(self):
        two = GOOD.replace('</head>', '<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-8158546915072061"></script></head>')
        errors, _ = c.check_top_html(two, 't')
        self.assertTrue(any('読み込みスクリプト' in e for e in errors))

    def test_repository_index(self):
        errors, links = c.check_top_html((ROOT / 'index.html').read_text(encoding='utf-8'), 'index.html')
        self.assertEqual(errors, [])
        self.assertTrue(links)


if __name__ == '__main__':
    unittest.main()
