"use strict";
async function tistoryAction(mode,payload){
 const sleep=ms=>new Promise(r=>setTimeout(r,ms));
 const title=document.querySelector('#post-title-inp,input[name="title"],textarea[placeholder*="제목"]');
 const tiny=window.tinymce||window.tinyMCE;
 const editor=tiny?.get?.('editor-tistory')||tiny?.activeEditor;
 const body=editor?.getBody?.();
 const blocked=Boolean(document.querySelector('input[name="captcha"],#captcha,[data-testid="captcha"]'));
 const existing=Boolean(title?.value?.trim()||body?.textContent?.trim()||body?.querySelector('img,video,iframe'));
 if(mode==='probe')return {eligible:Boolean(title&&body&&!existing&&!blocked),titleFound:Boolean(title),bodyFound:Boolean(body),existing,blocked};
 let stage='편집기 확인',count=0,changed=false;
 const uploads=[];
 const diagnostic=()=>({uploads,images:[...(editor?.getBody?.()?.querySelectorAll('img')||[])].map(img=>({complete:img.complete,width:img.naturalWidth,protocol:new URL(img.src,location.href).protocol})),editorFound:Boolean(editor),titleFound:Boolean(title),fileInputs:[...document.querySelectorAll('input[type=file]')].map(el=>({accept:el.accept,disabled:el.disabled})),buttons:[...document.querySelectorAll('button,[role=button]')].slice(0,50).map(el=>(el.getAttribute('title')||el.getAttribute('aria-label')||el.textContent||'').trim().slice(0,45))});
 try{
  if(blocked)throw Error('티스토리에서 추가 인증을 완료한 후 다시 시도해 주세요.');
  if(!title||!body)throw Error('티스토리 기본 편집기를 찾지 못했어요. HTML·마크다운 모드라면 기본 모드로 전환해 주세요.');
  if(existing)throw Error('이미 내용이 있는 편집기에는 덮어쓰지 않아요. 빈 새 글을 열어 주세요.');
  if(!payload||typeof payload.body!=='string'||typeof payload.title!=='string'||!Array.isArray(payload.photos)||payload.photos.length>10)throw Error('전달된 초안 형식이 올바르지 않아요.');
  const escape=s=>s.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
  const align=payload.format?.align==='left'?'left':'center';
  const fontName=payload.format?.font_key==='nanumgothic'?'Nanum Gothic':'Nanum Myeongjo';
  const fontLabel=fontName==='Nanum Gothic'?'나눔고딕':'나눔명조';
  const style="text-align:"+align+";font-family:'"+fontName+"',"+(fontName==='Nanum Gothic'?'sans-serif':'serif')+";font-size:15px;line-height:2";
  const normal=s=>s.normalize('NFC').replace(/[\s\u200b\ufe0e\ufe0f]/g,'');
  stage='제목 입력';
  const proto=title.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(proto,'value').set.call(title,payload.title);
  title.dispatchEvent(new Event('input',{bubbles:true}));title.dispatchEvent(new Event('change',{bubbles:true}));changed=true;
  const markers=[...payload.body.matchAll(/\[\[photo:(\d+)\]\]/g)].map(m=>Number(m[1]));
  if(markers.join(',')!==payload.photos.map((_,i)=>i+1).join(','))throw Error('사진 위치와 순서가 맞지 않아요. 앱에서 다시 저장해 주세요.');
  const blocks=payload.body.split(/(\[\[photo:\d+\]\])/g);const expectedSegments=[];
  for(const block of blocks){
   if(!block.trim())continue;
   const marker=block.match(/^\[\[photo:(\d+)\]\]$/);
   if(!marker){
    stage='본문·서식 입력';
    const html=block.trim().split(/\n\s*\n/).map(paragraph=>{
     const heading=paragraph.startsWith('## '),tag=heading?'h3':'p',text=heading?paragraph.slice(3):paragraph;
     expectedSegments.push(normal(text));
     return '<'+tag+' style="'+style+'">'+escape(text).replaceAll('\n','<br>')+'</'+tag+'>';
    }).join('');
    editor.focus();editor.insertContent(html);editor.nodeChanged();editor.save();
   }else{
    stage='사진 '+marker[1]+' 업로드';
    const before=[...editor.getBody().querySelectorAll('img')];
    const photo=payload.photos[Number(marker[1])-1];
    const bookmark=editor.selection.getBookmark(2,true);
    // Native uploaders can create, click and discard a file input in one call.
    // Supply the photo at that click, while the application's own handlers exist.
    const trace={photo:Number(marker[1]),route:"",inputEvent:false,changeEvent:false,detached:false};uploads.push(trace);
    const binary=Uint8Array.from(atob(photo.base64),c=>c.charCodeAt(0));
    let supplied=false;
    const supply=input=>{
     if(supplied||input.disabled)return;
     supplied=true;trace.detached=!input.isConnected;
     editor.focus();editor.selection.moveToBookmark(bookmark);
     const view=input.ownerDocument.defaultView,transfer=new view.DataTransfer();
     transfer.items.add(new view.File([binary],photo.name,{type:'image/jpeg'}));
     input.value='';input.files=transfer.files;
     input.dispatchEvent(new view.Event('input',{bubbles:true}));trace.inputEvent=true;
     input.dispatchEvent(new view.Event('change',{bubbles:true}));trace.changeEvent=true;
    };
    const proto=HTMLInputElement.prototype,ownClick=Object.getOwnPropertyDescriptor(proto,'click');
    const nativeClick=proto.click;
    Object.defineProperty(proto,'click',{configurable:true,writable:true,value:function(...args){
     if(this.type==='file'){trace.route='native-picker';supply(this);return;}
     return nativeClick.apply(this,args);
    }});
    try{
     const visible=el=>Boolean(el&&el.getClientRects().length);
     const attach=[...document.querySelectorAll('#attach-layer-btn,[data-command="image"],button,[role="button"]')].find(el=>visible(el)&&(/^(첨부|사진|이미지)$/.test((el.getAttribute('title')||el.getAttribute('aria-label')||el.textContent||'').trim())||el.id==='attach-layer-btn'));
     if(attach){attach.click();await sleep(100);}
     if(!supplied){
      const photoItem=[...document.querySelectorAll('button,a,li,[role="menuitem"]')].find(el=>visible(el)&&/^(사진|이미지)$/.test(el.textContent.trim())&&!el.querySelector('button,a'));
      if(photoItem)photoItem.click();
     }
     for(let i=0;i<20&&!supplied;i++){
      const input=[...document.querySelectorAll('input[type=file]')].find(el=>!el.disabled&&/image|\.jpe?g|\.png/i.test(el.accept));
      if(input){trace.route='existing-input';supply(input);}else await sleep(150);
     }
    }finally{
     if(ownClick)Object.defineProperty(proto,'click',ownClick);else delete proto.click;
    }
    if(!supplied)throw Error('사진 선택 창을 찾지 못했어요. 첨부 → 사진 메뉴가 열리는지 확인하고 진단을 복사해 주세요.');
    let added;
    for(let i=0;i<240;i++){
     added=[...(editor.getBody()?.querySelectorAll('img')||[])].find(img=>!before.includes(img)&&img.complete&&img.naturalWidth>0&&/^https:\/\//.test(img.src));
     if(added)break;await sleep(250);
    }
    if(!added)throw Error('사진 업로드 완료를 확인하지 못했어요. 티스토리 화면에서 결과를 확인해 주세요.');
    count++;
    const figure=added.closest('figure')||added;
    editor.selection.select(figure);editor.selection.collapse(false);
    editor.insertContent('<p style="'+style+'"><br></p>');editor.nodeChanged();editor.save();
   }
  }
  stage='입력 결과 확인';editor.save();
  let offset=0;const actualText=normal(editor.getBody().textContent);
  const textVerified=expectedSegments.every(segment=>{const found=actualText.indexOf(segment,offset);if(found<0)return false;offset=found+segment.length;return true;});
  if(title.value!==payload.title||!textVerified)throw Error('입력한 글의 반영을 확인하지 못했어요. 일부 내용이 남아 있으니 편집기를 확인해 주세요.');
  if(count!==payload.photos.length)throw Error('사진 개수를 확인해 주세요.');
  const paragraphs=[...editor.getBody().querySelectorAll('p,h3')].filter(el=>el.textContent.trim()&&!el.closest("figure,figcaption"));
  const view=editor.getWin?.()||body.ownerDocument.defaultView;
  const alignment=paragraphs.length>0&&paragraphs.every(el=>view.getComputedStyle(el).textAlign===align);
  const leaves=[];
  for(const paragraph of paragraphs){
   const walker=paragraph.ownerDocument.createTreeWalker(paragraph,NodeFilter.SHOW_TEXT);let node;
   while(node=walker.nextNode())if(node.textContent.trim())leaves.push(node.parentElement);
  }
  const size=leaves.length>0&&leaves.every(el=>Math.abs(parseFloat(view.getComputedStyle(el).fontSize)-15)<.5);
  const font=leaves.length>0&&leaves.every(el=>view.getComputedStyle(el).fontFamily.includes(fontName));
  const verified=alignment&&size&&font;
  return {state:verified?'ready':'partial',ok:verified,count,stage,message:verified?'티스토리에 글과 사진을 옮겼어요. 내용을 확인한 뒤 직접 발행해 주세요.':'글과 사진은 옮겼지만 일부 서식이 확인되지 않았어요. 글을 다시 넣지 말고 편집기와 진단을 확인해 주세요.',formatting:{requested:true,alignment,size,font,verified,expected:{align,size:15,font:fontLabel}}};
 }catch(error){return {state:blocked?'blocked':'failed',count,stage,message:error.message+(changed?' 일부 내용이 남아 있을 수 있어요.':''),diagnostics:diagnostic()};}
}
