"use strict";
importScripts("editor.js");
let busy=false,launching=false;
const version=()=>chrome.runtime.getManifest().version;
async function status(message,running=true,extra={}){
 await chrome.storage.session.set({lastStatus:{message,detail:message,busy:running,version:version(),updated:Date.now(),...extra}});
}
async function finish(result){
 const full={version:version(),...result};
 await chrome.storage.session.set({lastDiagnostic:full,lastStatus:{...full,busy:false,updated:Date.now()}});
 return full;
}
function localBase(raw){
 const url=new URL(raw);
 if(url.protocol!=="http:"||!["127.0.0.1","localhost"].includes(url.hostname)||url.username||url.password||url.search||url.hash||url.pathname!=="/")throw Error("앱 주소는 http://127.0.0.1:8787 형식이어야 해요.");
 return url.origin;
}
async function request(base,path,body){
 const response=await fetch(base+path,{method:"POST",headers:{"Content-Type":"application/json","X-Dajeong-Extension":"1"},body:JSON.stringify(body)});
 const result=await response.json();if(!response.ok)throw Error(result.error||"로컬 앱에 연결하지 못했어요.");return result;
}
async function runFill(message){
 if(busy)return {ok:false,version:version(),stage:"진행 중",message:"이미 입력 중이에요. 열린 네이버 탭을 확인해 주세요."};
 busy=true;const heartbeat=setInterval(()=>chrome.storage.session.get("lastStatus").catch(()=>{}),15000);let payload,base,reported=false,stage="전달 번호 확인",probes=[];
 try{
  base=localBase(message.base);
  if(!/^[A-Za-z0-9_-]{32}$/.test(message.code||""))throw Error("유효한 전달 코드가 없어요. 앱에서 새 전달 코드를 만들어 주세요.");
  await chrome.storage.session.set({pending:{base,code:message.code,expires:Date.now()+600000}});
  stage="네이버 편집기 찾기";await status(stage,true,{stage});
  let target,tab;
  const deadline=Date.now()+30000;
  do{
   tab=await chrome.tabs.get(message.tabId);
   if(tab.status==="complete"){
    if(!tab.url||new URL(tab.url).hostname!=="blog.naver.com")throw Error("네이버 로그인 화면으로 이동했어요. 직접 로그인한 뒤 빈 글쓰기 탭에서 ‘준비한 글 가져오기’를 눌러 주세요. 전달 코드는 10분간 유지돼요.");
    const results=await chrome.scripting.executeScript({target:{tabId:tab.id,allFrames:true},world:"MAIN",func:editorAction,args:["probe",null]});
    probes=results.map(item=>({frameId:item.frameId,...item.result}));
    if(results.some(item=>item.result?.blocked)){
     await request(base,"/api/extension/block",{code:message.code});
     throw Error("네이버 보호조치·추가 인증 화면을 감지해 입력을 중단했어요. 공식 네이버에서 직접 확인해 주세요.");
    }
    target=results.find(item=>item.result?.eligible);if(target)break;
    if(results.some(item=>item.result?.titleFound&&item.result?.bodyFound&&item.result?.existing))throw Error("열린 편집기에 이미 글이나 사진이 있어 덮어쓰지 않았어요. 네이버에서 기존 글을 보관하고 빈 글쓰기 화면을 연 뒤 준비한 글을 가져와 주세요.");
   }
   await new Promise(resolve=>setTimeout(resolve,500));
  }while(Date.now()<deadline);
  if(!target)throw Error("30초 동안 제목·본문 입력 영역을 찾지 못했어요. 네이버 메인 화면 또는 임시저장 안내가 열렸는지 확인하고, 빈 글쓰기 탭에서 전달 코드를 넣어 주세요. 아래 프레임 진단을 복사하면 원인을 확인할 수 있어요.");
  stage="초안 받기 · 재입력 제한 확인";await status(stage,true,{stage});
  payload=await request(base,"/api/extension/redeem",{code:message.code});
  await chrome.storage.session.set({lastFormat:payload.format,lastFormatVersion:version()});
  await chrome.storage.session.remove("pending");
  await chrome.storage.session.set({fallbackText:{title:payload.title,
    body:payload.body.replace(/^\s*\[\[photo:\d+\]\]\s*$/gm,"").replace(/^##\s+/gm,"").trim(),
    photoCount:payload.expected_photos,expires:Date.now()+600000}});
  stage="제목·본문·사진·서식 입력";await status("글과 사진을 먼저 옮긴 뒤 정렬·글꼴을 적용해요. 완료 안내가 나올 때까지 네이버 탭을 그대로 두세요.",true,{stage});
  const output=await chrome.scripting.executeScript({target:{tabId:tab.id,frameIds:[target.frameId]},world:"MAIN",func:editorAction,args:["fill",payload]});
  const result=output[0]?.result||{state:"failed",message:"편집기에서 결과를 받지 못했어요."};
  const full={...result,codeConsumed:true,ok:result.state==="ready",contentReady:["ready","partial"].includes(result.state),
   stage:result.stage||stage,detail:result.message,diagnostics:{...result.diagnostics,frames:probes}};
  await chrome.storage.session.set({lastDiagnostic:{version:version(),...full}});
  stage="앱에 결과 기록";
  await request(base,"/api/extension/report",{token:payload.report_token,state:result.state,count:result.count,diagnostic:{version:version(),...full}});reported=true;
  if(full.contentReady)await chrome.storage.session.remove("fallbackText");
  return await finish(full);
 }catch(error){
  if(payload&&base&&!reported){try{await request(base,"/api/extension/report",{token:payload.report_token,state:"failed",count:0});}catch{}}
  return await finish({ok:false,state:"failed",codeConsumed:Boolean(payload),stage,message:error.message,detail:error.message,diagnostics:{frames:probes}});
 }finally{clearInterval(heartbeat);busy=false;}
}
async function formatOnly(tabId){
 if(busy||launching)return {ok:false,message:"글 입력이 끝난 뒤 서식만 적용해 주세요."};
 busy=true;const heartbeat=setInterval(()=>chrome.storage.session.get("lastStatus").catch(()=>{}),15000);const stage="기존 글의 서식만 적용";
 try{
  const tab=await chrome.tabs.get(tabId);
  if(!tab.url||new URL(tab.url).hostname!=="blog.naver.com")throw Error("서식을 바꿀 네이버 편집기 탭에서 눌러 주세요.");
  const {lastFormat,lastFormatVersion}=await chrome.storage.session.get(["lastFormat","lastFormatVersion"]);
  const format=(lastFormatVersion===version()&&lastFormat)||{align:"center",font:"나눔바른히피",font_key:"nanumbareunhipi",size:15,label:"감성 후기"};
  await status("글·사진은 다시 넣지 않고 서식만 확인하고 있어요.",true,{stage});
  const frames=await chrome.scripting.executeScript({target:{tabId,allFrames:true},world:"MAIN",func:editorAction,args:["probe",null]});
  if(frames.some(item=>item.result?.blocked))throw Error("네이버 본인 인증이 필요해 서식을 변경하지 않았어요.");
  const target=frames.find(item=>item.result?.bodyFound&&item.result?.existing);
  if(!target)throw Error("기존 본문이 있는 편집기를 찾지 못했어요. 발행된 글 페이지에서는 서식을 변경할 수 없어요.");
  const output=await chrome.scripting.executeScript({target:{tabId,frameIds:[target.frameId]},world:"MAIN",func:editorAction,args:["format",{format}]});
  const result=output[0]?.result||{state:"failed",message:"서식 결과가 없어요."};
  return await finish({...result,ok:result.state==="ready",stage,detail:result.message});
 }catch(error){return await finish({ok:false,stage,message:error.message,detail:error.message});}
 finally{clearInterval(heartbeat);busy=false;}
}
chrome.runtime.onMessage.addListener((message,sender,respond)=>{
 if(sender.id!==chrome.runtime.id||!["fill","format"].includes(message.type))return false;
 (async()=>{
  if(message.type==="format")return formatOnly(message.tabId);
  const {pending}=await chrome.storage.session.get("pending");
  if(!message.code&&pending?.expires<Date.now())throw Error("전달 코드가 10분을 지나 만료됐어요. 앱에서 새 코드를 만들어 주세요.");
  return runFill({...message,base:message.base||pending?.base,code:message.code||pending?.code});
 })().then(respond).catch(error=>respond({ok:false,version:version(),stage:"전달 준비",message:error.message,detail:error.message}));
 return true;
});
chrome.runtime.onMessageExternal.addListener((message,sender,respond)=>{
 let origin;
 try{origin=localBase(new URL(sender.url).origin);}catch{return false;}
 (async()=>{
  const {pairedBase}=await chrome.storage.local.get("pairedBase");
  if(!pairedBase||localBase(pairedBase)!==origin)return {ok:false,message:"먼저 다정 아이콘에서 ‘앱과 연결하기’를 눌러 주세요."};
  if(message.type==="ping")return {ok:true,version:version()};
  if(message.type==="status"){
   const result=await chrome.storage.session.get("lastStatus");return result.lastStatus||{message:"준비됐어요.",busy:false,version:version()};
  }
  if(message.type!=="prepare")return {ok:false,message:"지원하지 않는 요청이에요."};
  if(busy||launching)return {ok:false,message:"이미 글을 옮기고 있어요. 네이버 화면을 확인해 주세요."};
  if(localBase(message.base)!==origin||!/^[A-Za-z0-9_-]{32}$/.test(message.code))throw Error("로컬 앱 연결이나 전달 코드가 올바르지 않아요.");
  const writer=new URL(message.writer_url);
  if(writer.origin!=="https://blog.naver.com"||!/^\/[A-Za-z0-9_-]+$/.test(writer.pathname)||writer.searchParams.get("Redirect")!=="Write")throw Error("네이버 글쓰기 주소가 올바르지 않아요.");
  launching=true;
  try{
   await chrome.storage.session.set({pending:{base:origin,code:message.code,expires:Date.now()+600000}});
   const tab=await chrome.tabs.create({url:writer.href,active:true});
   return await runFill({tabId:tab.id,base:origin,code:message.code});
  }finally{launching=false;}
 })().then(respond).catch(async error=>respond(await finish({ok:false,stage:"새 글쓰기 탭 열기",message:error.message,detail:error.message})));
 return true;
});
