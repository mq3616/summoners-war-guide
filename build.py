"""Build a noncommercial attributed copy; fail if any original image is missing."""
from pathlib import Path
from html.parser import HTMLParser
from html import escape
from urllib.request import Request,urlopen
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,re,time
root=Path(__file__).parent
original=(root/'source/article.html').read_text()
meta=json.loads((root/'source/provenance.json').read_text())
out=root/'docs';(out/'assets').mkdir(parents=True,exist_ok=True)
class Images(HTMLParser):
 def __init__(self): super().__init__();self.urls=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='img': self.urls.append(a.get('data-src') or a.get('src'))
images=Images();images.feed(original);urls=list(dict.fromkeys(images.urls))
assert all(urlparse(u).hostname in ('truth.bahamut.com.tw','i2.bahamut.com.tw') for u in urls)
paths={u:'assets/'+hashlib.sha256(u.encode()).hexdigest()[:20]+Path(urlparse(u).path).suffix.lower() for u in urls}
def download(u):
 p=out/paths[u]
 for attempt in range(3):
  try:
   with urlopen(Request(u,headers={'User-Agent':'Mozilla/5.0','Referer':meta['url']}),timeout=45) as r:
    data=r.read();typ=r.headers.get('Content-Type','')
   assert typ.startswith('image/'),typ
   assert len(data)>30
   p.write_bytes(data)
   return {'url':u,'path':paths[u],'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
  except Exception:
   if attempt==2:raise
   time.sleep(2)
with ThreadPoolExecutor(max_workers=6) as pool: manifest=list(pool.map(download,urls))
class Clean(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=False);self.parts=[];self.text=[]
 def handle_starttag(self,t,attrs):
  a=dict(attrs)
  assert t not in ('script','object','embed','form'),t
  allowed={'class','style','face','color','size','bgcolor','width','height','colspan','rowspan'}
  a={k:v for k,v in a.items() if k in allowed or k in ('href','src','allowfullscreen')}
  if t=='img':
   old=dict(attrs);u=old.get('data-src') or old.get('src');a={'src':paths[u],'alt':'原文圖片','loading':'lazy','class':'emotion' if '/emotion/' in u else 'guide-image'}
  if t=='a' and a.get('href') in paths:a['href']=paths[a['href']]
  if t=='iframe':
   assert a.get('src','').startswith('https://www.youtube.com/embed/')
   a={'src':a['src'],'title':'原作者完整攻略影片','allowfullscreen':'','loading':'lazy','referrerpolicy':'strict-origin-when-cross-origin'}
  self.parts.append('<'+t+''.join(' '+k+'="'+escape(v or '',quote=True)+'"' for k,v in a.items())+'>')
 def handle_endtag(self,t):self.parts.append('</'+t+'>')
 def handle_data(self,d):self.parts.append(d);self.text.append(d)
 def handle_entityref(self,n):self.parts.append('&'+n+';')
 def handle_charref(self,n):self.parts.append('&#'+n+';')
c=Clean();c.feed(original);content=''.join(c.parts)
# Check that all original text and every image occurrence survives conversion.
class Text(HTMLParser):
 def __init__(self):super().__init__();self.text=[];self.img=[]
 def handle_data(self,d):self.text.append(d)
 def handle_starttag(self,t,a):
  if t=='img':self.img.append(dict(a).get('src'))
a=Text();a.feed(original);b=Text();b.feed(content)
assert a.text==b.text,'Original text changed'
assert len(a.img)==len(b.img)
assert all((out/u).is_file() for u in b.img)
css='''*{box-sizing:border-box}body{margin:0;background:#e9eff1;color:#333;font-family:Arial,"Microsoft JhengHei",sans-serif}.top{background:#117e96;color:white;padding:18px max(20px,calc((100vw - 1120px)/2));font-size:18px}.wrap{max-width:1120px;margin:24px auto;background:#fff;border:1px solid #d5dfe2}.heading{padding:26px 32px;border-bottom:1px solid #dbe4e6}h1{font-size:25px;line-height:1.5;margin:0 0 12px}.meta{color:#66777c;font-size:14px;line-height:1.9}.meta a{color:#087e99}.notice{padding:12px 32px;background:#f6fafb;font-size:14px;line-height:1.8}.body{padding:30px 36px;overflow-wrap:anywhere;line-height:1.65;font-size:16px}.body img.guide-image{max-width:100%;height:auto;vertical-align:middle}.body img.emotion{max-width:28px;vertical-align:middle}.body iframe{width:100%;aspect-ratio:16/9;height:auto;border:0}.videoWrapper{max-width:100%}footer{padding:22px 32px;border-top:1px solid #ddd;font-size:13px;line-height:1.9}a{color:#087e99}@media(max-width:700px){.wrap{margin:0;border:0}.heading,.body{padding:20px 16px}.notice,footer{padding:14px 16px}h1{font-size:21px}.top{padding:14px 16px}.body{font-size:16px}}'''
page='''<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'''+escape(meta['title'])+'''</title><style>'''+css+'''</style></head><body><header class="top">魔靈召喚 · 原文閱讀鏡像</header><main class="wrap"><header class="heading"><h1>'''+escape(meta['title'])+'''</h1><div class="meta">作者：'''+escape(meta['author'])+'''<br>原文編輯時間：'''+meta['edited']+''' · <a href="'''+escape(meta['url'])+'''">查看原帖</a><br>授權：作者標示－非商業性</div></header><aside class="notice">本頁保留原文文字、圖片與排列順序，圖片已存入本倉庫。這是 2026 年 9 月的活動攻略，活動獎勵及取得條件請以遊戲當前畫面為準。YouTube 影片保留原始嵌入，播放仍需能連線 YouTube。</aside><article class="body">'''+content+'''</article><footer>原作者：'''+escape(meta['author'])+'''。依原帖「作者標示－非商業性」授權作非商業閱讀轉載。<br>僅調整閱讀外框、圖片本地化及響應式顯示，未改寫正文。巴哈姆特標誌、廣告、其他用戶留言與網站功能不包含於本鏡像。<br><a href="'''+escape(meta['url'])+'''">原文與授權出處</a> · <a href="https://github.com/mq3616/summoners-war-guide">GitHub 原始檔與圖片</a></footer></main></body></html>'''
(out/'index.html').write_text(page)
(out/'assets-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
report={'text_preserved':True,'original_image_occurrences':len(images.urls),'saved_unique_images':len(manifest),'total_image_bytes':sum(x['bytes'] for x in manifest),'source_text_characters':len(''.join(a.text))}
(out/'verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
