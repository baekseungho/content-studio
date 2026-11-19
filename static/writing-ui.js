/* Scoped proposals are isolated from the draft until explicitly accepted. */
(() => {
 'use strict';
 const presets={warm:{label:'다정한 일상',ko:'크림이 고소해서 천천히 마셨던 한 잔이에요.',en:'The cream had this lovely, nutty taste.'},friendly:{label:'친구와 수다',ko:'이날 마신 라떼, 크림이 고소하더라고요 ㅎㅎ',en:'That nutty cream on top? So good.'},neat:{label:'깔끔한 기록',ko:'라떼 위에 크림이 올라가요. 고소한 맛이 좋았어요.',en:'A latte with cream on top. I liked the nutty taste.'},witty:{label:'가볍고 센스 있게',ko:'오늘의 한 잔은 크림라떼. 고소함이 포인트 ☕',en:'A cream latte kind of day ☕'},calm:{label:'차분한 취향',ko:'라떼 한 잔을 마셨어요. 고소한 크림이 기억에 남아요.',en:'A latte, a little cream. That nutty taste stayed with me.'}};
 const clone=v=>JSON.parse(JSON.stringify(v));
 const el=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};
 const button=(label,fn,cls='quiet')=>{const n=el('button',cls,label);n.type='button';n.onclick=fn;return n;};
 const defaultVoice=p=>({name:'',preset:p,formality:'auto',emoji:p==='neat'||p==='calm'?'none':'light',sentence:'balanced',sample:'',avoid:''});
 let store={revision:0,profiles:{}},storeError='',voiceChannel=activePlatform(),session=null,history={},loadedEpoch=navigationEpoch;
 function label(platform){const v=draft.voice_styles?.[platform];return v?(v.name||presets[v.preset]?.label||'내 말투'):'';}
 function setVoice(platform,value){if(busy)return;draft.voice_styles||={};if(value)draft.voice_styles[platform]=clone(value);else delete draft.voice_styles[platform];markDirty();renderVoices();updateOptionSummaries();}
 const home=el('section','voice-home');home.id='voiceHome';
 const heading=el('div','voice-heading'),intro=el('div');intro.append(el('strong','','내 글에 어울리는 말투'),el('small','','채널마다 다르게 고를 수 있어요. 이미 만든 글은 바뀌지 않아요.'));
 const channels=el('select');channels.id='voiceChannel';channels.setAttribute('aria-label','말투를 설정할 채널');Object.entries(platformInfo).forEach(([key,info])=>{const o=el('option','',info.label);o.value=key;channels.append(o);});channels.value=voiceChannel;channels.onchange=()=>{voiceChannel=channels.value;renderVoices();};heading.append(intro,channels);
 const cards=el('div','voice-cards');cards.id='voiceCards';cards.setAttribute('role','group');cards.setAttribute('aria-label','말투 고르기');
 const footer=el('div','voice-footer'),voiceNote=el('small');voiceNote.id='voiceNote';const manage=button('내 말투 만들기 · 저장',()=>openVoice());manage.id='manageVoice';const reset=button('기존 말투 사용',()=>setVoice(voiceChannel,null));reset.id='resetVoice';footer.append(voiceNote,manage,reset);home.append(heading,cards,footer);
 const optionHome=$('writingOptions');optionHome.querySelector('summary').after(home);
 // Keep all legacy controls available without presenting seventeen choices first.
 const legacy=el('details','voice-legacy'),legacyTitle=el('summary','','기본 말투 더 보기 · 기존 예시');legacy.append(legacyTitle);const toneWrap=$('tone').parentElement;legacy.append(toneWrap);const sampleWrap=$('style').closest('details');if(sampleWrap&&sampleWrap!==optionHome)legacy.append(sampleWrap);home.after(legacy);
 function renderVoices(){
  const chosen=draft.voice_styles?.[voiceChannel],lang=$('language').value;cards.replaceChildren();channels.value=voiceChannel;
  Object.entries(presets).forEach(([key,item])=>{const card=button('',()=>setVoice(voiceChannel,defaultVoice(key)),'voice-card');card.dataset.voicePreset=key;card.setAttribute('aria-pressed',String(chosen?.preset===key));card.disabled=busy;card.append(el('strong','',item.label),el('span','',item[lang]||item.ko));cards.append(card);});
  voiceNote.textContent=label(voiceChannel)?'현재 · '+label(voiceChannel):'현재 · 기본 말투를 사용해요';reset.hidden=!chosen;[manage,reset,channels].forEach(n=>n.disabled=busy);
 }
 async function readStore(){try{store=await api('/api/voice-profiles');storeError='';return true;}catch(error){storeError=error.message;return false;}}
 async function openVoice(){
  if(busy)return;await readStore();if(busy||$('modal').open)return;
  const channel=voiceChannel,initial=clone(draft.voice_styles?.[channel]||store.profiles[channel]||defaultVoice('warm'));const box=modal(platformInfo[channel].label+' · 내 말투');$('modal').dataset.view='voice';
  box.append(el('p','hint','좋아하는 문장 리듬만 참고해요. 예시 속 장소·경험·신상은 새 글에 가져오지 않아요.'));
  const fields={};const field=(name,title,type,max)=>{const wrap=el('label','voice-field',title),input=el(type==='textarea'?'textarea':type==='select'?'select':'input');input.id='voice-'+name;if(max)input.maxLength=max;fields[name]=input;wrap.append(input);box.append(wrap);return input;};
  field('name','말투 이름 · 선택','input',30).value=initial.name;
  const choose=(name,title,values)=>{const input=field(name,title,'select');Object.entries(values).forEach(([value,name])=>{const o=el('option','',name);o.value=value;input.append(o);});input.value=initial[name];};
  choose('preset','기본 분위기',Object.fromEntries(Object.entries(presets).map(([k,v])=>[k,v.label])));choose('formality','한국어 높임말',{auto:'채널에 맞게',polite:'편안한 존댓말',casual:'친근한 반말'});choose('emoji','이모지',{none:'사용하지 않기',light:'가끔, 자연스럽게',expressive:'조금 더 생기 있게'});choose('sentence','문장 길이',{short:'짧고 가볍게',balanced:'자연스러운 길이'});
  const preferenceGrid=el('div','voice-preferences');for(const key of ['preset','formality','emoji','sentence'])preferenceGrid.append(fields[key].parentElement);box.append(preferenceGrid);
  field('avoid','피하고 싶은 표현 · 쉼표로 구분','input',600).value=initial.avoid;
  const sample=field('sample','내가 쓴 글 예시 · 선택','textarea',2000);sample.rows=5;sample.value=initial.sample;sample.placeholder='마음에 드는 내 글 일부를 붙여넣어 주세요.';
  const note=el('p','writing-feedback');note.setAttribute('role','status');if(storeError)note.textContent=storeError;
  const analyze=button('예시에서 말투 살펴보기',async()=>{analyze.disabled=true;try{const result=await api('/api/voice/analyze',{sample:sample.value});for(const key of ['formality','sentence','emoji'])fields[key].value=result.profile[key];note.textContent=result.notes.join(' ');}catch(error){note.textContent=error.message;}finally{analyze.disabled=false;}},'secondary');analyze.id='analyzeVoice';box.append(analyze,note);
  const rememberWrap=el('label','voice-remember'),remember=el('input');remember.type='checkbox';remember.checked=true;remember.id='rememberVoice';rememberWrap.append(remember,document.createTextNode('다음 새 글에도 이 채널의 말투로 사용하기'));box.append(rememberWrap);
  const actions=el('div','writing-actions');const use=button('이 말투 적용',async()=>{
   const profile=Object.fromEntries(Object.entries(fields).map(([k,n])=>[k,n.value]));use.disabled=true;
   try{if(remember.checked){if(storeError)throw Error('저장한 설정을 읽지 못했어요. 창을 다시 열어 확인하거나 ‘다음 새 글에도 사용’을 해제해 주세요.');store=await api('/api/voice-profiles',{channel,profile,revision:store.revision});}if(!$('modal').open||!box.isConnected)return;setVoice(channel,profile);$('modal').close();notify(remember.checked?'이 채널의 말투를 기억했어요. 새로 만드는 글부터 적용해요.':'이 글의 말투를 골랐어요. 새로 만드는 글부터 적용해요.');}
   catch(error){note.textContent=error.message;if(error.code==='voice_conflict')await readStore();}finally{use.disabled=false;}
  },'primary');use.id='useVoice';actions.append(button('취소',()=>$('modal').close(),'secondary'),use);box.append(actions);
 }
 const controls=$('editor').querySelector('.editor-controls');const titleButton=button('✦ 제목 추천',()=>openTarget({kind:'title'},'titles'));titleButton.id='suggestTitles';const snsButton=button('✦ 필요한 부분 다듬기',()=>{const n=$('body'),selected=n.selectionEnd>n.selectionStart;openTarget({kind:'body',start:selected?n.selectionStart:0,end:selected?n.selectionEnd:n.value.length});});snsButton.id='refineCaption';const undo=button('↶ 수정 전으로',()=>{
  const platform=activePlatform(),last=history[platform]?.at(-1);if(busy||!last)return;if(draft[contentKey()]!==last.after){notify('그 뒤에 글이 바뀌었어요. 현재 글을 보호하기 위해 되돌리지 않았어요.');return;}draft[contentKey()]=last.before;$('body').value=last.before;history[platform].pop();markDirty();renderTab();notify('부분 수정 전 글로 되돌렸어요.');
 });undo.id='undoTextEdit';controls.prepend(titleButton,snsButton,undo);
 function refresh(){titleButton.hidden=tab!=='blog';snsButton.hidden=tab==='blog';undo.hidden=tab==='blog'||!history[activePlatform()]?.length;[titleButton,snsButton,undo].forEach(n=>n.disabled=busy||!draft[contentKey()]?.trim());renderVoices();}
 function loaded(){if(loadedEpoch!==navigationEpoch){history={};loadedEpoch=navigationEpoch;}if(!draft.id&&!anyContent()&&!Object.keys(draft.voice_styles||{}).length)draft.voice_styles=clone(store.profiles);voiceChannel=activePlatform();refresh();updateOptionSummaries();}
 function requestFor(target,action='natural',hint=''){
  const platform=activePlatform(),doc=tab==='blog'?BlockWorkspace.ensure():null,requirements={};for(const key of [...campaignTextFields,...campaignNumberFields,'campaign_count_spaces','campaign_enabled'])requirements[key]=draft[key];
  const language=draft.platform_languages?.[platform]||draft.language||'ko';const facts=language==='en'?(draft.facts_translation_source===draft.facts?draft.facts_translation||'':''):draft.facts||'';
  return {platform,tone:draft.tone,protected_names:[draft.selected_place?.name,draft.campaign_enabled?draft.campaign_brand:''].filter(Boolean),protected_lines:platform==='instagram'?facts.split(/\n+/).map(v=>v.trim()).filter(Boolean):[],target:clone(target),action,hint,language:draft.platform_languages?.[platform]||draft.language||'ko',title:tab==='blog'?draft[titleKey()]||'':'',body:doc?'':draft[contentKey()]||'',document:doc?{version:1,blocks:clone(doc.blocks),source:doc.source,template:doc.template}:undefined,voice:draft.voice_styles?.[platform]||null,requirements,disclosure:draft.disclosure||'none',notes:(draft.facts||'').slice(0,2800)+'\n'+(draft.prompt||'').slice(0,1199)};
 }
 const signature=target=>JSON.stringify(requestFor(target));
 function openBlock(block,start,end){openTarget({kind:'block',id:block.id,start,end});}
 function openTarget(target,firstAction='natural'){
  if(busy||$('modal').open)return;sync();
  const platform=activePlatform(),epoch=navigationEpoch,base=requestFor(target),snap=signature(target);let original='';
  if(target.kind==='title')original=base.title;
  else if(target.kind==='body')original=base.body.slice(target.start,target.end);
  else{const b=base.document.blocks.find(b=>b.id===target.id);if(!b)return;original=(b.type==='photo'?b.caption:b.text).slice(target.start,target.end);}
  if(!original.trim()&&firstAction!=='titles')return notify('다듬을 글을 먼저 적어 주세요.');if([...original].length>2000)return notify('한 번에 2,000자까지 다듬을 수 있어요. 필요한 문장만 선택해 주세요.');
  const box=modal(firstAction==='titles'?'내 글에 어울리는 제목':'이 부분만, 더 내 글답게');$('modal').dataset.view='writing-refine';$('modal').dataset.editKind=target.kind;const s={alive:true,owned:false,sequence:0,valid:null,request:null};session=s;
  const active=()=>s.alive&&session===s&&$('modal').open&&box.isConnected;
  const current=()=>epoch===navigationEpoch&&platform===activePlatform()&&snap===signature(target);
  const cleanup=()=>{s.alive=false;delete $('modal').dataset.editKind;clearInterval(s.clock);clearTimeout(s.debounce);if(s.owned){s.owned=false;lock(false);}if(session===s)session=null;};$('modal').addEventListener('close',cleanup,{once:true});
  box.append(el('p','hint',platformInfo[platform].label+' · '+(label(platform)||'현재 말투')+' · 선택한 부분만 바꿔요. 사진과 다른 원고는 유지해요.'));
  const methods=el('div','refine-methods');methods.setAttribute('role','group');methods.setAttribute('aria-label','다듬는 방법');let action=firstAction;
  const names=firstAction==='titles'?{titles:'제목 3개 추천'}:{natural:'자연스럽게',shorten:'짧고 또렷하게',expand:'경험 보태기',my_voice:'내 말투로'};const methodButtons=[];
  Object.entries(names).forEach(([key,name])=>{const b=button(name,()=>{action=key;methodButtons.forEach(n=>n.setAttribute('aria-pressed',String(n===b)));hintWrap.hidden=key!=='expand';generate.textContent=s.request?'다른 제안 받기':key==='titles'?'제목 3개 추천받기':'수정 제안 받기';s.valid=null;++s.sequence;clearTimeout(s.debounce);s.request=null;candidate.disabled=true;apply.disabled=true;feedback.textContent='선택한 방법으로 새 제안을 받아 주세요.';},'refine-method');b.setAttribute('aria-pressed',String(action===key));methodButtons.push(b);methods.append(b);});box.append(methods);
  const hintWrap=el('label','voice-field','덧붙일 실제 경험 · 선택'),hint=el('textarea');hint.id='refineExperience';hint.maxLength=600;hint.rows=3;hint.placeholder='예) 창가에 앉았고 크림이 고소했어요. 직접 겪은 내용만 적어 주세요.';hintWrap.append(hint);hintWrap.hidden=action!=='expand';box.append(hintWrap);
  const progress=el('div','refine-progress');progress.hidden=true;progress.setAttribute('role','status');const spinner=el('span','refine-spinner'),message=el('span'),elapsed=el('small');progress.append(spinner,message,elapsed);box.append(progress);
  const comparison=el('div','refine-comparison'),before=el('section'),after=el('section');before.append(el('h3','','지금 글'),el('div','refine-original',original||'아직 제목이 없어요. 본문에서 어울리는 제목을 찾아요.'));after.append(el('h3','','수정 제안'));const choices=el('div','title-choices');choices.id='titleChoices';choices.hidden=true;const candidate=el('textarea');candidate.id='refineCandidate';candidate.rows=7;candidate.maxLength=4000;candidate.placeholder='제안을 받은 뒤 여기서 직접 고칠 수도 있어요.';candidate.disabled=true;candidate.setAttribute('aria-label','수정 제안 직접 고치기');after.append(choices,candidate);comparison.append(before,after);box.append(comparison);
  const diffDetails=el('details','refine-diff');diffDetails.hidden=true;diffDetails.append(el('summary','','달라진 표현 보기'));const diff=el('div');diff.id='refineDiff';diffDetails.append(diff);box.append(diffDetails);
  const feedback=el('div','writing-feedback');feedback.id='refineFeedback';feedback.setAttribute('role','status');box.append(feedback);
  const actions=el('div','writing-actions');const generate=button(action==='titles'?'제목 3개 추천받기':'수정 제안 받기',async()=>{
   if(!active()||busy)return;if(!current()){feedback.textContent='원고나 조건이 바뀌었어요. 창을 닫고 해당 부분을 다시 선택해 주세요.';return;}
   s.request={...clone(base),action,hint:hint.value};++s.sequence;clearTimeout(s.debounce);s.valid=null;apply.disabled=true;candidate.disabled=true;generate.disabled=true;methodButtons.forEach(n=>n.disabled=true);hint.disabled=true;choices.hidden=true;diffDetails.hidden=true;feedback.replaceChildren();progress.hidden=false;const started=Date.now();elapsed.textContent='0초';s.clock=setInterval(()=>elapsed.textContent=Math.floor((Date.now()-started)/1000)+'초',1000);message.textContent='선택한 부분을 준비하고 있어요.';s.owned=true;lock(true);
   try{
    const job=await api('/api/writing/refine',s.request);let result;
    for(let attempt=0;attempt<550;attempt++){
     if(!active())return;const state=await api('/api/jobs/'+encodeURIComponent(job.job));if(!active())return;message.textContent=state.message||'수정 제안을 기다리고 있어요.';
     if(state.state==='failed')throw Error(state.error||'제안을 만들지 못했어요. 원고는 그대로예요.');if(state.state==='done'){result=state.result;break;}await new Promise(resolve=>setTimeout(resolve,1200));
    }
    if(!result?.choices?.length)throw Error('결과를 확인하지 못했어요. 원고는 그대로예요.');
    if(!current())throw Error('원고나 조건이 바뀌어 제안을 적용하지 않았어요. 창을 닫고 다시 선택해 주세요.');
    candidate.disabled=false;choices.replaceChildren();choices.hidden=result.choices.length===1;
    const choose=item=>{candidate.value=item.text;void validateCandidate();choices.querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.value===item.text)));};
    result.choices.forEach((item,i)=>{const b=button('',()=>choose(item),'title-choice');b.dataset.value=item.text;b.append(el('small','','후보 '+(i+1)),el('span','',item.text));choices.append(b);});choose(result.choices[0]);generate.textContent='다른 제안 받기';
   }catch(error){if(active()){feedback.replaceChildren(el('p','refine-error',error.message));candidate.disabled=!candidate.value;}}
   finally{clearInterval(s.clock);if(s.owned){s.owned=false;lock(false);}if(active()){progress.hidden=true;generate.disabled=false;methodButtons.forEach(n=>n.disabled=false);hint.disabled=false;}}
  },'secondary');generate.id='requestRefine';
  const apply=button('이 부분에 적용',()=>{
   if(!active()||busy||!s.valid?.can_apply||s.valid.text!==candidate.value)return;if(!current()){s.valid=null;apply.disabled=true;feedback.textContent='원고나 조건이 달라졌어요. 현재 글을 보호하기 위해 적용하지 않았어요. 다시 열어 주세요.';return;}
   const value=candidate.value;
   if(target.kind==='block')BlockWorkspace.editor.mutate(doc=>{const b=doc.blocks.find(b=>b.id===target.id),field=b.type==='photo'?'caption':'text';b[field]=b[field].slice(0,target.start)+value+b[field].slice(target.end);},target.id);
   else if(target.kind==='title')BlockWorkspace.editor.mutate(()=>{$('title').value=value;draft[titleKey()]=value;});
   else{const before=draft[contentKey()],after=before.slice(0,target.start)+value+before.slice(target.end);history[platform]||=[];history[platform].push({before,after});if(history[platform].length>20)history[platform].shift();draft[contentKey()]=after;$('body').value=after;markDirty();renderTab();}
   if(preview)renderPreview();$('modal').close();refresh();notify('선택한 부분만 바꿨어요. ↶ 되돌리기로 복구할 수 있어요.');
  },'primary');apply.id='applyRefine';apply.disabled=true;actions.append(button('원문 유지 · 닫기',()=>$('modal').close(),'quiet'),generate,apply);box.append(actions);
  async function validateCandidate(){
   const seq=++s.sequence;s.valid=null;apply.disabled=true;if(!s.request)return;
   feedback.textContent='숫자와 글 조건을 확인하고 있어요.';diffDetails.hidden=true;
   try{const result=await api('/api/writing/validate',{...s.request,candidate:candidate.value});if(!active()||seq!==s.sequence)return;if(!current()){feedback.textContent='원고가 바뀌었어요. 창을 닫고 다시 선택해 주세요.';return;}s.valid=result;feedback.replaceChildren();result.errors.forEach(text=>feedback.append(el('p','refine-error','확인 필요 · '+text)));result.warnings.forEach(text=>feedback.append(el('p','refine-warning',text)));apply.disabled=!result.can_apply;renderDiff(original,candidate.value,diff);diffDetails.hidden=false;}
   catch(error){if(active()&&seq===s.sequence)feedback.textContent=error.message;}
  }
  candidate.addEventListener('input',()=>{++s.sequence;s.valid=null;apply.disabled=true;clearTimeout(s.debounce);s.debounce=setTimeout(validateCandidate,300);});
 }
 function renderDiff(before,after,host){
  // Bounded token LCS preserves whitespace and emoji without interpreting HTML.
  host.replaceChildren();const a=before.match(/\s+|[^\s]+/gu)||[],b=after.match(/\s+|[^\s]+/gu)||[];
  if(a.length>220||b.length>220){host.append(el('p','',after));return;}
  const dp=Array.from({length:a.length+1},()=>new Uint16Array(b.length+1));for(let i=a.length-1;i>=0;i--)for(let j=b.length-1;j>=0;j--)dp[i][j]=a[i]===b[j]?1+dp[i+1][j+1]:Math.max(dp[i+1][j],dp[i][j+1]);
  let i=0,j=0;while(i<a.length||j<b.length){if(i<a.length&&j<b.length&&a[i]===b[j]){host.append(document.createTextNode(a[i]));i++;j++;}else if(j<b.length&&(i===a.length||dp[i][j+1]>=dp[i+1][j]))host.append(el('ins','',b[j++]));else host.append(el('del','',a[i++]));}
 }
 window.WritingUI={openBlock,openTarget,label,refresh,loaded,lock:()=>refresh()};
 $('language').addEventListener('change',renderVoices);refresh();
 const initialEpoch=navigationEpoch;void readStore().then(ok=>{if(ok&&initialEpoch===navigationEpoch&&!draft.id&&!anyContent()&&!dirty&&!Object.keys(draft.voice_styles||{}).length){draft.voice_styles=clone(store.profiles);renderVoices();updateOptionSummaries();}});
})();
