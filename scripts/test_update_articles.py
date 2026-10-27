import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

spec = importlib.util.spec_from_file_location('updater', Path(__file__).with_name('update_articles.py'))
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)

SOURCE = '省エネの工夫を行う際は、取扱説明書を確認し、無理のない範囲で取り組むことが大切です。'
TEXT = ('使い方を見直すときは、まず機器の取扱説明書を読み、使える機能や注意事項を確認しましょう。'
        '日々の生活で続けやすい方法を選び、無理のない範囲で取り組むことが大切です。')
ARTICLE = {'title': '無理なく省エネに取り組むための確認事項', 'sections': [
    {'heading': '取扱説明書の確認', 'text': TEXT, 'evidence': SOURCE} for _ in range(3)]}


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for name, value in [('automation-state.json', {}), ('articles.json', [])]:
            (self.root / name).write_text(json.dumps(value))
        self.root_patch = patch.object(updater, 'ROOT', self.root)
        self.root_patch.start()

    def tearDown(self):
        self.root_patch.stop()
        self.temp.cleanup()

    def test_without_confirmation_never_calls_network(self):
        with patch.dict('os.environ', {}, clear=True), patch.object(updater, 'fetch_source') as fetch:
            updater.main()
            fetch.assert_not_called()

    def test_missing_key_never_calls_network(self):
        with patch.dict('os.environ', {'GEMINI_FREE_TIER_CONFIRMED': 'true'}, clear=True), patch.object(updater, 'fetch_source') as fetch:
            updater.main()
            fetch.assert_not_called()

    def test_unchanged_sources_never_call_gemini(self):
        state = {s['slug']: {'hash': hashlib.sha256(updater.normalize(SOURCE).encode()).hexdigest()} for s in updater.SOURCES}
        (self.root / 'automation-state.json').write_text(json.dumps(state))
        with patch.dict('os.environ', {'GEMINI_FREE_TIER_CONFIRMED': 'true', 'GEMINI_API_KEY': 'test'}, clear=True), patch.object(updater, 'fetch_source', return_value=SOURCE), patch.object(updater, 'generate') as generate:
            updater.main()
            generate.assert_not_called()

    def test_missing_evidence_rejected(self):
        article = copy.deepcopy(ARTICLE)
        article['sections'][0]['evidence'] = '原文には存在していない根拠を勝手に作ってはいけません。'
        with self.assertRaises(ValueError):
            updater.validate(article, SOURCE)

    def test_html_and_numbers_rejected(self):
        for title in ['<script>危険なコード</script>', '電気代が必ず100円安くなる']:
            article = copy.deepcopy(ARTICLE)
            article['title'] = title
            with self.assertRaises(ValueError):
                updater.validate(article, SOURCE)

    def test_quota_error_does_not_write_files(self):
        with patch.dict('os.environ', {'GEMINI_FREE_TIER_CONFIRMED': 'true', 'GEMINI_API_KEY': 'test'}, clear=True), patch.object(updater, 'fetch_source', return_value=SOURCE), patch.object(updater, 'generate', side_effect=urllib.error.HTTPError('https://example.com', 429, 'Quota', {}, None)):
            with self.assertRaises(urllib.error.HTTPError):
                updater.main()
        self.assertEqual(json.loads((self.root / 'articles.json').read_text()), [])
        self.assertFalse((self.root / 'articles').exists())

    def test_success_updates_only_one_article(self):
        updater.validate(ARTICLE, SOURCE)
        with patch.dict('os.environ', {'GEMINI_FREE_TIER_CONFIRMED': 'true', 'GEMINI_API_KEY': 'test'}, clear=True), patch.object(updater, 'fetch_source', return_value=SOURCE), patch.object(updater, 'generate', return_value=ARTICLE) as generate:
            updater.main()
        generate.assert_called_once()
        listing = json.loads((self.root / 'articles.json').read_text())
        self.assertEqual(len(listing), 1)
        page = (self.root / listing[0]['path']).read_text()
        self.assertIn(updater.SOURCES[0]['url'], page)
        self.assertNotIn('GEMINI_API_KEY', page)
        self.assertIn('AIで要約', page)

    def test_manual_articles_are_not_regenerated(self):
        slugs = {s['slug'] for s in updater.SOURCES}
        self.assertFalse(slugs & updater.MANUAL_ARTICLES)
        self.assertIn('house-cleaning-checklist', updater.MANUAL_ARTICLES)

    def test_summary_is_short_and_ends_at_sentence(self):
        long_text = '最初の文はここで終わります。' * 12
        result = updater.summary(long_text)
        self.assertLessEqual(len(result), 110)
        self.assertTrue(result.endswith('。'))
        self.assertEqual(updater.summary('短い文。'), '短い文。')

    def test_new_listing_keeps_category(self):
        with patch.dict('os.environ', {'GEMINI_FREE_TIER_CONFIRMED': 'true', 'GEMINI_API_KEY': 'test'}, clear=True), patch.object(updater, 'fetch_source', return_value=SOURCE), patch.object(updater, 'generate', return_value=ARTICLE):
            updater.main()
        listing = json.loads((self.root / 'articles.json').read_text())
        self.assertEqual(listing[0]['category'], updater.SOURCES[0]['category'])
        self.assertLessEqual(len(listing[0]['description']), 110)


if __name__ == '__main__':
    unittest.main()
