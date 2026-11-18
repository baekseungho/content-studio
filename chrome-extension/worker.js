"use strict";
importScripts("editor.js","tistory.js");
let busy=false,launching=false,recovering=false,reportRetrying=false,recoveryFlight=null;
const version=()=>chrome.runtime.getManifest().version;
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const channelOf=value=>value==="tistory"?"tistory":"naver";
const actionFor=channel=>channel==="tistory"?tistoryAction:editorAction;
const labelFor=channel=>channel==="tistory"?"티스토리":"네이버";
async function status(message,running=true,extra={}){
 await chrome.storage.session.set({lastStatus:{message,detail:message,busy:running,version:version(),updated:Date.now(),...extra}});
}
async function finish(result){
 const full={version:version(),...result};await chrome.storage.session.set({lastDiagnostic:full,lastStatus:{...full,busy:false,updated:Date.now()}});return full;
}
function localBase(raw){
 const url=new URL(raw);if(url.protocol!=="http:"||!["127.0.0.1","localhost"].includes(url.hostname)||url.username||url.password||url.search||url.hash||url.pathname!=="/")throw Error("앱 주소는 http://127.0.0.1:8787 형식이어야 해요.");return url.origin;
}
async function request(base,path,body){
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),20000);
 try{const response=await fetch(base+path,{method:"POST",headers:{"Content-Type":"application/json","X-Dajeong-Extension":"1"},body:JSON.stringify(body),signal:controller.signal});const result=await response.json();if(!response.ok){const error=Error(result.error||"앱과 통신하지 못했어요.");error.status=response.status;throw error;}return result;}
 finally{clearTimeout(timer);}
}
function writerInfo(raw,channel){
 const writer=new URL(raw);if(writer.protocol!=="https:"||writer.username||writer.password||writer.port||writer.hash)throw Error("글쓰기 주소를 확인해 주세요.");
 if(channel==="tistory"){
  if(!/^[a-z0-9][a-z0-9-]*\.tistory\.com$/.test(writer.hostname)||["www.tistory.com","notice.tistory.com"].includes(writer.hostname)||writer.pathname!=="/manage/newpost/"||writer.search)throw Error("티스토리 글쓰기 주소가 올바르지 않아요.");
 }else if(writer.origin!=="https://blog.naver.com"||!/^\/[A-Za-z0-9_-]+$/.test(writer.pathname)||writer.searchParams.get("Redirect")!=="Write")throw Error("네이버 글쓰기 주소가 올바르지 않아요.");
 return writer;
}
function sameWriter(raw,writer,channel){
 try{const tab=new URL(raw);if(tab.origin!==writer.origin)return false;
  if(channel==="tistory")return /^\/manage\/newpost\/?$/.test(tab.pathname);
  const blog=writer.pathname.slice(1);return tab.pathname===writer.pathname&&tab.searchParams.get("Redirect")==="Write"||tab.pathname==="/PostWriteForm.naver"&&tab.searchParams.get("blogId")===blog;
 }catch{return false;}
}
async function chooseTab(writer,channel,reuse=true){
 if(reuse){const tabs=await chrome.tabs.query({url:channel==="tistory"?writer.origin+"/*":"https://blog.naver.com/*"}),eligible=[];
  for(const tab of tabs.filter(tab=>tab.status==="complete"&&sameWriter(tab.url,writer,channel))){
   try{const frames=await chrome.scripting.executeScript({target:{tabId:tab.id,allFrames:true},world:"MAIN",func:actionFor(channel),args:["probe",null]});if(frames.some(frame=>frame.result?.eligible)&&!frames.some(frame=>frame.result?.blocked||frame.result?.inProgress))eligible.push(tab);}catch{}
  }
  // Reuse only one unambiguous, blank editor for the exact requested blog.
  if(eligible.length===1){await chrome.tabs.update(eligible[0].id,{active:true});await chrome.windows.update(eligible[0].windowId,{focused:true});return {tab:eligible[0],reused:true};}
 }
 return {tab:await chrome.tabs.create({url:writer.href,active:true}),reused:false};
}
async function sendReceipt(entry){
 for(let attempt=0;attempt<2;attempt++){
  try{await request(entry.base,"/api/extension/report",{channel:entry.channel,token:entry.token,state:entry.state,count:entry.count,diagnostic:entry.diagnostic});return true;}
  catch(error){if([400,409,410].includes(error.status)||attempt===1)return false;await delay(300);}
 }
 return false;
}
async function rememberTransfer(full){
 const {transferResults={}}=await chrome.storage.session.get("transferResults");
 if(full.draftId){const key=full.channel+":"+full.draftId;delete transferResults[key];transferResults[key]=full;while(Object.keys(transferResults).length>16)delete transferResults[Object.keys(transferResults)[0]];}
 await chrome.storage.session.set({lastTransferDiagnostic:full,transferResults});
}
async function completeTransfer(result,operation){
 const full={...result,channel:operation.channel,draftId:operation.draftId,tabId:operation.tabId,codeConsumed:true,ok:result.state==="ready",contentReady:["ready","partial"].includes(result.state),stage:result.stage||"입력 결과 확인",detail:result.message};
 const entry={base:operation.base,channel:operation.channel,draftId:operation.draftId,token:operation.reportToken,state:result.state,count:result.count,diagnostic:{version:version(),...full},expires:Date.now()+600000};
 const stored=await chrome.storage.session.get("pendingReports");let queue=(stored.pendingReports||[]).filter(item=>item.expires>Date.now()&&item.token!==entry.token);queue.push(entry);await chrome.storage.session.set({pendingReports:queue.slice(-10)});
 if(await sendReceipt(entry)){queue=queue.filter(item=>item.token!==entry.token);await chrome.storage.session.set({pendingReports:queue});}
 else{full.reportPending=true;full.recordingWarning="편집기 결과는 유지했어요. 앱에 결과 기록만 다시 보내면 돼요. 글·사진을 다시 넣지 마세요.";full.detail=(full.message||"")+" " +full.recordingWarning;}
 if(full.contentReady)await chrome.storage.session.remove("fallbackText");
 await chrome.storage.session.remove("activeTransfer");await rememberTransfer(full);return finish(full);
}
async function checkpoint(operation){
 const output=await chrome.scripting.executeScript({target:{tabId:operation.tabId,frameIds:[operation.frameId]},world:"MAIN",func:actionFor(operation.channel),args:["progress",{transferId:operation.id}]});return output[0]?.result;
}
function recoverActive(){
 if(busy)return Promise.resolve();if(recoveryFlight)return recoveryFlight;recovering=true;
 recoveryFlight=(async()=>{try{
  const {activeTransfer:operation}=await chrome.storage.session.get("activeTransfer");if(!operation)return;
  if(operation.phase!=="input"){if(Date.now()-operation.updated>45000)await chrome.storage.session.remove("activeTransfer");return;}
  let point;try{point=await checkpoint(operation);}catch{}
  if(point?.state==="finished"&&point.result)return await completeTransfer(point.result,operation);
  if(point?.state==="running"){await status(point.message||"이전 편집기 입력이 진행 중이에요.",true,{stage:"편집기 입력",channel:operation.channel,done:point.done,total:point.total,tabId:operation.tabId});return;}
  return await completeTransfer({state:"failed",count:0,message:"이전 작업의 편집기 탭이 닫히거나 바뀌어 결과를 확인하지 못했어요. 남은 내용을 먼저 확인해 주세요.",stage:"이전 작업 확인"},operation);
 }finally{recovering=false;recoveryFlight=null;}})();
 return recoveryFlight;
}

