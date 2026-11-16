"use strict";
const $ = id => document.getElementById(id);
const token = document.querySelector('meta[name="studio-token"]').content;
let draft = fresh(), tab = "blog", preview = false, busy = false, dirty = false, status = {};
let uploadQueue = Promise.resolve();
let workflow={stage:1,state:""};
function fresh(){return {id:null,title:"",blog:"",instagram:"",prompt:"",style:"",tone:"밝고 자연스러운 일상 후기체",facts:"",disclosure:"none",template:"reference",images:[],sources:[]};}

function setWorkflow(stage,state=""){
 workflow={stage,state};renderWorkflow();
}
function renderWorkflow(){
 const editorOpen=!$("editor").hidden;
 const content=editorOpen&&$("body").value.trim();
 const canMove=Boolean(content&&(tab==="instagram"?draft.images.length:$("title").value.trim()));
 if(workflow.state==="writing"&&!busy)workflow={stage:editorOpen?2:1,state:""};
 const {stage,state}=workflow;
 $("workflow").dataset.stage=String(stage);$("workflow").dataset.state=state;
 $("lastStepLabel").textContent=tab==="blog"?"블로그로 옮기기":"인스타에 올리기";
 const hints={
  writing:"사진을 살피며 나다운 글로 정리하고 있어요.",
  sending:"글과 사진을 옮기고 있어요. 잠시만 기다려 주세요.",
  prepared:"도우미에서 준비한 글을 가져와 주세요.",
  ready:"네이버로 옮겼어요. 내용을 확인한 뒤 발행해 주세요.",
  partial:"글과 사진을 옮겼어요. 네이버에서 서식을 확인해 주세요.",
  published:"인스타그램에 오늘의 이야기를 올렸어요.",
  error:"아래 진행 안내에서 이유를 확인하고 이어가 주세요."
 };
 $("workflowHint").textContent=hints[state]||(stage===1?"사진을 고르고 오늘의 이야기를 짧게 적어 주세요.":stage===2?"글과 사진을 살펴보고, 마음에 들면 다음 단계로 가요.":tab==="blog"?"준비됐어요. 아래 버튼으로 네이버에 옮겨 보세요.":"내용을 확인하고 인스타그램에 올려 보세요.");
 $("workflowCaption").textContent=state==="ready"?"네이버에서 마지막 확인":state==="published"?"오늘의 이야기, 발행 완료":"오늘의 기록, 차근차근";
 document.querySelectorAll(".step-button").forEach(button=>{
  const n=Number(button.dataset.step),done=n<stage||(n===3&&["ready","published"].includes(state));
  button.disabled=busy||(n===2&&!editorOpen)||(n===3&&!canMove);
  button.classList.toggle("is-current",n===stage);button.classList.toggle("is-done",done);button.classList.toggle("is-attention",n===3&&["error","partial"].includes(state));
  if(n===stage)button.setAttribute("aria-current","step");else button.removeAttribute("aria-current");
  button.querySelector(".step-mark").textContent=done?"✓":String(n);
  button.querySelector(".step-state").textContent=n===3&&state==="ready"?"옮김 완료":n===3&&state==="published"?"발행 완료":n===stage?(state==="writing"||state==="sending"?"진행 중":"지금 여기"):done?"완료":"";
  button.title=n===2&&!editorOpen?"글이 완성되면 여기에서 확인할 수 있어요.":n===3&&!canMove?"글을 확인한 뒤 옮길 수 있어요.":"해당 작업 위치로 이동";
 });
 $("composeCard").classList.toggle("is-current",stage===1);
 $("resultCard").classList.toggle("is-current",stage>=2);
 $("publishArea").classList.toggle("is-current",stage===3);
}
document.querySelectorAll(".step-button").forEach(button=>button.addEventListener("click",()=>{
 if(busy)return;const stage=Number(button.dataset.step);setWorkflow(stage);
 if(stage===2&&!preview){sync();preview=true;$("editFields").hidden=true;$("preview").hidden=false;$("previewToggle").textContent="글 수정";renderPreview();}
 const target=$(button.getAttribute("aria-controls"));
 target.scrollIntoView({behavior:matchMedia("(prefers-reduced-motion: reduce)").matches?"auto":"smooth",block:"start"});
 if(stage===1)$(draft.images.length?"prompt":"dropzone").focus({preventScroll:true});
 if(stage===3)$("publish").focus({preventScroll:true});
}));
$("dropzone").addEventListener("click",()=>$("photos").click());
for(const id of ["prompt","facts","style","tone","template"])$(id).addEventListener("focus",()=>{if(!busy)setWorkflow(1);});
for(const id of ["title","body"])$(id).addEventListener("focus",()=>{if(!busy)setWorkflow(2);});
function notify(message){$("toast").textContent=message;$("toast").classList.add("show");clearTimeout(notify.timer);notify.timer=setTimeout(()=>$("toast").classList.remove("show"),6500);}
async function api(path, body){
 const response=await fetch(path,{method:body===undefined?"GET":"POST",headers:body===undefined?{}:{"Content-Type":"application/json","X-Studio-Token":token},body:body===undefined?undefined:JSON.stringify(body)});
 const result=await response.json();if(!response.ok){
  if(path.startsWith("/api/naver/")){showProgress(result.error||"네이버 전달 요청이 실패했어요.");showNaverDiagnostic({stage:"전달 준비 · 앱 검사",detail:result.error});}
  const message=result.error||"요청을 처리하지 못했어요.";
  if(path==="/api/drafts"){showProgress(message);dirty=true;markDirty();}
  throw Error(message);
 }return result;
}
function run(fn){return async(...args)=>{try{await fn(...args);}catch(e){notify(e.message);}};}
function sync(){draft.prompt=$("prompt").value;draft.style=$("style").value;draft.tone=$("tone").value;draft.template=$("template").value;draft.facts=$("facts").value;draft.disclosure=$("disclosure").value;draft.title=$("title").value;if(!$("editor").hidden)draft[tab]=$("body").value;}
function markDirty(){
 if($("naverDiagnostic").classList.contains("is-success")){$("naverDiagnostic").hidden=true;$("naverDiagnostic").dataset.relevant="false";$("jobProgress").hidden=true;}
 if(["ready","partial","published","prepared","error"].includes(workflow.state))workflow={stage:$("editor").hidden?1:2,state:""};
 dirty=true;renderWorkflow();$("saveState").textContent="수정 중";clearTimeout(markDirty.timer);
 markDirty.timer=setTimeout(()=>{if(!dirty)return;try{sync();localStorage.setItem("dajeong-recovery",JSON.stringify({draft,saved:Date.now()}));}catch{}},800);
}
function renderPhotos(){
 $("photoOrderHint").hidden=draft.images.length<2;
 $("photoCount").textContent=draft.images.length+" / 10장";$("photoGrid").replaceChildren();
 draft.images.forEach((id,i)=>{
 const box=document.createElement("div");box.className="photo";const img=document.createElement("img");img.src="/media/"+id+".jpg";img.alt="사진 "+(i+1);box.append(img);
 function button(label,cls,action){const b=document.createElement("button");b.type="button";b.textContent=label;b.className=cls;b.disabled=busy;b.addEventListener("click",()=>{if(busy)return;action();renderPhotos();markDirty();if(preview)renderPreview();});return b;}
 const remove=button("×","remove",()=>draft.images.splice(i,1));remove.setAttribute("aria-label","사진 "+(i+1)+" 삭제");box.append(remove);
 const controls=document.createElement("div");controls.className="photo-controls";
 if(i>0){const b=button("←","",()=>[draft.images[i-1],draft.images[i]]=[draft.images[i],draft.images[i-1]]);b.setAttribute("aria-label","사진 앞으로 이동");controls.append(b);}
 const n=document.createElement("small");n.textContent=i+1;controls.append(n);
 if(i<draft.images.length-1){const b=button("→","",()=>[draft.images[i+1],draft.images[i]]=[draft.images[i],draft.images[i+1]]);b.setAttribute("aria-label","사진 뒤로 이동");controls.append(b);}box.append(controls);$("photoGrid").append(box);
 });renderWorkflow();}
