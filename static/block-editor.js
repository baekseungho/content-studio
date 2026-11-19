"use strict";
// No editor HTML is stored. The document contains plain text and stable photo IDs.
(function(root){
 const clone=value=>JSON.parse(JSON.stringify(value));
 const HISTORY_LIMIT=20;
 const uid=()=>crypto.randomUUID().replaceAll('-','');
 function photos(doc){return doc.blocks.filter(b=>b.type==='photo').map(b=>b.image_id);}
 function serialize(doc){let n=0;return doc.blocks.flatMap(b=>b.type==='photo'?[`[[photo:${++n}]]`,...(b.caption?[b.caption]:[])]:b.text?[(b.type==='heading'?'## ':'')+b.text]:[]).join('\n\n');}
 function parse(body,images,previous){
  const blocks=[],used=new Set();
  for(const chunk of body.replace(/\r\n/g,'\n').split(/(\[\[photo:\d+\]\])/)){
   const match=chunk.match(/^\[\[photo:(\d+)\]\]$/);
   if(match){const image=images[Number(match[1])-1];if(image&&!used.has(image)){used.add(image);blocks.push({id:uid(),type:'photo',image_id:image,caption:''});}continue;}
   for(const paragraph of chunk.split(/\n[ \t]*\n/)){
    const lines=[];const flush=()=>{if(lines.length){blocks.push({id:uid(),type:'paragraph',text:lines.join('\n')});lines.length=0;}};
    for(const line of paragraph.replace(/^\n+|\n+$/g,'').split('\n')){if(!line&&!lines.length)continue;if(line.startsWith('## ')){flush();blocks.push({id:uid(),type:'heading',text:line.slice(3)});}else lines.push(line);}flush();
   }
  }
  if(previous){const old=[...previous.blocks];for(let i=0;i<blocks.length;i++){const b=blocks[i],at=old.findIndex(o=>o.type===b.type&&(b.type==='photo'?o.image_id===b.image_id:o.text===b.text));if(at<0)continue;const prior=old.splice(at,1)[0];b.id=prior.id;if(b.type==='photo'&&prior.caption&&blocks[i+1]?.type==='paragraph'&&blocks[i+1].text.replace(/\s/g,'')===prior.caption.replace(/\s/g,'')){b.caption=blocks[i+1].text;blocks.splice(i+1,1);}}}
  return blocks;
 }
 function create(body,images,title='',template='reference',previous){
  const doc=previous?clone(previous):{version:1,undo:[],redo:[],template,original:{body,title,images:[...images]}};
  doc.blocks=parse(body,previous?photos(previous):images,previous);
  if(!previous){const used=new Set(photos(doc));for(const id of images)if(!used.has(id))doc.blocks.push({id:uid(),type:'photo',image_id:id,caption:''});}
  if(!doc.blocks.length)doc.blocks.push({id:uid(),type:'paragraph',text:''});doc.source=serialize(doc);return doc;
 }
 function snapshot(doc,title){return {blocks:clone(doc.blocks),title,template:doc.template};}
 function remember(doc,title){doc.undo.push(snapshot(doc,title));doc.undo=doc.undo.slice(-HISTORY_LIMIT);doc.redo=[];}
 root.StoryBlocks={HISTORY_LIMIT,uid,clone,photos,serialize,parse,create,snapshot,remember};
})(window);

