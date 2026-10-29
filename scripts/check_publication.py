"""公開前にサイト内リンクとページ内の移動先を検証する。外部通信は行わない。"""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]

class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('id'):
            self.ids.add(attrs['id'])
        key = 'href' if tag in ('a', 'link') else 'src' if tag in ('img', 'script') else None
        if key and attrs.get(key):
            self.refs.append(attrs[key])

# 掲載を承認済みのA8.net広告（a8mat の値）。新しい案件は提携承認を確認してからここに追加する。
APPROVED_A8 = {'4BEPPP+7WL8PM+4X26+TRVYQ',
               '4BERA4+2WSC0Q+4JGQ+BX3J6',  # マネーフォワード クラウド確定申告（2026-10-29提携）
               '45K6H2+8JT5AY+348+64Z8Y',  # ロリポップ！（くらしの手帖掲載用）
               '4BERA4+34IYVU+2PEO+6C1VM',  # ココナラ出品者募集（2026-10-29提携）
               # バナー素材（2026-10-29 A8管理画面「広告リンク作成」で掲載サイト＝くらしの手帖を選んで取得）
               '4BEPPP+7WL8PM+4X26+TSJ41',  # FireWorks 300x250
               '4BERA4+2WSC0Q+4JGQ+BYDTT',  # マネーフォワード クラウド確定申告 300x250
               '4BERA4+34IYVU+2PEO+64C3L',  # ココナラ 300x250
               '45K6H2+8JT5AY+348+6EMGX'}  # ロリポップ！ 336x280


def seo_errors(name, text):
    """公開ページのSEO情報・広告表記が壊れていないかを確認する。"""
    errors = []
    if len(re.findall(r'<title>', text)) != 1:
        errors.append(f'{name}: titleが1つではありません')
    if len(re.findall(r'rel=["\']canonical["\']', text)) != 1:
        errors.append(f'{name}: canonicalが1つではありません')
    desc = re.search(r'<meta name="description" content="([^"]*)"', text)
    if not desc or not desc.group(1).strip():
        errors.append(f'{name}: meta descriptionがありません')
    elif len(desc.group(1)) > 160:
        errors.append(f'{name}: meta descriptionが長すぎます（{len(desc.group(1))}字）')
    if len(re.findall(r'<h1[\s>]', text)) != 1:
        errors.append(f'{name}: h1が1つではありません')
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', text, re.S):
        try:
            json.loads(block)
        except ValueError:
            errors.append(f'{name}: 構造化データのJSONが壊れています')
    for tag in re.findall(r'<a\b[^>]*href="https?://px\.a8\.net/[^"]*"[^>]*>', text):
        if 'sponsored' not in tag:
            errors.append(f'{name}: A8.netの広告リンクに rel="sponsored" がありません')
        mat = re.search(r'a8mat=([^"&]+)', tag)
        if not mat or mat.group(1) not in APPROVED_A8:
            errors.append(f'{name}: 承認済み一覧にないA8.net広告リンクがあります')
    if 'a8.net' in text and not re.search(r'広告|PR', text):
        errors.append(f'{name}: 広告リンクがあるのに「広告」「PR」の表示がありません')
    return errors


def check(root=ROOT):
    root = root.resolve()
    files = sorted(root.glob('*.html')) + sorted((root / 'articles').glob('*.html'))
    pages = {}
    for file in files:
        page = Page()
        page.feed(file.read_text(encoding='utf-8'))
        pages[file.resolve()] = page
    errors = []
    if not (root / 'index.html').is_file():
        errors.append('トップページがありません')
    for file, page in pages.items():
        for ref in page.refs:
            url = urlsplit(ref)
            if url.scheme or url.netloc:
                continue
            target = (root / unquote(url.path).lstrip('/')) if url.path.startswith('/') else (file.parent / unquote(url.path)) if url.path else file
            target = target.resolve()
            if not target.is_relative_to(root):
                errors.append(f'{file.relative_to(root)}: 公開範囲外のリンク {ref}')
            elif not target.is_file():
                errors.append(f'{file.relative_to(root)}: リンク先がありません {ref}')
            elif url.fragment and target in pages and unquote(url.fragment) not in pages[target].ids:
                errors.append(f'{file.relative_to(root)}: ページ内の移動先がありません {ref}')
    for file in pages:
        errors.extend(seo_errors(str(file.relative_to(root)), file.read_text(encoding='utf-8')))
    if errors:
        for error in errors:
            print(error)
        return 1
    print(f'公開前リンク検査に成功しました（{len(pages)}ページ）。')
    return 0

if __name__ == '__main__':
    sys.exit(check())
