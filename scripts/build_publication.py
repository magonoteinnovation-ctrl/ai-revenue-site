"""公開記事の一覧・サイトマップ・正規URLを毎回まとめて更新する。"""
from pathlib import Path
import html
import json
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://magonoteinnovation-ctrl.github.io/ai-revenue-site/'
OFFICIAL_URL = 'https://magonote-innovation.wixsite.com/benriya'
START = '<!-- 自動記事一覧 開始 -->'
END = '<!-- 自動記事一覧 終了 -->'
NS = 'http://www.sitemaps.org/schemas/sitemap/0.9'
SUPPORT = [('request-memo.html', '作業依頼メモ'), ('about.html', 'このサイトについて'),
           ('contact.html', 'お問い合わせ'), ('privacy.html', 'プライバシーと広告')]


def support_links(text, prefix, available):
    start, end = '<!-- 共通案内 開始 -->', '<!-- 共通案内 終了 -->'
    links = ''.join(f'<a href="{prefix}{path}">{label}</a>' for path, label in SUPPORT if path in available)
    block = start + '<nav aria-label="サイトのご案内" style="display:flex;flex-wrap:wrap;gap:18px;margin-top:20px">' + links + f'<a href="{OFFICIAL_URL}">便利屋まごの手INNOVATION公式サイト</a>' + '</nav>' + end
    if start in text:
        return re.sub(re.escape(start) + '.*?' + re.escape(end), lambda _: block, text, flags=re.S)
    return text.replace('</footer>', block + '</footer>') if links else text


def valid_articles(root):
    items = json.loads((root / 'articles.json').read_text(encoding='utf-8'))
    seen = set()
    for item in items:
        path = item.get('path', '')
        if not re.fullmatch(r'articles/[a-z0-9-]+\.html', path):
            raise ValueError('記事のURLが不正です')
        if path in seen or not (root / path).is_file():
            raise ValueError('記事ファイルが見つからないか重複しています')
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', item.get('checked_at', '')):
            raise ValueError('記事の日付が不正です')
        for field in ('title', 'description'):
            if not isinstance(item.get(field), str):
                raise ValueError('記事情報が不正です')
        seen.add(path)
    return items


def cards(items):
    e = html.escape
    return ''.join(
        '<article class="article"><span class="tag">公式資料から読む暮らしのヒント</span>'
        f'<h3><a href="{e(x["path"], quote=True)}">{e(x["title"])}</a></h3>'
        f'<p>{e(x["description"])}</p><p>資料確認日：{e(x["checked_at"])}</p></article>'
        for x in items)


def set_canonical(text, url):
    # 所有権確認のみ。広告配信スクリプトは審査・同意設定後に追加する。
    meta = '<meta name="google-adsense-account" content="ca-pub-8158546915072061">'
    if 'name="google-adsense-account"' not in text:
        text = text.replace('</head>', meta + '\n</head>')
    text = re.sub(r'<link\b[^>]*\brel=["\x27]canonical["\x27][^>]*>\s*', '', text, flags=re.I)
    return text.replace('</head>', '<link rel="canonical" href="' + html.escape(url, quote=True) + '">\n</head>')


def build(root=ROOT):
    items = valid_articles(root)
    index_path = root / 'index.html'
    index = index_path.read_text(encoding='utf-8')
    block = START + '<div id="automaticArticles" class="articles" aria-live="polite">' + cards(items) + '</div>' + END
    if START in index and END in index:
        index = re.sub(re.escape(START) + '.*?' + re.escape(END), lambda _: block, index, flags=re.S)
    else:
        marker = '<div id="automaticArticles" class="articles" aria-live="polite"></div>'
        if marker not in index:
            raise ValueError('トップページの記事一覧の挿入先が見つかりません')
        index = index.replace(marker, block)
    # JavaScriptでの一覧生成をやめ、検索エンジンにも読める通常のリンクにする。
    index = re.sub(r'\n// 公開済みの記事一覧だけを読み込みます。.*?\.catch\(\(\)=>\{\}\);\n', '\n', index, flags=re.S)
    if '<a href="article-list.html">記事一覧</a>' not in index:
        index = index.replace('<div class="footerlinks">', '<div class="footerlinks"><a href="article-list.html">記事一覧</a>')
    index_path.write_text(set_canonical(index, BASE), encoding='utf-8')
    e = html.escape
    list_page = '''<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="くらしの手帖の公開記事一覧。掃除や住まいの困りごとを公式資料とともに紹介します。">
<title>記事一覧｜くらしの手帖</title><style>
body{margin:0;background:#faf8f2;color:#1b2d29;font-family:Meiryo,sans-serif;line-height:1.9}
header,footer{padding:24px;background:#173b32;color:#fff}header a,footer a{color:#fff}
main{max-width:900px;padding:40px 22px 70px;margin:auto}h1{font-size:34px}
.article{background:white;border:1px solid #dce5db;border-radius:16px;padding:24px;margin:20px 0}
.article h3{font-size:22px;line-height:1.6}.article p{color:#53685e}a{color:#276a4c}.tag{font-size:13px;color:#276a4c}
</style></head><body><header><a href="index.html">くらしの手帖｜トップへ戻る</a></header>
<main><h1>暮らしに役立つ記事一覧</h1><p>公式資料をもとにした記事には、出典と資料の確認日を掲載しています。</p>'''
    list_page += cards(items)
    list_page += '<article class="article"><span class="tag">住まい・生活支援</span><h3><a href="pest-control-guide.html">家で害虫・害獣を見つけたら？</a></h3><p>安全に確認する手順と、専門業者に相談する際の確認項目。</p></article>'
    if (root / 'unwanted-items-guide.html').is_file():
        list_page += '<article class="article"><span class="tag">片付け・整理</span><h3><a href="unwanted-items-guide.html">不用品の処分・買取ガイド</a></h3><p>買取、自治体処分、業者依頼を選ぶ前の確認事項。</p></article>'
    list_page += '<p><a href="sitemap.xml">検索エンジン向けのサイトマップ</a></p></main><footer>くらしの手帖</footer></body></html>'
    (root / 'article-list.html').write_text(set_canonical(list_page, BASE + 'article-list.html'), encoding='utf-8')
    available = [path for path, _ in SUPPORT if (root / path).is_file()]
    paths = [p for p in ['pest-control-guide.html', 'unwanted-items-guide.html'] if (root / p).is_file()] + [x['path'] for x in items] + available
    for path in ['index.html', 'article-list.html'] + paths:
        file = root / path
        text = set_canonical(file.read_text(encoding='utf-8'), BASE + ('' if path == 'index.html' else path))
        text = support_links(text, '../' if path.startswith('articles/') else '', available)
        file.write_text(text, encoding='utf-8')
    ET.register_namespace('', NS)
    sitemap = ET.Element('{' + NS + '}urlset')
    dated = {x['path']: x['checked_at'] for x in items}
    for path in ['', 'article-list.html'] + paths:
        entry = ET.SubElement(sitemap, '{' + NS + '}url')
        ET.SubElement(entry, '{' + NS + '}loc').text = BASE + path
        if path in dated:
            ET.SubElement(entry, '{' + NS + '}lastmod').text = dated[path]
    ET.ElementTree(sitemap).write(root / 'sitemap.xml', encoding='utf-8', xml_declaration=True)
    print(f'記事一覧とサイトマップを更新しました（{len(paths) + 2}ページ）。')


if __name__ == '__main__':
    build()