async function addPhotos(files){
 if(busy)return;
 setWorkflow(1);lock(true);try{
 for(const file of files){
 if(draft.images.length>=10){notify("사진은 최대 10장까지 넣을 수 있어요.");break;}
 if(file.size>10_000_000){notify(file.name+": 10MB 이하 사진을 선택해 주세요.");continue;}
 if(!["image/jpeg","image/png","image/webp"].includes(file.type)){notify("JPG, PNG, WebP 사진을 선택해 주세요.");continue;}
 const data=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result.split(",")[1]);r.onerror=()=>reject(Error("사진을 읽지 못했어요."));r.readAsDataURL(file);});
 const result=await api("/api/upload",{data});draft.images.push(result.id);renderPhotos();markDirty();
 }$("photos").value="";}finally{lock(false);}
}
$("photos").addEventListener("change",e=>{const files=[...e.target.files];uploadQueue=uploadQueue.then(run(()=>addPhotos(files)));});
for(const ev of ["dragover","dragleave","drop"])$("dropzone").addEventListener(ev,e=>{e.preventDefault();$("dropzone").classList.toggle("drag",ev==="dragover");if(ev==="drop"){const files=[...e.dataTransfer.files];uploadQueue=uploadQueue.then(run(()=>addPhotos(files)));}});
function showEditor(){$("emptyResult").hidden=true;$("editor").hidden=false;renderTab();setWorkflow(2);}
function renderTab(){
 $("blogTab").classList.toggle("active",tab==="blog");$("instaTab").classList.toggle("active",tab==="instagram");
 $("blogTab").setAttribute("aria-selected",tab==="blog");$("instaTab").setAttribute("aria-selected",tab==="instagram");
 $("title").hidden=tab!=="blog";$("body").value=draft[tab];$("body").maxLength=tab==="instagram"?2200:30000;
 $("editorLabel").textContent=tab==="blog"?"블로그 초안":"인스타그램 캡션";$("export").hidden=tab!=="blog";
 $("naverTestControls").hidden=tab!=="blog";
 $("publishLabel").textContent=tab==="blog"?"블로그에 이야기 담기":"인스타그램에 이야기 담기";
 $("publishHint").textContent=tab==="blog"?"평소 쓰는 네이버로 글과 사진을 옮겨드려요. 확인 후 발행만 눌러 주세요.":"연결된 인스타그램에 글과 사진을 올려요.";
 $("publish").textContent=tab==="blog"?"블로그로 옮기기 ↗":"인스타에 올리기 ↗";
 $("editorHint").textContent=preview?"고치고 싶다면 ‘글 수정’을 눌러 주세요.":"제목과 본문을 자유롭게 다듬어 주세요.";
 $("naverDiagnostic").hidden=tab!=="blog"||$("naverDiagnostic").dataset.relevant!=="true";
 count();if(preview)renderPreview();renderSources();renderWorkflow();
}
function count(){$("charCount").textContent=$("body").value.length.toLocaleString()+"자"+(tab==="instagram"?" / 2,200자":"");}
function renderSources(){
 const box=$("sourceBox");box.replaceChildren();$("sourceDetails").hidden=!draft.sources.length;if(!draft.sources.length)return;
 const label=document.createElement("strong");label.textContent="찾아본 자료";box.append(label);
 draft.sources.forEach(s=>{try{const url=new URL(s.url);if(!["https:","http:"].includes(url.protocol))return;const a=document.createElement("a");a.href=url.href;a.textContent=s.title||url.hostname;a.target="_blank";a.rel="noopener noreferrer";box.append(a);}catch{}});
}
function renderPreview(){
 $("editorHint").textContent="고치고 싶다면 ‘글 수정’을 눌러 주세요.";
 sync();const box=$("preview");box.replaceChildren();box.classList.toggle("reference-style",tab==="blog"&&draft.template!=="clean");
 const add=(tag,value)=>{const el=document.createElement(tag);el.textContent=value;box.append(el);};
 const photo=(id,n)=>{const img=document.createElement("img");img.src="/media/"+id+".jpg";img.alt="사진 "+n;box.append(img);};
 if(tab==="blog"){
  add("h3",draft.title);const used=new Set();let lines=[];
  const flush=()=>{if(lines.length){add("p",lines.join("\n"));lines=[];}};
  for(const line of draft.blog.split("\n")){
   const m=line.trim().match(/^\[\[photo:(\d+)\]\]$/);
   if(m){flush();const i=Number(m[1])-1;if(draft.images[i]){photo(draft.images[i],i+1);used.add(i);}}
   else if(line.startsWith("## ")){flush();add("h2",line.slice(3));}
   else if(!line.trim())flush();else lines.push(line);
  }
  flush();draft.images.forEach((id,i)=>{if(!used.has(i))photo(id,i+1);});
 }
 else{draft.images.forEach((id,i)=>photo(id,i+1));add("p",draft.instagram);}
}
$("blogTab").addEventListener("click",()=>{sync();if(tab!=="blog"){workflow={stage:$("editor").hidden?1:2,state:""};$("jobProgress").hidden=true;}tab="blog";renderTab();});
$("instaTab").addEventListener("click",()=>{sync();if(tab!=="instagram"){workflow={stage:$("editor").hidden?1:2,state:""};$("jobProgress").hidden=true;}tab="instagram";renderTab();});
$("manualStart").addEventListener("click",()=>{showEditor();$("title").focus();});
$("previewToggle").addEventListener("click",()=>{sync();preview=!preview;setWorkflow(2);$("editFields").hidden=preview;$("preview").hidden=!preview;$("previewToggle").textContent=preview?"글 수정":"미리보기";$("editorHint").textContent=preview?"고치고 싶다면 ‘글 수정’을 눌러 주세요.":"제목과 본문을 자유롭게 다듬어 주세요.";if(preview)renderPreview();});
for(const id of ["prompt","style","tone","title","body","facts","disclosure","template"])$(id).addEventListener("input",()=>{markDirty();if(id==="body")count();});
function showProgress(message){
 const element=$("jobProgress");element.hidden=false;element.textContent=message;
}
async function waitJob(job){
 const deadline=Date.now()+660000;
 while(Date.now()<deadline){
  await new Promise(r=>setTimeout(r,1200));const r=await api("/api/jobs/"+job);
  if(r.message)showProgress(r.message);
  if(r.state==="done")return r.result;
  if(r.state==="failed"){showProgress(r.error);throw Error(r.error);}
 }
 const message="작업 결과를 확인하지 못했어요. 자동 재시도하지 말고 열린 편집기나 계정에서 결과를 확인해 주세요.";
 showProgress(message);throw Error(message);
}
function lock(value){
 busy=value;
 for(const id of ["generate","save","copy","export","publish","newDraft","showDrafts","showHistory","manualStart","photos","dropzone","prompt","style","tone","title","body","blogTab","instaTab","previewToggle","research","settingsButton","facts","disclosure","review","template","naverRepeat","naverManual"])$(id).disabled=value;
 document.querySelectorAll("[data-example]").forEach(b=>b.disabled=value);renderPhotos();
 $("saveState").textContent=value?"작업 중…":dirty?"수정 중":draft.id?"저장 완료":"작성 대기";
}
$("generate").addEventListener("click",run(async()=>{
 await uploadQueue;sync();if(!draft.prompt.trim())return notify("어떤 이야기를 쓰고 싶은지 알려 주세요.");
 if(!status.ai){openSettings();return;}
 if((draft.blog||draft.instagram)&&!confirm("글을 새로 만들어 볼까요? 지금 글을 남기려면 먼저 보관해 주세요."))return;
 lock(true);setWorkflow(2,"writing");$("generate").textContent="✦ 사진을 살피고 이야기를 쓰고 있어요…";
 try{const job=await api("/api/generate",{...draft,research:$("research").checked});const result=await waitJob(job.job);Object.assign(draft,result);$("title").value=draft.title;markDirty();showEditor();preview=true;$("editFields").hidden=true;$("preview").hidden=false;$("previewToggle").textContent="글 수정";renderPreview();showQuality(result.checks||[]);
 const usage=result.generation;if(usage)$("generationInfo").textContent=usage.model+(usage.style_pass?" → "+usage.writing_model+" 글 다듬기":"")+" · 입력 "+usage.input_tokens.toLocaleString()+" / 출력 "+usage.output_tokens.toLocaleString()+" 토큰 · 검색 "+usage.web_search_calls+"회";
 notify("이야기를 완성했어요. 내 경험과 다른 내용이 없는지 읽어 주세요.");}
 finally{lock(false);$("generate").textContent="✦ 예쁘게 글 만들기 →";}
}));
async function saveDraft(){await uploadQueue;sync();draft=await api("/api/drafts",draft);dirty=false;clearTimeout(markDirty.timer);try{localStorage.removeItem("dajeong-recovery");}catch{};$("body").value=draft[tab];count();if(preview)renderPreview();$("saveState").textContent="저장 완료";return draft;}
$("save").addEventListener("click",run(async()=>{await saveDraft();notify("이야기를 이 컴퓨터에 저장했어요.");}));
$("copy").addEventListener("click",run(async()=>{sync();await navigator.clipboard.writeText(tab==="blog"?draft.title+"\n\n"+draft.blog.replace(/^\s*\[\[photo:\d+\]\]\s*$/gm,""):draft.instagram);notify("본문을 복사했어요.");}));
$("export").addEventListener("click",run(async()=>{await saveDraft();const r=await fetch("/export/"+draft.id);if(!r.ok)throw Error("내보내기를 완료하지 못했어요.");const blob=await r.blob(),u=URL.createObjectURL(blob),a=document.createElement("a");a.href=u;a.download=(draft.title||"나의 이야기").replace(/[<>:"/\\|?*]/g,"_")+".html";a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);notify("글과 사진을 파일로 보관했어요.");}));
$("publish").addEventListener("click",run(async()=>{
 setWorkflow(3);status=await api("/api/status");
 if(tab==="blog"&&status.naver_guard?.blocked){showProgress("네이버 입력 잠금: "+status.naver_guard.reason);showNaverDiagnostic({stage:"네이버 보호 잠금",detail:status.naver_guard.reason});openSettings("blog");return;}
 if((tab==="blog"&&!status.naver)||(tab==="instagram"&&!status.instagram)){openSettings(tab);return;}
 await saveDraft();
 const checked=await api("/api/review",draft);showQuality(checked.checks);
 const blocking=checked.checks.filter(item=>item.level==="error"&&(tab==="blog"?!item.message.includes("인스타그램"):item.message.includes("인스타그램")));
 if(blocking.length)throw Error(blocking.map(item=>item.message).join(" "));
 if(tab==="blog"){
  const handoff=await api("/api/naver/handoff",{id:draft.id,repeat_confirm:$("naverRepeat").checked});await sendToNaver(handoff);return;
 }
 if(tab==="instagram"&&!confirm("이 글과 사진을 연결된 인스타그램 계정에 지금 공개 발행할까요?"))return;
 lock(true);setWorkflow(3,"sending");showProgress("발행 준비를 시작하고 있어요.");const target=tab;
 try{const j=await api(target==="blog"?"/api/naver/prepare":"/api/publish/instagram",{id:draft.id,confirm:true});notify(target==="blog"?"네이버 브라우저를 열고 있어요. 열린 창에서 로그인을 진행해 주세요.":"인스타그램에서 사진을 처리하고 있어요.");const result=await waitJob(j.job);const message=target==="blog"?result.message:"인스타그램에 발행했어요. 게시물 ID: "+result.media_id;showProgress(message);setWorkflow(3,"published");notify(message);}
 catch(error){setWorkflow(3,"error");showProgress(error.message);throw error;}
 finally{lock(false);}
}));
function extensionMessage(id,message){
 return new Promise((resolve,reject)=>{
  if(!globalThis.chrome?.runtime?.sendMessage)return reject(Error("크롬에서 앱을 열고 다정 도우미를 연결해 주세요."));
  chrome.runtime.sendMessage(id,message,result=>{
   const error=chrome.runtime.lastError;if(error)return reject(Error("확장 연결 실패: "+error.message+" / 크롬 오른쪽 위 다정 아이콘에서 ‘앱과 연결하기’를 다시 눌러 주세요."));
   resolve(result);
  });
 });
}
async function sendToNaver(handoff){
 let id;try{id=localStorage.getItem("dajeong-extension");}catch{}
 if(!/^[a-p]{32}$/.test(id||"")){showHandoff(handoff);return;}
 let timer,finished=false;
 lock(true);setWorkflow(3,"sending");showProgress("네이버 글쓰기 화면을 열고 있어요.");
 try{
  const ping=await extensionMessage(id,{type:"ping"});if(!ping?.ok)throw Error(ping?.message||"도우미 연결 응답이 없어요.");
  if(ping.version!=="1.4.1")throw Error("현재 확장 버전은 "+(ping.version||"확인 불가")+"예요. chrome://extensions에서 다정 확장을 새로고침하고 1.4.1을 확인해 주세요.");
  timer=setInterval(()=>extensionMessage(id,{type:"status"}).then(state=>{if(!finished&&state?.message)showProgress(state.message);}).catch(()=>{}),1300);
  const result=await extensionMessage(id,{type:"prepare",base:location.origin,code:handoff.code,writer_url:handoff.writer_url});
  finished=true;clearInterval(timer);
  showProgress(result?.detail||result?.message||"네이버에 옮겨진 내용을 확인해 주세요.");showNaverDiagnostic(result);
 }catch(error){finished=true;showProgress(error.message);showNaverDiagnostic({ok:false,stage:"앱과 확장 연결",detail:error.message});showHandoff(handoff);}
 finally{clearInterval(timer);lock(false);}
}
function showHandoff(handoff){
 if(workflow.state!=="error")setWorkflow(3,"prepared");
 const box=modal("네이버 전달 · 코드로 직접 옮기기");
 para(box,"크롬 오른쪽 위의 다정 아이콘을 누르고 ‘앱과 연결하기’를 눌러 주세요. 다음부터는 ‘블로그로 옮기기’ 한 번이면 돼요.");
 const help=document.createElement("details");const summary=document.createElement("summary");summary.textContent="다정 아이콘이 안 보여요";help.append(summary);
 para(help,"처음 설치는 도와주시는 분과 한 번만 진행해 주세요. 크롬 주소창에 chrome://extensions를 입력하고 개발자 모드 → 압축해제된 확장 프로그램을 로드 → 아래 폴더를 선택합니다.");
 para(help,"프로젝트 폴더 안의 chrome-extension 폴더");box.append(help);
 const direct=document.createElement("details");const directTitle=document.createElement("summary");directTitle.textContent="전달 코드 복사";direct.open=true;direct.append(directTitle);
 const code=document.createElement("input");code.readOnly=true;code.value=handoff.code;code.style.width="100%";code.setAttribute("aria-label","일회용 전달 코드");direct.append(code);
 const copy=document.createElement("button");copy.className="secondary";copy.textContent="옮기기 번호 복사";
 copy.addEventListener("click",run(async()=>{await navigator.clipboard.writeText(handoff.code);notify("번호를 복사했어요. 네이버에서 다정 아이콘을 눌러 주세요.");}));direct.append(copy);
 const link=document.createElement("a");link.href=handoff.writer_url;link.target="_blank";link.rel="noopener noreferrer";link.textContent=" 네이버 글쓰기 열기 ↗";direct.append(link);
 box.append(direct);
}
$("naverManual").addEventListener("click",run(async()=>{
 await saveDraft();const handoff=await api("/api/naver/handoff",{id:draft.id,repeat_confirm:$("naverRepeat").checked});showHandoff(handoff);
}));
function showNaverDiagnostic(result){
 const success=Boolean(result?.ok);setWorkflow(3,success?"ready":result?.contentReady?"partial":"error");
 const box=$("naverDiagnostic");box.replaceChildren();box.hidden=false;box.dataset.relevant="true";box.classList.toggle("is-success",success);
 const heading=document.createElement("strong");heading.textContent=success?"✓ 네이버로 잘 옮겼어요":result?.contentReady?"서식을 한 번 확인해 주세요":"전달을 마치지 못했어요";box.append(heading);
 para(box,success?"네이버에서 내용을 확인하고 마지막 발행을 눌러 주세요.":result?.detail||result?.message||"응답이 없어 결과를 확인하지 못했어요.");
 if(success)$("jobProgress").hidden=true;
 const details=document.createElement("details");details.className="diagnostic-details";details.open=!success;
 const summary=document.createElement("summary");summary.textContent="자세한 결과 · 문제 확인";details.append(summary);box.append(details);
 para(details,"확장 "+(result?.version||"버전 확인 안 됨")+" · "+(result?.stage||"결과 확인"));
 const format=result?.formatting;
 if(format?.requested)para(details,"정렬: "+(format.alignment?"적용 확인":"미적용 또는 확인 불가")+" / 글꼴: "+(format.font?"적용 확인":"미적용 또는 확인 불가")+" / 크기: "+(format.size?"적용 확인":"미적용 또는 확인 불가"));
 const diagnostic={version:result?.version,stage:result?.stage,reason:result?.detail||result?.message,formatting:format,diagnostics:result?.diagnostics};
 const raw=document.createElement("pre");raw.textContent=JSON.stringify(diagnostic,null,2);raw.style.cssText="white-space:pre-wrap;overflow-wrap:anywhere;font-size:11px";details.append(raw);
 const copy=document.createElement("button");copy.className="secondary";copy.textContent="진단 결과 복사";
 copy.addEventListener("click",run(async()=>{await navigator.clipboard.writeText(JSON.stringify(diagnostic,null,2));notify("진단 결과를 복사했어요.");}));details.append(copy);
}
function modal(title){$("modalTitle").textContent=title;$("modalBody").replaceChildren();$("modal").showModal();return $("modalBody");}
function showQuality(checks){
 const box=$("qualityBox");box.replaceChildren();box.hidden=!checks.length;box.classList.toggle("is-neutral",checks.every(item=>item.level==="info"));
 const title=document.createElement("strong");title.textContent="올리기 전에 살펴봐 주세요";box.append(title);
 const detail=document.createElement("details"),summary=document.createElement("summary");summary.textContent="확인한 내용 더 보기";detail.append(summary);
 for(const item of checks){const line=document.createElement("p");line.style.marginTop="7px";line.textContent=(item.level==="error"?"⛔ ":item.level==="warning"?"확인 · ":"안내 · ")+item.message;(item.level==="info"?detail:box).append(line);}
 if(checks.some(item=>item.level==="info"))box.append(detail);
}
$("review").addEventListener("click",run(async()=>{sync();const result=await api("/api/review",draft);showQuality(result.checks);}));
$("closeModal").addEventListener("click",()=>$("modal").close());
$("modal").addEventListener("click",e=>{if(e.target===$("modal"))$("modal").close();});
function para(container,txt){const p=document.createElement("p");p.textContent=txt;container.append(p);}
function openSettings(channel){
 const instagramOnly=channel==="instagram";
 const shell=modal(instagramOnly?"인스타그램 연결":"연결 설정");
 para(shell,"처음 한 번 연결해 두면 다음부터 편하게 사용할 수 있어요.");
 if(!instagramOnly&&status.naver_guard?.blocked)para(shell,"네이버 입력이 잠겨 있어요: "+status.naver_guard.reason);
 para(shell,(status.ai?"✓ 글 만들기 준비됐어요.":"○ 글 만들기 연결이 필요해요.")+" "+(status.instagram?"✓ 인스타그램 준비됐어요.":"○ 인스타그램은 아직 준비 중이에요."));
 const advanced=document.createElement("details"),heading=document.createElement("summary");
 heading.textContent="자세한 설정 보기";advanced.append(heading);
 const box=document.createElement("div");advanced.append(box);shell.append(advanced);
 if(!instagramOnly){
  para(box,".env에 연결 정보를 입력한 뒤 앱을 다시 실행해 주세요. 키는 이 컴퓨터에서만 읽어요.");
  para(box,(status.ai?"✓":"○")+" AI 글쓰기: "+(status.ai?"설정됨":"OPENAI_API_KEY 입력 필요"));
  para(box,(status.naver?"✓":"○")+" 네이버: "+(status.naver?"블로그 ID 설정됨":"NAVER_BLOG_ID 입력 필요"));
  para(box,"네이버는 chrome-extension 폴더의 다정 확장을 설치해 사용해요. 기존 크롬의 빈 글쓰기 탭에서 전달 코드를 붙여 넣어 주세요. 별도 로그인 브라우저를 실행하지 않아요.");
 }
 if(!instagramOnly&&status.naver_guard){
  const guard=status.naver_guard;
  para(box,guard.blocked?"네이버 자동 입력 잠금: "+guard.reason:"네이버 자동 입력은 1분 간격으로 실행할 수 있어요. 하루 횟수 제한은 없어요. 보호조치가 발생하지 않음을 보장하지는 않아요.");
  if(guard.blocked){
   const unlock=document.createElement("button");unlock.className="secondary";unlock.textContent="네이버 제한 해제·정상 로그인 확인";
   unlock.addEventListener("click",run(async()=>{
    if(!confirm("공식 네이버 화면에서 직접 보호조치를 해제하고 정상 로그인한 것을 확인하셨나요? 쿨다운·일일 제한은 유지됩니다."))return;
    await api("/api/naver/unblock",{confirm:true});status=await api("/api/status");$("modal").close();openSettings("blog");
   }));box.append(unlock);
  }
 }
 const checkButton=document.createElement("button");checkButton.className="secondary";checkButton.id="instagramCheck";
 checkButton.textContent="인스타그램 연결 확인";
 const checkResult=document.createElement("p");checkResult.setAttribute("role","status");
 checkButton.addEventListener("click",run(async()=>{
  checkButton.disabled=true;checkResult.textContent="토큰과 계정을 확인하고 있어요.";
  try{const result=await api("/api/instagram/check",{});checkResult.textContent=result.message;}
  catch(error){checkResult.textContent=error.message;}
  finally{checkButton.disabled=false;}
 }));
 shell.insertBefore(checkButton,advanced);shell.insertBefore(checkResult,advanced);
 const details=status.instagram_details;
 const labels={INSTAGRAM_ACCOUNT_ID:"인스타그램 계정 ID",INSTAGRAM_ACCESS_TOKEN:"인스타그램 액세스 토큰",PUBLIC_MEDIA_BASE_URL:"공개 사진 HTTPS 주소"};
 if(details){
  for(const [key,label] of Object.entries(labels)){
   const present=details.configured[key],invalid=details.invalid.includes(key);
   para(box,(present&&!invalid?"✓ ":"○ ")+label+": "+(invalid?"형식 확인 필요":present?"설정됨":"입력 필요")+" ("+key+")");
  }
  if(details.invalid.includes("INSTAGRAM_ACCOUNT_ID"))para(box,"계정 ID는 @사용자 이름이나 URL이 아닌 숫자 Instagram professional account ID를 넣어 주세요.");
  para(box,"연결 방식: "+(details.login_type==="unified"?"Instagram API 통합 로그인":"Instagram Login"));
  if(details.invalid.includes("INSTAGRAM_LOGIN_TYPE"))para(box,"INSTAGRAM_LOGIN_TYPE을 unified 또는 instagram으로 설정해 주세요.");
  if(details.missing.length===1&&details.missing[0]==="PUBLIC_MEDIA_BASE_URL"){
   para(box,"사진을 전달할 공개 HTTPS 주소가 비어 있어요. 위에서 계정 ID와 토큰 형식도 함께 확인해 주세요. 현재는 인스타그램 발행 요청을 보내지 않았어요.");
  }
 }else{
  para(box,(status.instagram?"✓ ":"○ ")+"인스타그램: 계정 ID·토큰·공개 사진 HTTPS 주소가 필요해요.");
 }
 if(details){
  const connected=details.temporary_connection;
  para(box,connected?"사진 전용 임시 연결이 켜져 있어요. 앱을 종료하거나 연결을 끄면 공개 주소도 닫혀요.":"공개 서버가 없다면 아래 버튼으로 사진 전용 임시 주소를 만들 수 있어요.");
  para(box,"Cloudflare를 통해 인스타그램 발행용으로 준비한 사진만 전달해요. 글 작성 화면·초안·API 키·원본 사진은 이 연결에서 제공하지 않아요. 임시 주소는 매번 달라질 수 있어요.");
  const button=document.createElement("button");button.className="primary";button.id="mediaConnection";
  button.textContent=connected?"사진 연결 끄기":"사진 연결하기";
  button.addEventListener("click",run(async()=>{
   button.disabled=true;
   try{
    if(connected){
     await api("/api/media/disconnect",{});
     notify("사진 공개 연결을 껐어요.");
    }else{
     button.textContent="사진 주소를 연결하는 중…";
     const job=await api("/api/media/connect",{});
     const result=await waitJob(job.job);
     notify(result.message);
    }
    status=await api("/api/status");$("modal").close();openSettings("instagram");
   }finally{button.disabled=false;}
  }));
  shell.insertBefore(button,advanced);
 }
 para(box,"사진 주소는 임의의 예시가 아니라 실제로 사진을 읽을 수 있는 서버 주소여야 해요. localhost나 PC 폴더 경로는 사용할 수 없어요.");
 para(box,"임시 연결을 사용하면 PUBLIC_MEDIA_BASE_URL은 직접 입력하지 않아도 돼요. 고정 서버를 사용하려면 .env를 수정하고 start.cmd를 다시 실행해 주세요.");
 para(box,"설정됨은 값의 존재 여부예요. 토큰 권한이나 실제 발행 성공을 의미하지 않아요.");
}
$("settingsButton").addEventListener("click",run(async()=>{status=await api("/api/status");openSettings();}));
$("showDrafts").addEventListener("click",run(async()=>{
 const rows=await api("/api/drafts"),box=modal("보관한 이야기");if(!rows.length)para(box,"저장한 이야기가 아직 없어요. 첫 이야기를 남겨 볼까요?");
 rows.forEach(r=>{const b=document.createElement("button");b.className="draft-row";const t=document.createElement("span");t.textContent=r.title||"제목 없는 이야기";const d=document.createElement("small");d.textContent=new Date(r.updated*1000).toLocaleDateString("ko-KR");b.append(t,d);b.addEventListener("click",run(async()=>{if(dirty&&!confirm("저장하지 않은 내용을 버리고 이 초안을 열까요?"))return;draft=await api("/api/drafts/"+r.id);loadDraft();$("modal").close();}));box.append(b);});
}));
function showToneGuide(){$("toneGuide").textContent=$("tone").selectedOptions[0]?.dataset.guide||"";}
$("tone").addEventListener("change",showToneGuide);
showToneGuide();
function loadDraft(){
 workflow={stage:1,state:""};$("naverDiagnostic").hidden=true;$("naverDiagnostic").dataset.relevant="false";$("jobProgress").hidden=true;$("naverTestControls").open=false;
 $("naverRepeat").checked=false;
 if(draft.tone&&!Array.from($("tone").options).some(option=>option.value===draft.tone)){
  const option=document.createElement("option");option.value=draft.tone;option.textContent=draft.tone;$("tone").append(option);
 }
 for(const id of ["prompt","style","tone","title","facts","disclosure","template"])$(id).value=draft[id]||(id==="disclosure"?"none":id==="template"?"reference":"");
 showToneGuide();$("qualityBox").hidden=true;$("generationInfo").textContent="";
 clearTimeout(markDirty.timer);try{localStorage.removeItem("dajeong-recovery");}catch{};tab="blog";preview=Boolean(draft.blog||draft.instagram);$("preview").hidden=!preview;$("editFields").hidden=preview;$("previewToggle").textContent=preview?"글 수정":"미리보기";dirty=false;renderPhotos();showEditor();$("saveState").textContent="저장 완료";}
$("newDraft").addEventListener("click",()=>{if(busy)return;if(dirty&&!confirm("저장하지 않은 내용을 버리고 새 이야기를 쓸까요?"))return;draft=fresh();loadDraft();$("editor").hidden=true;$("emptyResult").hidden=false;$("saveState").textContent="작성 대기";$("prompt").focus();setWorkflow(1);});
$("showHistory").addEventListener("click",run(async()=>{
 const rows=await api("/api/history"),box=modal("인스타그램 발행 기록");if(!rows.length)para(box,"아직 발행한 이야기가 없어요. 네이버 도우미의 편집기 입력은 발행 기록에 포함되지 않아요.");
 const labels={published:"발행 완료",publishing:"진행 중 · 앱 재시작 뒤에는 계정 확인 필요",failed:"실패 · 다시 시도 가능",uncertain:"결과 확인 필요 · 계정에서 중복 여부 확인"};
 rows.forEach(r=>{const div=document.createElement("div");div.className="draft-row";div.textContent=(r.title||"제목 없는 이야기")+" · "+labels[r.state]+" · "+new Date(r.created*1000).toLocaleString("ko-KR");box.append(div);});
}));
const examples={카페:"주말에 다녀온 카페를 소개하고 싶어. 친구에게 추천하듯 자연스럽게 써줘. 방문한 곳과 실제로 느낀 점: ",일상:"오늘의 소소한 순간을 일상 기록으로 남기고 싶어. 사진 속 장면을 중심으로 따뜻하지만 과하지 않게 써줘. 오늘 있었던 일: ",제품:"직접 써 본 제품의 후기를 쓰고 싶어. 좋았던 점과 아쉬운 점이 드러나는 솔직한 리뷰로 써줘. 제품 이름과 사용 경험: "};
document.querySelectorAll("[data-example]").forEach(b=>b.addEventListener("click",()=>{if($("prompt").value.trim()&&!confirm("입력한 메모를 예시 문구로 바꿀까요?"))return;$("prompt").value=examples[b.dataset.example];$("prompt").focus();markDirty();}));
window.addEventListener("beforeunload",e=>{if(dirty||busy){e.preventDefault();e.returnValue="";}});
api("/api/status").then(s=>{status=s;if(!s.ai){$("connectionNotice").hidden=false;$("connectionNotice").textContent="처음 한 번 글쓰기 연결이 필요해요. 오른쪽 위 ‘연결 설정’을 눌러 주세요.";}}).catch(e=>notify(e.message));


try{
 const stored=JSON.parse(localStorage.getItem("dajeong-recovery")||"null");
 if(stored?.draft&&Array.isArray(stored.draft.images)&&typeof stored.draft.blog==="string"&&confirm("이전에 저장하지 않은 글이 있어요. 복구할까요?")){
  draft={...fresh(),...stored.draft};loadDraft();markDirty();notify("작성 중이던 글을 복구했어요. 글 보관하기를 눌러 보관해 주세요.");
 }
}catch{}

(async()=>{
 const id=new URLSearchParams(location.hash.slice(1)).get("extension");
 if(!/^[a-p]{32}$/.test(id||""))return;
 try{
  const result=await extensionMessage(id,{type:"ping"});if(!result?.ok)return;
  localStorage.setItem("dajeong-extension",id);history.replaceState(null,"",location.pathname);
  $("connectionNotice").hidden=false;$("connectionNotice").textContent="다정 도우미 연결이 끝났어요. 이제 ‘블로그로 옮기기’를 눌러 주세요.";
  const rows=await api("/api/drafts");
  if(rows.length&&!dirty){draft=await api("/api/drafts/"+rows[0].id);loadDraft();}
 }catch{notify("도우미 연결을 마치지 못했어요. 크롬에서 다시 눌러 주세요.");}
})();

renderWorkflow();
