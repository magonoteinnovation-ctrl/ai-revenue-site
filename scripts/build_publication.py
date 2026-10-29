"""公開記事の一覧・サイトマップ・正規URLを毎回まとめて更新する。"""
from pathlib import Path
import html
import json
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://magonoteinnovation-ctrl.github.io/ai-revenue-site/'
OFFICIAL_URL = 'https://magonote-innovation.wixsite.com/benriya'
# 運営会社の公式SNS（Wix公式サイトに掲載されているアカウント）
SNS_LINKS = [('Instagram', 'https://www.instagram.com/magonoteinnovation/'), ('X（旧Twitter）', 'https://x.com/benriyamagonote')]
GUIDE_PATHS = ('pest-control-guide.html', 'unwanted-items-guide.html')
# カテゴリー（トップの「お悩みから探す」の3分類＋仕事・副業の効率化）。記事一覧の見出しと関連記事に使う。
CATEGORIES = [('katazuke', '片付け・整理'), ('souji', '掃除・お手入れ'), ('sumai', '住まい・生活支援'),
              ('shigoto', '仕事・副業の効率化')]
CATEGORY_NAMES = [name for _, name in CATEGORIES]
DEFAULT_CATEGORY = '住まい・生活支援'
# 手書きのガイド（トップ直下のページ）。存在するものだけを一覧・関連記事・サイトマップに載せる。
GUIDES = [
    {'path': 'unwanted-items-guide.html', 'category': '片付け・整理', 'title': '不用品の処分・買取で迷ったときの確認表',
     'description': '買取、自治体処分、業者依頼を選ぶ前の確認事項と、許可業者の確かめ方。'},
    {'path': 'pest-control-guide.html', 'category': '住まい・生活支援', 'title': '家で害虫・害獣を見つけたら？',
     'description': '安全に確認する手順と、専門業者に相談する際の確認項目。'},
]
OG_IMAGE = 'og-image.png'
RELATED_START, RELATED_END = '<!-- 関連記事 開始 -->', '<!-- 関連記事 終了 -->'
START = '<!-- 自動記事一覧 開始 -->'
END = '<!-- 自動記事一覧 終了 -->'
NS = 'http://www.sitemaps.org/schemas/sitemap/0.9'
SUPPORT = [('request-memo.html', '作業依頼メモ'), ('about.html', 'このサイトについて'),
           ('contact.html', 'お問い合わせ'), ('privacy.html', 'プライバシーと広告')]


def support_links(text, prefix, available):
    start, end = '<!-- 共通案内 開始 -->', '<!-- 共通案内 終了 -->'
    links = ''.join(f'<a href="{prefix}{path}">{label}</a>' for path, label in SUPPORT if path in available)
    block = start + '<nav aria-label="サイトのご案内" style="display:flex;flex-wrap:wrap;gap:18px;margin-top:20px">' + links + f'<a href="{OFFICIAL_URL}">便利屋まごの手INNOVATION公式サイト</a>' + ''.join(
        f'<a href="{url}" rel="noopener">公式{label}</a>' for label, url in SNS_LINKS) + '</nav>' + end
    if start in text:
        return re.sub(re.escape(start) + '.*?' + re.escape(end), lambda _: block, text, flags=re.S)
    return text.replace('</footer>', block + '</footer>') if '</footer>' in text else text


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
        if item.get('category', DEFAULT_CATEGORY) not in CATEGORY_NAMES:
            raise ValueError('記事のカテゴリーが不正です')
        seen.add(path)
    return items


def cards(items):
    e = html.escape
    return ''.join(
        f'<article class="article"><span class="tag">{e(x.get("category", DEFAULT_CATEGORY))}</span>'
        f'<h3><a href="{e(x["path"], quote=True)}">{e(x["title"])}</a></h3>'
        f'<p>{e(x["description"])}</p>'
        + (f'<p>{e(x.get("date_label", "資料確認日"))}：{e(x["checked_at"])}</p>' if x.get('checked_at') else '') + '</article>'
        for x in items)


def page_date(text):
    """手書きページの本文から日付を読み取る（資料確認日 → 掲載日 → 「YYYY年M月D日公開」の順）。"""
    patterns = [r'資料確認日[^0-9]{0,3}(\d{4})[-年/](\d{1,2})[-月/](\d{1,2})',
                r'確認日[^0-9]{0,3}(\d{4})[-年/](\d{1,2})[-月/](\d{1,2})',
                r'掲載日[^0-9]{0,3}(\d{4})[-年/](\d{1,2})[-月/](\d{1,2})',
                r'(\d{4})年(\d{1,2})月(\d{1,2})日公開']
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return '%04d-%02d-%02d' % tuple(int(x) for x in m.groups())
    return None