(function(root){
 const M=root.StoryBlocks;
 class StoryBlockEditor {
  constructor(node,options){
   this.node=node;this.options=options;this.transaction=null;this.dragged=null;this.renderVersion=0;
   node.addEventListener('keydown',event=>{
    if(!(event.ctrlKey||event.metaKey)||event.isComposing)return;
    if(event.key.toLowerCase()==='z'){event.preventDefault();event.shiftKey?this.redo():this.undo();}
    else if(event.key.toLowerCase()==='y'){event.preventDefault();this.redo();}
   });
  }
  button(label,text,action,disabled=false){const b=document.createElement('button');b.type='button';b.className='block-action';b.textContent=text;b.setAttribute('aria-label',label);b.title=label;b.disabled=disabled||this.options.isBusy();b.addEventListener('click',action);return b;}
  remember(doc,key){const now=Date.now();if(!this.transaction||this.transaction.key!==key||now-this.transaction.at>1000)M.remember(doc,this.options.getTitle());this.transaction={key,at:now};}
  mutate(action,focus){if(this.options.isBusy())return;const doc=this.options.getDocument();M.remember(doc,this.options.getTitle());this.transaction=null;action(doc);this.options.commit(doc);this.render(focus);}
  undo(){
   const doc=this.options.getDocument();if(this.options.isBusy()||!doc.undo.length)return;
   doc.redo.push(M.snapshot(doc,this.options.getTitle()));doc.redo=doc.redo.slice(-M.HISTORY_LIMIT);const prior=doc.undo.pop();doc.blocks=prior.blocks;doc.template=prior.template;this.options.setTitle(prior.title);this.transaction=null;this.options.commit(doc);this.render();this.options.notify('방금 편집한 내용을 되돌렸어요.');
  }
  redo(){
   const doc=this.options.getDocument();if(this.options.isBusy()||!doc.redo.length)return;
   doc.undo.push(M.snapshot(doc,this.options.getTitle()));doc.undo=doc.undo.slice(-M.HISTORY_LIMIT);const next=doc.redo.pop();doc.blocks=next.blocks;doc.template=next.template;this.options.setTitle(next.title);this.transaction=null;this.options.commit(doc);this.render();
  }
  addText(after=-1,type='paragraph'){
   if(this.options.getDocument().blocks.length>=250)return this.options.notify('문단이 많아요. 가까운 문단에 이어서 적어 주세요.');
   const id=M.uid();this.mutate(doc=>doc.blocks.splice(after<0?doc.blocks.length:after+1,0,{id,type,text:''}),id);
  }
  move(id,to){const doc=this.options.getDocument(),at=doc.blocks.findIndex(b=>b.id===id);if(at<0||to===at||to<0||to>=doc.blocks.length)return;this.mutate(d=>{const item=d.blocks.splice(at,1)[0];d.blocks.splice(to,0,item);},id);this.options.notify('문단 순서를 바꿨어요.');}
  choosePhoto(after=-1,replacing=null){
   const doc=this.options.getDocument();if(!replacing&&doc.blocks.length>=250)return this.options.notify("문단이 많아요. 가까운 문단에 이어서 적어 주세요.");if(!replacing&&M.photos(doc).length>=10)return this.options.notify('한 원고에는 사진을 최대 10장 넣을 수 있어요.');
   this.options.choosePhoto(image=>{
    const current=this.options.getDocument();if(M.photos(current).includes(image)&&current.blocks.find(b=>b.id===replacing)?.image_id!==image)return this.options.notify('이 사진은 이미 글에 있어요. 기존 사진을 이동해 주세요.');
    const id=replacing||M.uid();this.mutate(d=>{if(replacing){const b=d.blocks.find(b=>b.id===replacing);if(b)b.image_id=image;}else d.blocks.splice(after<0?d.blocks.length:after+1,0,{id,type:'photo',image_id:image,caption:''});},id);
   },replacing);
  }
  resize(field){field.style.height='auto';field.style.height=Math.max(field.scrollHeight,field.dataset.caption?44:50)+'px';}
  render(focus){
   const version=++this.renderVersion,initiator=document.activeElement;focus ||= initiator?.dataset.editorFor;const focused=initiator?.id;const doc=this.options.getDocument();this.node.replaceChildren();this.node.classList.toggle('reference-style',doc.template!=='clean');this.node.classList.toggle('clean-style',doc.template==='clean');this.node.classList.toggle('is-busy',this.options.isBusy());
   const toolbar=document.createElement('div');toolbar.className='block-toolbar';toolbar.setAttribute('role','toolbar');toolbar.setAttribute('aria-label','글과 사진 편집');
   const state=document.createElement('span');state.className='block-toolbar-label';state.textContent='드래그하거나 ↑↓로 순서를 바꿔요';toolbar.append(state);
   const undo=this.button('편집 되돌리기','↶',()=>this.undo(),!doc.undo.length),redo=this.button('편집 다시 실행','↷',()=>this.redo(),!doc.redo.length);undo.id='blockUndo';redo.id='blockRedo';undo.title='편집 되돌리기 · 최근 '+M.HISTORY_LIMIT+'단계 보관';redo.title='되돌린 편집 다시 실행';toolbar.append(undo,redo);
   const paragraph=this.button('문단 추가','＋ 문단',()=>this.addText()),picture=this.button('사진 추가','＋ 사진',()=>this.choosePhoto());paragraph.id='blockAddText';picture.id='blockAddPhoto';toolbar.append(paragraph,picture);this.node.append(toolbar);
   const body=document.createElement('div');body.className='block-list';body.setAttribute('role','list');body.setAttribute('aria-label','글과 사진 순서');this.node.append(body);
   if(!doc.blocks.length){const empty=document.createElement('div');empty.className='block-empty';empty.textContent='첫 문단을 적거나 사진부터 넣어 보세요.';body.append(empty);}
   let photoNumber=0;
   doc.blocks.forEach((block,index)=>{
    const row=document.createElement('section');row.className='story-block '+block.type+'-block';row.dataset.blockId=block.id;row.setAttribute('role','listitem');
    const tools=document.createElement('div');tools.className='block-tools';
    const handle=this.button('이 문단을 끌어서 이동','⠿',()=>{});handle.draggable=!this.options.isBusy();handle.classList.add('block-grip');handle.addEventListener('dragstart',e=>{this.dragged=block.id;e.dataTransfer.setData('text/plain',block.id);e.dataTransfer.effectAllowed='move';row.classList.add('is-dragging');});handle.addEventListener('dragend',()=>{this.dragged=null;this.node.querySelectorAll('[data-drop]').forEach(n=>delete n.dataset.drop);row.classList.remove('is-dragging');});tools.append(handle);
    const label=document.createElement('span');label.className='block-type-label';label.textContent=block.type==='photo'?'사진 '+(++photoNumber):block.type==='heading'?'소제목':'본문';tools.append(label);
    tools.append(this.button('이 문단 위로 이동','↑',()=>this.move(block.id,index-1),index===0),this.button('이 문단 아래로 이동','↓',()=>this.move(block.id,index+1),index===doc.blocks.length-1));
    if(block.type!=='photo')tools.append(this.button(block.type==='heading'?'본문으로 바꾸기':'소제목으로 바꾸기',block.type==='heading'?'본문':'소제목',()=>this.mutate(d=>{d.blocks[index].type=block.type==='heading'?'paragraph':'heading';},block.id)));
    const remove=this.button(block.type==='photo'?'이 글에서 사진 빼기':'이 문단 삭제',block.type==='photo'?'빼기':'삭제',()=>{this.mutate(d=>d.blocks.splice(index,1));this.options.notify('이 글에서 뺐어요. ↶ 되돌리기로 복구할 수 있어요.');});tools.append(remove);row.append(tools);
    if(block.type==='photo'){
     const image=document.createElement('img');image.src='/media/'+block.image_id+'.jpg';image.alt=block.caption||'사진 '+photoNumber;image.draggable=false;image.tabIndex=0;image.setAttribute('role','button');image.setAttribute('aria-label','사진 크게 보기');image.onclick=()=>this.options.previewPhoto(block.image_id);image.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();image.click();}};row.append(image);
     const actions=document.createElement('div');actions.className='block-photo-actions';actions.append(this.button('이 글의 사진 교체','사진 바꾸기',()=>this.choosePhoto(index,block.id)));row.append(actions);
    }
    const input=document.createElement('textarea');input.className=block.type==='photo'?'block-caption':'block-text';input.rows=1;input.value=block.type==='photo'?block.caption:block.text;input.maxLength=block.type==='photo'?2000:30000;input.dataset.editorFor=block.id;if(block.type==='photo')input.dataset.caption='true';input.setAttribute('aria-label',block.type==='photo'?'이 사진의 설명':block.type==='heading'?'소제목 편집':'문단 편집');input.placeholder=block.type==='photo'?'사진에 짧은 설명을 남겨 보세요 · 선택':block.type==='heading'?'소제목을 적어 주세요':'이곳에 이야기를 이어가세요';input.disabled=this.options.isBusy();
    input.addEventListener('input',()=>{
     const current=this.options.getDocument(),target=current.blocks.find(b=>b.id===block.id);if(!target)return;this.remember(current,block.id);const field=block.type==='photo'?'caption':'text',old=target[field];if(/\[\[photo:\d+\]\]/.test(input.value)){input.value=input.value.replace(/\[\[photo:\d+\]\]/g,'');this.options.notify('사진은 ‘사진 추가’로 넣어 주세요.');}target[field]=input.value;
     if(M.serialize(current).length>30000){target[field]=old;input.value=old;return this.options.notify('원고가 너무 길어요. 문단을 나눠 보관해 주세요.');}
     this.options.commit(current);this.resize(input);this.node.querySelector('#blockUndo').disabled=false;this.node.querySelector('#blockRedo').disabled=true;
    });
    input.addEventListener('keydown',e=>{
     if(e.isComposing||block.type==='photo'||e.key!=='Enter'||!(e.ctrlKey||e.metaKey))return;e.preventDefault();const at=input.selectionStart,end=input.selectionEnd,id=M.uid();this.mutate(d=>{d.blocks[index].text=input.value.slice(0,at);d.blocks.splice(index+1,0,{id,type:'paragraph',text:input.value.slice(end)});},id);
    });row.append(input);
    if(this.options.refine){
     const actions=document.createElement('div');actions.className='block-refine-actions';
     const refine=this.button('이 부분만 AI로 다듬기','✦ 문단 다듬기',()=>{const start=input.selectionStart,end=input.selectionEnd;this.options.refine(block,start===end?0:start,start===end?input.value.length:end);});
     const hint=document.createElement('small');hint.textContent='문장을 선택하면 그 부분만 고쳐요';
     const selected=()=>{refine.textContent=input.selectionEnd>input.selectionStart?'✦ 선택 부분 다듬기':block.type==='photo'?'✦ 사진 설명 다듬기':'✦ 문단 다듬기';refine.disabled=this.options.isBusy()||!input.value.trim();};
     ['select','keyup','mouseup','input'].forEach(name=>input.addEventListener(name,selected));selected();actions.append(refine,hint);row.append(actions);
    }
    const insert=this.button('이 아래에 문단 추가','＋ 이어 쓰기',()=>this.addText(index));insert.classList.add('block-insert');row.append(insert);
    row.addEventListener('dragover',event=>{if(!this.dragged||this.options.isBusy())return;event.preventDefault();row.dataset.drop=event.clientY<row.getBoundingClientRect().top+row.offsetHeight/2?'before':'after';});
    row.addEventListener('dragleave',e=>{if(!row.contains(e.relatedTarget))delete row.dataset.drop;});
    row.addEventListener('drop',event=>{if(!this.dragged||this.options.isBusy())return;event.preventDefault();const from=doc.blocks.findIndex(b=>b.id===this.dragged);let to=index+(row.dataset.drop==='after'?1:0);if(from<to)to--;delete row.dataset.drop;this.move(this.dragged,Math.max(0,Math.min(doc.blocks.length-1,to)));this.dragged=null;});body.append(row);
   });
   const footer=document.createElement('div');footer.className='block-bottom';footer.append(this.button('맨 아래에 문단 추가','＋ 문단 추가',()=>this.addText()),this.button('맨 아래에 사진 추가','＋ 사진 추가',()=>this.choosePhoto()));
   const original=this.button('처음 불러온 원고 보기','처음 원고',()=>this.options.showOriginal());footer.append(original);this.node.append(footer);
   requestAnimationFrame(()=>{this.node.querySelectorAll('textarea').forEach(field=>this.resize(field));if(version!==this.renderVersion||(document.activeElement!==document.body&&document.activeElement!==initiator))return;if(!focus&&['blockUndo','blockRedo'].includes(focused)){const action=this.node.querySelector('#'+focused);const alternative=this.node.querySelector(focused==='blockUndo'?'#blockRedo':'#blockUndo');(action&&!action.disabled?action:alternative)?.focus({preventScroll:true});}if(focus){const target=this.node.querySelector(`[data-editor-for="${focus}"]`);if(target){target.focus({preventScroll:true});target.scrollIntoView({block:'nearest',behavior:'auto'});}}});
  }
 }
 root.StoryBlockEditor=StoryBlockEditor;
})(window);
