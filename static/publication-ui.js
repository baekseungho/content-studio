/* A user's publication confirmation is distinct from editor input and API publication. */
(() => {
 'use strict';
 const el=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};
 const button=(id,text,fn,cls='secondary')=>{const b=el('button',cls,text);b.type='button';if(id)b.id=id;b.onclick=fn;return b;};
 const isBlog=p=>['naver','tistory'].includes(p);
 const readableUrl=value=>{try{return decodeURI(value);}catch{return value;}};
 const link=(url,text)=>{const a=el('a','publication-link',text);try{const u=new URL(url);if(u.protocol!=='https:'||!(/^(?:m\.)?blog\.naver\.com$/.test(u.hostname)||/^[a-z0-9-]+\.tistory\.com$/.test(u.hostname)))return el('span','','주소 확인 필요');a.href=url;a.target='_blank';a.rel='noopener noreferrer';}catch{return el('span','','주소 확인 필요');}return a;};
 let records=[],loadedFor='',loadingFor='',sequence=0;
 const panel=el('section','publication-panel');panel.id='publicationPanel';panel.hidden=true;const title=el('strong','','블로그에서 발행하셨나요?'),note=el('p','','발행한 글 주소를 남기면 내 글에서 다시 열 수 있어요. 편집기 입력과 발행은 별개예요.'),links=el('div','publication-panel-links'),hint=el('p','hint');hint.id='publicationRecordHint';const add=button('recordPublishedPost','발행한 글 주소 남기기',()=>openRecord());panel.append(title,note,links,add,hint);$('publishArea').after(panel);
 function refresh(){
  const p=activePlatform();panel.hidden=!isBlog(p)||!draft[platformInfo[p].body]?.trim();if(panel.hidden)return;
  const items=records.filter(r=>r.platform===p&&r.draft_id===draft.id);links.replaceChildren();for(const item of items.slice(0,2)){const row=el('div','publication-mini');row.append(link(item.url,'발행한 글 열기 ↗'),el('small','',!dirty&&item.matches_current&&loadedFor===draft.id+'@'+draft.updated?'이 저장 원고로 발행 · 직접 확인':'이전 발행 주소 · 현재 원고와 다시 확인'));links.append(row);}
  add.disabled=busy||dirty||!draft.id;hint.textContent=dirty?'원고를 수정 중이에요. 실제 발행한 글과 내용이 같은지 읽고 먼저 보관해 주세요.':!draft.id?'글을 보관한 뒤 발행 주소를 남길 수 있어요.':'게시물을 직접 읽고 같은 원고로 발행한 글인지 확인해 주세요. 주소를 자동으로 열거나 검증하지 않아요.';
 }
 async function reload(){
  const id=draft.id,version=draft.updated,nav=navigationEpoch,key=id+'@'+version;if(!id){records=[];loadedFor='';refresh();return;}if(loadingFor===key)return;loadingFor=key;const seq=++sequence;
  try{const value=await api('/api/publications?draft_id='+id);if(seq!==sequence||id!==draft.id||version!==draft.updated||nav!==navigationEpoch)return;records=value;loadedFor=key;refresh();}
  catch{if(seq===sequence){records=[];loadedFor='';refresh();}}
  finally{if(seq===sequence)loadingFor='';}
 }
 function loaded(){++sequence;loadingFor='';records=[];loadedFor='';refresh();void reload();}
 function saved(){loadedFor='';loadingFor='';void reload();}
 function appendLinks(article,item){const section=el('div','library-publication-links');for(const [p,state] of Object.entries(item.channel_states||{})){if(!state.published_url)continue;const row=el('div');row.append(link(state.published_url,platformInfo[p].label+' 게시물 열기 ↗'),el('small','',state.state==='published'?'발행 직접 확인':'이전 원고 발행 주소'));section.append(row);}if(section.childElementCount)article.append(section);}
 function openRecord(){
  const p=activePlatform();if(busy||dirty||!draft.id||!isBlog(p))return;const id=draft.id,version=draft.updated,nav=navigationEpoch,epoch=editEpoch,blogUrl=p==='tistory'?$('tistoryUrl').value.trim():'';
  const box=modal('발행한 글 주소 남기기');$('modal').dataset.view='publication-record';box.append(el('p','publication-eyebrow',platformInfo[p].label+' · 내가 직접 확인한 게시 기록'),el('h3','','이 원고로 발행한 글이 맞나요?'),el('p','','이미 블로그에서 발행한 게시물의 주소를 넣어 주세요. 이 기능으로 새 글을 올리거나 게시물 내용을 자동 확인하지 않아요.'));
  const snapshot=el('div','publication-story');snapshot.append(el('strong','',draft[platformInfo[p].title]||'제목 없는 이야기'),el('small','',new Date(version*1000).toLocaleString('ko-KR')+' 저장한 원고'));box.append(snapshot);
  const label=el('label','field-label','발행한 게시물 주소'),input=el('input');input.id='publishedPostUrl';input.type='url';input.maxLength=2048;input.autocomplete='off';input.placeholder=p==='naver'?'https://blog.naver.com/내아이디/글번호':'https://내블로그.tistory.com/글번호';label.htmlFor=input.id;const urlRow=el('div','publication-url-row');const validate=button('validatePublicationUrl','주소 확인',()=>void prepare());urlRow.append(input,validate);box.append(label,urlRow);
  const preview=el('div','publication-url-preview');preview.hidden=true;preview.id='publicationUrlPreview';const checkLabel=el('label','publication-confirm'),check=el('input');check.id='publicationConfirmed';check.type='checkbox';checkLabel.append(check,el('span','','게시물을 직접 열어 읽었고, 위 저장 원고로 발행한 글이 맞아요.'));const feedback=el('p','publication-feedback');feedback.id='publicationFeedback';feedback.setAttribute('role','status');const actions=el('div','publication-actions'),cancel=button('cancelPublicationRecord','취소',()=>$('modal').close()),save=button('savePublicationRecord','확인한 발행 주소 기록',()=>void submit(),'primary');save.disabled=true;actions.append(cancel,save);box.append(preview,checkLabel,feedback,actions);frameModal(box,actions);
  let canonical='',serial=0,pending=false;const active=()=>box.contains(input)&&$('modal').open&&$('modal').dataset.view==='publication-record'&&id===draft.id&&version===draft.updated&&nav===navigationEpoch&&epoch===editEpoch&&!dirty;
  function reset(){++serial;canonical='';preview.hidden=true;preview.replaceChildren();check.checked=false;save.disabled=true;feedback.textContent='';}input.oninput=reset;check.onchange=()=>{save.disabled=!canonical||!check.checked||pending;};
  async function prepare(){if(pending||!active())return;if(!input.value.trim()){input.focus();feedback.textContent='발행한 글 주소를 먼저 붙여 넣어 주세요.';return;}const seq=++serial;canonical='';save.disabled=true;check.checked=false;validate.disabled=true;feedback.textContent='주소 형식을 확인하고 있어요.';
   try{const value=await api('/api/publications/preview',{platform:p,url:input.value.trim(),blog_url:blogUrl});if(!active()||seq!==serial)return;canonical=value.url;preview.replaceChildren(el('small','','추적용 문구를 뺀 게시물 주소예요.'),link(canonical,readableUrl(canonical)+' ↗'));preview.hidden=false;feedback.textContent='주소 형식을 확인했어요. 게시물을 직접 읽고 아래에 확인해 주세요.';}
   catch(error){if(active()&&seq===serial){preview.hidden=true;feedback.textContent=error.message;input.setAttribute('aria-invalid','true');}}
   finally{if(box.contains(validate))validate.disabled=false;}
  }
  async function submit(){if(!active()||pending||!canonical||!check.checked)return;pending=true;save.disabled=validate.disabled=input.disabled=check.disabled=true;feedback.textContent='이 저장 원고에 발행 주소를 기록하고 있어요.';
   try{await api('/api/publications',{id,updated:version,platform:p,url:canonical,blog_url:blogUrl,confirmed:true});saved();window.LibraryUI?.saved();if(active()){$('modal').close();notify('발행한 글 주소를 기록했어요. 내 글에서 다시 열 수 있어요.');}}
   catch(error){if(active())feedback.textContent=error.message;}
   finally{pending=false;if(box.contains(save)){input.disabled=validate.disabled=check.disabled=false;save.disabled=!canonical||!check.checked;}}
  }
  input.addEventListener('input',()=>input.removeAttribute('aria-invalid'));input.focus();
 }

 async function history(){
  if(busy)return;const box=modal('게시 기록');$('modal').dataset.view='publication-history';libraryViews(box,true);box.append(el('p','hint','블로그 주소는 내가 직접 확인한 기록이에요. SNS 발행 결과와 구분해요. 최근 100개의 블로그 주소와 최근 SNS 기록을 보여줘요.'));
  const toggle=button('toggleArchivedPublications','정리한 발행 주소 보기',()=>{archived=!archived;void draw();},'quiet'),feedback=el('p','publication-feedback'),list=el('div','publication-history-list');feedback.id='publicationHistoryFeedback';feedback.setAttribute('role','status');const retry=button('retryPublicationHistory','다시 불러오기',()=>void draw(),'quiet');retry.hidden=true;box.append(toggle,retry,feedback,list);let archived=false,seq=0;const alive=()=>box.contains(list)&&$('modal').open&&$('modal').dataset.view==='publication-history';
  async function draw(){const serial=++seq;feedback.textContent='게시 기록을 확인하고 있어요.';toggle.disabled=true;
   try{const results=await Promise.allSettled([api('/api/publications'+(archived?'?archived=1':'')),archived?Promise.resolve([]):api('/api/history')]);if(!alive()||serial!==seq)return;list.replaceChildren();const manual=results[0].status==='fulfilled'?results[0].value:[],sns=results[1].status==='fulfilled'?results[1].value:[],failures=results.flatMap((r,i)=>r.status==='rejected'?[(i===0?'블로그 주소 기록':'SNS 발행 기록')+'을 불러오지 못했어요. '+r.reason.message]:[]);feedback.textContent=failures.join(' ');retry.hidden=!failures.length;toggle.textContent=archived?'현재 발행 주소 보기':'정리한 발행 주소 보기';toggle.setAttribute('aria-pressed',String(archived));
    if(!manual.length&&!sns.length&&!failures.length)list.append(el('p','library-empty',archived?'정리한 발행 주소가 없어요.':'아직 기록한 게시물이 없어요. 블로그에서 직접 발행한 뒤 마지막 확인 화면에서 주소를 남길 수 있어요.'));
    for(const item of manual){const card=el('article','publication-history-card');card.dataset.recordId=item.id;card.append(el('small','publication-eyebrow',platformInfo[item.platform].label+' · 직접 확인한 발행 기록'),el('h3','',item.title||'제목 없는 이야기'),link(item.url,'게시물 열기 ↗'),el('p','hint',item.draft_unreadable?'보관 원고를 읽지 못해 일치 여부를 확인할 수 없어요. 발행 주소는 그대로 보관했어요.':item.matches_current?'기록한 저장 원고와 현재 보관 원고가 같아요.':'이전 원고로 남긴 발행 기록이에요. 현재 보관 원고는 달라요.'),el('small','',new Date(item.created*1000).toLocaleString('ko-KR')));
     const controls=el('div','publication-actions'),open=button('','원고 열기',()=>window.LibraryUI?.goTo(item.draft_id,item.platform),'quiet'),archive=button('',archived?'기록 다시 꺼내기':'이 앱에서 기록만 정리',async()=>{archive.disabled=true;const targetArchived=!archived;try{await api('/api/publications/archive',{record_id:item.id,revision:item.revision,archived:targetArchived});saved();window.LibraryUI?.saved();if(alive()){await draw();feedback.textContent=(targetArchived?'기록만 정리했어요. 실제 게시물과 원고는 그대로예요.':'발행 주소를 다시 꺼냈어요.')+(feedback.textContent?' '+feedback.textContent:'');}}catch(error){if(alive())feedback.textContent=error.message;archive.disabled=false;}},'quiet');archive.dataset.action='archive-publication';controls.append(open,archive);card.append(controls);list.append(card);
    }
    const labels={published:'발행 완료',publishing:'진행 중 · 계정에서 결과 확인',uncertain:'발행 결과 확인 필요',failed:'발행 실패 기록'};for(const item of sns){const card=el('article','publication-history-card');card.append(el('small','publication-eyebrow',(item.channel==='threads'?'Threads':'인스타그램')+' · 연결된 계정의 발행 기록'),el('h3','',item.title||'제목 없는 이야기'),el('p','',labels[item.state]||'결과 확인 필요'),el('small','',new Date(item.created*1000).toLocaleString('ko-KR')));list.append(card);}
   }catch(error){if(alive()&&serial===seq)feedback.textContent=error.message;}
   finally{if(alive()&&serial===seq)toggle.disabled=false;}
  }
  await draw();
 }
 window.PublicationUI={loaded,saved,refresh,lock:refresh,appendLinks,history,openRecord};loaded();
})();
