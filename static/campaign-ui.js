"use strict";
(function(){
 let timer,sequence=0,signature='',last=null,parsed=null,parseEpoch=0,pending=false,waiting=false;
 const labels={campaign_brand:'업체·제품 이름',campaign_benefit:'제공 내역',title_keywords:'제목 키워드',body_keywords:'본문 키워드',required_phrases:'필수 문구',hashtags:'블로그 태그',campaign_forbidden:'사용하지 않을 표현',keyword_min_count:'본문 키워드 횟수',campaign_min_chars:'본문 최소 분량',campaign_max_chars:'본문 최대 분량',campaign_min_photos:'최소 사진 수',campaign_count_spaces:'공백 계산'};
 const node=(tag,className,text)=>{const n=document.createElement(tag);if(className)n.className=className;if(text!==undefined)n.textContent=text;return n;};
 function button(text,action,kind='quiet'){const b=node('button',kind,text);b.type='button';b.disabled=busy;b.onclick=run(action);return b;}
 function payload(platform=activePlatform(),future=false){
  const values=Object.fromEntries(campaignTextFields.map(id=>[id,$(id).value]));for(const id of campaignNumberFields)values[id]=Number($(id).value);
  const body=$('body').value,title=$('title').value;return {...values,campaign_enabled:$('campaignEnabled').checked,campaign_count_spaces:$('campaign_count_spaces').checked,disclosure:$('disclosure').value,prompt:$('prompt').value,facts:$('facts').value,language:future?$('language').value:draft.platform_languages?.[platform]||$('language').value,title,blog:body,tistory:body,tistory_title:title,images:window.BlockWorkspace?.photos()||draft.images,platform:platform==='tistory'?'tistory':'naver',campaign_manual_checks:draft.campaign_manual_checks||[],campaign_manual_state:draft.campaign_manual_state||{},campaign_brief_review:draft.campaign_brief_review||{},campaign_experience:draft.campaign_experience||{}};
 }
 function format(field,value){if(field==='campaign_count_spaces')return value?'공백 포함':'공백 제외';if(typeof value==='number')return value.toLocaleString()+(field.includes('chars')?'자':field.includes('photos')?'장':field.includes('count')?'회':'');return String(value);}
 function source(quote){
  goWorkspace(1);$('campaignPanel').open=true;const value=$('campaign_brief').value,at=value.indexOf(quote);$('campaign_brief').focus();if(at>=0)$('campaign_brief').setSelectionRange(at,at+quote.length);$('campaign_brief').scrollIntoView({block:'center',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});if(at<0)notify('안내문이 바뀌어 이전 근거를 찾지 못했어요. 다시 정리해 주세요.');
 }
 function evidence(item){
  const field=item.field,current=$(field)?.value;const normalized=value=>/[가-힣]/.test(value)?String(value).replace(/\s/g,'').toLowerCase():String(value).replace(/\s+/g,' ').trim().toLowerCase();
  return draft.campaign_brief_review?.sources?.find(source=>{
   if(source.field!==field)return false;
   if(item.needle){const values=['title_keywords','body_keywords','campaign_forbidden','required_phrases','hashtags'].includes(field)?split(String(source.value),field):[String(source.value)];return values.some(value=>normalized(value)===normalized(item.needle));}
   return typeof source.value==='number'?Number(current)===source.value:typeof source.value==='boolean'?$('campaign_count_spaces').checked===source.value:String(current)===String(source.value);
  });
 }
 function conditions(){
  const box=$('confirmedConditions');box.replaceChildren();if(!$('campaignEnabled').checked){box.hidden=true;return;}
  const items=[];for(const [field,label] of Object.entries(labels)){const value=field==='campaign_count_spaces'?$('campaign_count_spaces').checked:campaignNumberFields.includes(field)?Number($(field).value):$(field).value.trim();if(field==='keyword_min_count'&&!$('body_keywords').value.trim()||field==='campaign_count_spaces'&&!Number($('campaign_min_chars').value)&&!Number($('campaign_max_chars').value)||!value&&field!=='campaign_count_spaces')continue;items.push([label,format(field,value)]);}
  box.hidden=!items.length&&!draft.campaign_manual_checks?.length;if(box.hidden)return;
  const head=node('div','confirmed-heading');head.append(node('strong','','이번 글에 반영할 조건'),button('수정',()=>{goWorkspace(1);$('campaignPanel').open=true;$('missionDetails').open=true;$('missionDetails').scrollIntoView({block:'center'});}));box.append(head);
  const chips=node('div','condition-chips');for(const [label,value] of items){const chip=node('span','');chip.append(node('small','',label),node('span','',value.length>90?value.slice(0,90)+'…':value));chip.title=value;chips.append(chip);}box.append(chips);
  if(draft.campaign_manual_checks?.length)box.append(node('p','hint','직접 확인할 항목 '+draft.campaign_manual_checks.length+'개도 함께 보관해요.'));
 }
 function drawPreflight(result){
  document.querySelectorAll('[data-requirement-invalid]').forEach(field=>{delete field.dataset.requirementInvalid;if(!field.dataset.missionInvalid)field.removeAttribute('aria-invalid');const ids=(field.getAttribute('aria-describedby')||'').split(' ').filter(id=>id&&!id.startsWith('requirement-'));if(ids.length)field.setAttribute('aria-describedby',ids.join(' '));else field.removeAttribute('aria-describedby');});const box=$('campaignPreflight');box.replaceChildren();box.hidden=!result.preflight.length;
  for(const item of result.preflight){const line=node('div','requirement-message '+item.level);line.id='requirement-'+item.code+'-'+item.field;line.append(node('strong','',item.level==='error'?'먼저 정리해 주세요':'한 번 확인해 주세요'),node('p','',item.message));for(const id of [item.field,...(item.related_fields||[])])if($(id)){if(item.level==='error'){const field=$(id);field.dataset.requirementInvalid='true';field.setAttribute('aria-invalid','true');field.setAttribute('aria-describedby',[field.getAttribute('aria-describedby'),line.id].filter(Boolean).join(' '));}line.append(button(labels[id]||'확인하기',()=>focusIssue({field:id})));}box.append(line);}
 }
 function showPhoto(){
  setWorkflow(2);preview=false;$('preview').hidden=true;$('editFields').hidden=false;$('previewToggle').textContent='미리보기';window.BlockWorkspace.refresh();window.BlockWorkspace.editor.choosePhoto();
 }
 function contentAction(item){
  if(item.field==='campaign_min_chars')return experience();
  if(item.field==='campaign_min_photos')return showPhoto();
  if(item.field==='disclosure')return showDisclosureHelp();
  if(item.field==='hashtags')return saveDraft().then(()=>{notify('태그를 반영하고 저장했어요.');schedule(true);});
  if(item.target)focusIssue(item,true);else focusIssue(item);
 }
 function draw(result,epoch){
  last=result;drawPreflight(result);conditions();if(issuesVisible&&result.quality_checks)showQuality(result.quality_checks);const box=$('campaignChecklist');box.replaceChildren();box.hidden=!(tab==='blog'&&$('campaignEnabled').checked);if(box.hidden)return;
  const failed=result.checks.filter(x=>!x.passed),pendingManual=result.manual.filter(x=>!x.checked);const summary=node('summary','');summary.append(node('strong','',result.preflight.some(x=>x.level==='error')?'조건끼리 맞지 않는 부분이 있어요':failed.length?'자동 확인 · '+failed.length+'개 수정 필요':'자동 확인 · '+result.checks.length+'개 충족'),node('span','mission-summary-count','직접 확인 '+pendingManual.length+'개 남음'));box.append(summary);
  if(workflow.stage===3&&(failed.length||pendingManual.length))box.open=true;
  const automatic=node('div','mission-check-group');automatic.append(node('h3','','글에서 확인한 조건'));
  for(const item of result.checks){const row=node('div','mission-check-row '+(item.passed?'is-met':'is-missing'));const text=node('div','');text.append(node('strong','',(item.passed?'✓ ':'○ ')+item.label));if(!item.passed)text.append(node('p','',item.detail));row.append(text);
   const actions=node('div','mission-row-actions');if(!item.passed){actions.append(button(item.field==='campaign_min_chars'?'경험 더 적기':item.field==='campaign_min_photos'?'사진 추가':item.field==='hashtags'?'태그 반영·저장':item.field==='disclosure'?'제공 내용 선택':'원고 고치기',()=>contentAction(item)));if(item.field!=='disclosure')actions.append(button('조건 수정',()=>focusIssue(item)));}
   else if(item.field!=='campaign_forbidden'&&item.needle&&item.target)actions.append(button('위치 보기',()=>focusIssue(item,true)));
   const origin=evidence(item);if(origin)actions.append(button(origin.edited?'원문·수정한 값':'원문 보기',()=>{source(origin.quote);if(origin.edited)notify('원문과 다르게 직접 수정해서 반영한 조건이에요.');}));row.append(actions);automatic.append(row);
  }
  if(!result.checks.length)automatic.append(node('p','hint','조건이 서로 맞는지 먼저 정리한 뒤 원고를 확인해요.'));box.append(automatic);
  if(result.manual.length){const manual=node('div','mission-check-group');manual.append(node('h3','','직접 확인할 조건'),node('p','hint','지도·배너·링크는 블로그로 옮긴 뒤에도 추가할 수 있어요. 이 항목이 남아 있어도 옮길 수 있어요.'));
   for(const item of result.manual){const row=node('div','manual-check-row'),label=node('label',''),input=document.createElement('input');input.type='checkbox';input.checked=item.checked;input.disabled=busy;input.setAttribute('aria-label',item.text+' 직접 확인');input.onchange=()=>{
     if(epoch!==editEpoch){notify('원고가 바뀌었어요. 다시 확인한 뒤 선택해 주세요.');schedule(true);return;}
     draft.campaign_manual_state ||= {};const states=draft.campaign_manual_state[activePlatform()] ||= {};if(input.checked)states[item.id]=result.fingerprint;else delete states[item.id];markDirty();schedule(true);
    };label.append(input,node('span','',item.text));row.append(label);const actions=node('div','mission-row-actions');if(item.quote)actions.append(button('원문 보기',()=>source(item.quote)));actions.append(button('항목 빼기',()=>{draft.campaign_manual_checks=draft.campaign_manual_checks.filter(x=>x.id!==item.id);for(const state of Object.values(draft.campaign_manual_state||{}))delete state[item.id];markDirty();schedule(true);}));row.append(actions);manual.append(row);}
   manual.append(node('small','hint','원고나 조건을 바꾸면 직접 확인한 항목을 다시 확인해요.'));box.append(manual);
  }
  box.append(node('p','mission-honest-note','확인해서 반영한 조건만 검사해요. 실제 경험·업체 안내·최종 게시 화면도 함께 살펴 주세요.'));
 }
 async function check(force=false){
  if(tab!=='blog'||!$('campaignEnabled').checked){$('campaignChecklist').hidden=true;conditions();return;}
  const data=payload(),key=JSON.stringify(data)+'|'+workflow.stage;if(!force&&key===signature)return;signature=key;const seq=++sequence,epoch=editEpoch,nav=navigationEpoch,platform=activePlatform();
  try{const result=await api('/api/campaign/check',data);if(seq!==sequence||epoch!==editEpoch||nav!==navigationEpoch||platform!==activePlatform())return;if(key!==JSON.stringify(payload())+'|'+workflow.stage){signature='';schedule(true);return;}draw(result,epoch);}
  catch(e){signature='';const box=$('campaignPreflight');box.hidden=false;box.replaceChildren(node('p','',e.message),button('다시 확인',()=>check(true)));}
 }
 function schedule(force=false){
  conditions();if(parsed&&parsed.source!==$('campaign_brief').value){parsed=null;pending=false;$('campaignSuggestions').hidden=true;$('campaignParseStatus').textContent='안내문을 바꿨어요. 다시 정리해 주세요.';}
  clearTimeout(timer);if(!busy)timer=setTimeout(()=>check(force),200);
 }
 function split(value,field){return field==='hashtags'?value.split(/[#,\s]+/).filter(Boolean):value.split(field==='required_phrases'?/\n+/:/[,\n]+/).map(x=>x.trim()).filter(Boolean);}
 function unique(values){const seen=new Set();return values.filter(value=>{const key=(/[가-힣]/.test(value)?value.toLowerCase().replace(/\s/g,''):value.toLowerCase().replace(/\s+/g,' '));if(seen.has(key))return false;seen.add(key);return true;});}
 async function parse(){
  if(busy||waiting)return;const sourceText=$('campaign_brief').value,nav=navigationEpoch,epoch=++parseEpoch;waiting=true;$('parseCampaign').disabled=true;$('campaignParseStatus').textContent='안내문에서 조건을 정리하고 있어요.';
  try{const result=await api('/api/campaign/parse',{brief:sourceText});if(epoch!==parseEpoch||nav!==navigationEpoch||sourceText!==$('campaign_brief').value){$('campaignParseStatus').textContent='안내문이 바뀌었어요. 다시 정리해 주세요.';return;}parsed={...result,source:sourceText};pending=true;drawSuggestions();$('campaignParseStatus').textContent=result.suggestions.length+'개 항목을 찾았어요. '+(result.truncated?result.notice:'원문과 비교하고 반영할 항목을 골라 주세요.');}
  catch(e){$('campaignParseStatus').textContent=e.message;}finally{if(epoch===parseEpoch){waiting=false;$('parseCampaign').disabled=busy;}}
 }
 function drawSuggestions(){
  const proposalHash=parsed.brief_hash;const box=$('campaignSuggestions');box.hidden=false;box.replaceChildren();box.append(node('h3','','원문을 보며 조건을 골라 주세요'),node('p','hint','자동 확인할 조건과 직접 확인할 메모를 나눴어요. 값을 고쳐서 반영할 수도 있어요.'));
  const rows=[];const controls=node('div','suggestion-controls');controls.append(button('모두 선택',()=>{rows.forEach(row=>row.check.checked=true);update();}));const mode=document.createElement('select');mode.id='campaignApplyMode';mode.setAttribute('aria-label','조건 반영 방법');for(const [value,text] of [['merge','기존 조건에 더하기'],['replace','선택한 항목만 바꾸기']]){const option=node('option','',text);option.value=value;mode.append(option);}controls.append(mode);box.append(controls);const list=node('div','campaign-suggestion-list');list.id='campaignSuggestionList';list.tabIndex=0;list.setAttribute('role','region');list.setAttribute('aria-label','찾은 조건 목록');box.append(list);
  for(const proposal of parsed.suggestions){const row=node('article','campaign-suggestion '+proposal.kind),label=node('label','suggestion-label'),checkBox=document.createElement('input');checkBox.type='checkbox';checkBox.setAttribute('aria-label',proposal.label+' 반영');label.append(checkBox,node('strong','',proposal.label),node('small','',proposal.kind==='manual'?'직접 확인':'글에서 자동 확인'));row.append(label);
   let input;if(proposal.kind!=='manual'&&proposal.field==='campaign_count_spaces'){input=document.createElement('select');for(const [value,text] of [['false','공백 제외'],['true','공백 포함']]){const option=node('option','',text);option.value=value;input.append(option);}input.value=String(proposal.value);}else{input=document.createElement('input');input.type=proposal.kind!=='manual'&&typeof proposal.value==='number'?'number':'text';input.value=String(proposal.value);input.maxLength=proposal.kind==='manual'?600:2000;if(input.type==='number'){input.min=proposal.field==='keyword_min_count'?'1':'0';input.max=proposal.field.includes('chars')?'5000':proposal.field==='keyword_min_count'?'5':'10';}}
   input.setAttribute('aria-label',proposal.label+' 값');row.append(input);const proof=node('details','suggestion-evidence');proof.append(node('summary','',proposal.kind==='manual'?'원문·확인할 이유':'원문 보기'));if(proposal.reason)proof.append(node('p','hint',proposal.reason));proof.append(node('blockquote','',proposal.quote),button('안내문에서 보기',()=>source(proposal.quote)));row.append(proof);list.append(row);rows.push({proposal,check:checkBox,input});checkBox.onchange=update;
  }
  const error=node('p','field-error');error.id='campaignApplyError';error.setAttribute('role','alert');box.append(error);const apply=button('선택한 조건 반영',()=>{
   if(!parsed||parsed.brief_hash!==proposalHash||parsed.source!==$('campaign_brief').value){$('campaignParseStatus').textContent='안내문이 바뀌었어요. 다시 정리해 주세요.';return;}const selected=rows.filter(x=>x.check.checked);if(!selected.length)return;const next={},numeric={};
   for(const row of selected){const {proposal,input}=row;if(proposal.kind==='manual')continue;const value=proposal.field==='campaign_count_spaces'?input.value==='true':typeof proposal.value==='number'?Number(input.value):input.value.trim();if(typeof value==='number'&&(!Number.isInteger(value)||!input.checkValidity())){error.textContent='숫자 조건의 범위를 확인해 주세요.';input.focus();return;}if(typeof value==='number'||typeof value==='boolean'){if(proposal.field in numeric&&numeric[proposal.field]!==value){error.textContent=proposal.label+' 조건이 서로 달라요. 맞는 항목 하나만 선택해 주세요.';return;}numeric[proposal.field]=value;}next[proposal.field] ||= [];next[proposal.field].push(value);}
   let manual=[...(draft.campaign_manual_checks||[])];for(const row of selected.filter(x=>x.proposal.kind==='manual')){const text=(row.proposal.field?row.proposal.label+' · ':'')+(row.proposal.field&&typeof row.proposal.value==='number'&&/^\d+$/.test(row.input.value)?format(row.proposal.field,Number(row.input.value))+' · 지원 범위 확인':row.input.value.trim());if(text.length>600){error.textContent='직접 확인할 항목은 한 줄에 600자 이내로 적어 주세요.';row.input.focus();return;}if(text&&!manual.some(x=>x.id===row.proposal.id||x.text===text))manual.push({id:row.proposal.id,text,quote:row.proposal.quote});}if(manual.length>20){error.textContent='직접 확인할 항목은 20개까지 보관해요. 항목을 줄여 주세요.';return;}
   for(const [field,values] of Object.entries(next)){const current=$(field);if(typeof values[0]==='boolean')current.checked=values[0];else if(typeof values[0]==='number'||['campaign_brand','campaign_benefit'].includes(field))current.value=values[values.length-1];else{const old=mode.value==='merge'?split(current.value,field):[];const merged=unique([...old,...values.flatMap(v=>split(v,field))]);current.value=field==='hashtags'?merged.map(x=>'#'+x).join(' '):merged.join(field==='required_phrases'?'\n':', ');}}
   draft.campaign_manual_checks=manual;const oldSources=(draft.campaign_brief_review?.sources||[]).filter(s=>mode.value==='merge'||!(s.field in next));draft.campaign_brief_review={hash:parsed.brief_hash,sources:[...oldSources,...selected.filter(x=>x.proposal.kind!=='manual').map(row=>({field:row.proposal.field,value:row.proposal.field==='campaign_count_spaces'?row.input.value==='true':typeof row.proposal.value==='number'?Number(row.input.value):row.input.value.trim(),quote:row.proposal.quote,edited:String(row.proposal.field==='campaign_count_spaces'?row.input.value==='true':row.input.value.trim())!==String(row.proposal.value)}))].slice(-60)};
   pending=false;box.hidden=true;sync();markDirty();renderTagChips();renderCampaign();schedule(true);$('campaignParseStatus').textContent='선택한 조건을 반영했어요. 아래 요약에서 확인해 주세요.';
  },'primary');apply.id='applyCampaignSuggestions';box.append(apply);
  box.scrollIntoView({block:'start',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});
  function update(){const count=rows.filter(x=>x.check.checked).length;apply.disabled=busy||!count;apply.textContent=count?'선택한 '+count+'개 조건 반영':'반영할 항목을 골라 주세요';}update();
  if(!rows.length)box.append(node('p','hint','확실하게 나눌 조건을 찾지 못했어요. 아래에서 직접 적어 주세요.'));
 }
 async function confirmManual(){if(busy)return;const epoch=editEpoch,nav=navigationEpoch,result=await api('/api/campaign/check',payload());if(epoch!==editEpoch||nav!==navigationEpoch){$('campaignParseStatus').textContent='입력이 바뀌었어요. 현재 조건을 다시 확인해 주세요.';return;}draft.campaign_brief_review={hash:result.brief_hash,sources:[]};pending=false;parsed=null;$('campaignSuggestions').hidden=true;markDirty();schedule(true);$('campaignParseStatus').textContent='직접 입력한 조건을 기준으로 확인하고 작성해요.';}
 async function beforeGenerate(platforms){
  if(!$('campaignEnabled').checked||!platforms.some(p=>['naver','tistory'].includes(p)))return true;
  if(waiting||pending){goWorkspace(1);$('campaignPanel').open=true;$('campaignParseStatus').textContent='정리한 조건을 반영하거나 직접 입력한 조건을 확인한 뒤 만들어 주세요.';return false;}
  const platform=platforms.find(p=>['naver','tistory'].includes(p)),epoch=editEpoch,nav=navigationEpoch,data=payload(platform,true),result=await api('/api/campaign/check',data);if(epoch!==editEpoch||nav!==navigationEpoch){notify('입력이 바뀌었어요. 현재 조건으로 다시 눌러 주세요.');return false;}
  const errors=result.preflight.filter(x=>x.level==='error');drawPreflight(result);if(errors.length){goWorkspace(1);$('campaignPanel').open=true;focusIssue(errors[0]);notify('조건끼리 맞지 않는 부분을 먼저 정리해 주세요.');return false;}return true;
 }
 function experience(){
  const box=modal('조금 더 들려주실래요?');para(box,'직접 겪은 내용만 적어 주세요. 모르는 항목은 비워 두어도 괜찮아요.');const descriptions={process:'주문·방문·사용 과정',good:'좋았던 점과 구체적인 이유',caution:'아쉬운 점이나 알아둘 점'};
  for(const [key,text] of Object.entries(descriptions)){const label=node('label','field-label',text),input=document.createElement('textarea');input.id='experience-'+key;input.maxLength=600;input.rows=3;input.value=draft.campaign_experience?.[key]||'';label.htmlFor=input.id;input.oninput=()=>{draft.campaign_experience ||= {};draft.campaign_experience[key]=input.value;markDirty();};box.append(label,input);}
  const error=node('p','field-error');error.setAttribute('role','alert');box.append(error);box.append(button('경험 메모에 담기',()=>{const notes=Object.entries(descriptions).flatMap(([key,label])=>{const value=$('experience-'+key).value.trim();return value?[label+': '+value]:[];});if(!notes.length){error.textContent='기억나는 내용을 한 항목만 적어 주세요.';return;}const current=$('facts').value;const addition=notes.filter(x=>!current.includes(x)).join('\n');const next=current+(current&&addition?'\n':'')+addition;if(next.length>4000){error.textContent='추가 메모가 길어요. 기존 메모와 합쳐 4,000자 이내로 정리해 주세요.';return;}$('facts').value=next;sync();markDirty();$('modal').close();focusIssue({field:'facts'});notify('실제 경험을 메모에 담았어요. 원고의 분량 보완을 누르면 반영해요.');},'primary'));
 }
 function loaded(){++sequence;++parseEpoch;waiting=false;pending=false;parsed=null;signature='';last=null;$('campaignSuggestions').hidden=true;$('campaignParseStatus').textContent='원문과 비교한 뒤 선택한 항목만 반영해요.';schedule(true);}
 function lock(value){document.querySelectorAll('#campaignSuggestions button,#campaignSuggestions input,#campaignSuggestions select,#campaignChecklist button,#campaignChecklist input,#confirmedConditions button,#campaignPreflight button').forEach(n=>n.disabled=value);for(const id of ['parseCampaign','confirmCampaignManual','applyCampaignSuggestions'])if($(id))$(id).disabled=value||id==='parseCampaign'&&waiting;if(!value){if($('applyCampaignSuggestions'))$('applyCampaignSuggestions').disabled=!$('campaignSuggestions').querySelector('input[type=checkbox]:checked');schedule(true);}}
 $('parseCampaign').onclick=run(parse);$('confirmCampaignManual').onclick=run(confirmManual);
 document.addEventListener('input',()=>schedule());document.addEventListener('change',()=>schedule());
 window.CampaignUI={schedule,beforeGenerate,experience,loaded,lock,openChecks:async()=>{const platform=activePlatform(),nav=navigationEpoch;await check(true);if(platform!==activePlatform()||nav!==navigationEpoch)return;$("campaignChecklist").open=true;$("campaignChecklist").scrollIntoView({block:"center",behavior:matchMedia("(prefers-reduced-motion: reduce)").matches?"auto":"smooth"});}};loaded();
})();
