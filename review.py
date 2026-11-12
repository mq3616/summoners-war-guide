"""Apply explicit applicability annotations and simplified Chinese to the licensed text."""
from pathlib import Path
from bs4 import BeautifulSoup,NavigableString,Doctype,Comment
from opencc import OpenCC
import json,re,hashlib
ROOT=Path(__file__).parent
_converter=OpenCC('tw2sp').convert
def convert(text):
 return _converter(text).replace('砲','炮')

def render_review(page):
 audit=json.loads((ROOT/'source/audit.json').read_text())
 soup=BeautifulSoup(page,'html.parser');body=soup.select_one('article.body')
 original_nodes=list(body.find_all(string=True));full=''.join(str(n) for n in original_nodes)
 positions=[i for i,c in enumerate(full) if not c.isspace()];normalized=''.join(full[i] for i in positions)
 def find(target):
  t=''.join(target.split());idx=normalized.find(t)
  assert idx>=0,'Missing annotation target: '+target
  assert normalized.find(t,idx+1)<0,'Ambiguous annotation target: '+target
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
  start,end=find(a['start'])
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
 imgs=body.find_all('img');assert len(imgs)==56
 for idx,img in enumerate(imgs):
  if '/assets/' not in img.get('src','') and not img.get('src','').startswith('assets/'):continue
  if 'emotion' in img.get('class',[]):continue
  caption=soup.new_tag('span',attrs={'class':'image-note'})
  if idx in audit['expired_image_indices']:
   caption.string='已失效的活动／领奖历史截图（保留原图供对照，不是现在可操作的入口）';caption['class']='image-note expired-image-note'
  else:caption.string='原作者历史截图：图内繁体文字保留原样，角色、符文与数值须结合本节核对说明。'
  anchor=img.find_parent('a');(anchor or img).insert_after(caption)
 soup.html['lang']='zh-CN'
 soup.title.string='魔灵召唤开荒攻略｜简体核对版 · 2026-11-12'
 soup.select_one('.top').string='魔灵召唤 · 简体核对版'
 soup.h1.string='2026 新手开局速通攻略｜简体核对版'
 meta=soup.select_one('.meta');meta.append(soup.new_tag('br'));meta.append('核对日期：2026-11-12 · 原文署名保留，删除线及说明由本页新增')
 notice=soup.select_one('.notice');notice.clear()
 notice.append(BeautifulSoup('''<strong>先看这里：</strong>原文是9月的火热时刻活动攻略，该活动10月25日结束、10月26日截止领奖。<br><del>删除线</del>＝现在不能照做的旧活动步骤，或需纠正的绝对说法；蓝色说明＝角色、账号福利、技能或配装条件仍须核对。未划掉不代表已实测现版本稳刷。<br>正文已转简体，原截图保留原样；图片里的旧活动按钮、奖励或繁体字不作当前承诺。YouTube 视频保留原始嵌入。<br><strong>现在可优先参考：</strong>召唤师之路、正常推图、公会参与；已有角色的配队、技能与符文思路。不要为了旧活动花500水晶、凑任务数或批量升星。''','html.parser'))
 foot=soup.footer;foot.clear();foot.append('原作者：亚服的小布（纳闷／xbbryan）。依原帖“作者标示－非商业性”许可转载。原始正文和52个图片文件完整保留；本版将网页文字转简体，并于2026-11-12增加删除线与核对说明。截图保持原样，不改写图中文字。未进行游戏内通关验证。')
 refs=soup.new_tag('details');summary=soup.new_tag('summary');summary.string='核对来源与适用范围';refs.append(summary)
 for key,src in audit['sources'].items():
  p=soup.new_tag('p');link=soup.new_tag('a',href=src['url']);link.string=src['title'];p.append(link);refs.append(p)
 foot.append(refs)
 css=soup.new_tag('style');css.string='''.audit-note{display:block!important;margin:10px 0 16px!important;padding:10px 12px!important;border-left:3px solid #267b9a!important;background:#eff7fb!important;color:#294c5b!important;font:14px/1.8 Arial,"Microsoft YaHei",sans-serif!important;white-space:normal!important}.audit-note a{color:#086887!important}.audit-note.expired,.audit-note.correction{border-color:#b95442!important;background:#fff3ed!important;color:#704433!important}.audit-note.section-note{background:#f3f7f7!important;border-color:#78979e!important}.expired-text{color:#737373!important;text-decoration:line-through!important;text-decoration-thickness:1.5px!important}.expired-text *{color:inherit!important}.image-note{display:block!important;color:#66777c!important;font:12px/1.7 Arial,sans-serif!important;margin:5px 0 18px!important}.expired-image-note{color:#944839!important;background:#fff1e9!important;padding:5px 8px!important}details summary{cursor:pointer;font-weight:bold}''';soup.head.append(css)
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
 assert len(check.find_all('img'))==56
 assert len(soup.select('[data-audit-id]'))==len(audit['annotations'])
 report={'reviewed_at':audit['reviewed_at'],'annotations':len(entries),'expired_or_corrected_passages':sum(a['kind'] in ('expired','correction') for a in audit['annotations']),'reviewed_sections':len(audit['sections']),'original_text_retained_and_simplified':True,'images_retained':56,'screenshot_text':'original retained','runtime_game_validation':False}
 (ROOT/'docs/review-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
 return str(soup),report