def catalog(root, items):
    """手書きガイドと自動・手書き記事をまとめた一覧（カテゴリー・日付つき）。"""
    entries = []
    for g in GUIDES:
        if (root / g['path']).is_file():
            entries.append(dict(g, checked_at=page_date((root / g['path']).read_text(encoding='utf-8')), date_label='更新日'))
    for x in items:
        entries.append(dict(x, category=x.get('category', DEFAULT_CATEGORY)))
    return entries


def related_block(path, entries, limit=3):
    """同じカテゴリーを優先して、他の記事への関連リンクを作る。"""
    e = html.escape
    me = next((x for x in entries if x['path'] == path), None)
    if not me:
        return ''
    others = [x for x in entries if x['path'] != path]
    others.sort(key=lambda x: (x['category'] != me['category'], entries.index(x)))
    prefix = '../' if path.startswith('articles/') else ''
    links = ''.join(f'<li><a href="{prefix}{e(x["path"], quote=True)}">{e(x["title"])}</a>'
                    f'<span class="tag">{e(x["category"])}</span></li>' for x in others[:limit])
    if not links:
        return ''
    return (RELATED_START + '<section class="related" aria-label="関連記事"><h2>あわせて読みたい記事</h2><ul>' + links +
            f'</ul><p><a href="{prefix}article-list.html">記事一覧を見る</a></p></section>' + RELATED_END)


PR_START, PR_END = '<!-- 広告表記 開始 -->', '<!-- 広告表記 終了 -->'
PR_NOTE = (PR_START + '<p class="pr-note">このページには広告（PR）を含みます。広告の有無にかかわらず、'
           '確認事項は公的資料などをもとに整理しています。</p>' + PR_END)


def set_pr_note(text):
    """広告リンクを含む記事ページでは、ページ上部に広告を含む旨を表示する（なければ取り除く）。"""
    text = re.sub(re.escape(PR_START) + '.*?' + re.escape(PR_END), '', text, flags=re.S)
    body = text.split('<body', 1)[-1]
    if 'px.a8.net' in body and '</h1>' in text:
        text = text.replace('</h1>', '</h1>' + PR_NOTE, 1)
    return text


def set_related(text, block):
    text = re.sub(re.escape(RELATED_START) + '.*?' + re.escape(RELATED_END), '', text, flags=re.S)
    return text.replace('</main>', block + '</main>', 1) if block else text


SEO_START, SEO_END = '<!-- SEO 開始 -->', '<!-- SEO 終了 -->'
PUBLISHER = '株式会社まごの手INNOVATION'


