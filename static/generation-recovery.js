/* Reconnect to an existing writing job. Never submits or publishes a second request. */
(() => {
 'use strict';
 const KEY='mellow-pending-generation-v1',LIMIT=700000;
 const el=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
 const button=(id,text,fn)=>{const n=el('button',text);n.type='button';n.id=id;n.className='secondary';n.onclick=fn;return n;};
 const allowed=['prompt','tone','style','facts','disclosure','language','template','threads_tone','threads_community','threads_networking','campaign_enabled','blog_layouts','campaign_count_spaces','selected_place','research','images','voice_styles','channel_images','campaign_manual_checks','campaign_experience',...campaignTextFields,...campaignNumberFields];
 let record=null,checking=false,serial=0,appliedNavigation=null;
 const banner=el('section');banner.id='generationRecovery';banner.className='workspace-recovery';banner.hidden=true;banner.setAttribute('aria-label','이전 글 만들기 결과');$('workflow').before(banner);
 function read(){try{const raw=sessionStorage.getItem(KEY);if(!raw||raw.length>LIMIT)return null;const r=JSON.parse(raw);if(r.version!==1||!/^[a-f0-9]{32}$/.test(r.job||'')||!Array.isArray(r.platforms)||!r.platforms.length||r.platforms.length>4||r.platforms.some(p=>!Object.hasOwn(platformInfo,p))||new Set(r.platforms).size!==r.platforms.length||!r.input||typeof r.input!=='object'||Array.isArray(r.input))return null;if(!Array.isArray(r.input.images)||r.input.images.length>10||r.input.images.some(id=>typeof id!=='string'||!/^[a-f0-9]{32}$/.test(id))||typeof r.input.prompt!=='string'||!['ko','en'].includes(r.input.language))return null;for(const key of ['prompt','tone','style','facts','disclosure','template','threads_tone',...campaignTextFields])if(Object.hasOwn(r.input,key)&&typeof r.input[key]!=='string')return null;for(const key of ['research','campaign_enabled','campaign_count_spaces','threads_community','threads_networking'])if(Object.hasOwn(r.input,key)&&typeof r.input[key]!=='boolean')return null;for(const key of campaignNumberFields)if(Object.hasOwn(r.input,key)&&(!Number.isFinite(r.input[key])||r.input[key]<0))return null;for(const key of ['voice_styles','blog_layouts','channel_images','campaign_experience'])if(Object.hasOwn(r.input,key)&&(!r.input[key]||typeof r.input[key]!=='object'||Array.isArray(r.input[key])))return null;if(r.input.campaign_manual_checks&&!Array.isArray(r.input.campaign_manual_checks))return null;if(r.input.selected_place!==undefined&&r.input.selected_place!==null&&(typeof r.input.selected_place!=='object'||typeof r.input.selected_place.name!=='string'||typeof r.input.selected_place.address!=='string'))return null;r.applied=false;return r;}catch{return null;}}
 function write(){try{const raw=JSON.stringify(record);if(raw.length>LIMIT)throw Error();sessionStorage.setItem(KEY,raw);return true;}catch{return false;}}
 function clear(){++serial;record=null;try{sessionStorage.removeItem(KEY);}catch{}render();}
 function render(){
  banner.hidden=!record;if(!record)return;banner.replaceChildren();const copy=el('div');copy.append(el('strong',record.applied?'불러온 원고를 보관해 주세요':'이전에 요청한 글, 결과부터 확인할까요?'),el('p',record.applied?'이 브라우저의 임시 보관에 실패했어요. 글 보관하기로 원고를 저장해 주세요.':'새로 요청하기 전에 진행 중이던 글을 확인해요. 결과 확인은 글을 다시 만들지 않아요.'));const actions=el('div');actions.className='help-actions';actions.append(button('checkGenerationResult','이전 결과 확인',()=>void check()),button('forgetGeneration','이 요청 정리',forget));banner.append(copy,actions);banner.querySelectorAll('button').forEach(b=>b.disabled=busy||checking);
 }
 function forget(){if(busy||checking)return;const box=modal('이전 요청을 정리할까요?');$('modal').dataset.view='generation-forget';para(box,'기록을 정리해도 이미 진행 중인 글 만들기는 취소되지 않아요. 결과를 먼저 확인하는 것을 권해요.');box.append(button('confirmForgetGeneration','결과 확인 없이 기록 정리',()=>{clear();$('modal').close();notify('이전 요청 기록을 정리했어요. 새 요청은 글 만들기 버튼에서 직접 시작해 주세요.');}));}
 function begin(job,platforms,request){
  if(!/^[a-f0-9]{32}$/.test(job||''))return;
  const checkpoint={...request,campaign_manual_checks:draft.campaign_manual_checks||[],campaign_experience:draft.campaign_experience||{}};const input=Object.fromEntries(allowed.filter(k=>Object.hasOwn(checkpoint,k)).map(k=>[k,checkpoint[k]]));
  record=JSON.parse(JSON.stringify({version:1,job,platforms:[...platforms],input,started:Date.now(),applied:false}));
  if(!write())notify('이 브라우저에는 작업 정보를 임시 보관할 수 없어요. 글이 완성될 때까지 이 탭을 열어 두세요.');render();
 }
 function completed(){if(!record)return;record.applied=true;appliedNavigation=navigationEpoch;persistRecovery();if(recoveryReady)clear();else{write();render();}}
 function saved(){if(record?.applied&&appliedNavigation===navigationEpoch)clear();}
 function beforeGenerate(){if(!record||record.applied)return true;render();banner.scrollIntoView({block:'center'});notify('같은 글을 다시 요청하기 전에 이전 결과를 확인하거나 요청 기록을 정리해 주세요.');return false;}
 function newStory(result,notesOnly=false){
  const next=fresh(),input=record.input;
  for(const key of allowed)if(Object.hasOwn(next,key)&&Object.hasOwn(input,key))next[key]=JSON.parse(JSON.stringify(input[key]));
  next.images=Array.isArray(input.images)?input.images.filter(id=>typeof id==='string'&&/^[a-f0-9]{32}$/.test(id)).slice(0,10):[];
  next.language=input.language==='en'?'en':'ko';next.selected_platforms=[...record.platforms];next.editing_platform=record.platforms[0];next.selective_generation=true;next.workspace_step=notesOnly?1:2;
  next.campaign_manual_state={};next.campaign_brief_review={hash:'',sources:[]};
  if(notesOnly)return next;
  for(const p of record.platforms){const info=platformInfo[p];if(typeof result?.[info.body]!=='string'||!result[info.body].trim()||result[info.body].length>100000||(info.title&&(typeof result[info.title]!=='string'||!result[info.title].trim()||result[info.title].length>200)))throw Error('완성된 원고의 내용을 확인하지 못했어요. 이전 요청을 정리하기 전에 앱 상태를 확인해 주세요.');next[info.body]=result[info.body];if(info.title)next[info.title]=result[info.title];next.platform_languages[p]=next.language;
   if(info.title)next.blog_documents[p]=StoryBlocks.create(result[info.body],next.images,result[info.title],next.template);
   else{const selected=input.channel_images?.[p];next.channel_media[p]={version:1,images:Array.isArray(selected)?selected.filter(id=>next.images.includes(id)):next.images.slice(),frame:p==='threads'?'original':'portrait',adjustments:{}};}
  }
  // Let the channel adapter normalize configuration on load; never restore publication/review records.
  if(record.platforms.includes('instagram')){next.facts_translation=typeof result.facts_translation==='string'?result.facts_translation:'';next.facts_translation_source=typeof result.facts_translation_source==='string'?result.facts_translation_source:'';}
  return next;
 }
 function importStory(box,result,notesOnly=false){
  if(busy||!record)return;let next;try{next=newStory(result,notesOnly);}catch(e){notify(e.message);return;}
  const current=record;const proceed=()=>{if(record!==current||busy||!box.isConnected||!$('modal').open)return;draft=next;loadDraft();markDirty();completed();$('modal').close();notify(notesOnly?'요청에 사용한 메모를 새 글감으로 불러왔어요.':'결과를 새 이야기로 불러왔어요. 내용을 읽고 글 보관하기를 눌러 주세요.');};
  window.LibraryUI.leaveGuard(box,proceed);
 }
 async function check(){
  if(!record||busy||checking)return;const current=record,seq=++serial;checking=true;render();const box=modal('이전 글 만들기 결과');$('modal').dataset.view='generation-result';const note=el('p','기존 요청의 진행 상황을 확인하고 있어요.');note.id='recoveryResultStatus';note.setAttribute('role','status');box.append(note);const active=()=>seq===serial&&record===current&&box.contains(note)&&$('modal').open&&$('modal').dataset.view==='generation-result';
  try{
   const result=await api('/api/jobs/'+current.job);if(!active())return;
   if(result.state==='running'){note.textContent=result.message||'글을 만들고 있어요. 잠시 뒤 결과를 확인해 주세요.';box.append(button('refreshGenerationResult','진행 상황 다시 확인',()=>void check()));}
   else if(result.state==='done'){const next=newStory(result.result);note.textContent='글이 준비됐어요. 지금 작성 중인 이야기와 별도로 불러올 수 있어요.';for(const p of current.platforms){const preview=el('section');preview.className='recovered-preview';preview.append(el('h3',platformInfo[p].label),el('p',next[platformInfo[p].body].replace(/\[\[photo:\d+\]\]/g,'[사진]')));box.append(preview);}box.append(button('importGenerationResult','새 이야기로 불러오기',()=>importStory(box,result.result)));}
   else{note.textContent=result.code==='job_missing'?'앱이 다시 시작됐거나 결과 보관 시간이 지나 완성 글을 확인할 수 없어요. 자동으로 다시 요청하지 않았어요. 요청에 쓴 메모는 새 글감으로 불러올 수 있어요.':(result.error||'글 만들기를 완료하지 못했어요.');box.append(button('restoreGenerationNotes','요청했던 메모 불러오기',()=>importStory(box,null,true)));}
  }catch(error){if(active())note.textContent=error.message;}
  finally{if(seq===serial){checking=false;render();}}
 }
 $('modal').addEventListener('close',()=>{if($('modal').dataset.view==='generation-result'){++serial;checking=false;render();}});
 window.GenerationRecovery={begin,completed,saved,beforeGenerate,refresh:render};record=read();render();
})();
