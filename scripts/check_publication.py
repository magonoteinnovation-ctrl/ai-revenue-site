"""公開前にサイト内リンクとページ内の移動先を検証する。外部通信は行わない。"""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote
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
    if errors:
        for error in errors:
            print(error)
        return 1
    print(f'公開前リンク検査に成功しました（{len(pages)}ページ）。')
    return 0

if __name__ == '__main__':
    sys.exit(check())
