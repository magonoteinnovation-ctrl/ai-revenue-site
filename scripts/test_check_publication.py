import json
from pathlib import Path
import tempfile
import unittest
from check_publication import check, seo_errors

GOOD = ('<html><head><title>記事｜くらしの手帖</title><meta name="description" content="説明">'
        '<link rel="canonical" href="https://example.com/a.html"></head><body><h1>見出し</h1>{body}</body></html>')


class CheckTests(unittest.TestCase):
    def test_good_page_passes(self):
        self.assertEqual(seo_errors('a.html', GOOD.format(body='')), [])

    def test_missing_seo_items_are_reported(self):
        broken = GOOD.replace('<link rel="canonical" href="https://example.com/a.html">', '').replace('<h1>見出し</h1>', '')
        errors = seo_errors('a.html', broken)
        self.assertTrue(any('canonical' in e for e in errors))
        self.assertTrue(any('h1' in e for e in errors))

    def test_broken_json_ld_is_reported(self):
        page = GOOD.format(body='<script type="application/ld+json">{壊れた</script>')
        self.assertTrue(any('構造化データ' in e for e in seo_errors('a.html', page)))

    def test_a8_links_need_sponsored_label_and_approval(self):
        approved = '<p>PR・広告</p><a href="https://px.a8.net/svt/ejp?a8mat=4BEPPP+7WL8PM+4X26+TRVYQ" rel="nofollow sponsored">詳細（広告）</a>'
        self.assertEqual(seo_errors('a.html', GOOD.format(body=approved)), [])
        unknown = approved.replace('4BEPPP+7WL8PM+4X26+TRVYQ', 'UNKNOWN')
        self.assertTrue(any('承認済み' in e for e in seo_errors('a.html', GOOD.format(body=unknown))))
        no_rel = approved.replace(' rel="nofollow sponsored"', '')
        self.assertTrue(any('sponsored' in e for e in seo_errors('a.html', GOOD.format(body=no_rel))))

    def test_check_reports_missing_link_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'articles').mkdir()
            (root / 'index.html').write_text(GOOD.format(body='<a href="missing.html">x</a>'))
            self.assertEqual(check(root), 1)
            (root / 'missing.html').write_text(GOOD.format(body=''))
            self.assertEqual(check(root), 0)


if __name__ == '__main__':
    unittest.main()
