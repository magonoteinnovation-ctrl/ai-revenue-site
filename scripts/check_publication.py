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
               '45K6H2+8JT5AY+348+6EMGX',  # ロリポップ！ 336x280
               '3HC21T+C6SIE2+2HOM+BWGDT',  # 楽天市場 商品リンク（A8楽天ツール・掲載サイト＝くらしの手帖、2026-10-29）
               '3HC21T+C6SIE2+2HOM+6B70I',  # 楽天市場トップ テキスト素材「楽天市場」（現在は未使用）
               '3HC21T+C6SIE2+2HOM+BW8O1'}  # 楽天市場トップ 任意ページリンク（A8楽天ツール、表示テキストを生成時に指定、くらしの手帖、2026-10-29）


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
    for tag in re.findall(r'<a\b[^>]*href="https?://r?px\.a8\.net/[^"]*"[^>]*>', text):
        if 'sponsored' not in tag:
            errors.append(f'{name}: A8.netの広告リンクに rel="sponsored" がありません')
        mat = re.search(r'a8mat=([^"&]+)', tag)
        if not mat or mat.group(1) not in APPROVED_A8:
            errors.append(f'{name}: 承認済み一覧にないA8.net広告リンクがあります')
    if 'a8.net' in text and not re.search(r'広告|PR', text):
        errors.append(f'{name}: 広告リンクがあるのに「広告」「PR」の表示がありません')
    return errors



def app_errors(root):
    """アプリ版（app/）のマニフェスト・アイコン・内部リンクと、広告リンクを置いていないことを確認する。"""
    app = root / 'app'
    if not app.is_dir():
        return []
    errors = []
    page = app / 'index.html'
    if not page.is_file():
        return ['app: index.html がありません']
    text = page.read_text(encoding='utf-8')
    try:
        manifest = json.loads((app / 'manifest.webmanifest').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return ['app: manifest.webmanifest が読めません']
    for key in ('name', 'short_name', 'start_url', 'scope', 'display', 'icons'):
        if not manifest.get(key):
            errors.append(f'app: manifest に {key} がありません')
    sizes = {i.get('sizes') for i in manifest.get('icons', [])}
    if not {'192x192', '512x512'} <= sizes:
        errors.append('app: 192x192 と 512x512 のアイコンが必要です')
    for icon in manifest.get('icons', []):
        if not (app / icon.get('src', '')).is_file():
            errors.append(f"app: アイコンがありません {icon.get('src')}")
    if 'rel="manifest"' not in text:
        errors.append('app: index.html に manifest のリンクがありません')
    # アプリ版には広告（アフィリエイト）リンクを置かない（各提携先のアプリ利用条件を確認するまで）
    if re.search(r'a8\.net|amazon\.co\.jp|amzn\.|rakuten', text):
        errors.append('app: アプリ版の画面に広告・ショッピングサイトへのリンクがあります')
    for ref in re.findall(r'(?:href|src)="([^"]+)"', text):
        url = urlsplit(ref)
        if url.scheme or url.netloc or not url.path:
            continue
        target = (app / unquote(url.path)).resolve()
        if not target.is_relative_to(root):
            errors.append(f'app: 公開範囲外のリンク {ref}')
        elif not target.is_file():
            errors.append(f'app: リンク先がありません {ref}')
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
    index_file = root / 'index.html'
    if root == ROOT.resolve() and index_file.is_file():
        # トップの「気になるテーマを選ぶ」直下の楽天市場（A8）導線が、自動更新などで消えていないか確認する
        top = index_file.read_text(encoding='utf-8')
        cta = re.search(r'<!-- 楽天市場トップ（A8）開始 -->(.*?)<!-- 楽天市場トップ（A8）終了 -->', top, flags=re.S)
        if not cta or 'a8mat=3HC21T+C6SIE2+2HOM+BW8O1' not in cta.group(1) or 'PR' not in cta.group(1):
            errors.append('index.html: 楽天市場トップ（A8）の導線がないか、計測コード・PR表記が欠けています')
        elif top.find('id="categories"') > top.find('<!-- 楽天市場トップ（A8）開始 -->'):
            errors.append('index.html: 楽天市場トップ（A8）の導線が「気になるテーマを選ぶ」より上にあります')
        # Amazonアソシエイトの導線（正規の特別リンク・トラッキングID・開示文言・PR表記）が残っているか確認する
        amz = re.search(r'<!-- Amazonトップ（アソシエイト）開始 -->(.*?)<!-- Amazonトップ（アソシエイト）終了 -->', top, flags=re.S)
        if not amz or 'tag=magonoteinnov-22' not in amz.group(1) or 'sponsored' not in amz.group(1) \
                or '適格販売により収入を得ています' not in amz.group(1) or 'PR' not in amz.group(1):
            errors.append('index.html: Amazonアソシエイトの導線がないか、トラッキングID・開示文言・PR表記が欠けています')
        elif top.find('id="categories"') > top.find('<!-- Amazonトップ（アソシエイト）開始 -->'):
            errors.append('index.html: Amazonの導線が「気になるテーマを選ぶ」より上にあります')
    errors.extend(app_errors(root))
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
