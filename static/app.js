"use strict";
const $ = id => document.getElementById(id);
const token = document.querySelector('meta[name="studio-token"]').content;
let draft = fresh(), tab = "blog", preview = false, busy = false, dirty = false, status = {};
let uploadQueue = Promise.resolve();
let blogDestination="naver",manualPlatform=null;
const platformInfo={naver:{label:"네이버 블로그",body:"blog",title:"title",tab:"blogTab"},instagram:{label:"인스타그램",body:"instagram",tab:"instaTab"},tistory:{label:"티스토리",body:"tistory",title:"tistory_title",tab:"tistoryTab"},threads:{label:"Threads",body:"threads",tab:"threadsTab"}};
function activePlatform(){return tab==="blog"?blogDestination:tab;}
function contentKey(){return platformInfo[activePlatform()].body;}
function titleKey(){return platformInfo[activePlatform()].title||"title";}
function anyContent(){return Boolean(draft.blog||draft.tistory||draft.instagram||draft.threads);}
const campaignTextFields=["campaign_brand","campaign_benefit","campaign_brief","title_keywords","body_keywords","required_phrases","hashtags","campaign_forbidden"];
const campaignNumberFields=["keyword_min_count","campaign_min_chars","campaign_max_chars","campaign_min_photos"];
let workflow={stage:1,state:""};
let workspaceToolsOpen=false;
let generationUndo={},recoveryReady=false,editEpoch=0,navigationEpoch=0,reviewInFlight=false;
function fresh(){return {selected_platforms:preferredPlatforms(),workspace_step:1,channel_media:{},channel_origins:{},voice_styles:{},blog_documents:{},blog_layouts:{},layout_bases:{},layout_last:{},tistory:"",tistory_title:"",selective_generation:false,platform_languages:{},selected_place:null,research:false,campaign_enabled:false,campaign_brand:"",campaign_benefit:"",campaign_brief:"",campaign_forbidden:"",campaign_manual_checks:[],campaign_manual_state:{},campaign_brief_review:{hash:"",sources:[]},campaign_experience:{},title_keywords:"",body_keywords:"",required_phrases:"",hashtags:"",managed_blog_tags:[],keyword_min_count:1,campaign_min_chars:0,campaign_max_chars:0,campaign_count_spaces:false,campaign_min_photos:0,threads_community:true,threads_networking:false,id:null,title:"",blog:"",instagram:"",threads:"",language:"ko",threads_tone:"casual",threads_include_images:true,facts_translation:"",facts_translation_source:"",prompt:"",style:"",tone:"밝고 자연스러운 일상 후기체",facts:"",disclosure:"none",template:"reference",images:[],sources:[],...writingPreferences()};}

const layoutPresets={manual:{width:28,lines:3},notes:{width:20,lines:2},comfort:{width:28,lines:3},review:{width:40,lines:5}};
function renderLayout(){
 $("layoutPanel").hidden=tab!=="blog";if(tab!=="blog")return;
 const config=draft.blog_layouts?.[activePlatform()]||{preset:"manual",width:28,lines:3},english=(draft.platform_languages?.[activePlatform()]||draft.language)==="en";
 $("layoutWidth").value=config.width;$("layoutLines").value=config.lines;
 $("layoutWidthLabel").textContent="약 "+config.width*(english?2:1)+"자";$("layoutLinesLabel").textContent=config.lines+"줄마다";
 document.querySelectorAll("[data-layout]").forEach(button=>{button.classList.toggle("is-selected",button.dataset.layout===config.preset);button.setAttribute("aria-pressed",String(button.dataset.layout===config.preset));});
 const sample=english?"A small moment from today, with a little room to breathe. Photos and a few words, just the way I want to remember it.":"사진 사이에 잠깐 숨을 고르고, 오늘의 작은 이야기를 남겨요. 내 취향대로 한 줄씩, 읽기 편안한 리듬으로 담아볼게요.";
 const width=config.width*(english?2:1);const lines=[];let current="";
 for(const word of sample.split(" ")){if(current&&Array.from(current+" "+word).length>width){lines.push(current);current=word;}else current+=(current?" ":"")+word;}if(current)lines.push(current);
 $("layoutSample").replaceChildren();
 if(config.preset==="manual"){const p=document.createElement("p");p.textContent="직접 나눈 줄과 문단을 그대로 사용해요.";$("layoutSample").append(p);}else for(let i=0;i<lines.length;i+=config.lines){const p=document.createElement("p");p.textContent=lines.slice(i,i+config.lines).join("\n");$("layoutSample").append(p);}
 const body=!$("editor").hidden?$("body").value:(draft[contentKey()]||"");$("layoutApply").disabled=busy||!body.trim();$("layoutUndo").disabled=busy||!draft.layout_bases?.[activePlatform()]||draft.layout_last?.[activePlatform()]!==body;
}
function chooseLayout(config){if(busy||tab!=="blog")return;draft.blog_layouts[activePlatform()]=config;markDirty();renderLayout();$("layoutStatus").textContent="새 글에 사용할 설정이에요. 지금 원고를 바꾸려면 ‘지금 글에 적용’을 눌러 주세요.";}
document.querySelectorAll("[data-layout]").forEach(button=>button.addEventListener("click",()=>chooseLayout({preset:button.dataset.layout,...layoutPresets[button.dataset.layout]})));
for(const id of ["layoutWidth","layoutLines"])$(id).addEventListener("input",()=>chooseLayout({preset:"custom",width:Number($("layoutWidth").value),lines:Number($("layoutLines").value)}));
$("layoutApply").addEventListener("click",run(async()=>{
 if(busy||tab!=="blog")return;sync();const platform=activePlatform(),field=contentKey(),current=draft[field]||"";if(!current.trim())return;
 const source=draft.layout_bases[platform]&&draft.layout_last[platform]===current?draft.layout_bases[platform]:current;
 lock(true);
 try{const result=await api("/api/blog/layout",{body:source,settings:draft.blog_layouts[platform],language:draft.platform_languages[platform]||draft.language});draft.layout_bases[platform]=source;draft.layout_last[platform]=result.body;draft[field]=result.body;$("body").value=result.body;markDirty();updateBodyCount();if(preview)renderPreview();renderMissionChecklist();$("layoutStatus").textContent="줄바꿈을 적용했어요. 사진 위치와 미리보기를 확인해 주세요. AI는 사용하지 않았어요.";}
 finally{lock(false);renderLayout();}
}));
$("layoutUndo").addEventListener("click",()=>{if(busy||tab!=="blog")return;sync();const platform=activePlatform(),base=draft.layout_bases[platform];if(base===undefined||draft.layout_last[platform]!==draft[contentKey()])return;draft[contentKey()]=base;draft.layout_last[platform]=base;draft.blog_layouts[platform]={preset:"manual",...layoutPresets.manual};$("body").value=base;markDirty();updateBodyCount();if(preview)renderPreview();renderMissionChecklist();renderLayout();$("layoutStatus").textContent="적용 전 줄바꿈으로 되돌렸어요.";});

