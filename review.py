"""Apply explicit applicability annotations and simplified Chinese to the licensed text."""
from pathlib import Path
from bs4 import BeautifulSoup,NavigableString,Doctype,Comment
from opencc import OpenCC
import json,re,hashlib
ROOT=Path(__file__).parent
_converter=OpenCC('t2s').convert
def convert(text):
 return re.sub(r'(?<=[急看哭活有留临照接绕])著', '着', _converter(text)).replace('著手','着手').replace('砲','炮')

def render_review(page):
 audit=json.loads((ROOT/'source/audit.json').read_text())
 soup=BeautifulSoup(page,'html.parser');body=soup.select_one('article.body')
 original_nodes=list(body.find_all(string=True));full=''.join(str(n) for n in original_nodes)
 positions=[i for i,c in enumerate(full) if not c.isspace()];normalized=''.join(full[i] for i in positions)
 def find(target,after=None):
  t=''.join(target.split());begin=normalized.find(''.join(after.split()))+len(''.join(after.split())) if after else 0;idx=normalized.find(t,begin)
  assert idx>=0,'Missing annotation target: '+target
  assert after or normalized.find(t,idx+1)<0,'Ambiguous annotation target: '+target
  return positions[idx],positions[idx+len(t)-1]+1
 def section_find(target):
  matches=[];offset=0
  for node in original_nodes:
   if ''.join(str(node).split())==''.join(target.split()):
    score=max([2 if a.name=='font' and a.get('size') in ('4','5') else 1 if a.name in ('b','strong') else 0 for a in node.parents])
    matches.append((score,offset,offset+len(str(node))))
   offset+=len(str(node))
  if matches:
   _,start,end=max(matches);return start,end
  return find(target)
 intervals=[];notes={};entries=[]
 for i,a in enumerate(audit['annotations']):
  start,end=find(a['start'],a.get('after'))
  if a['end']:end=find(a['end'])[1]
  assert start<end
  if a['kind'] in ('expired','correction'):intervals.append((start,end))
  label={'expired':'已失效','correction':'纠正','conditional':'条件说明','historical':'历史说明'}[a['kind']]
  note=soup.new_tag('span',attrs={'class':'audit-note '+a['kind'],'data-audit-id':str(i)})
  strong=soup.new_tag('strong');strong.string=label+' · ';note.append(strong);note.append(a['reason']+' ')
  src=audit['sources'][a['source']];link=soup.new_tag('a',href=src['url']);link.string='核对依据';note.append(link)
  notes.setdefault(end,[]).append(note);entries.append({'id':i,'kind':a['kind'],'start':start,'end':end})
 for i,section in enumerate(audit['sections']):
  start,end=section_find(section['heading']);note=soup.new_tag('span',attrs={'class':'audit-note section-note','id':'section-'+str(i)});note.string='本节核对：'+section['note'];notes.setdefault(end,[]).append(note)
 offset=0
 for node in original_nodes:
  text=str(node);start=offset;end=start+len(text);offset=end
  cuts={start,end}
  for left,right in intervals:
   if start<left<end:cuts.add(left)
   if start<right<end:cuts.add(right)
  cuts.update(p for p in notes if start<p<=end)
  points=sorted(cuts)
  for left,right in zip(points,points[1:]):
   value=NavigableString(text[left-start:right-start])
   if any(a<=left and right<=b for a,b in intervals):
    tag=soup.new_tag('del',attrs={'class':'expired-text'});tag.append(value);node.insert_before(tag)
   else:node.insert_before(value)
   for note in notes.get(right,[]):node.insert_before(note)
  node.extract()
 # Preserve every original character; only added notes are excluded from this audit.
 copy=BeautifulSoup(str(body),'html.parser')
 for note in copy.select('.audit-note'):note.decompose()
 assert copy.get_text()==full,'Annotation removed or changed source text'
 # Screenshots remain unaltered; outdated reward screenshots are visibly labelled.
 imgs=body.find_all('img');assert len(imgs)==audit['image_occurrences']
 for idx,img in enumerate(imgs):
  if '/assets/' not in img.get('src','') and not img.get('src','').startswith('assets/'):continue
  if 'emotion' in img.get('class',[]):continue
  caption=soup.new_tag('span',attrs={'class':'image-note'})
  if idx in audit['expired_image_indices']:
   caption.string='已失效的活动／领奖历史截图（保留原图供对照，不是现在可操作的入口）';caption['class']='image-note expired-image-note'
  else:caption.string='原作者历史截图：图内繁体文字保留原样，角色、符文与数值须结合本节核对说明。'
  anchor=img.find_parent('a');(anchor or img).insert_after(caption)
 soup.html['lang']='zh-CN'
 soup.title.string=audit['page_title']
 soup.select_one('.top').string='魔灵召唤 · 简体核对版'
 soup.h1.string=audit['page_heading']
 meta=soup.select_one('.meta');meta.append(soup.new_tag('br'));meta.append('核对日期：2026-11-12 · 原文署名保留，删除线及说明由本页新增')
 notice=soup.select_one('.notice');notice.clear()
 notice.append(BeautifulSoup('<strong>阅读说明：</strong>'+audit['overview']+'<br>'+audit['reading_note'],'html.parser'))
 nav=soup.new_tag('nav',attrs={'class':'guide-toc','aria-label':'攻略目录'})
 label=soup.new_tag('strong');label.string='章节目录';nav.append(label)
 for i,section in enumerate(audit['sections']):
  link=soup.new_tag('a',href='#section-'+str(i));link.string=section['heading'];nav.append(link)
 notice.insert_after(nav)
 foot=soup.footer;foot.clear();meta=json.loads((ROOT/'source/provenance.json').read_text())
 foot.append('原作者：'+meta['author']+'。依原帖“作者标示－非商业性”许可转载。本版保留完整楼主正文和图片，网页文字转简体，并于2026-11-12增加核对说明；原图不改动。未进行游戏内通关验证。')
 refs=soup.new_tag('details');summary=soup.new_tag('summary');summary.string='核对来源与适用范围';refs.append(summary)
 for key,src in audit['sources'].items():
  p=soup.new_tag('p');link=soup.new_tag('a',href=src['url']);link.string=src['title'];p.append(link);refs.append(p)
 foot.append(refs)
 css=soup.new_tag('style');css.string='''.audit-note{display:block!important;margin:10px 0 16px!important;padding:10px 12px!important;border-left:3px solid #267b9a!important;background:#eff7fb!important;color:#294c5b!important;font:14px/1.8 Arial,"Microsoft YaHei",sans-serif!important;white-space:normal!important}.audit-note a{color:#086887!important}.audit-note.expired,.audit-note.correction{border-color:#b95442!important;background:#fff3ed!important;color:#704433!important}.audit-note.section-note{background:#f3f7f7!important;border-color:#78979e!important}.expired-text{color:#737373!important;text-decoration:line-through!important;text-decoration-thickness:1.5px!important}.expired-text *{color:inherit!important}.image-note{display:block!important;color:#66777c!important;font:12px/1.7 Arial,sans-serif!important;margin:5px 0 18px!important}.expired-image-note{color:#944839!important;background:#fff1e9!important;padding:5px 8px!important}details summary{cursor:pointer;font-weight:bold}.guide-toc{padding:16px 32px;background:#f8fafb;border-bottom:1px solid #dde6e9;display:flex;flex-wrap:wrap;gap:8px 18px;font-size:14px;line-height:1.8}.guide-toc strong{flex-basis:100%}.guide-toc a{max-width:100%}.body blockquote{margin:12px 0;padding:0 0 0 12px;border-left:2px solid #dbe4e7}.body blockquote blockquote{margin:4px 0;padding:0;border:0}.body h2{font-size:23px}.body h3{font-size:19px}.body h4{font-size:16px}.body table{max-width:100%}.body ul,.body ol{padding-left:22px}@media(max-width:700px){.guide-toc{padding:14px 16px}.body blockquote{padding-left:8px}.body blockquote blockquote{padding-left:0}}''';soup.head.append(css)
 for node in list(soup.find_all(string=True)):
  if not isinstance(node,(Doctype,Comment)) and node.parent.name not in ('style','script'):node.replace_with(convert(str(node)))
 for t in soup.find_all(True):
  for a in ['alt','title','aria-label']:
   if t.has_attr(a):t[a]=convert(t[a])
 # Verify simplified source is still complete, no character or image was discarded.
 check=BeautifulSoup(str(soup.select_one('article.body')),'html.parser')
 for tag in check.select('.audit-note,.image-note'):tag.decompose()
 expected=''.join(convert(str(n)) for n in original_nodes)
 assert check.get_text()==expected,'Simplified source coverage mismatch'
 assert len(check.find_all('img'))==audit['image_occurrences']
 assert len(soup.select('[data-audit-id]'))==len(audit['annotations'])
 report={'reviewed_at':audit['reviewed_at'],'annotations':len(entries),'expired_or_corrected_passages':sum(a['kind'] in ('expired','correction') for a in audit['annotations']),'reviewed_sections':len(audit['sections']),'original_text_retained_and_simplified':True,'images_retained':len(imgs),'screenshot_text':'original retained','runtime_game_validation':False}
 (ROOT/'docs/review-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
 return str(soup),report
