"""トップの買い物ボタン（hero-shop）と手動広告枠（top-ad）、代表記事へのリンクを検査する。

使い方:
  python scripts/check_live_site.py                # 公開中のサイト（両方のトップURL）を検査
  python scripts/check_live_site.py --file index.html   # 公開前のファイルを検査

広告リンクはクリックせず、HTMLの内容だけを照合する。
広告枠の「設置」だけを確認し、実際の配信実績はAdSense管理画面で確認する。
収益データや認証情報は扱わない。
"""
import argparse
import html.parser
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = 'https://magonoteinnovation-ctrl.github.io/ai-revenue-site/'
TOP_URLS = [BASE, BASE + 'index.html']
AMAZON_TAG = 'tag=magonoteinnov-22'
RAKUTEN_A8 = 'a8mat=3HC21T+C6SIE2+2HOM+BW8O1'
AD_CLIENT = 'ca-pub-8158546915072061'
AD_SLOT = '2417620558'
ARTICLE_SAMPLES = 3
UA = 'Mozilla/5.0 (compatible; ai-revenue-site-check/1.0)'


class TopParser(html.parser.HTMLParser):
    """hero-shop と top-ad の中身、記事リンクを集める。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []  # (tag, region)
        self.hero_links = []
        self.top_ad_ins = []
        self.all_slots = []
        self.article_links = []

    def _region(self):
        for _, region in reversed(self.stack):
            if region:
                return region
        return None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = (a.get('class') or '').split()
        region = 'hero-shop' if 'hero-shop' in classes else 'top-ad' if 'top-ad' in classes else None
        current = region or self._region()
        if tag == 'a':
            href = a.get('href') or ''
            if current == 'hero-shop':
                self.hero_links.append({'href': href, 'rel': a.get('rel') or ''})
            path = urllib.parse.urlparse(href).path
            if path.startswith('articles/') or '/articles/' in path:
                if path.endswith('.html') and href not in self.article_links:
                    self.article_links.append(href)
        if tag == 'ins' and 'adsbygoogle' in classes:
            if a.get('data-ad-slot'):
                self.all_slots.append(a.get('data-ad-slot'))
            if current == 'top-ad':
                self.top_ad_ins.append(a)
        if tag not in ('img', 'br', 'hr', 'meta', 'link', 'input', 'source', 'wbr'):
            self.stack.append((tag, region))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break


def check_top_html(text, label):
    """トップHTMLを検査し、(エラー一覧, 記事リンク一覧) を返す。"""
    p = TopParser()
    p.feed(text)
    errors = []
    hero = p.hero_links
    amazon = [l for l in hero if AMAZON_TAG in l['href']]
    rakuten = [l for l in hero if RAKUTEN_A8 in l['href']]
    if not amazon:
        errors.append(f'{label}: hero-shop に Amazon の計測付きリンク（{AMAZON_TAG}）がありません')
    if not rakuten:
        errors.append(f'{label}: hero-shop に 楽天市場（A8）の計測付きリンク（{RAKUTEN_A8}）がありません')
    for l in amazon + rakuten:
        rel = set(l['rel'].split())
        if not {'nofollow', 'sponsored', 'noopener'} <= rel:
            errors.append(f'{label}: hero-shop の広告リンクに rel="nofollow sponsored noopener" がありません')
    if 'PR' not in text[text.find('hero-shop'):text.find('hero-shop') + 4000]:
        errors.append(f'{label}: hero-shop にPR表記がありません')
    if len(p.top_ad_ins) != 1:
        errors.append(f'{label}: top-ad の手動広告枠が {len(p.top_ad_ins)} 個です（1個であること）')
    else:
        ins = p.top_ad_ins[0]
        if ins.get('data-ad-slot') != AD_SLOT or ins.get('data-ad-client') != AD_CLIENT:
            errors.append(f'{label}: top-ad の広告ユニットIDが想定（slot {AD_SLOT}）と違います')
    if p.all_slots.count(AD_SLOT) != 1:
        errors.append(f'{label}: トップ専用ユニット（slot {AD_SLOT}）がページ内に {p.all_slots.count(AD_SLOT)} 個あります（1個であること）')
    if text.count('adsbygoogle.js') != 1:
        errors.append(f'{label}: AdSense読み込みスクリプトが {text.count("adsbygoogle.js")} 本です（1本であること）')
    if not p.article_links:
        errors.append(f'{label}: 代表記事へのリンクが見つかりません')
    return errors, p.article_links


def fetch(url, tries=4, wait=20):
    last = None
    for i in range(tries):
        try:
            sep = '&' if '?' in url else '?'
            req = urllib.request.Request(f'{url}{sep}check={int(time.time())}', headers={'User-Agent': UA, 'Cache-Control': 'no-cache'})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.read().decode('utf-8', 'replace')
        except urllib.error.HTTPError as e:
            last = (e.code, '')
        except Exception as e:  # 一時的な通信エラーは再試行する
            last = (0, str(e))
        if i < tries - 1:
            time.sleep(wait)
    return last


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--file', help='公開前のトップHTMLファイルを検査する')
    ap.add_argument('--wait', type=int, default=20, help='再試行の待ち秒数')
    args = ap.parse_args(argv)

    errors = []
    if args.file:
        with open(args.file, encoding='utf-8') as f:
            errs, _ = check_top_html(f.read(), args.file)
        errors += errs
    else:
        articles = []
        for url in TOP_URLS:
            status, text = fetch(url, wait=args.wait)
            if status != 200:
                errors.append(f'{url}: HTTP {status}')
                continue
            errs, links = check_top_html(text, url)
            errors += errs
            articles = articles or links
        for href in articles[:ARTICLE_SAMPLES]:
            url = urllib.parse.urljoin(BASE, href)
            status, text = fetch(url, wait=args.wait)
            if status != 200:
                errors.append(f'代表記事 {url}: HTTP {status}')
            elif '<h1' not in text:
                errors.append(f'代表記事 {url}: 本文の見出し（h1）がありません')
            else:
                print(f'代表記事OK: {url}')
    if errors:
        for e in errors:
            print('::error::' + e)
        return 1
    print('トップの買い物ボタン（Amazon・楽天）・手動広告枠1つ・代表記事リンクの検査に成功しました。'
          '（広告枠の設置のみ確認。配信実績はAdSense管理画面で確認）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