function writingPreferences(){
 try{const p=JSON.parse(localStorage.getItem("mellow-writing-preferences")||"{}");return {tone:typeof p.tone==="string"&&p.tone.length<=100?p.tone:"밝고 자연스러운 일상 후기체",language:p.language==="en"?"en":"ko",template:p.template==="clean"?"clean":"reference"};}catch{return {};}
}
function preferredPlatforms(){
 try{const p=JSON.parse(localStorage.getItem("mellow-selected-platforms")||"null");if(Array.isArray(p))return [...new Set(p.filter(x=>["naver","instagram","tistory","threads"].includes(x)))];}catch{}return ["naver"];
}
function selectedPlatforms(){return [...$("destinationChoices").querySelectorAll("input:checked")].map(input=>input.value);}
function restoreDestinations(){
 const values=Array.isArray(draft.selected_platforms)?draft.selected_platforms:Object.keys(platformInfo).filter(p=>draft[platformInfo[p].body]?.trim());
 const chosen=values.length||Array.isArray(draft.selected_platforms)?values:["naver"];
 $("destinationChoices").querySelectorAll("input").forEach(input=>input.checked=chosen.includes(input.value));draft.selected_platforms=[...chosen];
}
function setWorkflow(stage,state=""){workflow={stage,state};draft.workspace_step=stage;renderWorkflow();}
function renderWorkspace(){
 window.LibraryUI?.refresh();window.PublicationUI?.refresh();
 const stage=workflow.stage,writing=workflow.state==="writing"&&busy,chosen=selectedPlatforms(),currentPhotos=window.BlockWorkspace?.photos()||draft.images;
 document.body.dataset.workspaceStep=String(stage);document.body.dataset.writing=String(writing);
 $("composeCard").hidden=stage!==1;$("resultCard").hidden=stage!==2;$("transferCard").hidden=stage!==3;$("preparationAside").hidden=stage!==1;
 $("workspacePanels").setAttribute("role",stage===1?"region":"tabpanel");
 if(stage===1){$("workspacePanels").removeAttribute("aria-labelledby");$("workspacePanels").setAttribute("aria-label","이야기 준비");}else{$("workspacePanels").removeAttribute("aria-label");$("workspacePanels").setAttribute("aria-labelledby",platformInfo[activePlatform()].tab);}
 for(const [p,info] of Object.entries(platformInfo)){const button=$(info.tab);button.tabIndex=p===activePlatform()?0:-1;button.setAttribute("aria-controls","workspacePanels");}
 $("workspaceContext").hidden=stage===1||writing;$("workspaceTools").hidden=stage!==2||!workspaceToolsOpen||writing;
 $("editSettings").setAttribute("aria-expanded",String(stage===2&&workspaceToolsOpen));$("editSettings").hidden=stage===3;
 const tools=stage===1?$("prepareOptions"):$("workspaceTools");
 for(const id of ["moreOptions","writingOptions","threadsOptions"])if($(id).parentElement!==tools)tools.append($(id));
 $("threadsOptions").hidden=stage===1?!chosen.includes("threads"):tab!=="threads";
 const checks=stage===3?$("transferChecks"):$("resultCard");if($("validationPanel").parentElement!==checks){if(stage===3)checks.append($("validationPanel"));else checks.insertBefore($("validationPanel"),$("resultCard").querySelector(".stage-next"));}
 const headings={1:["오늘의 이야기를 시작해 볼까요?","사진과 짧은 메모면 충분해요. 나머지는 함께 다듬어요.","이야기 준비"],2:[writing?"당신의 이야기를 만들고 있어요":"조금 더 나다운 문장으로.",writing?"준비한 사진과 메모를 선택한 곳에 맞게 정리하고 있어요.":"글과 사진을 읽어 보고, 마음에 드는 모습으로 다듬어요.","글 다듬기"],3:["이제, 이야기를 전할 차례예요.","빠진 내용이 없는지 살펴보고 원하는 곳으로 옮겨요.","확인하고 옮기기"]};
 $("workspaceHeading").textContent=headings[stage][0];$("workspaceDescription").textContent=headings[stage][1];$("workspaceCrumb").textContent=headings[stage][2];
 const labels=chosen.map(p=>platformInfo[p].label);$("generationSummary").textContent=chosen.length?labels.join(" · ")+" 글을 만들어요":"올릴 곳을 하나 이상 골라 주세요";
 $("destinationHint").textContent=chosen.length?chosen.length+"곳 선택 · 고른 곳에 어울리는 글만 만들어요.":"올릴 곳을 하나 이상 골라 주세요.";
 $("destinationChoices").parentElement.dataset.empty=String(!chosen.length);$("generate").disabled=busy||!chosen.length;
 $("saveWorkspace").disabled=busy;$("continueToTransfer").disabled=busy||!$("body").value.trim();
 for(const id of ["backToPrepare","backToEdit","editSettings","prepareStyleEdit"])$(id).disabled=busy;
 $("destinationChoices").querySelectorAll("input").forEach(input=>input.disabled=busy);
 const ready=(id,text,value)=>{const node=$(id);node.textContent=text;node.classList.toggle("is-ready",Boolean(value));};
 ready("prepPhotos",draft.images.length?"사진 "+draft.images.length+"장 준비됐어요":"사진을 골라 주세요 · 선택",draft.images.length);
 ready("prepMemo",$("prompt").value.trim()?"나의 경험이 담겼어요":"나의 경험 한 줄",$("prompt").value.trim());
 ready("prepChannels",chosen.length?"올릴 곳 "+chosen.length+"곳 선택":"올릴 곳 선택",chosen.length);
 $("prepareStyleSummary").textContent=$("writingOptionsSummary").textContent;
 if(stage===3){const info=platformInfo[activePlatform()],raw=$("body").value.replace(/\[\[photo:\d+\]\]/g,"");$("transferChannel").textContent=info.label;$("transferStoryTitle").textContent=tab==="blog"?$("title").value||"제목 없는 이야기":raw.trim().slice(0,65)||"나의 이야기";
 $("transferMeta").textContent=$("charCount").textContent+" · 사진 "+(tab==="threads"&&!$("threadsPhotos").checked?0:currentPhotos.length)+"장";
 const image=$("transferThumbnail");image.hidden=!currentPhotos.length||(tab==="threads"&&!$("threadsPhotos").checked);if(!image.hidden){if(tab!=="blog"&&window.ChannelUI)window.ChannelUI.transferThumbnail(image,currentPhotos[0],activePlatform());else image.src="/media/"+currentPhotos[0]+".jpg";}
 $("transferExpectation").textContent=tab==="blog"?"글과 사진을 "+info.label+" 편집기로 옮겨요. 내용을 확인하고 마지막 발행은 블로그에서 직접 눌러 주세요.":"확인 후 ‘"+info.label+"에 발행하기’를 누르면 연결된 계정에 공개돼요.";
 $("publish").disabled=busy||!raw.trim()||(tab==="blog"&&!$("title").value.trim())||(tab==="instagram"&&!(window.ChannelUI?.photos("instagram")||draft.images).length);
 }
}
function renderWorkflow(){
 const editorOpen=!$("editor").hidden,content=editorOpen&&$("body").value.trim();
 const canMove=Boolean(content&&(tab==="instagram"?(window.ChannelUI?.photos("instagram")||draft.images).length:tab==="threads"?true:$("title").value.trim()));
 const {stage,state}=workflow;$("workflow").dataset.stage=String(stage);$("workflow").dataset.state=state;$("lastStepLabel").textContent="확인하고 옮기기";
 $("workflowHint").textContent=state==="writing"?"선택한 플랫폼의 글을 만들고 있어요.":state==="error"?"안내를 확인한 뒤 이어서 작업해 주세요.":stage===1?"사진과 메모로 시작해요.":stage===2?"원고를 자유롭게 다듬어요.":"확인한 뒤 글을 옮기거나 게시해요.";
 document.querySelectorAll(".step-button").forEach(button=>{const n=Number(button.dataset.step),done=n<stage||(n===3&&["ready","published"].includes(state));button.disabled=busy||(n===2&&!editorOpen&&$("writingProgress").hidden)||(n===3&&!canMove);button.classList.toggle("is-current",n===stage);button.classList.toggle("is-done",done);button.classList.toggle("is-attention",n===3&&["error","partial"].includes(state));if(n===stage)button.setAttribute("aria-current","step");else button.removeAttribute("aria-current");button.querySelector(".step-mark").textContent=done?"✓":String(n);button.querySelector(".step-state").textContent=n===stage?"현재 작업":"";button.title=button.disabled?"앞의 작업을 먼저 마쳐 주세요.":"이 작업으로 이동";});
 renderWorkspace();
}
function goWorkspace(stage,check=false){
 if(busy)return;sync();setWorkflow(stage);
 // Returning to the editor preserves the user's chosen edit/preview mode.
 $("workflow").scrollIntoView({behavior:matchMedia("(prefers-reduced-motion: reduce)").matches?"auto":"smooth",block:"start"});
 const target=$(stage===1?"prompt":stage===3?"backToEdit":"previewToggle");target.focus({preventScroll:true});
 if(stage===3&&check)void reviewCurrent().catch(error=>notify(error.message));
}
document.querySelectorAll(".step-button").forEach(button=>button.addEventListener("click",()=>goWorkspace(Number(button.dataset.step),Number(button.dataset.step)===3)));
$("backToPrepare").addEventListener("click",()=>goWorkspace(1));$("backToEdit").addEventListener("click",()=>goWorkspace(2));$("continueToTransfer").addEventListener("click",()=>goWorkspace(3,true));
$("saveWorkspace").addEventListener("click",()=>$("save").click());
$("editSettings").addEventListener("click",()=>{workspaceToolsOpen=!workspaceToolsOpen;renderWorkspace();});
$("prepareStyleEdit").addEventListener("click",()=>{$("writingOptions").open=true;$("writingOptions").scrollIntoView({block:"center",behavior:matchMedia("(prefers-reduced-motion: reduce)").matches?"auto":"smooth"});$("tone").focus({preventScroll:true});});
$("workspaceContext").querySelector('[role="tablist"]').addEventListener("keydown",event=>{
 if(busy||!["ArrowLeft","ArrowRight","Home","End"].includes(event.key))return;event.preventDefault();const platforms=Object.keys(platformInfo),current=platforms.indexOf(activePlatform()),index=event.key==="Home"?0:event.key==="End"?platforms.length-1:(current+(event.key==="ArrowRight"?1:-1)+platforms.length)%platforms.length;switchPlatform(platforms[index],false);$(platformInfo[platforms[index]].tab).focus();
});
$("workspaceTools").addEventListener("keydown",event=>{if(event.key==="Escape"){event.preventDefault();workspaceToolsOpen=false;renderWorkspace();$("editSettings").focus();}});
$("destinationChoices").addEventListener("change",()=>{draft.selected_platforms=selectedPlatforms();try{localStorage.setItem("mellow-selected-platforms",JSON.stringify(draft.selected_platforms));}catch{}markDirty();});
for(const id of ["tone","language","template"])$(id).addEventListener("change",()=>{try{localStorage.setItem("mellow-writing-preferences",JSON.stringify({tone:$("tone").value,language:$("language").value,template:$("template").value}));}catch{}});
$("dropzone").addEventListener("click",()=>$("photos").click());
for(const id of ["prompt"])$(id).addEventListener("focus",()=>{if(!busy)setWorkflow(1);});
for(const id of ["title","body"])$(id).addEventListener("focus",()=>{if(!busy)setWorkflow(2);});
function notify(message){$("toast").textContent=message;$("toast").classList.add("show");clearTimeout(notify.timer);notify.timer=setTimeout(()=>$("toast").classList.remove("show"),6500);}
async function api(path, body){
 let response,result;
 try{response=await fetch(path,{method:body===undefined?"GET":"POST",headers:body===undefined?{}:{"Content-Type":"application/json","X-Studio-Token":token},body:body===undefined?undefined:JSON.stringify(body)});}
 catch{window.WorkspaceHelp?.apiError(path,"network");throw Error("앱과 연결이 끊겼어요. 실행 창이 켜져 있는지 확인해 주세요. 발행 중이었다면 계정에서 결과를 먼저 확인하고 다시 시도해 주세요.");}
 try{result=await response.json();}catch{window.WorkspaceHelp?.apiError(path,"invalid_response");throw Error("앱 응답을 읽지 못했어요. 작성 중인 내용은 그대로 두고 앱 실행 상태를 확인해 주세요.");}
 if(!response.ok){
  if(path.startsWith("/api/naver/")||path.startsWith("/api/tistory/")){showProgress(result.error||"네이버 전달 요청이 실패했어요.");showNaverDiagnostic({stage:"전달 준비 · 앱 검사",detail:result.error});}
  const message=result.error||"요청을 처리하지 못했어요.";
  if(path==="/api/drafts"){showProgress(message);dirty=true;markDirty();}
  if(result.code==="delivery_conflict"){$("saveConflict").hidden=false;showProgress(message);}
  const error=Error(message);error.code=result.code;throw error;
 }return result;
}
async function copyWithFallback(value,message){if(window.WorkspaceHelp)return window.WorkspaceHelp.copyText(value,message);await navigator.clipboard.writeText(value);notify(message);}
function run(fn){return async(...args)=>{try{await fn(...args);}catch(e){notify(e.message);}};}
function sync(){draft.campaign_count_spaces=$("campaign_count_spaces").checked;draft.research=$("research").checked;draft.campaign_enabled=$("campaignEnabled").checked;draft.threads_community=$("threadsCommunity").checked;draft.threads_networking=$("threadsNetworking").checked;for(const id of campaignTextFields)draft[id]=$(id).value;for(const id of campaignNumberFields)draft[id]=Number($(id).value);draft.language=$("language").value;draft.threads_tone=$("threadsTone").value;draft.threads_include_images=$("threadsPhotos").checked;draft.prompt=$("prompt").value;draft.style=$("style").value;draft.tone=$("tone").value;draft.template=$("template").value;draft.facts=$("facts").value;draft.disclosure=$("disclosure").value;if(tab==="blog")draft[titleKey()]=$("title").value;if(!$("editor").hidden)draft[contentKey()]=$("body").value;draft.editing_platform=activePlatform();draft.selected_platforms=selectedPlatforms();draft.workspace_step=workflow.stage;}
function markDirty(){
 ++editEpoch;
 if($("naverDiagnostic").classList.contains("is-success")){$("naverDiagnostic").hidden=true;$("naverDiagnostic").dataset.relevant="false";$("jobProgress").hidden=true;}
 if(["ready","partial","published","prepared","error"].includes(workflow.state))workflow={stage:workflow.stage,state:""};
 dirty=true;recoveryReady=false;renderWorkflow();renderSaveState();clearTimeout(markDirty.timer);
 markDirty.timer=setTimeout(persistRecovery,800);
}
function persistRecovery(){
 if(!dirty)return;
 try{sync();localStorage.setItem("dajeong-recovery",JSON.stringify({draft,saved:Date.now()}));recoveryReady=true;renderSaveState();}catch{recoveryReady=false;renderSaveState(true);}
}
function photoChanged(){
 draft.layout_bases={};draft.layout_last={};generationUndo={};renderUndo();renderLayout();
 if(anyContent()){$("photoChangeHint").hidden=false;$("photoChangeHint").textContent="준비 사진을 바꿨어요. 이미 작성한 블로그의 사진 배치는 유지해요. 글 속 사진은 ‘글 다듬기’에서 추가하거나 빼 주세요.";}
}
function movePreparedPhoto(from,to){
 window.ChannelUI?.freeze();
 const prior=[...draft.images];[draft.images[from],draft.images[to]]=[draft.images[to],draft.images[from]];
 for(const [p,field] of [["naver","blog"],["tistory","tistory"]])if(!draft.blog_documents?.[p])draft[field]=(draft[field]||"").replace(/\[\[photo:(\d+)\]\]/g,(marker,n)=>{const at=draft.images.indexOf(prior[Number(n)-1]);return at>=0?"[[photo:"+(at+1)+"]]":"";});
 if(tab==="blog")$("body").value=draft[contentKey()];
}
function removePhoto(index){
 window.ChannelUI?.freeze();
 draft.images.splice(index,1);
 for(const [platform,field] of [["naver","blog"],["tistory","tistory"]])if(!draft.blog_documents?.[platform])draft[field]=(draft[field]||"").replace(/\[\[photo:(\d+)\]\]/g,(marker,n)=>Number(n)===index+1?"":Number(n)>index+1?"[[photo:"+(Number(n)-1)+"]]":marker);
 if(tab==="blog")$("body").value=draft[contentKey()];
}
function renderCampaign(){
 const enabled=$("campaignEnabled").checked;$("campaignPanel").hidden=!enabled;
 if(!enabled)clearDisclosureHelp();
 $(enabled?"campaignDisclosureSlot":"disclosureHome").append($("disclosureField"));
 if(enabled)$("missionDetails").insertBefore($("tagField"),$("missionDetails").querySelector(".campaign-length"));else $("tagHome").append($("tagField"));
 $("personalMode").classList.toggle("is-selected",!enabled);$("campaignMode").classList.toggle("is-selected",enabled);
 $("personalMode").setAttribute("aria-pressed",String(!enabled));$("campaignMode").setAttribute("aria-pressed",String(enabled));
 renderTagChips();renderMissionChecklist();updateOptionSummaries();
}
function renderTagChips(){
 const box=$("tagChips");box.replaceChildren();
 const tags=[...new Set($("hashtags").value.split(/[#,\s]+/).filter(Boolean))];
 for(const tag of tags.slice(0,30)){const chip=document.createElement("span");chip.textContent="#"+tag;box.append(chip);}
 $("copyTags").hidden=tab!=="blog"||!tags.length;
}
function renderMissionChecklist(){
 updateBodyCount();if(window.CampaignUI){window.CampaignUI.schedule();return;}
 const box=$("campaignChecklist");box.replaceChildren();box.hidden=!(tab==="blog"&&$("campaignEnabled").checked);if(box.hidden)return;
 const title=document.createElement("strong");title.textContent="업체 미션 확인";const overview=document.createElement("summary");overview.append(title);box.append(overview);
 const edit=document.createElement("button");edit.type="button";edit.className="mission-edit";edit.textContent="미션 수정";edit.disabled=busy;edit.onclick=event=>{event.preventDefault();focusIssue({field:"campaign_brand"});$("campaignPanel").open=true;$("missionDetails").open=true;};overview.append(edit);
 const specs=[];const words=id=>[...new Set($(id).value.split(/[,\n]+/).map(x=>x.trim()).filter(Boolean))];
 const count=(value,word)=>{
  if(/[가-힣]/.test(word))return value.replace(/\s/g,"").toLocaleLowerCase().split(word.replace(/\s/g,"").toLocaleLowerCase()).length-1;
  let n=0,offset=0;const hay=value.replace(/\s+/g," ").toLocaleLowerCase(),needle=word.replace(/\s+/g," ").toLocaleLowerCase();
  while((offset=hay.indexOf(needle,offset))>=0){if(!/[\p{L}\p{N}_]/u.test(hay[offset-1]||"")&&!/[\p{L}\p{N}_]/u.test(hay[offset+needle.length]||""))n++;offset+=Math.max(1,needle.length);}return n;
 };
 const body=(tab==="blog"?$("body").value:draft.blog)||"";
 const prose=body.replace(/\[\[photo:\d+\]\]/g,"").replace(/(?<![\p{L}\p{N}_])#[\p{L}\p{N}_]+/gu,"").replace(/^##\s+/gm,"");
 const brand=$("campaign_brand").value.trim();if(brand)specs.push({label:"업체·제품 이름",ok:count($("title").value+" "+prose,brand)>0});
 for(const word of words("title_keywords"))specs.push({label:"제목 · "+word,ok:count($("title").value,word)>0});
 for(const word of words("body_keywords")){const n=count(prose,word),min=Number($("keyword_min_count").value);specs.push({label:"본문 · "+word+"  "+n+"/"+min+"회",ok:n>=min});}
 for(const phrase of $("required_phrases").value.split("\n").filter(x=>x.trim()))specs.push({label:"필수 문구 · "+phrase.slice(0,40),ok:body.replace(/\s/g,"").includes(phrase.trim().replace(/\s/g,""))});
 const actualTags=new Set([...body.matchAll(/#([\p{L}\p{N}_]+)/gu)].map(match=>match[1].toLocaleLowerCase()));
 for(const tag of $("hashtags").value.split(/[#,\s]+/).filter(Boolean))specs.push({label:"태그 · #"+tag,ok:actualTags.has(tag.toLocaleLowerCase())});
 const photoCount=(window.BlockWorkspace?.photos()||draft.images).length;
 const chars=Number($("campaign_min_chars").value),maxChars=Number($("campaign_max_chars").value),charCount=Array.from($("campaign_count_spaces").checked?prose.replace(/[\r\n]/g,""):prose.replace(/\s/g,"")).length,photos=Number($("campaign_min_photos").value);
 if(chars)specs.push({label:"본문 "+charCount+"/"+chars+"자",ok:charCount>=chars});
 specs.push({label:"본문 "+charCount+"/"+(maxChars||5000)+"자 이내",ok:charCount<=(maxChars||5000)});
 if(photos)specs.push({label:"사진 "+photoCount+"/"+photos+"장",ok:photoCount>=photos});
 specs.push({label:$("disclosure").value==="none"?"제공받은 내용 · 종류를 골라 주세요":"제공받은 내용 · "+$("disclosure").selectedOptions[0].textContent,ok:$("disclosure").value!=="none",field:"disclosure"});
 const missing=specs.filter(item=>!item.ok).length;title.textContent=missing?"업체 미션 · "+missing+"개 확인 필요":"업체 미션 · 모두 충족했어요";
 const list=document.createElement("ul");specs.forEach(item=>{const li=document.createElement("li");li.className=item.ok?"is-met":"is-missing";li.textContent=(item.ok?"✓ ":"○ ")+item.label;if(!item.ok&&item.field==="disclosure"){const choose=document.createElement("button");choose.type="button";choose.className="disclosure-choose";choose.textContent="선택하기";choose.disabled=busy;choose.onclick=showDisclosureHelp;li.append(choose);}if(!item.ok&&item.field!=="disclosure"){const fix=document.createElement("button");fix.type="button";fix.className="issue-fix";fix.textContent="이유·수정 위치 확인";fix.disabled=busy;fix.onclick=run(()=>reviewCurrent(true));li.append(fix);}list.append(li);});box.append(list);
 const note=document.createElement("small");note.textContent="업체 안내문의 세부 조건·사실 여부는 직접 확인해 주세요. 발행 준비 시 서버에서 다시 검사해요.";box.append(note);
}
for(const [id,enabled] of [["personalMode",false],["campaignMode",true]])$(id).addEventListener("click",()=>{sync();$("campaignEnabled").checked=enabled;if(enabled){$("campaignPanel").open=true;}renderCampaign();markDirty();});
for(const id of [...campaignTextFields,...campaignNumberFields])$(id).addEventListener("input",()=>{markDirty();renderTagChips();renderMissionChecklist();});
for(const id of ["threadsCommunity","threadsNetworking"])$(id).addEventListener("change",markDirty);
$("campaign_count_spaces").addEventListener("change",()=>{markDirty();renderMissionChecklist();});
for(const id of [...campaignTextFields,...campaignNumberFields,"campaign_count_spaces","title","body","disclosure"])$(id).addEventListener("input",()=>{
 validateLength();if(!issuesVisible)return;const sequence=++issueSequence,platform=activePlatform();clearTimeout(showQuality.timer);showQuality.timer=setTimeout(async()=>{if(busy||sequence!==issueSequence||platform!==activePlatform())return;try{sync();const result=await api("/api/review",{...draft,review_channel:platform==="tistory"?"tistory":tab});if(sequence===issueSequence&&!busy&&platform===activePlatform())showQuality(result.checks);}catch{}},500);
});
$("copyTags").addEventListener("click",run(async()=>{const tags=[...new Set($("hashtags").value.split(/[#,\s]+/).filter(Boolean))];await copyWithFallback(tags.join(", "),"태그를 복사했어요. 네이버 발행창의 태그 칸에 붙여넣어 주세요.");}));

function resetPlaceSearch(){
 $("placeQuery").value="";$("placeName").value="";$("placeAddress").value="";$("placeResults").replaceChildren();$("placeManual").open=false;$("placePanel").open=false;
 $("placeSearchStatus").textContent="지역과 지점명을 함께 적으면 더 정확하게 찾을 수 있어요.";
}
function renderPlace(changed=false){
 const place=draft.selected_place;
 $("selectedPlace").hidden=!place;$("placeSummary").textContent=place?"장소 바꾸기":"어디에 다녀왔나요?";
 $("selectedPlaceName").textContent=place?.name||"";$("selectedPlaceAddress").textContent=place?(place.road_address||place.address):"";
 $("placeContextHint").hidden=!place&&!changed;
 $("placeContextHint").textContent=changed&&(draft.blog||draft.tistory||draft.instagram||draft.threads)?"장소를 바꿨어요. 이미 만든 글은 그대로예요. 바뀐 장소로 쓰려면 글을 다시 만들어 주세요.":place?($("research").checked?"이 이름과 주소를 기준으로 검색해요. 확인하기 어려운 상세정보는 넣지 않아요.":"이 장소를 글의 기준으로 사용해요. 영업시간 등도 찾고 싶다면 아래 ‘필요한 정보도 찾아서 담기’를 켜 주세요."):"장소 선택을 해제했어요. 메모에 적은 이야기로 글을 만들 수 있어요.";
 $("researchHint").textContent=place?"선택한 장소의 이름과 주소를 함께 확인해요. 다른 지점이거나 확인하기 어려운 정보는 빼요.":"선택한 장소가 있으면 그 주소를 기준으로 찾아요. 지점이 불분명한 정보는 빼요.";
}
function choosePlace(place){
 if(busy)return;
 draft.selected_place=place;$("placeResults").replaceChildren();$("placePanel").open=false;renderPlace(true);updateOptionSummaries();markDirty();
}
$("placeSearch").addEventListener("click",run(async()=>{
 if(busy)return;
 const query=$("placeQuery").value.trim();if(query.length<2)return notify("장소 이름과 지역을 함께 적어 주세요. 예: 성수 퍼프아웃");
 lock(true);$("placeSearch").textContent="찾는 중…";$("placeSearchStatus").textContent="이름과 주소가 함께 나오는 장소를 찾고 있어요. 잠시만 기다려 주세요.";$("placeResults").replaceChildren();
 try{
  const job=await api("/api/places/search",{query});const result=await waitJob(job.job,()=>{});
  $("placeSearchStatus").textContent=(result.notice||"").replace("검색에는 소액의 AI 이용료가 들어요.","").trim()||"이름과 주소를 확인한 뒤 골라 주세요.";
  if(!result.places.length){$("placeSearchStatus").textContent="주소까지 확인할 수 있는 장소를 찾지 못했어요. 지역·지점명을 더 적거나 아래에서 직접 입력해 주세요.";$("placeManual").open=true;}
  for(const place of result.places){
   const row=document.createElement("div");row.className="place-result";
   const text=document.createElement("div"),name=document.createElement("strong"),address=document.createElement("p"),category=document.createElement("small"),button=document.createElement("button");
   name.textContent=place.name;address.textContent=place.road_address||place.address;category.textContent=place.category||"이름·주소를 확인해 주세요";text.append(name,address,category);button.type="button";button.className="secondary";button.textContent="여기로 선택";button.setAttribute("aria-label",place.name+" · "+(place.road_address||place.address)+" 선택");button.addEventListener("click",()=>choosePlace(place));row.append(text,button);$("placeResults").append(row);
  }
 }catch(error){$("placeSearchStatus").textContent=error.message;$("placeManual").open=true;}
 finally{$("placeSearch").textContent="장소 찾기";lock(false);}
}));
$("placeQuery").addEventListener("keydown",event=>{if(event.key==="Enter"&&!event.isComposing){event.preventDefault();$("placeSearch").click();}});
$("placeUseManual").addEventListener("click",()=>{
 const name=$("placeName").value.trim(),address=$("placeAddress").value.trim();if(!name||!address)return notify("장소 이름과 전체 주소를 함께 적어 주세요.");
 choosePlace({name,address,road_address:"",branch:"",category:"",url:""});
});
$("placeClear").addEventListener("click",()=>{if(busy)return;draft.selected_place=null;resetPlaceSearch();renderPlace(true);updateOptionSummaries();markDirty();});
$("research").addEventListener("change",()=>{markDirty();renderPlace();});
renderPlace();

function renderPhotos(){
 $("photoOrderHint").hidden=!draft.images.length;
 $("photoCount").textContent=draft.images.length+" / 10장";$("photoGrid").replaceChildren();
 draft.images.forEach((id,i)=>{
 const box=document.createElement("div");box.className="photo";const img=document.createElement("img");img.src="/media/"+id+".jpg";img.alt="사진 "+(i+1);const view=document.createElement("button");view.type="button";view.className="photo-open";view.setAttribute("aria-label","사진 "+(i+1)+" 크게 보기");view.disabled=busy;view.append(img);view.onclick=()=>openPhoto(i);box.append(view);
 function button(label,cls,action){const b=document.createElement("button");b.type="button";b.textContent=label;b.className=cls;b.disabled=busy;b.addEventListener("click",()=>{if(busy)return;sync();action();photoChanged();renderPhotos();markDirty();if(preview)renderPreview();});return b;}
 const remove=button("×","remove",()=>removePhoto(i));remove.setAttribute("aria-label","사진 "+(i+1)+" 삭제");box.append(remove);
 const controls=document.createElement("div");controls.className="photo-controls";
 if(i>0){const b=button("←","",()=>movePreparedPhoto(i,i-1));b.setAttribute("aria-label","사진 앞으로 이동");controls.append(b);}
 const n=document.createElement("small");n.textContent=i+1;controls.append(n);
 if(i<draft.images.length-1){const b=button("→","",()=>movePreparedPhoto(i,i+1));b.setAttribute("aria-label","사진 뒤로 이동");controls.append(b);}box.append(controls);$("photoGrid").append(box);
 });renderWorkflow();renderMissionChecklist();}
async function addPhotos(files){
 if(busy)return;window.ChannelUI?.freeze();
 setWorkflow(1);lock(true);try{
 for(const file of files){
 if(draft.images.length>=10){notify("사진은 최대 10장까지 넣을 수 있어요.");break;}
 if(file.size>10_000_000){notify(file.name+": 10MB 이하 사진을 선택해 주세요.");continue;}
 if(!["image/jpeg","image/png","image/webp"].includes(file.type)){notify("JPG, PNG, WebP 사진을 선택해 주세요.");continue;}
 const data=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result.split(",")[1]);r.onerror=()=>reject(Error("사진을 읽지 못했어요."));r.readAsDataURL(file);});
 const result=await api("/api/upload",{data});draft.images.push(result.id);renderPhotos();markDirty();photoChanged();if(preview)renderPreview();
 }$("photos").value="";}finally{lock(false);}
}
$("photos").addEventListener("change",e=>{const files=[...e.target.files];uploadQueue=uploadQueue.then(run(()=>addPhotos(files)));});
for(const ev of ["dragover","dragleave","drop"])$("dropzone").addEventListener(ev,e=>{e.preventDefault();$("dropzone").classList.toggle("drag",ev==="dragover");if(ev==="drop"){const files=[...e.dataTransfer.files];uploadQueue=uploadQueue.then(run(()=>addPhotos(files)));}});
function showEditor(){$("emptyResult").hidden=true;$("editor").hidden=false;renderTab();setWorkflow(2);}
function renderTab(){
 $("threadsTab").classList.toggle("active",tab==="threads");$("threadsTab").setAttribute("aria-selected",String(tab==="threads"));$("threadsOptions").hidden=tab!=="threads";$("threadsManual").hidden=tab!=="threads";
 $("tistoryTab").classList.toggle("active",tab==="blog"&&blogDestination==="tistory");
 $("tistoryTab").setAttribute("aria-selected",String(tab==="blog"&&blogDestination==="tistory"));
 $("tistorySettings").hidden=!(tab==="blog"&&blogDestination==="tistory");if(!$("tistorySettings").hidden&&!$("tistoryUrl").value.trim())$("tistorySettings").open=true;
 $("blogTab").classList.toggle("active",tab==="blog"&&blogDestination==="naver");$("instaTab").classList.toggle("active",tab==="instagram");
 $("blogTab").setAttribute("aria-selected",tab==="blog"&&blogDestination==="naver");$("instaTab").setAttribute("aria-selected",tab==="instagram");
 $("title").hidden=tab!=="blog";$("body").maxLength=tab==="threads"?1000:tab==="instagram"?4400:30000;$("body").value=draft[contentKey()]||"";$("title").value=draft[titleKey()]||"";
 $("editorLabel").textContent=platformInfo[activePlatform()].label+" 초안";$("export").hidden=tab!=="blog";
 $("naverTestControls").hidden=tab!=="blog";
 $("publishLabel").textContent=tab==="blog"?"블로그에 이야기 담기":"인스타그램에 이야기 담기";
 $("publishHint").textContent=tab==="blog"?"평소 쓰는 네이버로 글과 사진을 옮겨드려요. 확인 후 발행만 눌러 주세요.":"연결된 인스타그램에 글과 사진을 올려요.";
 $("publish").textContent=tab==="blog"?"블로그로 옮기기 ↗":"인스타에 올리기 ↗";
 $("editorHint").textContent=preview?"고치고 싶다면 ‘글 수정’을 눌러 주세요.":(tab==="blog"?"제목과 본문을 자유롭게 다듬어 주세요.":"본문을 자유롭게 다듬어 주세요.");
 $("naverDiagnostic").hidden=tab!=="blog"||$("naverDiagnostic").dataset.relevant!=="true";
 if(tab==="blog"&&blogDestination==="tistory"){
  $("publishLabel").textContent="티스토리에 이야기 담기";$("publishHint").textContent="글과 사진을 티스토리로 옮겨요. 마지막 발행은 직접 눌러 주세요.";$("publish").textContent="티스토리로 옮기기 ↗";
 }
 if(tab==="threads"){$("editorLabel").textContent="Threads 초안";$("publishLabel").textContent="Threads에 이야기 건네기";$("publishHint").textContent="연결한 Threads 계정에 글과 선택한 사진을 발행해요. 마지막 확인 후 공개됩니다.";$("publish").textContent="Threads에 발행하기 ↗";}
 const missing=draft.selective_generation&&!draft[contentKey()]?.trim()&&manualPlatform!==activePlatform();
 $("platformEmpty").hidden=!missing;
 if(missing){$("emptyResult").hidden=true;$("editor").hidden=true;$("platformEmptyTitle").textContent=platformInfo[activePlatform()].label+" 글은 아직 만들지 않았어요";}
 else if(anyContent()||manualPlatform===activePlatform()){$("editor").hidden=false;$("emptyResult").hidden=true;}
 for(const [p,info] of Object.entries(platformInfo))$(info.tab).classList.toggle("not-generated",draft.selective_generation&&!draft[info.body]?.trim());
 renderUndo();updateBodyCount();if(preview&&!missing)renderPreview();renderSources();renderWorkflow();renderTagChips();renderMissionChecklist();renderLayout();updateOptionSummaries();window.BlockWorkspace?.refresh();window.WritingUI?.refresh();window.ChannelUI?.refresh();
}
function updateBodyCount(){
 const raw=$("body").value,isBlog=tab==="blog",campaign=$("campaignEnabled").checked;
 const prose=raw.replace(/\[\[photo:\d+\]\]/g,"").replace(/(?<![\p{L}\p{N}_])#[\p{L}\p{N}_]+/gu,"").replace(/^##\s+/gm,"");
 const spaces=$("campaign_count_spaces").checked;
 const value=Array.from(isBlog?(spaces?prose.replace(/[\r\n]/g,""):prose.replace(/\s/g,"")):raw).length;
 const maximum=isBlog?(campaign?Math.max(1,Math.min(Number($("campaign_max_chars").value)||5000,5000)):5000):tab==="threads"?500:2200;
 const minimum=isBlog&&campaign?Number($("campaign_min_chars").value)||0:0;
 const state=value>maximum?"long":minimum&&value<minimum?"short":minimum&&value?"fit":"neutral";
 $("charCount").textContent=value.toLocaleString()+" / "+maximum.toLocaleString()+"자";
 $("lengthMeter").dataset.state=state;
 $("lengthTrack").setAttribute("aria-valuemax",String(maximum));$("lengthTrack").setAttribute("aria-valuenow",String(Math.min(value,maximum)));$("lengthTrack").setAttribute("aria-valuetext",value+"자, 최대 "+maximum+"자");
 $("lengthTrack").firstElementChild.style.width=Math.min(100,value/maximum*100)+"%";
 const unit=isBlog?(spaces?"공백 포함 · 줄바꿈 제외":"공백 제외"):"공백·줄바꿈 포함";
 $("lengthStatus").textContent=unit+" · "+(state==="long"?"상한보다 "+(value-maximum).toLocaleString()+"자 많아요":state==="short"?"최소 "+minimum.toLocaleString()+"자까지 "+(minimum-value).toLocaleString()+"자 더 필요해요":state==="fit"?"분량 조건을 충족했어요":isBlog?"제목·태그·사진 표시는 제외해요":"이모지도 글자 수에 포함해요");
}

function renderSources(){
 // 검색 근거는 초안 데이터에 보관하고 작성 화면에는 링크를 노출하지 않는다.
 $("sourceBox").replaceChildren();$("sourceDetails").hidden=true;
}

function renderPreview(){
 $("editorHint").textContent="고치고 싶다면 ‘글 수정’을 눌러 주세요.";
 sync();const box=$("preview");box.replaceChildren();box.classList.toggle("reference-style",tab==="blog"&&draft.template!=="clean");
 box.classList.toggle("tistory-preview",tab==="blog"&&blogDestination==="tistory");box.classList.toggle("clean-style",draft.template==="clean");box.classList.toggle("instagram-preview",tab==="instagram"||tab==="threads");box.classList.toggle("threads-preview",tab==="threads");box.classList.toggle("english-preview",(draft.platform_languages?.[activePlatform()]||draft.language)==="en");
 const add=(tag,value)=>{const el=document.createElement(tag);el.textContent=value;box.append(el);};
 const photo=(id,n)=>{const img=document.createElement("img");img.src="/media/"+id+".jpg";img.alt="사진 "+n;photoPreviewAction(img,n-1);box.append(img);};
 if(tab==="blog"){
  const doc=window.BlockWorkspace?.ensure(),images=doc?window.StoryBlocks.photos(doc):draft.images;add("h3",draft[titleKey()]||"");
  if(doc){box.classList.toggle("reference-style",doc.template!=="clean");box.classList.toggle("clean-style",doc.template==="clean");let n=0;for(const block of doc.blocks){if(block.type==="photo"){const img=document.createElement("img");img.src="/media/"+block.image_id+".jpg";img.alt=block.caption||"사진 "+(n+1);n++;img.className="can-enlarge";img.tabIndex=0;img.setAttribute("role","button");const at=images.indexOf(block.image_id);img.onclick=()=>openPhoto(at,images);img.onkeydown=e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();img.click();}};box.append(img);if(block.caption)add("p",block.caption);}else{const paragraph=document.createElement(block.type==="heading"?"h2":"p");paragraph.textContent=block.text;paragraph.className="preview-editable";paragraph.tabIndex=0;paragraph.setAttribute("role","button");paragraph.setAttribute("aria-label","이 문단 수정");paragraph.title="눌러서 이 문단 수정";paragraph.onclick=()=>window.BlockWorkspace.focus({block_id:block.id});paragraph.onkeydown=e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();paragraph.click();}};box.append(paragraph);}}}
  else{for(const line of (draft[contentKey()]||"").split("\n"))if(line.trim()&&!line.includes("[[photo:"))add(line.startsWith("## ")?"h2":"p",line.replace(/^## /,""));draft.images.forEach((id,i)=>photo(id,i+1));}
 }
 else if(window.ChannelUI){window.ChannelUI.renderPreview(box);}
 else{
  if(draft.images.length){
   const label=document.createElement("small");label.className="insta-photo-label";label.textContent="사진 "+draft.images.length+"장 · "+(tab==="threads"?($("threadsPhotos").checked?"함께 올릴 순서":"사진은 발행하지 않아요"):"올릴 순서");box.append(label);
   const strip=document.createElement("div");strip.className="insta-photo-strip";strip.setAttribute("role","region");strip.setAttribute("aria-label","인스타그램 사진 순서");strip.tabIndex=0;
   draft.images.forEach((id,i)=>{const item=document.createElement("figure"),img=document.createElement("img"),number=document.createElement("figcaption");img.src="/media/"+id+".jpg";img.alt="사진 "+(i+1);number.textContent=String(i+1);photoPreviewAction(img,i);item.append(img,number);strip.append(item);});box.append(strip);
  }
  add("p",draft[contentKey()]||"");
 }
}
function switchPlatform(platform,offer=true){
 if(busy)return;clearIssueMarks();issuesVisible=false;++issueSequence;$("qualityBox").hidden=true;sync();manualPlatform=null;
 tab=["naver","tistory"].includes(platform)?"blog":platform;if(tab==="blog")blogDestination=platform;
 $("naverDiagnostic").hidden=true;$("naverDiagnostic").dataset.relevant="false";$("jobProgress").hidden=true;workflow={stage:workflow.stage===3&&draft[contentKey()]?.trim()?3:anyContent()?2:1,state:""};renderTab();
 // Missing channel drafts are offered inline; switching tabs never starts generation.
}
$("blogTab").addEventListener("click",()=>switchPlatform("naver"));
$("instaTab").addEventListener("click",()=>switchPlatform("instagram"));
$("threadsTab").addEventListener("click",()=>switchPlatform("threads"));
$("threadsTone").addEventListener("change",()=>{markDirty();});
$("threadsPhotos").addEventListener("change",()=>{markDirty();sync();if(preview)renderPreview();});
$("threadsSettings").addEventListener("click",run(async()=>{status=await api("/api/status");openThreadsSettings();}));
$("language").addEventListener("change",()=>{markDirty();$("languageHint").textContent=$("language").value==="en"?"메모는 한국어로 적어도 괜찮아요. 글 만들기를 누르면 자연스러운 영어로 새로 작성해요.":"선택한 언어로 새 글을 만들어요. 이미 만든 글은 자동으로 바뀌지 않아요.";});
$("tistoryTab").addEventListener("click",()=>switchPlatform("tistory"));
try{$("tistoryUrl").value=localStorage.getItem("mellow-tistory-url")||"";}catch{}
async function detectTistory(){
 let id;try{id=localStorage.getItem("dajeong-extension");}catch{}
 if(!id)throw Error("크롬의 Mellow 확장에서 앱과 연결하기를 먼저 눌러 주세요.");
 const result=await extensionMessage(id,{type:"tistoryBlogs"});
 if(!result?.ok)throw Error("확장을 새로고침한 뒤 다시 눌러 주세요.");
 const select=url=>{$("tistoryUrl").value=url;$("tistoryUrl").dispatchEvent(new Event("input"));};
 if(result.blogs?.length===1){select(result.blogs[0]);notify("열린 티스토리 블로그를 가져왔어요.");return true;}
 if(!result.blogs?.length)throw Error("티스토리 블로그나 관리 화면을 크롬에 열어 둔 뒤 다시 눌러 주세요.");
 const box=modal("어느 블로그에 올릴까요?");
 result.blogs.forEach(url=>{const button=document.createElement("button");button.className="secondary";button.textContent=url;button.style.cssText="display:block;width:100%;margin:10px 0";button.onclick=()=>{select(url);$("modal").close();};box.append(button);});
 return false;
}
$("detectTistory").addEventListener("click",run(detectTistory));
if($("tistoryUrl").value)$("tistoryDetected").textContent=$("tistoryUrl").value;
$("tistoryUrl").addEventListener("input",()=>{$("tistoryDetected").textContent=$("tistoryUrl").value.trim()||"블로그를 선택해 주세요.";try{localStorage.setItem("mellow-tistory-url",$("tistoryUrl").value.trim());}catch{}});
$("manualStart").addEventListener("click",()=>{if(!anyContent()){const first=selectedPlatforms()[0]||"naver";switchPlatform(first,false);}manualPlatform=activePlatform();showEditor();if(tab==="blog"&&window.BlockWorkspace)window.BlockWorkspace.focus({});else $("body").focus();});
$("previewToggle").addEventListener("click",()=>{sync();preview=!preview;setWorkflow(2);$("editFields").hidden=preview;$("preview").hidden=!preview;$("previewToggle").textContent=preview?"글 수정":"미리보기";$("editorHint").textContent=preview?"고치고 싶다면 ‘글 수정’을 눌러 주세요.":(tab==="blog"?"제목과 본문을 자유롭게 다듬어 주세요.":"본문을 자유롭게 다듬어 주세요.");if(preview)renderPreview();else window.BlockWorkspace?.refresh();});
for(const id of ["prompt","style","tone","title","body","facts","disclosure","template"])$(id).addEventListener("input",()=>{markDirty();if(id==="body"){updateBodyCount();renderLayout();}renderMissionChecklist();});
function showProgress(message){
 if(tab==="blog"&&blogDestination==="tistory")message=message.replaceAll("네이버","티스토리");
 const element=$("jobProgress");element.hidden=false;element.textContent=message;
}
async function waitJob(job,onProgress){
 const deadline=Date.now()+660000;
 while(Date.now()<deadline){
  await new Promise(r=>setTimeout(r,1200));const r=await api("/api/jobs/"+job);
  if(onProgress)onProgress(r);else if(r.message)showProgress(r.message);
  if(r.state==="done")return r.result;
  if(r.state==="failed"){showProgress(r.error);const error=Error(r.error);error.code=r.code;throw error;}
 }
 const message="작업 결과를 확인하지 못했어요. 자동 재시도하지 말고 열린 편집기나 계정에서 결과를 확인해 주세요.";
 showProgress(message);throw Error(message);
}
function lock(value){
 busy=value;window.PublicationUI?.lock();window.GenerationRecovery?.refresh();window.CampaignUI?.lock(value);window.WritingUI?.lock(value);window.ChannelUI?.lock(value);window.LibraryUI?.lock(value);window.KitsUI?.lock(value);if(value){++issueSequence;clearTimeout(showQuality.timer);}
 for(const id of ["generate","save","copy","export","publish","newDraft","showDrafts","showHistory","manualStart","photos","dropzone","prompt","style","tone","title","body","blogTab","instaTab","threadsTab","threadsTone","threadsPhotos","threadsSettings","threadsManual","language","layoutWidth","layoutLines","layoutApply","layoutUndo","platformGenerate","platformWriteManual","placeQuery","placeSearch","placeName","placeAddress","placeUseManual","placeClear","personalMode","campaignMode","copyTags","threadsCommunity","threadsNetworking","campaign_count_spaces",...campaignTextFields,...campaignNumberFields,"tistoryTab","tistoryUrl","detectTistory","previewToggle","undoGeneration","saveConflictCopy","saveConflictLoad","research","settingsButton","facts","disclosure","review","template","naverRepeat","naverManual"])$(id).disabled=value;
 document.querySelectorAll("[data-example],[data-layout],.place-result button,.disclosure-choose,.issue-fix,.library-row,.library-controls input,.library-controls select").forEach(b=>b.disabled=value);renderPhotos();
 renderSaveState();renderUndo();renderWorkflow();window.BlockWorkspace?.refresh();
}
let writingTimer=null,writingStarted=0,writingStage=1;
function updateWriting(job){
 if(Number.isInteger(job.stage))writingStage=job.stage;
 if(job.message)$("writingMessage").textContent=job.message;
 document.querySelectorAll(".writing-stages li").forEach((el,i)=>{
  el.classList.toggle("is-done",i+1<writingStage);el.classList.toggle("is-active",i+1===writingStage);
  if(i+1===writingStage)el.setAttribute("aria-current","step");else el.removeAttribute("aria-current");
 });
}
function startWriting(){
 clearInterval(writingTimer);writingStarted=Date.now();writingStage=1;
 $("writingProgress").hidden=false;$("writingProgress").dataset.state="running";
 $("resultCard").classList.add("is-writing");$("resultCard").setAttribute("aria-busy","true");
 $("writingTitle").textContent="이야기를 만들고 있어요";$("writingNote").hidden=false;
 const elapsed=()=>{$("writingElapsed").textContent=Math.floor((Date.now()-writingStarted)/1000)+"초째, 정성껏 쓰는 중";};
 elapsed();writingTimer=setInterval(elapsed,1000);updateWriting({stage:1,message:"사진과 메모를 준비하고 있어요."});
 $("writingProgress").scrollIntoView({behavior:matchMedia("(prefers-reduced-motion: reduce)").matches?"auto":"smooth",block:"center"});
}
function finishWriting(error){
 clearInterval(writingTimer);$("resultCard").classList.remove("is-writing");$("resultCard").setAttribute("aria-busy","false");
 $("writingProgress").dataset.state=error?"error":"done";$("writingTitle").textContent=error?"글 만들기를 마치지 못했어요":"오늘의 이야기, 완성됐어요";
 $("writingMessage").textContent=error||"아래에서 글과 사진을 확인해 주세요.";$("writingNote").hidden=true;
 $("writingElapsed").textContent=Math.floor((Date.now()-writingStarted)/1000)+"초 소요";
 if(!error){updateWriting({stage:5});$("writingProgress").hidden=true;}
}
async function offerGeneration(platforms,additional=false){
 if(window.GenerationRecovery&&!window.GenerationRecovery.beforeGenerate())return;
 await uploadQueue;if(busy)return;sync();if(platforms.some(p=>["naver","tistory"].includes(p))&&!validateLength()){focusIssue({field:"campaign_min_chars"});return;}if(!draft.prompt.trim()){focusIssue({field:"prompt"});return notify("어떤 이야기를 쓰고 싶은지 한 줄만 알려 주세요.");}
 if(!platforms.length){notify("올릴 곳을 하나 이상 골라 주세요.");goWorkspace(1);return;}
 if(!status.ai){openSettings();return;}
 if(additional){openPlatformPicker(platforms,true);return;}
 const existing=platforms.filter(p=>draft[platformInfo[p].body]?.trim());
 if(existing.length&&!confirm(existing.map(p=>platformInfo[p].label).join(" · ")+" 글을 새로 만들까요? 지금 원고는 ‘이전 글로’에서 되돌릴 수 있어요."))return;
 await generateForPlatforms(platforms,false);
}
function openPlatformPicker(platforms=[activePlatform()],additional=false){
 const box=modal(additional?platformInfo[platforms[0]].label+" 글도 만들까요?":"어디에 올릴 글을 만들까요?");
 para(box,additional?"이 플랫폼 글만 새로 만들어요. 이미 완성한 다른 글은 그대로 둘게요.":"고른 플랫폼만 작성해요. 다른 플랫폼은 나중에 추가할 수 있어요.");
 const choices=document.createElement("div");choices.className="platform-choices";box.append(choices);
 for(const p of (additional?platforms:Object.keys(platformInfo))){
  const row=document.createElement("label"),input=document.createElement("input"),text=document.createElement("span"),name=document.createElement("strong"),note=document.createElement("small");input.type="checkbox";input.value=p;input.id="platformChoice-"+p;input.checked=platforms.includes(p);name.textContent=platformInfo[p].label;note.textContent=draft[platformInfo[p].body]?.trim()?"선택하면 이 원고를 다시 써요":"새 글 만들기";text.append(name,note);row.append(input,text);choices.append(row);
 }
 const hint=document.createElement("p");hint.className="hint";hint.textContent="선택한 플랫폼의 글만 만들어요. 다른 원고는 그대로 유지해요.";box.append(hint);
 const start=document.createElement("button");start.id="startSelectedGeneration";start.className="primary";start.style.width="100%";
 const selected=()=>[...choices.querySelectorAll("input:checked")].map(input=>input.value);
 const update=()=>{const count=selected().length;start.disabled=!count;start.textContent=count?(count===1?platformInfo[selected()[0]].label+" 글만 만들기":count+"곳에 어울리는 글 만들기"):"플랫폼을 하나 이상 골라 주세요";};choices.addEventListener("change",update);update();
 start.addEventListener("click",run(async()=>{const chosen=selected();if(!chosen.length)return;$("modal").close();await generateForPlatforms(chosen,additional);}));box.append(start);
}
async function generateForPlatforms(platforms,additional,lengthRevision=false){
 if(window.GenerationRecovery&&!window.GenerationRecovery.beforeGenerate())return;
 if(window.CampaignUI&&!await window.CampaignUI.beforeGenerate(platforms))return;
 await uploadQueue;if(busy)return;sync();if(platforms.some(p=>["naver","tistory"].includes(p))&&!validateLength()){focusIssue({field:"campaign_min_chars"});return;}if(!draft.prompt.trim()){focusIssue({field:"prompt"});return notify("어떤 이야기를 쓰고 싶은지 한 줄만 알려 주세요.");}
 const contextFields=["prompt","tone","style","facts","disclosure","language","template","threads_tone","threads_community","threads_networking","campaign_enabled","blog_layouts","campaign_count_spaces","selected_place","research","images",...campaignTextFields,...campaignNumberFields];
 const request=Object.fromEntries(contextFields.map(key=>[key,draft[key]]));request.campaign_brief_review={hash:draft.campaign_brief_review?.hash||""};request.voice_styles=Object.fromEntries(platforms.filter(p=>draft.voice_styles?.[p]).map(p=>[p,draft.voice_styles[p]]));request.platforms=platforms;request.reuse_research=additional;request.channel_images=Object.fromEntries(platforms.filter(p=>["instagram","threads"].includes(p)).map(p=>[p,window.ChannelUI?.selected(p)||draft.images]));if(lengthRevision){request.images=[...(window.BlockWorkspace?.photos()||draft.images)];request.language=draft.platform_languages?.[activePlatform()]||draft.language;request.seed={title:draft[titleKey()]||"",body:draft[contentKey()]||""};}
 lock(true);setWorkflow(2,"writing");$("generate").textContent="✦ 이야기를 만드는 중…";startWriting();$("writingNote").textContent=platforms.map(p=>platformInfo[p].label).join(" · ")+" 글만 만들어요. 다른 원고는 그대로 유지해요.";
 try{
  const job=await api(lengthRevision?"/api/blog/expand":"/api/generate",request);window.GenerationRecovery?.begin(job.job,platforms,request);const result=await waitJob(job.job,updateWriting);
  for(const p of platforms){const info=platformInfo[p];if(typeof result[info.body]!=="string"||!result[info.body].trim()||(info.title&&(typeof result[info.title]!=="string"||!result[info.title].trim())))throw Error("선택한 플랫폼의 글을 확인하지 못했어요. 기존 글은 그대로 두었어요.");}
  rememberGeneration(platforms,result);window.ChannelUI?.generated(platforms,request);
  for(const p of platforms){const info=platformInfo[p];draft[info.body]=result[info.body];if(info.title)draft[info.title]=result[info.title];draft.platform_languages[p]=request.language;}
  if(platforms.includes("instagram")){draft.facts_translation=result.facts_translation||"";draft.facts_translation_source=result.facts_translation_source||"";}
  draft.layout_bases={...draft.layout_bases,...result.layout_bases};draft.layout_last={...draft.layout_last,...result.layout_last};
  draft.sources=[...new Map([...(draft.sources||[]),...(result.sources||[])].map(source=>[source.url,source])).values()];draft.selective_generation=true;draft.generation=result.generation;manualPlatform=null;window.BlockWorkspace?.generated(platforms,request.images,lengthRevision);for(const p of platforms)if(generationUndo[p])generationUndo[p].afterBody=draft[platformInfo[p].body];
  const destination=platforms.includes(activePlatform())?activePlatform():platforms[0];tab=["naver","tistory"].includes(destination)?"blog":destination;if(tab==="blog")blogDestination=destination;
  $("title").value=draft[titleKey()]||"";$("body").value=draft[contentKey()]||"";markDirty();showEditor();preview=true;$("editFields").hidden=true;$("preview").hidden=false;$("previewToggle").textContent="글 수정";renderPreview();showQuality(result.checks||[]);
  $("photoChangeHint").hidden=true;renderMissionChecklist();if(draft.campaign_enabled){$("campaignPanel").open=false;$("moreOptions").open=false;}finishWriting();window.GenerationRecovery?.completed();notify(result.needs_more_notes?"초안은 준비됐지만 분량 조건이 남아 있어요. 실제 경험 메모를 더 적고 이 초안에서 보완해 주세요.":result.needs_length_revision?"초안이 최대 분량을 넘어 일부 설명을 줄여야 해요. 이 초안에서 분량을 맞춰 주세요.":"고른 플랫폼의 글을 완성했어요. 내 경험과 같은지 읽어 주세요.");
 }catch(error){finishWriting(error.message);setWorkflow(2,"error");throw error;}
 finally{lock(false);$("generate").textContent="선택한 곳에 맞춰 글 만들기 →";}
}
$("generate").addEventListener("click",run(()=>offerGeneration(selectedPlatforms())));
$("platformGenerate").addEventListener("click",run(()=>offerGeneration([activePlatform()],true)));
$("platformWriteManual").addEventListener("click",()=>{manualPlatform=activePlatform();preview=false;$("preview").hidden=true;$("editFields").hidden=false;showEditor();if(tab==="blog"&&window.BlockWorkspace)window.BlockWorkspace.focus({});else $("body").focus();});
async function saveDraft(alreadyLocked=false){
 await uploadQueue;if(busy&&!alreadyLocked)throw Error("진행 중인 작업이 끝난 뒤 다시 눌러 주세요.");
 sync();if(!alreadyLocked)lock(true);
 try{
  draft=await api("/api/drafts",draft);$("saveConflict").hidden=true;dirty=false;clearTimeout(markDirty.timer);try{localStorage.removeItem("dajeong-recovery");}catch{}
  $("body").value=draft[contentKey()]||"";updateBodyCount();renderLayout();if(preview)renderPreview();renderTagChips();renderMissionChecklist();if(draft.campaign_enabled){$("campaignPanel").open=false;$("moreOptions").open=false;}$("saveState").textContent="저장 완료";window.LibraryUI?.saved();window.GenerationRecovery?.saved();window.PublicationUI?.saved();return draft;
 }catch(error){dirty=true;persistRecovery();if(error.code==="draft_conflict")$("saveConflict").hidden=false;throw error;}finally{if(!alreadyLocked)lock(false);}
}
$("save").addEventListener("click",run(async()=>{await saveDraft();notify("이야기를 이 컴퓨터에 저장했어요.");}));
$("copy").addEventListener("click",run(async()=>{sync();const value=(tab==="blog"?(draft[titleKey()]||"")+"\n\n":"")+(draft[contentKey()]||"").replace(/\[\[photo:\d+\]\]/g,"").trim();await copyWithFallback(value,"본문을 복사했어요.");}));
$("export").addEventListener("click",run(async()=>{await uploadQueue;if(busy)return;const platform=activePlatform();lock(true);try{const saved=await saveDraft(true);const r=await fetch("/export/"+saved.id+(platform==="tistory"?"?platform=tistory":""));if(!r.ok)throw Error("내보내기를 완료하지 못했어요.");const blob=await r.blob(),u=URL.createObjectURL(blob),a=document.createElement("a");a.href=u;a.download=(saved[platformInfo[platform].title]||"나의 이야기").replace(/[<>:"/\\|?*]/g,"_")+".html";a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);notify("글과 사진을 파일로 보관했어요.");}finally{lock(false);}}));
function clearDisclosureHelp(){
 $("disclosure").removeAttribute("aria-invalid");$("disclosureHelp").classList.remove("disclosure-attention");
 if($("jobProgress").dataset.reason==="disclosure"){$("jobProgress").hidden=true;delete $("jobProgress").dataset.reason;}
}
function showDisclosureHelp(){
 for(let parent=$("disclosure").parentElement;parent;parent=parent.parentElement)if(parent.tagName==="DETAILS")parent.open=true;
 $("disclosure").setAttribute("aria-invalid","true");
 $("disclosureHelp").classList.add("disclosure-attention");
 const message="체험단 후기는 제공받은 종류를 골라 주세요. 제품·식사/이용권·광고비 중 선택하면 돼요. 직접 구매한 후기라면 ‘일상·솔직한 후기’로 바꿔 주세요.";
 showProgress(message);$("jobProgress").dataset.reason="disclosure";notify(message);
 $("disclosure").scrollIntoView({behavior:matchMedia("(prefers-reduced-motion: reduce)").matches?"auto":"smooth",block:"center"});
 $("disclosure").focus({preventScroll:true});
}
$("disclosure").addEventListener("change",()=>{clearDisclosureHelp();if($("disclosure").value!=="none")notify("제공 안내를 선택했어요. 다시 ‘블로그로 옮기기’를 누르면 글 첫머리에 반영해요.");});
$("publish").addEventListener("click",run(async()=>{
 await uploadQueue;if(busy)return;sync();if(tab==="blog"&&!validateLength()){focusIssue({field:"campaign_min_chars"});return;}
 if(tab==="blog"&&draft.campaign_enabled&&draft.disclosure==="none"){showDisclosureHelp();return;}
 lock(true);
 try{
 sync();
 if(tab==="threads"){
  if(!draft.threads.trim()){showProgress("Threads에 올릴 이야기를 먼저 적어 주세요.");return;}
  if(Array.from(draft.threads).length>500){showProgress("Threads 글을 500자 이내로 줄여 주세요.");return;}
  status=await api("/api/status");
  const channelImages=window.ChannelUI?.selected("threads")||draft.images;const include=$("threadsPhotos").checked&&channelImages.length>0;
  if(!status.threads||(include&&!status.threads_details?.media_ready)){openThreadsSettings(include&&!status.threads_details?.media_ready);return;}
  await saveDraft(true);
  const inspected=await api("/api/review",{...draft,review_channel:"threads"});showQuality(inspected.checks);
  const errors=inspected.checks.filter(item=>item.level==="error");if(errors.length){setTimeout(()=>focusIssue(errors[0]),0);throw Error("표시된 내용을 수정한 뒤 Threads에 발행해 주세요.");}
  if(window.DeliveryUI?!await window.DeliveryUI.confirm("threads",include):!confirm("이 글을 연결된 Threads 계정에 지금 공개 발행할까요?"))return;
  setWorkflow(3,"sending");showProgress("Threads 발행을 준비하고 있어요.");
  try{
   const job=await api("/api/publish/threads",{id:draft.id,updated:draft.updated,with_images:include,confirm:true});
   const result=await waitJob(job.job);showProgress("Threads에 발행했어요. 게시물 ID: "+result.media_id);setWorkflow(3,"published");notify("Threads에 이야기를 올렸어요.");
  }catch(error){setWorkflow(3,"error");showProgress(error.message);throw error;}
  return;
 }
 if(tab==="instagram"&&(!(window.ChannelUI?.photos("instagram")||draft.images).length||!draft.instagram.trim())){showProgress(!(window.ChannelUI?.photos("instagram")||draft.images).length?"인스타그램에 올릴 사진을 먼저 골라 주세요.":"인스타그램에 올릴 글을 먼저 적어 주세요.");return;}
 if(tab==="blog"&&blogDestination==="tistory"&&!$("tistoryUrl").value.trim()&&!await detectTistory())return;
 setWorkflow(3);status=await api("/api/status");
 if(tab==="blog"&&blogDestination==="naver"&&status.naver_guard?.blocked){showProgress("네이버 입력 잠금: "+status.naver_guard.reason);showNaverDiagnostic({stage:"네이버 보호 잠금",detail:status.naver_guard.reason});openSettings("blog");return;}
 if(tab==="blog"&&blogDestination==="tistory"&&status.tistory_guard?.blocked){showProgress("티스토리 입력 잠금: "+status.tistory_guard.reason);showNaverDiagnostic({stage:"티스토리 입력 잠금",detail:status.tistory_guard.reason});openSettings("blog");return;}
 if((tab==="blog"&&blogDestination==="naver"&&!status.naver)||(tab==="instagram"&&!status.instagram)){openSettings(tab);return;}
 await saveDraft(true);
 const checked=await api("/api/review",{...draft,review_channel:activePlatform()==="tistory"?"tistory":tab});showQuality(checked.checks);
 const blocking=checked.checks.filter(item=>item.level==="error"&&(tab==="blog"?!item.message.includes("인스타그램"):item.message.includes("인스타그램")));
 if(blocking.length){setTimeout(()=>focusIssue(blocking[0]),0);throw Error("수정할 항목 "+blocking.length+"개를 표시했어요. 표시된 이유를 보고 수정한 뒤 다시 옮겨 주세요.");}
 if(tab==="blog"){
  if(window.DeliveryUI&&!await window.DeliveryUI.confirm(activePlatform()))return;
  const handoff=await api(blogDestination==="tistory"?"/api/tistory/handoff":"/api/naver/handoff",{id:draft.id,updated:draft.updated,blog_url:$("tistoryUrl").value.trim(),repeat_confirm:$("naverRepeat").checked});await sendToNaver(handoff);return;
 }
 if(tab==="instagram"&&(window.DeliveryUI?!await window.DeliveryUI.confirm("instagram"):!confirm("이 글과 사진을 연결된 인스타그램 계정에 지금 공개 발행할까요?")))return;
 lock(true);setWorkflow(3,"sending");showProgress("발행 준비를 시작하고 있어요.");const target=tab;
 try{const j=await api(target==="blog"?"/api/naver/prepare":"/api/publish/instagram",{id:draft.id,updated:draft.updated,confirm:true});notify(target==="blog"?"네이버 브라우저를 열고 있어요. 열린 창에서 로그인을 진행해 주세요.":"인스타그램에서 사진을 처리하고 있어요.");const result=await waitJob(j.job);const message=target==="blog"?result.message:"인스타그램에 발행했어요. 게시물 ID: "+result.media_id;showProgress(message);setWorkflow(3,"published");notify(message);}
 catch(error){setWorkflow(3,"error");showProgress(error.message);throw error;}
 finally{lock(false);}
 }finally{lock(false);}
}));
function openThreadsComposer(){
  const box=modal("Threads에서 이어 쓰기");para(box,"아래 버튼을 누르면 준비한 본문을 Threads 작성 화면으로 가져가요. 사진은 직접 추가하고, 내용을 확인한 뒤 발행해 주세요.");
  const link=document.createElement("a");link.id="threadsComposerLink";link.href="https://www.threads.com/intent/post?text="+encodeURIComponent(draft.threads);link.target="_blank";link.rel="noopener noreferrer";link.className="primary threads-composer-link";link.textContent="Threads 작성 화면 열기 ↗";box.append(link);
  const copy=document.createElement("button");copy.className="secondary";copy.textContent="본문 복사";copy.onclick=run(async()=>{await copyWithFallback(draft.threads,"본문을 복사했어요. Threads에 붙여 넣어 주세요.");});box.append(copy);
 setWorkflow(3,"prepared");
}
$("threadsManual").addEventListener("click",run(async()=>{
 if(busy)return;await saveDraft();if(!draft.threads.trim())throw Error("Threads 글을 먼저 적어 주세요.");openThreadsComposer();
}));
function openThreadsSettings(needPhotos=false){
 const box=modal("Threads 연결");
 para(box,status.threads?"✓ Threads 계정 설정이 있어요.":"Threads 전용 연결이 한 번 필요해요. 인스타그램 설정과는 별개예요.");
 if(needPhotos)para(box,"사진을 함께 올리려면 아래에서 사진 연결을 켜 주세요. 사진 포함을 끄면 글만 발행할 수 있어요.");
 const check=document.createElement("button");check.className="secondary";check.id="threadsCheck";check.textContent="Threads 계정 연결 확인";
 const result=document.createElement("p");result.className="hint";
 check.onclick=run(async()=>{check.disabled=true;try{const response=await api("/api/threads/check",{});result.textContent=response.message+(response.username?" · @"+response.username:"");}catch(error){result.textContent=error.message;}finally{check.disabled=false;}});box.append(check,result);
 const help=document.createElement("details"),summary=document.createElement("summary");summary.textContent="처음 연결하는 방법";help.open=!status.threads;help.append(summary);
 para(help,"Meta 개발자 화면에서 Threads 사용 사례로 앱을 준비하고 계정을 연결해 주세요. threads_basic과 threads_content_publish 권한의 Threads 사용자 토큰이 필요해요.");
 para(help,"프로젝트의 .env에 THREADS_USER_ID(Threads 숫자 계정 ID), THREADS_ACCESS_TOKEN(Threads 전용 토큰)을 채우고 앱을 다시 실행해 주세요. 토큰을 채팅에 보내지 마세요.");
 para(help,"연결 확인은 계정과 토큰을 검사해요. 실제 발행 권한까지 성공을 보장하는 표시는 아니에요. 자세한 순서는 README.md에 있어요.");box.append(help);
 const connected=Boolean(status.threads_details?.temporary_connection);
 const media=document.createElement("button");media.className="secondary";media.id="threadsMediaConnection";media.textContent=connected?"사진 연결 끄기":"사진 연결 켜기";
 const mediaResult=document.createElement("p");mediaResult.className="hint";mediaResult.textContent=status.threads_details?.media_ready?"✓ 공개 사진 연결이 준비돼 있어요.":"사진 없이 글만 올릴 때는 공개 사진 연결이 필요 없어요.";
 media.onclick=run(async()=>{media.disabled=true;try{
  if(connected)await api("/api/media/disconnect",{});else{const job=await api("/api/media/connect",{});mediaResult.textContent="사진 연결을 준비하고 있어요…";await waitJob(job.job);}
  status=await api("/api/status");$("modal").close();openThreadsSettings();
 }catch(error){mediaResult.textContent=error.message;}finally{media.disabled=false;}});box.append(media,mediaResult);
 para(box,"사진 연결은 인스타그램과 함께 사용해요. 공개되는 것은 발행용으로 준비한 사진 경로뿐이에요.");
}
function extensionMessage(id,message){
 return new Promise((resolve,reject)=>{
  if(!globalThis.chrome?.runtime?.sendMessage)return reject(Error("크롬에서 앱을 열고 Mellow 도우미를 연결해 주세요."));
  chrome.runtime.sendMessage(id,message,result=>{
   const error=chrome.runtime.lastError;if(error)return reject(Error("확장 연결 실패: "+error.message+" / 크롬 오른쪽 위 Mellow 아이콘에서 ‘앱과 연결하기’를 다시 눌러 주세요."));
   resolve(result);
  });
 });
}
async function sendToNaver(handoff){
 let id;try{id=localStorage.getItem("dajeong-extension");}catch{}
 if(!/^[a-p]{32}$/.test(id||"")){showHandoff(handoff);return;}
 let timer,finished=false,dispatched=false;
 lock(true);setWorkflow(3,"sending");showProgress("네이버 글쓰기 화면을 열고 있어요.");
 try{
  const ping=await extensionMessage(id,{type:"ping"});if(!ping?.ok)throw Error(ping?.message||"도우미 연결 응답이 없어요.");
  if(ping.protocol!==2)throw Error("현재 확장 버전은 "+(ping.version||"확인 불가")+"예요. chrome://extensions에서 Mellow 확장을 새로고침하고 1.6.0 이상을 확인해 주세요.");
  timer=setInterval(()=>extensionMessage(id,{type:"status"}).then(state=>{if(!finished&&state?.message)showProgress(state.message);}).catch(()=>{}),1300);
  dispatched=true;const result=await extensionMessage(id,{type:"prepare",base:location.origin,code:handoff.code,writer_url:handoff.writer_url,channel:handoff.channel||"naver"});
  finished=true;clearInterval(timer);
  showProgress(result?.detail||result?.message||"네이버에 옮겨진 내용을 확인해 주세요.");showNaverDiagnostic(result);
 }catch(error){finished=true;showProgress(error.message);showNaverDiagnostic({ok:false,uncertain:dispatched,stage:"앱과 확장 연결",detail:dispatched?"도우미의 입력 결과를 확인하지 못했어요. 아래 ‘결과 확인·기록 다시 보내기’를 눌러 주세요. 글을 새로 넣지 않아요.":error.message});if(!dispatched)showHandoff(handoff);}
 finally{clearInterval(timer);lock(false);}
}
function showHandoff(handoff){
 const blogName=handoff.channel==="tistory"?"티스토리":"네이버";
 if(workflow.state!=="error")setWorkflow(3,"prepared");
 const box=modal(blogName+" 전달 · 코드로 직접 옮기기");
 para(box,"크롬 오른쪽 위의 Mellow 아이콘을 누르고 ‘앱과 연결하기’를 눌러 주세요. 다음부터는 ‘블로그로 옮기기’ 한 번이면 돼요.");
 const help=document.createElement("details");const summary=document.createElement("summary");summary.textContent="Mellow 아이콘이 안 보여요";help.append(summary);
 para(help,"처음 설치는 도와주시는 분과 한 번만 진행해 주세요. 크롬 주소창에 chrome://extensions를 입력하고 개발자 모드 → 압축해제된 확장 프로그램을 로드 → 아래 폴더를 선택합니다.");
 para(help,"프로젝트 폴더 안의 chrome-extension 폴더");box.append(help);
 const direct=document.createElement("details");const directTitle=document.createElement("summary");directTitle.textContent="전달 코드 복사";direct.open=true;direct.append(directTitle);
 const code=document.createElement("input");code.readOnly=true;code.value=handoff.code;code.style.width="100%";code.setAttribute("aria-label","일회용 전달 코드");direct.append(code);
 const copy=document.createElement("button");copy.className="secondary";copy.textContent="옮기기 번호 복사";
 copy.addEventListener("click",run(async()=>{await copyWithFallback(handoff.code,"번호를 복사했어요. "+blogName+"에서 Mellow 아이콘을 눌러 주세요.");}));direct.append(copy);
 const link=document.createElement("a");link.href=handoff.writer_url;link.target="_blank";link.rel="noopener noreferrer";link.textContent=" "+blogName+" 글쓰기 열기 ↗";direct.append(link);
 box.append(direct);
}
$("naverManual").addEventListener("click",run(async()=>{
 await uploadQueue;if(busy||tab!=="blog")return;sync();if(draft.campaign_enabled&&draft.disclosure==="none"){showDisclosureHelp();return;}
 lock(true);
 try{
  await saveDraft(true);const inspected=await api("/api/review",{...draft,review_channel:activePlatform()==="tistory"?"tistory":"blog"});showQuality(inspected.checks);const errors=inspected.checks.filter(item=>item.level==="error"&&!item.message.includes("인스타그램"));if(errors.length){setTimeout(()=>focusIssue(errors[0]),0);notify("표시된 항목의 이유를 보고 수정한 뒤 다시 옮겨 주세요.");return;}
  if(window.DeliveryUI&&!await window.DeliveryUI.confirm(activePlatform()))return;
  const handoff=await api(blogDestination==="tistory"?"/api/tistory/handoff":"/api/naver/handoff",{id:draft.id,updated:draft.updated,blog_url:$("tistoryUrl").value.trim(),repeat_confirm:$("naverRepeat").checked});showHandoff(handoff);
 }finally{lock(false);}
}));

function showNaverDiagnostic(result){
 const blogName=blogDestination==="tistory"?"티스토리":"네이버";
 const success=Boolean(result?.ok);setWorkflow(3,success?"ready":result?.contentReady?"partial":"error");
 const box=$("naverDiagnostic");box.replaceChildren();box.hidden=false;box.dataset.relevant="true";box.classList.toggle("is-success",success);
 const heading=document.createElement("strong");heading.textContent=success?"✓ "+blogName+"로 잘 옮겼어요":result?.contentReady?"서식을 한 번 확인해 주세요":"전달을 마치지 못했어요";box.append(heading);
 para(box,success?blogName+"에서 내용을 확인하고 마지막 발행을 눌러 주세요.":result?.detail||result?.message||"응답이 없어 결과를 확인하지 못했어요.");
 if(success)$("jobProgress").hidden=true;
 if(result?.reportPending||result?.uncertain){const warning=document.createElement("p");warning.textContent=result.recordingWarning||"입력 결과를 확인한 뒤 앱에 기록만 다시 보내요. 글·사진은 다시 넣지 않아요.";box.append(warning);const retry=document.createElement("button");retry.type="button";retry.className="secondary";retry.textContent="결과 확인·기록 다시 보내기";retry.onclick=run(async()=>{let id;try{id=localStorage.getItem("dajeong-extension");}catch{}if(!id)throw Error("Mellow 확장에서 결과를 확인해 주세요.");retry.disabled=true;try{const expectedDraft=draft.id,expectedPlatform=activePlatform();const response=await extensionMessage(id,{type:"retryReport",draftId:expectedDraft,channel:expectedPlatform});notify(response.message);if(response.ok&&response.result&&draft.id===expectedDraft&&activePlatform()===expectedPlatform)showNaverDiagnostic(response.result);}finally{retry.disabled=false;}});box.append(retry);}
 const details=document.createElement("details");details.className="diagnostic-details";details.open=!success;
 const summary=document.createElement("summary");summary.textContent="자세한 결과 · 문제 확인";details.append(summary);box.append(details);
 para(details,"확장 "+(result?.version||"버전 확인 안 됨")+" · "+(result?.stage||"결과 확인"));
 const format=result?.formatting;
 if(format?.requested)para(details,"정렬: "+(format.alignment?"적용 확인":"미적용 또는 확인 불가")+" / 글꼴: "+(format.font?"적용 확인":"미적용 또는 확인 불가")+" / 크기: "+(format.size?"적용 확인":"미적용 또는 확인 불가"));
 const diagnostic={version:result?.version,stage:result?.stage,reason:result?.detail||result?.message,formatting:format,diagnostics:result?.diagnostics};
 const raw=document.createElement("pre");raw.textContent=JSON.stringify(diagnostic,null,2);raw.style.cssText="white-space:pre-wrap;overflow-wrap:anywhere;font-size:11px";details.append(raw);
 const copy=document.createElement("button");copy.className="secondary";copy.textContent="진단 결과 복사";
 copy.addEventListener("click",run(async()=>{await copyWithFallback(JSON.stringify(diagnostic,null,2),"진단 결과를 복사했어요.");}));details.append(copy);
}
function frameModal(container,actions){
 const body=$("modalBody");if(!actions||actions.parentElement!==container||(container!==body&&!body.contains(container)))return;
 const scroll=document.createElement("div");scroll.className="modal-scroll-region";
 for(const node of [...container.childNodes])if(node!==actions)scroll.append(node);
 container.prepend(scroll);container.classList.add("modal-frame");actions.classList.add("modal-action-bar");
 if(container!==body)body.classList.add("modal-frame-host");
}
function modal(title){$("modal").dataset.view="";$("modalTitle").textContent=title;$("modalBody").replaceChildren();$("modalBody").classList.remove("modal-frame","modal-frame-host");$("modal").showModal();return $("modalBody");}
let issuesVisible=false,issueSequence=0;
function clearIssueMarks(){
 document.querySelectorAll("[data-mission-invalid]").forEach(field=>{field.removeAttribute("aria-invalid");delete field.dataset.missionInvalid;const ids=(field.getAttribute("aria-describedby")||"").split(" ").filter(id=>id&&!id.startsWith("issue-for-"));if(ids.length)field.setAttribute("aria-describedby",ids.join(" "));else field.removeAttribute("aria-describedby");});
 document.querySelectorAll(".mission-field-error").forEach(node=>node.remove());
}
function focusIssue(issue,editText=false){
 const id=editText?issue.target:issue.field;if(id==="body"&&tab==="blog"&&window.BlockWorkspace){window.BlockWorkspace.focus(issue);return;}const field=$(id);if(!field)return;setWorkflow(["body","title"].includes(id)?2:1);
 if(id==="body"||id==="title"){preview=false;$("preview").hidden=true;$("editFields").hidden=false;$("previewToggle").textContent="미리보기";window.BlockWorkspace?.refresh();}
 for(let parent=field.parentElement;parent;parent=parent.parentElement)if(parent.tagName==="DETAILS")parent.open=true;
 field.scrollIntoView({behavior:matchMedia("(prefers-reduced-motion: reduce)").matches?"auto":"smooth",block:"center"});field.focus({preventScroll:true});
 if(editText&&field.setSelectionRange){const range=window.BlockWorkspace?.range(field.value,issue.needle);const at=range?range[0]:issue.needle?field.value.indexOf(issue.needle):-1;field.setSelectionRange(at<0?field.value.length:at,range?range[1]:at<0?field.value.length:at+issue.needle.length);}
}
function validateLength(){
 const min=Number($("campaign_min_chars").value),max=Number($("campaign_max_chars").value);
 const outOfRange=![min,max].every(value=>Number.isInteger(value)&&value>=0&&value<=5000);
 const message=outOfRange?"본문 길이 조건은 0~5,000자 사이의 정수로 적어 주세요.":$("campaignEnabled").checked&&max>0&&min>max?"최소 글자 수가 최대보다 커요. 두 숫자를 확인해 주세요.":"";
 $("lengthError").hidden=!message;$("lengthError").textContent=message;return !message;
}
function showQuality(checks){
 queueMicrotask(()=>window.BlockWorkspace?.validity());
 clearIssueMarks();issuesVisible=true;checks=checks.filter(item=>!item.platform||item.platform===activePlatform());
 for(const item of checks.filter(item=>item.level==="error"&&item.field)){
  const field=$(item.field);if(!field)continue;field.dataset.missionInvalid="true";field.setAttribute("aria-invalid","true");
  const id="issue-for-"+item.field;let note=$(id);if(!note){note=document.createElement("small");note.id=id;note.className="mission-field-error";(field.closest("label")||field).insertAdjacentElement("afterend",note);field.setAttribute("aria-describedby",[field.getAttribute("aria-describedby"),id].filter(Boolean).join(" "));}note.textContent+=(note.textContent?" · ":"")+item.message;
 }

 const campaignErrors=window.CampaignUI?checks.filter(item=>item.message.startsWith("체험단 미션 ·")):[];const visibleChecks=checks.filter(item=>!campaignErrors.includes(item));
 const box=$("qualityBox");box.replaceChildren();box.hidden=!checks.length;box.classList.toggle("is-neutral",!checks.some(item=>item.level==="error"));
 const title=document.createElement("strong");title.textContent=checks.some(item=>item.level==="error")?"이 부분을 수정하면 옮길 수 있어요":"글 확인";box.append(title);
 const detail=document.createElement("details"),summary=document.createElement("summary");summary.textContent="참고할 내용 "+visibleChecks.filter(item=>item.level!=="error").length+"개";detail.append(summary);
 if(campaignErrors.length){const note=document.createElement("p");note.textContent="체험단 조건 "+campaignErrors.length+"개는 미션 목록에서 이유와 수정 위치를 확인해 주세요.";const jump=document.createElement("button");jump.type="button";jump.className="issue-fix";jump.textContent="미션 확인";jump.onclick=run(()=>window.CampaignUI.openChecks());note.append(jump);box.append(note);}
 for(const item of visibleChecks){const line=document.createElement("p");line.style.marginTop="7px";line.textContent=(item.level==="error"?"⛔ ":item.level==="warning"?"확인 · ":"안내 · ")+item.message;if(item.field){const button=document.createElement("button");button.type="button";button.className="issue-fix";button.disabled=busy;button.textContent="조건 수정";button.onclick=()=>focusIssue(item);line.append(button);if(["title","body"].includes(item.target)){const text=document.createElement("button");text.type="button";text.className="issue-fix";text.disabled=busy;text.textContent=item.target==="title"?"제목 수정":"본문 수정";text.onclick=()=>focusIssue(item,true);line.append(text);}}(item.level!=="error"?detail:box).append(line);}
 if(tab==="blog"&&checks.some(item=>item.level==="error"&&(["campaign_min_chars","campaign_max_chars"].includes(item.field)||item.code==="blog_length_limit"))){
  const short=checks.some(item=>item.level==="error"&&item.field==="campaign_min_chars");const note=document.createElement("p");note.className="length-followup";note.textContent=short?"조건을 낮추지 않고 이 초안에서 분량을 보완할 수 있어요. 내용이 부족하면 메뉴·이용 과정·구체적인 장단점 같은 실제 경험을 메모에 더해 주세요.":"조건을 바꾸지 않고 현재 초안의 핵심을 유지하며 분량을 줄일 수 있어요.";box.append(note);
  const more=document.createElement("button");more.type="button";more.className="secondary issue-fix";more.textContent="경험 메모 추가";more.disabled=busy;more.onclick=()=>window.CampaignUI?window.CampaignUI.experience():focusIssue({field:"facts"});if(short)box.append(more);
  const repair=document.createElement("button");repair.type="button";repair.className="secondary issue-fix length-repair";repair.textContent="이 초안에서 분량 보완";repair.disabled=busy;repair.onclick=run(()=>generateForPlatforms([activePlatform()],true,true));box.append(repair);
 }
 if(visibleChecks.some(item=>item.level!=="error"))box.append(detail);
}
async function reviewCurrent(scroll=false){
 if(busy||reviewInFlight)return;sync();const edit=editEpoch,nav=navigationEpoch,platform=activePlatform();reviewInFlight=true;$("review").disabled=true;
 try{const result=await api("/api/review",{...draft,review_channel:platform==="tistory"?"tistory":tab});if(edit!==editEpoch||nav!==navigationEpoch||platform!==activePlatform()){notify("점검하는 동안 글이 바뀌었어요. 현재 글을 다시 점검해 주세요.");return;}showQuality(result.checks);if(scroll)$("qualityBox").scrollIntoView({block:"center",behavior:matchMedia("(prefers-reduced-motion: reduce)").matches?"auto":"smooth"});}
 finally{reviewInFlight=false;$("review").disabled=busy;}
}
$("review").addEventListener("click",run(()=>reviewCurrent()));
$("closeModal").addEventListener("click",()=>$("modal").close());
$("modal").addEventListener("click",event=>{
 const dialog=$("modal");if(event.target!==dialog)return;
 const bounds=dialog.getBoundingClientRect();
 if(event.clientX<bounds.left||event.clientX>bounds.right||event.clientY<bounds.top||event.clientY>bounds.bottom)dialog.close();
});
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
  para(box,"네이버는 chrome-extension 폴더의 Mellow 확장을 설치해 사용해요. 기존 크롬의 빈 글쓰기 탭에서 전달 코드를 붙여 넣어 주세요. 별도 로그인 브라우저를 실행하지 않아요.");
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
  para(box,"연결 방식: "+(details.login_type==="unified"?"Instagram API 통합 로그인":details.login_type==="instagram"?"Instagram Login":"방식 선택 필요"));
  if(details.invalid.includes("INSTAGRAM_LOGIN_TYPE"))para(box,"토큰의 로그인 방식을 자동으로 구분하지 못했어요. 통합·Facebook 로그인에서 발급했다면 INSTAGRAM_LOGIN_TYPE=unified, Instagram Login에서 발급했다면 instagram으로 설정해 주세요. 토큰이 잘못됐다는 뜻은 아니에요.");
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
 if(!instagramOnly&&status.tistory_guard?.blocked){para(box,"티스토리 입력 잠금: "+status.tistory_guard.reason);const unlock=document.createElement("button");unlock.type="button";unlock.className="secondary";unlock.textContent="티스토리 정상 로그인 확인·입력 잠금 해제";unlock.onclick=run(async()=>{if(!confirm("공식 티스토리 화면에서 추가 인증을 완료하고 정상 로그인한 것을 확인하셨나요?"))return;await api("/api/tistory/unblock",{confirm:true});status=await api("/api/status");$("modal").close();openSettings("blog");});box.append(unlock);advanced.open=true;}
 para(box,"사진 주소는 임의의 예시가 아니라 실제로 사진을 읽을 수 있는 서버 주소여야 해요. localhost나 PC 폴더 경로는 사용할 수 없어요.");
 para(box,"임시 연결을 사용하면 PUBLIC_MEDIA_BASE_URL은 직접 입력하지 않아도 돼요. 고정 서버를 사용하려면 .env를 수정하고 start.cmd를 다시 실행해 주세요.");
 para(box,"설정됨은 값의 존재 여부예요. 토큰 권한이나 실제 발행 성공을 의미하지 않아요.");
}
$("settingsButton").addEventListener("click",run(async()=>{status=await api("/api/status");openSettings();}));
$("showDrafts").addEventListener("click",run(openLibrary));

function showToneGuide(){$("toneGuide").textContent=$("tone").selectedOptions[0]?.dataset.guide||"";}
$("tone").addEventListener("change",showToneGuide);
showToneGuide();
function loadDraft(){
 const requestedStep=draft.workspace_step;
 ++navigationEpoch;++editEpoch;workspaceToolsOpen=false;$("saveConflict").hidden=true;generationUndo={};recoveryReady=false;
 $("writingOptions").open=false;$("moreOptions").open=false;$("missionDetails").open=false;$("resultTools").open=false;
 issuesVisible=false;++issueSequence;clearIssueMarks();$("campaign_count_spaces").checked=draft.campaign_count_spaces===true;
 draft={...fresh(),...draft,blog_layouts:draft.blog_layouts||{},layout_bases:draft.layout_bases||{},layout_last:draft.layout_last||{},platform_languages:draft.platform_languages||{}};
 clearDisclosureHelp();restoreDestinations();
 $("research").checked=draft.research===true;resetPlaceSearch();renderPlace();
 $("photoChangeHint").hidden=true;
 manualPlatform=null;const preferred=draft.editing_platform;const first=platformInfo[preferred]?preferred:Object.keys(platformInfo).find(p=>draft[platformInfo[p].body]?.trim())||"naver";tab=["naver","tistory"].includes(first)?"blog":first;blogDestination=tab==="blog"?first:"naver";
 clearInterval(writingTimer);$("writingProgress").hidden=true;
 workflow={stage:1,state:""};$("naverDiagnostic").hidden=true;$("naverDiagnostic").dataset.relevant="false";$("jobProgress").hidden=true;$("naverTestControls").open=false;
 $("naverRepeat").checked=false;
 if(draft.tone&&!Array.from($("tone").options).some(option=>option.value===draft.tone)){
  const option=document.createElement("option");option.value=draft.tone;option.textContent=draft.tone;$("tone").append(option);
 }
 for(const id of ["prompt","style","tone","title","facts","disclosure","template","language"])$(id).value=draft[id]||(id==="disclosure"?"none":id==="template"?"reference":id==="language"?"ko":"");
 for(const id of campaignTextFields)$(id).value=draft[id]||"";
 for(const id of campaignNumberFields)$(id).value=draft[id]??(id==="keyword_min_count"?1:0);
 $("campaignEnabled").checked=Boolean(draft.campaign_enabled);$("threadsCommunity").checked=draft.threads_community!==false;$("threadsNetworking").checked=Boolean(draft.threads_networking);renderCampaign();
 $("threadsPhotos").checked=draft.threads_include_images!==false;$("threadsTone").value=draft.threads_tone||"casual";showToneGuide();updateOptionSummaries();$("qualityBox").hidden=true;
 clearTimeout(markDirty.timer);try{localStorage.removeItem("dajeong-recovery");}catch{};preview=Boolean(draft.blog||draft.tistory||draft.instagram||draft.threads);$("preview").hidden=!preview;$("editFields").hidden=preview;$("previewToggle").textContent=preview?"글 수정":"미리보기";dirty=false;renderPhotos();
 if(anyContent()){showEditor();setWorkflow([1,2,3].includes(requestedStep)?requestedStep:2);}else{$("editor").hidden=true;$("emptyResult").hidden=false;renderTab();setWorkflow(1);}
 renderSaveState();window.BlockWorkspace?.refresh(true);window.CampaignUI?.loaded();window.WritingUI?.loaded();window.ChannelUI?.loaded();window.LibraryUI?.loaded();window.KitsUI?.loaded();window.PublicationUI?.loaded();}
$("newDraft").addEventListener("click",()=>{if(busy)return;if(window.LibraryUI)return window.LibraryUI.startNew();if(dirty&&!confirm("저장하지 않은 내용을 버리고 새 이야기를 쓸까요?"))return;draft=fresh();loadDraft();$("editor").hidden=true;$("emptyResult").hidden=false;$("saveState").textContent="작성 대기";setWorkflow(1);$("prompt").focus();});
$("showHistory").addEventListener("click",run(async()=>{
 if(window.PublicationUI)return window.PublicationUI.history();
 const rows=await api("/api/history"),box=modal("내 글");libraryViews(box,true);if(!rows.length)para(box,"아직 발행한 이야기가 없어요. 네이버 도우미의 편집기 입력은 발행 기록에 포함되지 않아요.");
 const labels={published:"발행 완료",publishing:"진행 중 · 앱 재시작 뒤에는 계정 확인 필요",failed:"실패 · 다시 시도 가능",uncertain:"결과 확인 필요 · 계정에서 중복 여부 확인"};
 rows.forEach(r=>{const div=document.createElement("div");div.className="draft-row";div.textContent=(r.channel==="threads"?"Threads":"인스타그램")+" · "+(r.title||"제목 없는 이야기")+" · "+labels[r.state]+" · "+new Date(r.created*1000).toLocaleString("ko-KR");box.append(div);});
}));
const examples={여행:"여행지나 숙소에서 기억하고 싶은 장면: ",카페:"주말에 다녀온 카페를 소개하고 싶어. 친구에게 추천하듯 자연스럽게 써줘. 방문한 곳과 실제로 느낀 점: ",일상:"오늘의 소소한 순간을 일상 기록으로 남기고 싶어. 사진 속 장면을 중심으로 따뜻하지만 과하지 않게 써줘. 오늘 있었던 일: ",제품:"직접 써 본 제품의 후기를 쓰고 싶어. 좋았던 점과 아쉬운 점이 드러나는 솔직한 리뷰로 써줘. 제품 이름과 사용 경험: "};
document.querySelectorAll("[data-example]").forEach(b=>b.addEventListener("click",()=>{const current=$("prompt").value.trim(),example=examples[b.dataset.example];if(!current.includes(example.trim()))$("prompt").value=current?current+"\n\n"+example:example;$("prompt").focus();markDirty();}));
document.addEventListener("visibilitychange",()=>{if(document.hidden)persistRecovery();});
window.addEventListener("beforeunload",e=>{persistRecovery();if(dirty||busy){e.preventDefault();e.returnValue="";}});
api("/api/status").then(s=>{status=s;if(!s.ai){$("connectionNotice").hidden=false;$("connectionNotice").textContent="처음 한 번 글쓰기 연결이 필요해요. 오른쪽 위 ‘연결 설정’을 눌러 주세요.";}}).catch(e=>notify(e.message));


try{
 const stored=JSON.parse(localStorage.getItem("dajeong-recovery")||"null");
 if(stored?.draft&&Array.isArray(stored.draft.images)&&typeof stored.draft.blog==="string"&&confirm("이전에 저장하지 않은 글이 있어요. 복구할까요?")){
  draft={...fresh(),...stored.draft};if(!("tistory" in stored.draft)){draft.tistory=stored.draft.blog;draft.tistory_title=stored.draft.title;}loadDraft();markDirty();notify("작성 중이던 글을 복구했어요. 글 보관하기를 눌러 보관해 주세요.");
 }
}catch{}

(async()=>{
 const id=new URLSearchParams(location.hash.slice(1)).get("extension");
 if(!/^[a-p]{32}$/.test(id||""))return;
 try{
  const result=await extensionMessage(id,{type:"ping"});if(!result?.ok)return;
  localStorage.setItem("dajeong-extension",id);history.replaceState(null,"",location.pathname);
  $("connectionNotice").hidden=false;$("connectionNotice").textContent="Mellow 도우미 연결이 끝났어요. 이제 ‘블로그로 옮기기’를 눌러 주세요.";
  const epoch=navigationEpoch,rows=await api("/api/drafts");
  if(rows.length&&!dirty&&!busy&&epoch===navigationEpoch){const latest=await api("/api/drafts/"+rows[0].id);if(!dirty&&!busy&&epoch===navigationEpoch){draft=latest;loadDraft();}}
 }catch{notify("도우미 연결을 마치지 못했어요. 크롬에서 다시 눌러 주세요.");}
})();

renderWorkflow();

renderLayout();

function updateOptionSummaries(){
 const parts=[];if(draft.selected_place)parts.push(draft.selected_place.name);if($("facts").value.trim())parts.push("추가 메모");if(!$("campaignEnabled").checked&&$("hashtags").value.trim())parts.push("태그");
 $("contentOptionsSummary").textContent=parts.join(" · ")||"장소 · 꼭 넣을 이야기 · 태그";
 const tone=window.WritingUI?.label(activePlatform())||($("tone").value==="밝고 자연스러운 일상 후기체"?"자연스러운 후기":$("tone").selectedOptions[0].textContent);
 $("writingOptionsSummary").textContent=($("language").value==="en"?"English":"한국어")+" · "+tone+(tab==="blog"&&draft.blog_layouts?.[activePlatform()]?.preset&&draft.blog_layouts[activePlatform()].preset!=="manual"?" · 줄바꿈 조정":"");
}
document.addEventListener("input",()=>{updateOptionSummaries();renderWorkspace();});document.addEventListener("change",()=>{updateOptionSummaries();renderWorkspace();});
updateOptionSummaries();

renderCampaign();


// Small comforts for reviewing a story; none of these actions call the writing API.
function renderSaveState(failed=false){
 const node=$("saveState");node.dataset.state=busy?"busy":failed?"failed":dirty?(recoveryReady?"temporary":"editing"):draft.id?"saved":"empty";
 node.textContent=busy?"작업 중…":failed?"임시 보관 불가":dirty?(recoveryReady?"임시 보관됨":"수정 중"):draft.id?"저장 완료":"작성 대기";
 node.title=failed?"브라우저 임시 보관을 사용할 수 없어요. ‘글 보관하기’로 저장해 주세요.":dirty?"이 브라우저에서 복구할 수 있는 임시 보관이에요. 보관함에 남기려면 ‘글 보관하기’를 눌러 주세요.":draft.id?"보관함에 저장한 이야기예요.":"사진과 메모를 담아 첫 이야기를 시작해 보세요.";
}
function rememberGeneration(platforms,result,allowEmpty=false){
 for(const p of platforms){const info=platformInfo[p];if(!allowEmpty&&!draft[info.body]?.trim())continue;
  if(draft[info.body]===result[info.body]&&(!info.title||draft[info.title]===result[info.title]))continue;
  generationUndo[p]={channel_media:draft.channel_media?.[p]?JSON.parse(JSON.stringify(draft.channel_media[p])):null,channel_origin:draft.channel_origins?.[p]?JSON.parse(JSON.stringify(draft.channel_origins[p])):null,blog_document:draft.blog_documents?.[p]?JSON.parse(JSON.stringify(draft.blog_documents[p])):null,body:draft[info.body],title:info.title?draft[info.title]:null,language:draft.platform_languages[p]||draft.language,base:draft.layout_bases[p],last:draft.layout_last[p],facts_translation:draft.facts_translation,facts_translation_source:draft.facts_translation_source,afterBody:result[info.body],afterTitle:info.title?result[info.title]:null};
 }
}
function renderUndo(){const button=$("undoGeneration");button.hidden=!generationUndo[activePlatform()];button.disabled=busy;}
$("undoGeneration").addEventListener("click",()=>{
 if(busy)return;sync();const p=activePlatform(),prior=generationUndo[p],info=platformInfo[p];if(!prior)return;
 if((draft[info.body]!==prior.afterBody||(info.title&&draft[info.title]!==prior.afterTitle))&&!confirm("지금 수정한 내용 대신 새로 만들기 전 글로 되돌릴까요?"))return;
 draft[info.body]=prior.body;if(["instagram","threads"].includes(p)){draft.channel_media||={};draft.channel_origins||={};if(prior.channel_media)draft.channel_media[p]=prior.channel_media;else delete draft.channel_media[p];if(prior.channel_origin)draft.channel_origins[p]=prior.channel_origin;else delete draft.channel_origins[p];}if(draft.blog_documents){if(prior.blog_document)draft.blog_documents[p]=prior.blog_document;else delete draft.blog_documents[p];}if(info.title)draft[info.title]=prior.title;draft.platform_languages[p]=prior.language;
 for(const [field,value] of [["layout_bases",prior.base],["layout_last",prior.last]]){if(value===undefined)delete draft[field][p];else draft[field][p]=value;}
 if(p==="instagram"){draft.facts_translation=prior.facts_translation;draft.facts_translation_source=prior.facts_translation_source;}
 delete generationUndo[p];clearIssueMarks();issuesVisible=false;++issueSequence;$("qualityBox").hidden=true;
 $("body").value=draft[info.body];if(info.title)$("title").value=draft[info.title];markDirty();renderTab();setWorkflow(2);notify("새로 만들기 전 글로 되돌렸어요. 다른 플랫폼 원고는 그대로예요.");
});
function photoPreviewAction(img,index){
 img.tabIndex=0;img.setAttribute("role","button");img.setAttribute("aria-label","사진 "+(index+1)+" 크게 보기");img.classList.add("can-enlarge");img.addEventListener("click",()=>openPhoto(index));img.addEventListener("keydown",event=>{if(event.key==="Enter"||event.key===" "){event.preventDefault();openPhoto(index);}});
}
let viewingPhoto=0,viewingImages=[];
function openPhoto(index,images=draft.images){
 viewingImages=[...images];
 if(busy||!viewingImages.length)return;viewingPhoto=(index+viewingImages.length)%viewingImages.length;
 const box=$("modal").open?$("modalBody"):modal("사진 크게 보기");$("modal").dataset.view="photo";$("modalTitle").textContent="사진 "+(viewingPhoto+1)+" / "+viewingImages.length;box.replaceChildren();
 const img=document.createElement("img");img.src="/media/"+viewingImages[viewingPhoto]+".jpg";img.alt="사진 "+(viewingPhoto+1);img.className="photo-viewer-image";box.append(img);
 if(viewingImages.length>1){const controls=document.createElement("div");controls.className="photo-viewer-controls";for(const [label,step] of [["← 이전 사진",-1],["다음 사진 →",1]]){const button=document.createElement("button");button.className="secondary";button.type="button";button.textContent=label;button.onclick=()=>{openPhoto(viewingPhoto+step,viewingImages);$("modalBody").querySelectorAll("button")[step===1?1:0].focus();};controls.append(button);}box.append(controls);}
}
$("modal").addEventListener("keydown",event=>{if($("modal").dataset.view!=="photo")return;if(["ArrowLeft","ArrowRight"].includes(event.key)){event.preventDefault();openPhoto(viewingPhoto+(event.key==="ArrowRight"?1:-1),viewingImages);}});
function libraryViews(box,historyView=false){
 const tabs=document.createElement("div");tabs.className="library-view-tabs";
 for(const [label,selected,action] of [["보관한 글",!historyView,()=>void openLibrary().catch(error=>notify(error.message))],["게시 기록",historyView,()=>$("showHistory").click()]]){const b=document.createElement("button");b.type="button";b.className="quiet";b.classList.toggle("is-selected",selected);b.setAttribute("aria-pressed",String(selected));b.textContent=label;b.disabled=selected;b.onclick=action;tabs.append(b);}box.append(tabs);
}
async function openLibrary(){
 if(window.LibraryUI)return window.LibraryUI.open();
 const rows=await api("/api/drafts"),box=modal("내 글");$("modal").dataset.view="library";libraryViews(box);
 if(!rows.length){para(box,"저장한 이야기가 아직 없어요. 글을 만든 뒤 ‘글 보관하기’를 누르면 여기에 모여요.");return;}
 const controls=document.createElement("div");controls.className="library-controls";
 const search=document.createElement("input");search.type="search";search.id="librarySearch";search.placeholder="제목·장소·요약으로 찾기";search.setAttribute("aria-label","보관한 이야기 검색");
 const filter=document.createElement("select");filter.id="libraryPlatform";filter.setAttribute("aria-label","플랫폼으로 모아 보기");for(const [value,label] of [["","전체 플랫폼"],...Object.entries(platformInfo).map(([p,info])=>[p,info.label])]){const option=document.createElement("option");option.value=value;option.textContent=label;filter.append(option);}
 controls.append(search,filter);const count=document.createElement("p");count.className="library-count";count.setAttribute("role","status");const list=document.createElement("div");list.id="libraryList";box.append(controls,count,list);
 const draw=()=>{
  const query=search.value.trim().toLocaleLowerCase();const visible=rows.filter(row=>(!filter.value||(row.platforms||[]).includes(filter.value))&&[row.title,...(row.titles||[]),row.excerpt,row.place].join(" ").toLocaleLowerCase().includes(query));
  count.textContent=visible.length+"개 이야기 · 최근 수정한 순서";list.replaceChildren();if(!visible.length){const empty=document.createElement("p");empty.className="library-empty";empty.textContent="찾는 이야기가 없어요. 다른 검색어나 플랫폼을 골라 주세요.";list.append(empty);}
  for(const row of visible){const button=document.createElement("button");button.type="button";button.className="draft-row library-row";
   const art=document.createElement("span");art.className="library-art";art.setAttribute("aria-hidden","true");art.textContent="✦";if(/^[a-f0-9]{32}$/.test(row.thumbnail||"")){const img=document.createElement("img");img.src="/media/"+row.thumbnail+".jpg";img.alt="";img.loading="lazy";img.onerror=()=>img.remove();art.append(img);}
   const text=document.createElement("span");text.className="library-text";const title=document.createElement("strong");title.textContent=row.title||"제목 없는 이야기";const excerpt=document.createElement("span");excerpt.className="library-excerpt";excerpt.textContent=row.excerpt||"사진과 메모가 담긴 이야기";const meta=document.createElement("small");meta.textContent=new Date(row.updated*1000).toLocaleDateString("ko-KR")+" · "+(row.photo_count?"사진 "+row.photo_count+"장":"사진 없음");const badges=document.createElement("span");badges.className="library-badges";for(const p of row.platforms||[]){if(!platformInfo[p])continue;const badge=document.createElement("small");badge.textContent=platformInfo[p].label;badges.append(badge);}text.append(title);if(excerpt.textContent!==title.textContent)text.append(excerpt);text.append(meta,badges);button.append(art,text);
   button.addEventListener("click",run(async()=>{if(busy)return;if(dirty&&!confirm("저장하지 않은 내용을 버리고 이 초안을 열까요?"))return;lock(true);count.textContent="이야기를 불러오고 있어요…";try{const next=await api("/api/drafts/"+row.id);if(filter.value)next.editing_platform=filter.value;draft=next;loadDraft();$("modal").close();}finally{lock(false);}}));list.append(button);
  }
 };
 search.addEventListener("input",draw);filter.addEventListener("change",draw);draw();search.focus();
}
renderSaveState();


$("saveConflictCopy").addEventListener("click",run(async()=>{
 if(busy)return;sync();const original={id:draft.id,updated:draft.updated};draft.id=crypto.randomUUID().replaceAll("-","");delete draft.updated;
 try{await saveDraft();notify("두 원고를 모두 남겼어요. 지금 글은 새 이야기로 보관했어요.");}
 catch(error){draft.id=original.id;draft.updated=original.updated;dirty=true;persistRecovery();throw error;}
}));
$("saveConflictLoad").addEventListener("click",run(async()=>{
 if(busy||!draft.id)return;if(!confirm("지금 화면의 수정 내용 대신 보관함의 최신 저장 글을 열까요? 지금 내용도 남기려면 ‘새 이야기로 보관’을 먼저 눌러 주세요."))return;
 lock(true);try{const latest=await api("/api/drafts/"+draft.id);draft=latest;loadDraft();notify("최신 저장 글을 열었어요.");}finally{lock(false);}
}));

// Initialize defaults without disturbing restored drafts or recovery state.
restoreDestinations();
for(const id of ["tone","language","template"])if([...$(id).options].some(option=>option.value===draft[id]))$(id).value=draft[id];
showToneGuide();updateOptionSummaries();renderWorkflow();