def seo_meta(text, url, kind, modified=None, image=None):
    """OGPと構造化データを毎回作り直す。手書きのタグとは重複させない。"""
    e = lambda v: html.escape(v, quote=True)
    title = re.search(r'<title>(.*?)</title>', text, re.S)
    desc = re.search(r'<meta name="description" content="([^"]*)"', text)
    title = html.unescape(title.group(1).strip()) if title else 'くらしの手帖'
    desc = html.unescape(desc.group(1)) if desc else ''
    tags = [f'<meta property="og:{k}" content="{e(v)}">' for k, v in (
        ('type', 'article' if kind == 'article' else 'website'), ('site_name', 'くらしの手帖'),
        ('title', title), ('description', desc), ('url', url), ('locale', 'ja_JP'))]
    if image:
        tags.append(f'<meta property="og:image" content="{e(image)}">')
        tags.append('<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">')
    tags.append('<meta name="twitter:card" content="%s">' % ('summary_large_image' if image else 'summary'))
    if kind == 'article':
        headline = title.split('｜')[0][:110]
        data = {'@type': 'Article', 'headline': headline,
                'description': desc, 'mainEntityOfPage': url, 'inLanguage': 'ja',
                'author': {'@type': 'Organization', 'name': PUBLISHER, 'url': OFFICIAL_URL},
                'publisher': {'@type': 'Organization', 'name': PUBLISHER, 'url': OFFICIAL_URL}}
        if modified:
            data['dateModified'] = modified
        if image:
            data['image'] = image
        crumbs = {'@type': 'BreadcrumbList', 'itemListElement': [
            {'@type': 'ListItem', 'position': 1, 'name': 'くらしの手帖', 'item': BASE},
            {'@type': 'ListItem', 'position': 2, 'name': '記事一覧', 'item': BASE + 'article-list.html'},
            {'@type': 'ListItem', 'position': 3, 'name': headline, 'item': url}]}
        graph = {'@context': 'https://schema.org', '@graph': [data, crumbs]}
        tags.append('<script type="application/ld+json">' +
                    json.dumps(graph, ensure_ascii=False).replace('<', '\\u003c') + '</script>')
    block = SEO_START + ''.join(tags) + SEO_END
    text = re.sub(re.escape(SEO_START) + '.*?' + re.escape(SEO_END) + r'\n?', '', text, flags=re.S)
    return text.replace('</head>', block + '\n</head>', 1)


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
<meta name="description" content="片付け・不用品処分、掃除、引越し、住まいのトラブルを解決するための確認表・記事一覧。公的資料と便利屋の現場目線をもとに、依頼前に知りたいポイントを整理。">
<title>記事一覧｜くらしの手帖</title><style>
body{margin:0;background:#faf8f2;color:#1b2d29;font-family:Meiryo,sans-serif;line-height:1.9}
header,footer{padding:24px;background:#173b32;color:#fff}header a,footer a{color:#fff}
main{max-width:900px;padding:40px 22px 70px;margin:auto}h1{font-size:34px}
.article{background:white;border:1px solid #dce5db;border-radius:16px;padding:24px;margin:20px 0}
.article h3{font-size:22px;line-height:1.6}h2{margin-top:40px;font-size:26px}.cats{display:flex;flex-wrap:wrap;gap:20px 22px;margin:18px 0}.cats a{font-weight:700}.article p{color:#53685e}a{color:#276a4c}.tag{font-size:13px;color:#276a4c}
</style></head><body><header><a href="index.html">くらしの手帖｜トップへ戻る</a></header>
<main><h1>片付け・掃除・住まいの困りごとを解決する記事一覧</h1><p>不用品処分、遺品整理、ハウスクリーニング、引越し、住まいのトラブルなど、依頼前に確認したいことをテーマ別にまとめました。公式資料を参照した記事には、出典と資料の確認日を掲載しています。</p><p>作業を依頼する前に条件を整理したい方は、<a href="request-memo.html">無料の作業依頼メモ作成ツール</a>もご活用ください。</p>'''
    entries = catalog(root, items)
    list_page += '<nav class="cats" aria-label="カテゴリー">' + ''.join(
        f'<a href="#cat-{key}">{e(name)}</a>' for key, name in CATEGORIES
        if any(x['category'] == name for x in entries)) + '</nav>'
    for key, name in CATEGORIES:
        group = [x for x in entries if x['category'] == name]
        if group:
            list_page += f'<section id="cat-{key}"><h2>{e(name)}</h2>' + cards(group) + '</section>'
    list_page += '</main><footer>くらしの手帖</footer></body></html>'
    (root / 'article-list.html').write_text(set_canonical(list_page, BASE + 'article-list.html'), encoding='utf-8')
    available = [path for path, _ in SUPPORT if (root / path).is_file()]
    dated_items = {x['path']: x['checked_at'] for x in items}
    paths = [g['path'] for g in GUIDES if (root / g['path']).is_file()] + [x['path'] for x in items] + available
    image = BASE + OG_IMAGE if (root / OG_IMAGE).is_file() else None
    dated_items.update({x['path']: x['checked_at'] for x in entries if x.get('checked_at')})
    for path in ['index.html', 'article-list.html'] + paths:
        file = root / path
        text = set_canonical(file.read_text(encoding='utf-8'), BASE + ('' if path == 'index.html' else path))
        text = support_links(text, '../' if path.startswith('articles/') else '', available)
        # 文字サイズ・コントラストの共通CSSを全ページに適用（再生成時も重複させない）
        # 案内ページ用のレイアウトCSSをトップに適用しない
        css_path = '../readability.css' if path.startswith('articles/') else 'readability.css'
        css_tag = f'<link rel="stylesheet" href="{css_path}" data-site-readability="true">'
        text = re.sub(r'<link[^>]+data-site-readability="true"[^>]*>\n?', '', text)
        text = text.replace('</head>', css_tag + '\n</head>', 1)
        kind = 'article' if path.startswith('articles/') or path in GUIDE_PATHS else 'page'
        if kind == 'article':
            text = set_related(text, related_block(path, entries))
            text = set_pr_note(text)
        text = seo_meta(text, BASE + ('' if path == 'index.html' else path), kind, dated_items.get(path), image)
        file.write_text(text, encoding='utf-8')
    ET.register_namespace('', NS)
    sitemap = ET.Element('{' + NS + '}urlset')
    dated = dated_items
    for path in ['', 'article-list.html'] + paths:
        entry = ET.SubElement(sitemap, '{' + NS + '}url')
        ET.SubElement(entry, '{' + NS + '}loc').text = BASE + path
        if path in dated:
            ET.SubElement(entry, '{' + NS + '}lastmod').text = dated[path]
    ET.ElementTree(sitemap).write(root / 'sitemap.xml', encoding='utf-8', xml_declaration=True)
    # 予備のテキスト形式サイトマップ（1行1URL、UTF-8）。sitemap.xml と同じURL一覧から作る
    (root / 'sitemap.txt').write_text(
        ''.join(BASE + path + '\n' for path in ['', 'article-list.html'] + paths), encoding='utf-8')
    print(f'記事一覧とサイトマップを更新しました（{len(paths) + 2}ページ）。')


if __name__ == '__main__':
    build()
