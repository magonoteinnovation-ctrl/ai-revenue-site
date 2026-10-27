import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
from build_publication import build, BASE, NS, OFFICIAL_URL, page_date


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

    def _site(self, root):
        (root / 'articles').mkdir()
        page = '<html><head><title>{t}｜くらしの手帖</title><meta name="description" content="説明"></head><body><main>{b}</main><footer>f</footer></body></html>'
        (root / 'articles/a.html').write_text(page.format(t='記事A', b='本文'))
        (root / 'articles/b.html').write_text(page.format(t='記事B', b='本文'))
        (root / 'unwanted-items-guide.html').write_text(page.format(t='不用品', b='資料確認日：2026年10月27日'))
        (root / 'pest-control-guide.html').write_text(page.format(t='害虫', b='2026年10月26日公開'))
        (root / 'index.html').write_text('<html><head><title>トップ</title></head><body><div id="automaticArticles" class="articles" aria-live="polite"></div><footer><div class="footerlinks"></div></footer></body></html>')
        (root / 'articles.json').write_text(json.dumps([
            {'path': 'articles/a.html', 'title': '記事A', 'description': 'd', 'checked_at': '2026-10-20', 'category': '掃除・お手入れ'},
            {'path': 'articles/b.html', 'title': '記事B', 'description': 'd', 'checked_at': '2026-10-21', 'category': '片付け・整理'}]))

    def test_related_links_categories_and_breadcrumbs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._site(root)
            build(root)
            build(root)
            b = (root / 'articles/b.html').read_text()
            # 関連記事は1回だけ、同じカテゴリー（片付け・整理）の不用品ガイドが先頭
            self.assertEqual(b.count('<!-- 関連記事 開始 -->'), 1)
            related = b.split('<!-- 関連記事 開始 -->')[1]
            self.assertLess(related.index('../unwanted-items-guide.html'), related.index('../articles/a.html'))
            self.assertNotIn('href="../articles/b.html"', related)
            self.assertIn('"BreadcrumbList"', b)
            listing = (root / 'article-list.html').read_text()
            self.assertIn('id="cat-katazuke"', listing)
            self.assertIn('<h2>掃除・お手入れ</h2>', listing)
            self.assertNotIn('<h3>', listing.split('<h1>')[0])
            # 手書きガイドの日付がサイトマップと構造化データに入る
            sitemap = (root / 'sitemap.xml').read_text()
            self.assertIn('unwanted-items-guide.html</loc><lastmod>2026-10-27', sitemap)
            self.assertIn('pest-control-guide.html</loc><lastmod>2026-10-26', sitemap)

    def test_og_image_only_when_file_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._site(root)
            build(root)
            self.assertNotIn('og:image', (root / 'articles/a.html').read_text())
            (root / 'og-image.png').write_bytes(b'png')
            build(root)
            a = (root / 'articles/a.html').read_text()
            self.assertEqual(a.count('property="og:image"'), 1)
            self.assertIn('summary_large_image', a)

    def test_invalid_category_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._site(root)
            items = json.loads((root / 'articles.json').read_text())
            items[0]['category'] = '存在しない分類'
            (root / 'articles.json').write_text(json.dumps(items))
            with self.assertRaises(ValueError):
                build(root)

    def test_pr_note_only_on_pages_with_ads(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._site(root)
            guide = (root / 'pest-control-guide.html').read_text()
            guide = guide.replace('<main>', '<main><h1>害虫</h1><a href="https://px.a8.net/svt/ejp?a8mat=X" rel="nofollow sponsored">広告</a>')
            (root / 'pest-control-guide.html').write_text(guide)
            build(root)
            build(root)
            self.assertEqual((root / 'pest-control-guide.html').read_text().count('class="pr-note"'), 1)
            self.assertNotIn('pr-note', (root / 'articles/a.html').read_text())

    def test_page_date(self):
        self.assertEqual(page_date('資料確認日：2026年10月27日。掲載日：2026年10月20日'), '2026-10-27')
        self.assertEqual(page_date('2026年10月26日公開'), '2026-10-26')
        self.assertIsNone(page_date('日付なし'))


if __name__ == '__main__':
    unittest.main()
