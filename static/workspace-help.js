/* Optional, isolated examples and actionable recovery. No sample enters a real manuscript. */
(() => {
 'use strict';
 const el=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};
 const button=(id,text,fn,cls='secondary')=>{const b=el('button',cls,text);b.type='button';if(id)b.id=id;b.onclick=fn;return b;};
 const help=button('workspaceHelp','도움말',()=>open(),'quiet');$('themeToggle').before(help);
 const sample=button('tryWorkspace','예시로 사용법 보기',()=>demo(),'text-button');$('preparationAside').append(sample);
 const notice=el('section','workspace-recovery');notice.id='connectionRecovery';notice.hidden=true;notice.setAttribute('aria-label','앱 연결 확인');$('workflow').before(notice);
 let errorContext=null,checking=false;
 const text=()=>{sync();return (tab==='blog'?(draft[titleKey()]||'')+'\n\n':'')+(draft[contentKey()]||'').replace(/\[\[photo:\d+\]\]/g,'').trim();};
 function download(value=text()){
  if(!value.trim())return notify('아직 이 채널에 작성한 글이 없어요. 글을 만든 뒤 파일로 받을 수 있어요.');
  const blob=new Blob([value],{type:'text/plain;charset=utf-8'}),url=URL.createObjectURL(blob),link=el('a');link.href=url;link.download='Mellow-'+activePlatform()+'-'+new Date().toISOString().slice(0,10)+'.txt';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);notify('현재 채널의 글을 텍스트 파일로 내려받았어요. 사진은 포함되지 않아요.');
 }
 async function copyText(value,success='내용을 복사했어요.'){
  try{await navigator.clipboard.writeText(value);notify(success);return true;}catch{
   const box=modal('직접 복사할 수 있어요');$('modal').dataset.view='manual-copy';box.append(el('p','','브라우저가 자동 복사를 허용하지 않았어요. 아래 내용을 선택한 뒤 Ctrl+C를 눌러 주세요. 휴대폰에서는 길게 눌러 복사해 주세요.'));
   const area=el('textarea','manual-copy-text');area.id='manualCopyText';area.readOnly=true;area.rows=10;area.value=value;area.setAttribute('aria-label','복사할 내용');box.append(area,button('selectManualCopy','전체 선택',()=>{area.focus();area.select();}),button('downloadCopyText','텍스트 파일로 받기',()=>download(value)));area.focus();area.select();return false;
  }
 }
 function diagnostic(){return JSON.stringify({version:1,stage:workflow.stage,platform:activePlatform(),busy,unsaved:dirty,temporary_copy:recoveryReady,photo_count:Array.isArray(draft.images)?draft.images.length:0,text_chars:typeof draft[contentKey()]==='string'?draft[contentKey()].length:0,connection_error:errorContext?.kind||null,pending_generation:!$('generationRecovery')?.hidden},null,2);}
 function apiError(path,kind){
  // Background previews/searches do not interrupt the user with a global error card.
  if(!/^\/api\/(status$|drafts(?:\/|$)|generate$|blog\/expand$|jobs\/|publish\/|naver\/|tistory\/)/.test(path))return;
  errorContext={kind,publishing:/\/(publish|naver|tistory)\//.test(path)};renderError();
 }
 function renderError(){
  notice.hidden=!errorContext;if(!errorContext)return;notice.replaceChildren();const copy=el('div');copy.append(el('strong','','앱과의 연결을 확인해 주세요'),el('p','',errorContext.publishing?'발행·전달 결과가 불확실해요. 블로그 편집기나 계정에서 결과를 먼저 확인해 주세요. 중복 발행을 피하도록 자동으로 다시 시도하지 않아요.':'현재 탭의 내용을 유지하고 있어요. 앱 실행 상태를 확인한 뒤 연결 확인을 눌러 주세요. 글 만들기를 요청한 상태라면 이전 결과부터 확인해요.'));
  const actions=el('div','help-actions');actions.append(button('recheckConnection',checking?'확인 중…':'연결 확인',()=>void recheck()),button('downloadCurrentText','현재 글 텍스트로 받기',()=>download()),button('dismissConnectionRecovery','닫기',()=>{errorContext=null;renderError();},'quiet'));notice.append(copy,actions);notice.querySelector('#recheckConnection').disabled=checking;const feedback=el('p','help-feedback');feedback.id='connectionRecoveryStatus';feedback.setAttribute('role','status');notice.append(feedback);
 }
 async function recheck(){if(checking)return;checking=true;renderError();try{const result=await api('/api/status');status=result;if($('connectionRecoveryStatus'))$('connectionRecoveryStatus').textContent='앱에 다시 연결됐어요. 실패한 요청은 다시 보내지 않았어요. 이전 결과가 있다면 먼저 확인해 주세요.';}catch{if($('connectionRecoveryStatus'))$('connectionRecoveryStatus').textContent='아직 연결되지 않았어요. 앱 실행 창을 확인해 주세요. 현재 글은 파일로 받을 수 있어요.';}finally{checking=false;const b=$('recheckConnection');if(b){b.disabled=false;b.textContent='연결 확인';}}}
 function jump(step,id){if(busy)return;const after=()=>{if(busy)return;goWorkspace(step);const target=$(id);target?.closest('details')?.setAttribute('open','');target?.focus();target?.scrollIntoView({block:'center'});};$('modal').addEventListener('close',after,{once:true});$('modal').close();}
 function open(){
  const box=modal('Mellow, 이렇게 써 보세요');$('modal').dataset.view='workspace-help';const intro=el('div','help-intro');intro.append(el('span','help-eyebrow','A LITTLE GUIDE'),el('h3','','사진 한 장에서, 나다운 이야기까지'),el('p','','사진과 경험은 내가 담고, 글과 배치는 함께 다듬어요.'));box.append(intro);
  const steps=el('div','help-steps');for(const [n,title,body,id] of [[1,'이야기 준비','실제로 느낀 점을 메모하고 올릴 곳을 골라요. 체험단이라면 제공 내역·필수 조건도 담아 주세요.','prompt'],[2,'글 다듬기','채널별 원고를 읽고 사진 순서·말투·줄바꿈을 조절해요. 수정 제안은 비교 후 적용해요.','workspaceCrumb'],[3,'확인하고 옮기기','조건과 광고 표시를 확인해요. 블로그는 편집기 입력 후 직접 발행하고, SNS는 발행 확인을 거쳐요.','transferTitle']]){const card=el('section','help-step');card.append(el('span','',String(n).padStart(2,'0')),el('h3','',title),el('p','',body));const b=button('',title+' 화면 보기',()=>jump(n,id),'text-button');b.disabled=busy||(n>1&&!anyContent());card.append(b);steps.append(card);}box.append(steps);
  const actions=el('div','help-actions');actions.append(button('openHelpDemo','예시로 직접 둘러보기',()=>demo(),'primary'),button('downloadHelpText','현재 글 텍스트로 받기',()=>download()));box.append(actions);
  const faq=el('div','help-faq');for(const [title,body] of [['저장과 임시 보관은 어떻게 달라요?','글 보관하기는 내 글에 저장해요. 임시 보관은 이 브라우저에만 남는 복구용 사본이라 브라우저 기록 삭제 시 사라질 수 있어요. 중요한 글은 꼭 보관해 주세요.'],['새로고침하거나 연결이 끊겼어요','이전 결과 확인이 보이면 먼저 확인해 주세요. 앱이 계속 켜져 있었다면 기존 요청의 결과를 다시 확인할 수 있어요. 앱이 종료됐거나 시간이 지나면 결과를 찾지 못할 수 있어요.'],['옮겼는데 발행 기록이 없어요','네이버·티스토리 도우미는 편집기에 글을 입력해요. 마지막 발행은 블로그에서 직접 눌러 주세요. 편집기 입력 완료와 실제 발행은 구분해요.'],['체험단 조건에 걸려요','확인하고 옮기기 화면에 이유와 수정할 위치가 나와요. 실제 경험을 더 적거나 정확한 조건을 확인해 주세요. 허위 경험을 채워 넣지는 않아요.']]){const d=el('details'),s=el('summary','',title);d.append(s,el('p','',body));faq.append(d);}box.append(faq);
  const support=el('div','help-diagnostic');support.append(el('p','hint','문제가 계속되면 화면 상태만 복사해 전달해 주세요. 원고·사진·계정·키는 포함하지 않아요.'),button('copySafeDiagnostic','화면 상태 복사',()=>void copyText(diagnostic(),'원고와 계정 정보 없이 화면 상태를 복사했어요.')));box.append(support);
 }
 function demo(step=1,channel='naver',sampleText='창가에 앉아 따뜻한 라떼 한 잔.\n바쁜 하루 중 잠깐 쉬어 가기 좋았어요 ☕',swapped=false){
  const box=modal('체험 예시 · 실제 원고는 그대로예요');$('modal').dataset.view='workspace-demo';box.append(el('p','help-eyebrow','미리 준비한 예시 · 글 생성이나 발행 없이 둘러봐요'));
  const nav=el('div','help-demo-nav');for(const [n,label] of [[1,'1 준비'],[2,'2 다듬기'],[3,'3 옮기기']]){const b=button('',label,()=>demo(n,channel,sampleText,swapped),'quiet');b.setAttribute('aria-pressed',String(n===step));nav.append(b);}box.append(nav);
  if(step===1){box.append(el('h3','','짧은 메모면 충분해요'),el('p','demo-memo','주말에 카페에 다녀왔어. 창가 자리가 편했고 라떼는 고소했어. 친구에게 말하듯 써 줘.'),el('p','','올릴 곳을 고르면 그곳에 맞는 글만 만들어요. 아래 예시는 미리 준비한 글이에요.'),button('demoNext','예시 글 다듬어 보기',()=>demo(2,channel,sampleText,swapped),'primary'));}
  if(step===2){const channels=el('div','help-demo-nav');for(const p of ['naver','instagram','threads']){const b=button('',platformInfo[p].label,()=>demo(2,p,sampleText,swapped),'quiet');b.setAttribute('aria-pressed',String(p===channel));channels.append(b);}box.append(channels);const preview=el('section','demo-preview');preview.dataset.channel=channel;const photos=el('div','demo-photos');for(const [icon,label] of (swapped?[['☕','고소한 한 잔'],['✿','햇살 좋은 자리']]:[['✿','햇살 좋은 자리'],['☕','고소한 한 잔']])){const art=el('div','demo-photo');art.append(el('span','',icon),el('small','',label));photos.append(art);}const field=el('textarea');field.id='demoBody';field.rows=4;field.setAttribute('aria-label','예시 원고 수정');field.value=channel==='threads'?'스친들, 쉬고 싶을 때 어디 가?\n난 오늘 창가에서 라떼 한 잔 ☕':sampleText;field.oninput=()=>{sampleText=field.value;};preview.append(el('h3','',channel==='naver'?'라떼 한 잔, 느리게 보낸 오후':'오늘의 작은 쉼 ☕'),photos,field);box.append(preview,button('demoSwapPhotos','예시 사진 순서 바꾸기',()=>demo(2,channel,sampleText,!swapped)),button('demoTransfer','마지막 단계 보기',()=>demo(3,channel,sampleText,swapped),'primary'));}
  if(step===3){box.append(el('h3','','원고를 확인한 뒤, 내 채널로'),el('p','',channel==='naver'?'블로그 편집기에 글과 사진을 넣고, 최종 발행은 블로그에서 직접 눌러요.':'계정과 원고를 확인한 뒤 발행해요. 진행 결과가 불확실하면 계정에서 중복 여부를 먼저 확인해요.'),el('p','demo-success','✓ 여기까지는 체험 예시예요. 실제 원고나 계정은 바뀌지 않았어요.'),button('demoFinish','내 이야기로 돌아가기',()=>$('modal').close(),'primary'));}
 }
 const exportText=button('exportPlainText','텍스트 파일로 받기',()=>download());$('resultTools').append(exportText);
 window.WorkspaceHelp={open,demo,copyText,apiError,diagnostic};
})();
