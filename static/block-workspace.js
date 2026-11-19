"use strict";
// Adapter: existing save/review/handoff paths all receive the same serialized document.
(function(){
 const M=window.StoryBlocks;
 function ensure(platform=activePlatform()){
  draft.blog_documents ||= {};
  const info=platformInfo[platform],body=draft[info.body]||'';let doc=draft.blog_documents[platform];
  if(!doc||doc.version!==1){doc=M.create(body,draft.images,draft[info.title]||'',draft.template);draft.blog_documents[platform]=doc;}
  else if(doc.source!==body){doc=M.create(body,M.photos(doc),draft[info.title]||'',doc.template,doc);draft.blog_documents[platform]=doc;}
  draft[info.body]=doc.source;if(platform===activePlatform())$('body').value=doc.source;return doc;
 }
 function photos(){return tab==='blog'&&(!$('editor').hidden||draft[contentKey()]?.trim())?M.photos(ensure()):(window.ChannelUI?.photos()||draft.images);}
 function commit(doc){
  doc.source=M.serialize(doc);draft.blog_documents[activePlatform()]=doc;draft[contentKey()]=doc.source;draft[titleKey()]=$('title').value;draft.template=doc.template;$('template').value=doc.template;$('body').value=doc.source;
  draft.layout_bases[activePlatform()]=undefined;draft.layout_last[activePlatform()]=undefined;
  markDirty();updateBodyCount();renderMissionChecklist();renderLayout();validity();
 }
 function showEditing(){preview=false;$('preview').hidden=true;$('editFields').hidden=false;$('previewToggle').textContent='미리보기';setWorkflow(2);refresh();}
 function choosePhoto(accept,replacing){
  let active=true;$('modal').addEventListener('close',()=>active=false,{once:true});
  const platform=activePlatform(),epoch=navigationEpoch,doc=ensure(),used=new Set(M.photos(doc)),current=doc.blocks.find(b=>b.id===replacing)?.image_id;
  const box=modal(replacing?'이 사진을 바꿀까요?':'어떤 사진을 넣을까요?');para(box,replacing?'사진 아래에 적은 설명과 문단 위치는 그대로 유지돼요.':'이 블로그 원고에만 넣어요. 다른 채널의 사진은 바뀌지 않아요.');
  const grid=document.createElement('div');grid.className='block-photo-picker';box.append(grid);
  const ids=[...new Set([...draft.images,...Object.values(draft.blog_documents||{}).flatMap(d=>M.photos(d)),...doc.undo.flatMap(s=>M.photos(s)),...doc.original.images])];
  const choose=id=>{if(!active||!$('modal').open||epoch!==navigationEpoch||platform!==activePlatform())return;$("modal").close();accept(id);};
  for(const [index,id] of ids.entries()){
   const button=document.createElement('button');button.type='button';button.className='block-photo-choice';button.disabled=used.has(id);button.setAttribute('aria-label','사진 '+(index+1)+(button.disabled?' · 이미 사용 중':' 선택'));
   const image=document.createElement('img');image.src='/media/'+id+'.jpg';image.alt='';const text=document.createElement('span');text.textContent=id===current?'현재 사진':button.disabled?'글에 넣은 사진':'사진 '+(index+1);button.append(image,text);button.onclick=()=>choose(id);grid.append(button);
  }
  if(!ids.length)para(box,'아직 준비한 사진이 없어요. 아래에서 불러와 주세요.');
  const upload=document.createElement('input');upload.type='file';upload.accept='image/jpeg,image/png,image/webp';upload.hidden=true;box.append(upload);
  const button=document.createElement('button');button.type='button';button.className='secondary block-upload';button.textContent='새 사진 불러오기';button.onclick=()=>upload.click();box.append(button);
  const state=document.createElement('p');state.className='hint';state.setAttribute('role','status');box.append(state);
  upload.onchange=run(async()=>{
   const file=upload.files[0];if(!file)return;if(file.size>10000000||!['image/jpeg','image/png','image/webp'].includes(file.type)){state.textContent='10MB 이하 JPG, PNG, WebP 사진을 골라 주세요.';return;}
   button.disabled=true;lock(true);state.textContent='사진을 불러오고 있어요.';
   try{const data=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result.split(',')[1]);r.onerror=()=>reject(Error('사진을 읽지 못했어요.'));r.readAsDataURL(file);});const result=await api('/api/upload',{data});lock(false);choose(result.id);}
   catch(e){state.textContent=e.message;}finally{lock(false);button.disabled=false;upload.value='';}
  });
 }
 function original(){
  const doc=ensure(),source=doc.original;const box=modal('처음 불러온 원고');para(box,'블록으로 다듬기 전의 글과 사진을 보관했어요. 다른 채널의 글은 바꾸지 않아요.');
  const heading=document.createElement('h3');heading.textContent=source.title||'처음 원고';box.append(heading);for(const block of M.parse(source.body,source.images)){const item=document.createElement(block.type==='photo'?'img':block.type==='heading'?'h3':'p');if(block.type==='photo'){item.src='/media/'+block.image_id+'.jpg';item.alt='처음 원고의 사진';item.className='block-original-photo';}else{item.textContent=block.text;item.className='block-original';}box.append(item);}
  const restore=document.createElement('button');restore.type='button';restore.className='secondary';restore.textContent='이 원고를 처음으로 되돌리기';restore.onclick=()=>{if(!confirm('지금 원고 대신 처음 원고로 되돌릴까요? 편집 되돌리기로 다시 복구할 수 있어요.'))return;editor.mutate(d=>{const initial=M.create(source.body,source.images,source.title,d.template);d.blocks=initial.blocks;$('title').value=source.title;});$('modal').close();};box.append(restore);
 }
 const editor=new window.StoryBlockEditor($('blockEditor'),{getDocument:()=>ensure(),getTitle:()=>draft[titleKey()]||'',setTitle:value=>{$('title').value=value;draft[titleKey()]=value;},commit,choosePhoto,refine:(block,start,end)=>window.WritingUI?.openBlock(block,start,end),previewPhoto:id=>openPhoto(photos().indexOf(id),photos()),showOriginal:original,isBusy:()=>busy,notify});
 function refresh(reset=false){
  $('blockEditor').hidden=tab!=='blog';$('body').hidden=tab==='blog';$('bodyLabel').hidden=tab==='blog';
  if(tab!=='blog')return;
  if($('editor').hidden&&!draft[contentKey()]?.trim())return;
  const doc=ensure();$('template').value=doc.template;if(reset)editor.transaction=null;
  if(!preview&&!$('editor').hidden)editor.render();validity();
 }
 function validity(){const invalid=$('body').getAttribute('aria-invalid')==='true';$('blockEditor').setAttribute('aria-invalid',String(invalid));const description=$('body').getAttribute('aria-describedby');if(description)$('blockEditor').setAttribute('aria-describedby',description);else $('blockEditor').removeAttribute('aria-describedby');}
 function textRange(value,needle){
  if(!needle)return null;
  if(!/[가-힣]/.test(needle)){const escaped=needle.trim().split(/\s+/).map(word=>word.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).join('\\s+');const match=value.match(new RegExp('(?<![\\p{L}\\p{N}_])'+escaped+'(?![\\p{L}\\p{N}_])','iu'));return match?[match.index,match.index+match[0].length]:null;}
  let compact='',positions=[];
  for(let i=0;i<value.length;i++){if(/\s/.test(value[i]))continue;const part=value[i].toLowerCase();for(const char of part){compact+=char;positions.push(i);}}
  const target=needle.toLowerCase().replace(/\s/g,''),at=compact.indexOf(target);return at<0||!target?null:[positions[at],positions[at+target.length-1]+1];
 }
 function focus(issue){
  showEditing();const doc=ensure();const block=doc.blocks.find(b=>b.id===issue.block_id)||doc.blocks.find(b=>textRange(b.text||b.caption||'',issue.needle))||doc.blocks.find(b=>b.type!=='photo');if(!block){editor.addText();return;}
  const field=$('blockEditor').querySelector(`[data-editor-for="${block.id}"]`);if(field){field.focus();const range=textRange(field.value,issue.needle);field.setSelectionRange(range?range[0]:field.value.length,range?range[1]:field.value.length);field.scrollIntoView({block:'center',behavior:'auto'});}
 }
 function generated(platforms,images=draft.images,preserve=false){
  draft.blog_documents ||= {};
  for(const platform of platforms){if(!['naver','tistory'].includes(platform))continue;const info=platformInfo[platform],prior=draft.blog_documents[platform],doc=M.create(draft[info.body],images,draft[info.title],draft.template,preserve?prior:undefined);
   if(prior){doc.original=prior.original;doc.undo=[...prior.undo,M.snapshot(prior,generationUndo[platform]?.title||prior.original.title)].slice(-M.HISTORY_LIMIT);}draft.blog_documents[platform]=doc;draft[info.body]=doc.source;
  }
 }
 window.BlockWorkspace={ensure,photos,refresh,commit,focus,generated,validity,editor,range:textRange};
 $('title').addEventListener('keydown',event=>{if(tab!=='blog'||event.isComposing||!(event.ctrlKey||event.metaKey))return;if(event.key.toLowerCase()==='z'){event.preventDefault();event.shiftKey?editor.redo():editor.undo();}else if(event.key.toLowerCase()==='y'){event.preventDefault();editor.redo();}});
 $('title').addEventListener('input',()=>{if(tab!=='blog')return;const doc=ensure();editor.remember(doc,'title');draft[titleKey()]=$('title').value;commit(doc);});
 $('template').addEventListener('change',()=>{if(tab!=='blog'||$('editor').hidden)return;const doc=ensure();editor.mutate(d=>d.template=$('template').value);refresh();if(preview)renderPreview();});
 const fit=()=>document.querySelectorAll('#blockEditor textarea').forEach(field=>editor.resize(field));
 let lastWidth=0;new ResizeObserver(entries=>{const width=entries[0].contentRect.width;if(width&&width!==lastWidth){lastWidth=width;requestAnimationFrame(fit);}}).observe($('blockEditor'));
 document.fonts?.ready.then(fit);refresh(true);
})();
