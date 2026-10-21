import json, os, re, smtplib, ssl, time
from email.message import EmailMessage
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from pathlib import Path

CFG = json.loads(Path('products.json').read_text(encoding='utf-8'))
STATE_PATH = Path('state.json')
STATE = json.loads(STATE_PATH.read_text(encoding='utf-8')) if STATE_PATH.exists() else {}

POSITIVE = ['ajouter au panier','en stock','disponible','acheter maintenant','add to cart','in stock']
NEGATIVE = ['rupture','indisponible','épuisé','out of stock','currently unavailable','temporairement indisponible']
PRICE_RE = re.compile(r'(?<!\d)(\d{1,4}[,.]\d{2})\s*(?:€|eur)', re.I)

def fetch(url):
    req = Request(url, headers={'User-Agent':'Mozilla/5.0 (compatible; StockAvailabilityMonitor/1.0)','Accept-Language':'fr-FR,fr;q=0.9,en;q=0.7'})
    with urlopen(req, timeout=25) as r:
        return r.read().decode('utf-8','ignore')

def clean(html):
    text = re.sub(r'<script[\s\S]*?</script>|<style[\s\S]*?</style>', ' ', html, flags=re.I)
    text = re.sub(r'<[^>]+>', ' ', text)
    return re.sub(r'\s+', ' ', text).lower()

def status(text):
    neg = any(x in text for x in NEGATIVE)
    pos = any(x in text for x in POSITIVE)
    return 'available' if pos and not neg else 'unavailable' if neg else 'unknown'

def price(text):
    m = PRICE_RE.search(text)
    return (m.group(1).replace('.', ',') + ' €') if m else 'Prix non détecté'

def send(subject, body):
    host = os.environ['SMTP_HOST']
    port = int(os.environ.get('SMTP_PORT', '587'))
    user = os.environ['SMTP_USER']
    pwd = os.environ['SMTP_PASSWORD']
    sender = os.environ['SMTP_FROM']
    dest = os.environ.get(
        'ALERT_TO',
        'doublecacaman@yopmail.com'
    )

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = dest
    msg.set_content(body)

    ctx = ssl.create_default_context()

    with smtplib.SMTP(host, port, timeout=30) as s:
        s.starttls(context=ctx)
        s.login(user, pwd)
        s.send_message(msg)

changed=False
for item in CFG['products']:
    for page in item.get('urls',[]):
        url=page['url']; shop=page['shop']; key=url
        try:
            text=clean(fetch(url)); st=status(text); pr=price(text)
            prev=STATE.get(key,{}).get('status')
            print(f'{shop} | {item["name"]} | {st} | {pr}')
            if st=='available' and prev!='available':
                send(f'🔥 Stock Pokémon détecté - {item["name"]}', f'Produit : {item["name"]}\nBoutique : {shop}\nPrix : {pr}\nStatut : DISPONIBLE\n\nLien : {url}')
            STATE[key]={'status':st,'price':pr,'checked_at':int(time.time())}; changed=True
        except (HTTPError, URLError, TimeoutError, KeyError, smtplib.SMTPException) as e:
            print(f'ERREUR {shop} {url}: {e}')
if changed:
    STATE_PATH.write_text(json.dumps(STATE,ensure_ascii=False,indent=2),encoding='utf-8')