async function assertIdle(){
 if(busy||launching||reportRetrying)throw Error("이미 글을 옮기고 있어요. 작업 중인 편집기 탭을 확인해 주세요.");
 // Claim synchronously, before any storage/DOM await can interleave a second request.
 launching=true;
 try{await recoverActive();const {activeTransfer}=await chrome.storage.session.get("activeTransfer");if(activeTransfer)throw Error("앞선 편집기 작업을 확인하고 있어요. ‘결과 확인·기록 다시 보내기’를 눌러 주세요.");}
 catch(error){launching=false;throw error;}
}
async function runFill(message){
 if(busy)return {ok:false,version:version(),stage:"진행 중",message:"이미 입력 중이에요. 편집기 탭을 확인해 주세요."};
 busy=true;const channel=channelOf(message.channel),label=labelFor(channel);let payload,base,operation,timer,filling=false,stage="전달 코드 확인",probes=[];
 try{
  base=localBase(message.base);if(!/^[A-Za-z0-9_-]{32}$/.test(message.code||""))throw Error("앱에서 새 전달 코드를 만들어 주세요.");
  const ticket=await request(base,"/api/extension/inspect",{code:message.code,channel});
  const expectedWriter=ticket.writer_url?writerInfo(ticket.writer_url,channel):null;
  operation={id:crypto.randomUUID(),base,channel,draftId:ticket.draft_id,tabId:message.tabId,phase:"preparing",started:Date.now(),updated:Date.now()};
  await chrome.storage.session.set({pending:{base,code:message.code,channel,expires:Date.now()+600000},activeTransfer:operation,lastTarget:{tabId:message.tabId,channel}});
  stage=label+" 편집기 찾기";await status(stage,true,{stage,channel,tabId:message.tabId});
  let target,tab;const deadline=Date.now()+30000;
  do{
   tab=await chrome.tabs.get(message.tabId);
   if(tab.status==="complete"){
    const url=new URL(tab.url||"about:blank");
    if(channel==="naver"&&url.hostname!=="blog.naver.com"||channel==="tistory"&&(!/^[a-z0-9][a-z0-9-]*\.tistory\.com$/.test(url.hostname)||!/^\/manage\/newpost\/?$/.test(url.pathname)))throw Error(label+"에 직접 로그인한 뒤 빈 글쓰기 화면에서 확장의 ‘준비한 글 가져오기’를 눌러 주세요. 코드는 아직 사용하지 않았어요.");
    if(expectedWriter&&!sameWriter(tab.url,expectedWriter,channel))throw Error("앱에서 선택한 블로그와 다른 글쓰기 탭이에요. 선택한 블로그의 빈 편집기에서 가져와 주세요. 코드는 아직 사용하지 않았어요.");
    const frames=await chrome.scripting.executeScript({target:{tabId:tab.id,allFrames:true},world:"MAIN",func:actionFor(channel),args:["probe",null]});probes=frames.map(item=>({frameId:item.frameId,...item.result}));
    if(frames.some(item=>item.result?.blocked)){await request(base,"/api/extension/block",{code:message.code,channel});throw Error(label+" 추가 인증을 감지해 중단했어요. 공식 화면에서 직접 확인해 주세요.");}
    if(frames.some(item=>item.result?.inProgress))throw Error("이 편집기에서 앞선 글 입력이 진행 중이에요. 다시 넣지 않았어요.");
    target=frames.find(item=>item.result?.eligible);if(target)break;
    if(frames.some(item=>item.result?.existing&&item.result?.bodyFound))throw Error("열린 편집기에 글이나 사진이 있어 덮어쓰지 않았어요. 내용을 보관한 뒤 빈 글쓰기 화면에서 가져와 주세요. 코드는 아직 사용하지 않았어요.");
   }
   await delay(500);
  }while(Date.now()<deadline);
  if(!target)throw Error("30초 동안 빈 편집기를 찾지 못했어요. 임시저장 안내를 닫고 기본 글쓰기 화면에서 다시 가져와 주세요. 코드는 아직 사용하지 않았어요.");
  stage="초안 받기 · 재입력 제한 확인";await status(stage,true,{stage,channel});payload=await request(base,"/api/extension/redeem",{code:message.code,channel});
  operation={...operation,phase:"input",frameId:target.frameId,reportToken:payload.report_token,expectedPhotos:payload.expected_photos,updated:Date.now()};
  const stored=await chrome.storage.session.get("lastFormats");await chrome.storage.session.set({activeTransfer:operation,lastFormats:{...stored.lastFormats,[channel]:{format:payload.format,version:version()}},lastFormat:payload.format,lastFormatVersion:version(),fallbackText:{title:payload.title,body:payload.body.replace(/^\s*\[\[photo:\d+\]\]\s*$/gm,"").replace(/^##\s+/gm,"").trim(),photoCount:payload.expected_photos,channel,expires:Date.now()+600000}});await chrome.storage.session.remove("pending");
  stage=label+" 글·사진 입력";await status("글과 사진을 옮기고 있어요. 편집기 탭을 그대로 두세요.",true,{stage,channel,tabId:tab.id});
  let polling=false;filling=true;
  timer=setInterval(async()=>{if(polling)return;polling=true;try{const point=await checkpoint(operation);if(filling&&point?.state==="running")await status(point.message,true,{stage:point.message,channel,done:point.done,total:point.total,tabId:tab.id});}catch{}finally{polling=false;}},1200);
  // Never inject report credentials or local connection information into the blog page.
  const editorPayload={title:payload.title,body:payload.body,photos:payload.photos,format:payload.format,transferId:operation.id};
  const output=await chrome.scripting.executeScript({target:{tabId:tab.id,frameIds:[target.frameId]},world:"MAIN",func:actionFor(channel),args:["fill",editorPayload]});filling=false;clearInterval(timer);
  const result=output[0]?.result||{state:"failed",count:0,stage,message:"편집기에서 결과를 받지 못했어요. 남은 내용을 확인해 주세요."};result.diagnostics={...result.diagnostics,frames:probes};
  return await completeTransfer(result,operation);
 }catch(error){
  filling=false;clearInterval(timer);
  if(payload&&operation?.phase==="input"){
   try{const point=await checkpoint(operation);if(point?.state==="finished"&&point.result)return await completeTransfer(point.result,operation);}catch{}
   // Keep the operation checkpoint: status/retry reads the editor, never repeats fill.
   return finish({ok:false,state:"failed",uncertain:true,codeConsumed:true,stage,message:"입력 결과를 아직 확인하지 못했어요. 확장에서 ‘결과 확인·기록 다시 보내기’를 눌러 주세요. 글·사진은 다시 넣지 않아요.",detail:error.message,channel,tabId:operation.tabId});
  }
  await chrome.storage.session.remove("activeTransfer");return finish({ok:false,state:"failed",codeConsumed:false,stage,message:error.message,detail:error.message,channel,diagnostics:{frames:probes}});
 }finally{filling=false;clearInterval(timer);busy=false;}
}
async function runTistoryFill(message){return runFill({...message,channel:"tistory"});}
async function retryReports(filter={}){
 if(busy||launching||reportRetrying)return {ok:false,message:"입력 또는 결과 기록이 끝난 뒤 다시 확인해 주세요."};reportRetrying=true;
 try{
  await recoverActive();const matches=entry=>(!filter.draftId||entry.draftId===filter.draftId)&&(!filter.channel||entry.channel===filter.channel);
  const {pendingReports=[]}=await chrome.storage.session.get("pendingReports"),remaining=[];
  for(const entry of pendingReports){if(!matches(entry)||!await sendReceipt(entry))remaining.push(entry);}
  await chrome.storage.session.set({pendingReports:remaining});
  const {lastTransferDiagnostic,transferResults={},activeTransfer}=await chrome.storage.session.get(["lastTransferDiagnostic","transferResults","activeTransfer"]);
  const result=filter.draftId?transferResults[channelOf(filter.channel)+":"+filter.draftId]:lastTransferDiagnostic;
  const count=remaining.filter(matches).length,active=activeTransfer&&matches(activeTransfer);
  if(!count&&result?.reportPending){delete result.reportPending;delete result.recordingWarning;result.detail=result.message;await rememberTransfer(result);await finish(result);}
  const ok=!count&&!active&&Boolean(result);
  return {ok,pendingCount:count,message:active?"편집기에서 입력이 진행 중이에요. 최근 작업 탭을 확인해 주세요.":count?"앱에 결과 기록을 보내지 못했어요. 앱 실행 상태를 확인해 주세요. 글은 다시 넣지 않았어요.":!result?"이 글의 입력 결과를 확인하지 못했어요. 최근 편집기에서 남은 내용을 먼저 확인해 주세요.":"결과를 확인하고 앱에 기록했어요. 글·사진은 다시 넣지 않았어요.",result};
 }finally{reportRetrying=false;}
}

async function formatOnly(tabId){
 try{await assertIdle();}catch(error){return {ok:false,message:error.message};}busy=true;const heartbeat=setInterval(()=>status("글·사진을 유지하며 서식만 확인하고 있어요.",true,{stage:"서식만 적용"}).catch(()=>{}),15000);
 try{
  const tab=await chrome.tabs.get(tabId),url=new URL(tab.url||"about:blank"),channel=url.hostname.endsWith(".tistory.com")?"tistory":"naver";
  if(channel==="naver"&&url.hostname!=="blog.naver.com"||channel==="tistory"&&!/^\/manage\/newpost\/?$/.test(url.pathname))throw Error("서식을 바꿀 블로그 편집기 탭에서 눌러 주세요.");
  const {lastFormats={}}=await chrome.storage.session.get("lastFormats");const format=lastFormats[channel]?.format||{align:"center",font_key:channel==="tistory"?"nanummyeongjo":"nanumbareunhipi",font:"나눔바른히피",size:15,label:"감성 후기"};
  await status("글·사진을 유지하며 서식만 확인하고 있어요.",true,{stage:"서식만 적용",channel});
  const frames=await chrome.scripting.executeScript({target:{tabId,allFrames:true},world:"MAIN",func:actionFor(channel),args:["probe",null]});
  if(frames.some(item=>item.result?.blocked||item.result?.inProgress))throw Error("추가 인증 또는 다른 입력 작업이 있어 서식을 변경하지 않았어요.");
  const target=frames.find(item=>item.result?.bodyFound&&item.result?.existing);if(!target)throw Error("기존 글이 있는 편집기를 찾지 못했어요. 발행된 페이지에서는 서식을 바꾸지 않아요.");
  const output=await chrome.scripting.executeScript({target:{tabId,frameIds:[target.frameId]},world:"MAIN",func:actionFor(channel),args:["format",{format}]});const result=output[0]?.result||{state:"failed",message:"서식 결과를 받지 못했어요."};return finish({...result,ok:result.state==="ready",detail:result.message,channel,stage:"기존 글의 서식만 적용"});
 }catch(error){return finish({ok:false,stage:"서식만 적용",message:error.message,detail:error.message});}finally{clearInterval(heartbeat);busy=false;launching=false;}
}
async function currentStatus(){if(!busy)await recoverActive();const {lastStatus,activeTransfer}=await chrome.storage.session.get(["lastStatus","activeTransfer"]);if(!busy&&!launching&&!recovering&&!activeTransfer&&lastStatus?.busy&&Date.now()-(lastStatus.updated||0)>45000)return finish({ok:false,state:"failed",stage:"이전 작업 확인",message:"이전 작업의 연결이 끝났어요. 최근 편집기에서 내용을 확인해 주세요. 글은 자동으로 다시 넣지 않아요."});return lastStatus||{message:"준비됐어요.",busy:false,version:version()};}
async function localMessage(message){
 if(message.type==="status")return currentStatus();if(message.type==="retryReport")return retryReports(message);if(message.type==="format")return formatOnly(message.tabId);
 if(message.type==="showTarget"){const {lastTarget}=await chrome.storage.session.get("lastTarget");if(!lastTarget)throw Error("최근 편집기 탭이 없어요.");const tab=await chrome.tabs.get(lastTarget.tabId);await chrome.tabs.update(tab.id,{active:true});await chrome.windows.update(tab.windowId,{focused:true});return {ok:true};}
 await assertIdle();try{const {pending}=await chrome.storage.session.get("pending");if(!message.code&&(!pending||pending.expires<Date.now()))throw Error("앱에서 새 전달 코드를 만들어 주세요.");return await runFill({...message,channel:message.channel||pending?.channel,base:message.base||pending?.base,code:message.code||pending?.code});}finally{launching=false;}
}
chrome.runtime.onMessage.addListener((message,sender,respond)=>{
 if(sender.id!==chrome.runtime.id||!["fill","format","status","retryReport","showTarget"].includes(message.type))return false;
 localMessage(message).then(respond).catch(error=>respond({ok:false,version:version(),stage:"전달 준비",message:error.message,detail:error.message}));return true;
});
chrome.runtime.onMessageExternal.addListener((message,sender,respond)=>{
 let origin,ownsLaunch=false;try{origin=localBase(new URL(sender.url).origin);}catch{return false;}
 (async()=>{
  const {pairedBase}=await chrome.storage.local.get("pairedBase");if(!pairedBase||localBase(pairedBase)!==origin)return {ok:false,message:"먼저 Mellow 아이콘에서 ‘앱과 연결하기’를 눌러 주세요."};
  if(message.type==="ping")return {ok:true,version:version(),protocol:2};if(message.type==="status")return currentStatus();if(message.type==="retryReport")return retryReports(message);
  if(message.type==="tistoryBlogs"){const tabs=await chrome.tabs.query({url:"https://*.tistory.com/*"});return {ok:true,blogs:[...new Set(tabs.flatMap(tab=>{try{const url=new URL(tab.url);return /^[a-z0-9][a-z0-9-]*\.tistory\.com$/.test(url.hostname)&&!["www.tistory.com","notice.tistory.com"].includes(url.hostname)?[url.origin]:[];}catch{return [];}}))]};}
  if(message.type!=="prepare")return {ok:false,message:"지원하지 않는 요청이에요."};await assertIdle();
  try{
   if(localBase(message.base)!==origin||!/^[A-Za-z0-9_-]{32}$/.test(message.code||""))throw Error("로컬 앱 연결이나 전달 코드가 올바르지 않아요.");
   const channel=channelOf(message.channel),writer=writerInfo(message.writer_url,channel);ownsLaunch=true;await status("사용할 빈 편집기를 찾고 있어요.",true,{stage:"편집기 준비",channel});
   await chrome.storage.session.set({pending:{base:origin,code:message.code,channel,expires:Date.now()+600000}});const chosen=await chooseTab(writer,channel,message.reuseExisting!==false);return await runFill({tabId:chosen.tab.id,base:origin,code:message.code,channel});
  }finally{launching=false;}
 })().then(respond).catch(async error=>{const result={ok:false,version:version(),stage:"전달 준비",message:error.message,detail:error.message};respond(ownsLaunch?await finish(result):result);});return true;
});
