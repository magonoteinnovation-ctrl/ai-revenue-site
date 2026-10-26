import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
from build_publication import build, BASE, NS, OFFICIAL_URL


class PublicationTests(unittest.TestCase):
    def test_build_links_escape_and_sitemap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'articles').mkdir()
            (root / 'articles/example.html').write_text('<html><head></head><body>記事</body></html>')
            (root / 'pest-control-guide.html').write_text('<html><head></head></html>')
            (root / 'index.html').write_text('<html><head></head><body><div id="automaticArticles" class="articles" aria-live="polite"></div><div class="footerlinks"></div><footer></footer></body></html>')
            (root / 'articles.json').write_text(json.dumps([{'path': 'articles/example.html', 'title': '<危険>', 'description': '掃除 & 住まい', 'checked_at': '2026-10-26'}]))
            build(root)
            before = (root / 'index.html').read_text()
            build(root)
            self.assertEqual(before, (root / 'index.html').read_text())
            self.assertIn('&lt;危険&gt;', before)
            self.assertIn('href="articles/example.html"', before)
            self.assertEqual(before.count('rel="canonical"'), 1)
            self.assertEqual(before.count(OFFICIAL_URL), 1)
            self.assertNotIn(BASE + 'unwanted-items-guide.html', (root / 'sitemap.xml').read_text())
            urls = ET.parse(root / 'sitemap.xml').findall('{' + NS + '}url')
            locs = [x.find('{' + NS + '}loc').text for x in urls]
            self.assertEqual(len(locs), len(set(locs)))
            self.assertIn(BASE + 'articles/example.html', locs)
            self.assertNotIn(BASE + 'index.html', locs)

    def test_invalid_path_and_missing_file_abort(self):
        for path in ('../secret.html', 'articles/not-found.html'):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / 'articles.json').write_text(json.dumps([{'path': path, 'title': '確認', 'description': '記事', 'checked_at': '2026-10-26'}]))
                with self.assertRaises(ValueError):
                    build(root)
                self.assertFalse((root / 'sitemap.xml').exists())


    def test_seo_meta_is_regenerated_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'articles').mkdir()
            (root / 'articles/example.html').write_text('<html><head><title>見出し&lt;A&gt;｜くらしの手帖</title><meta name="description" content="説明"></head><body><footer>f</footer></body></html>')
            (root / 'index.html').write_text('<html><head><title>トップ</title></head><body><div id="automaticArticles" class="articles" aria-live="polite"></div><footer><div class="footerlinks"></div></footer></body></html>')
            (root / 'articles.json').write_text(json.dumps([{'path': 'articles/example.html', 'title': 't', 'description': 'd', 'checked_at': '2026-10-26'}]))
            build(root)
            build(root)
            article = (root / 'articles/example.html').read_text()
            self.assertEqual(article.count('property="og:title"'), 1)
            self.assertEqual(article.count('application/ld+json'), 1)
            self.assertIn('"dateModified": "2026-10-26"', article)
            self.assertNotIn('<A>', article)
            index = (root / 'index.html').read_text()
            self.assertIn('content="website"', index)
            self.assertNotIn('application/ld+json', index)


    def test_readability_css_once_and_no_layout_css_on_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'articles').mkdir()
            (root / 'articles/example.html').write_text('<html><head></head><body><footer>f</footer></body></html>')
            (root / 'index.html').write_text('<html><head><style>header{background:#fff}</style></head><body><div id="automaticArticles" class="articles" aria-live="polite"></div><footer><div class="footerlinks"></div></footer></body></html>')
            (root / 'articles.json').write_text(json.dumps([{'path': 'articles/example.html', 'title': 't', 'description': 'd', 'checked_at': '2026-10-26'}]))
            build(root)
            build(root)
            index = (root / 'index.html').read_text()
            self.assertEqual(index.count('href="readability.css"'), 1)
            self.assertNotIn('site-support.css', index)
            self.assertEqual((root / 'articles/example.html').read_text().count('href="../readability.css"'), 1)


if __name__ == '__main__':
    unittest.main()
