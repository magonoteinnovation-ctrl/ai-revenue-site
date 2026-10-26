import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
from build_publication import build, BASE, NS


class PublicationTests(unittest.TestCase):
    def test_build_links_escape_and_sitemap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'articles').mkdir()
            (root / 'articles/example.html').write_text('<html><head></head><body>記事</body></html>')
            (root / 'pest-control-guide.html').write_text('<html><head></head></html>')
            (root / 'index.html').write_text('<html><head></head><body><div id="automaticArticles" class="articles" aria-live="polite"></div><div class="footerlinks"></div></body></html>')
            (root / 'articles.json').write_text(json.dumps([{'path': 'articles/example.html', 'title': '<危険>', 'description': '掃除 & 住まい', 'checked_at': '2026-10-26'}]))
            build(root)
            before = (root / 'index.html').read_text()
            build(root)
            self.assertEqual(before, (root / 'index.html').read_text())
            self.assertIn('&lt;危険&gt;', before)
            self.assertIn('href="articles/example.html"', before)
            self.assertEqual(before.count('rel="canonical"'), 1)
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


if __name__ == '__main__':
    unittest.main()
