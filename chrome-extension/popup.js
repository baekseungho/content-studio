"use strict";
const $=id=>document.getElementById(id);let refreshing=false,lastShown=-1;
async function refresh(){
 if(refreshing)return;refreshing=true;
 try{
  const current=await chrome.runtime.sendMessage({type:"status"});
  const result=await chrome.storage.session.get(["lastStatus","fallbackText","pending","pendingReports","activeTransfer","lastTarget"]),state=result.lastStatus||current;
  const working=Boolean(state?.busy),fallback=result.fallbackText;
  $("fallback").hidden=!(fallback&&fallback.expires>Date.now());$("transferActivity").hidden=!working;
  for(const id of ["fill","connect","copyTitle","copyBody","copyDiagnostic","formatOnly"])$(id).disabled=working;
  $("retryReport").hidden=!(result.pendingReports?.length||result.activeTransfer||state?.uncertain||state?.reportPending);$("retryReport").disabled=working&&!state?.uncertain;
  $("showTarget").hidden=!result.lastTarget;
  if(fallback)$("photoHint").textContent="사진 "+fallback.photoCount+"장은 "+(fallback.channel==="tistory"?"티스토리":"네이버")+"의 사진 버튼으로 직접 넣을 수도 있어요.";
  if(state&&(state.updated||0)>lastShown){lastShown=state.updated||0;$("status").textContent=(state.message||"준비됐어요.")+(state.reportPending?"\n앱에 결과 기록만 다시 보내 주세요. 글은 다시 넣지 않아요.":"");$("detail").textContent="버전 "+(state.version||chrome.runtime.getManifest().version)+" · 단계: "+(state.stage||"준비")+(state.detail&&state.detail!==state.message?"\n"+state.detail:"");}
  $("elapsed").textContent=working&&result.activeTransfer?Math.floor((Date.now()-(result.activeTransfer.started||result.activeTransfer.updated))/1000)+"초째 · 편집기 탭을 그대로 두세요":"";
  if(result.pending?.expires<Date.now())await chrome.storage.session.remove("pending");
  if(fallback&&fallback.expires<Date.now())await chrome.storage.session.remove("fallbackText");
 }catch(error){$("status").textContent=error.message;}finally{refreshing=false;}
}
$("connect").addEventListener("click",async()=>{await chrome.storage.local.set({pairedBase:"http://127.0.0.1:8787"});await chrome.tabs.create({url:"http://127.0.0.1:8787/#extension="+chrome.runtime.id});});
$("fill").addEventListener("click",async()=>{
 $("fill").disabled=true;
 try{const [tab]=await chrome.tabs.query({active:true,currentWindow:true});const code=$("code").value.trim(),{pending}=await chrome.storage.session.get("pending");
  if(!code&&(!pending||pending.expires<Date.now()))throw Error("앱에서 ‘블로그로 옮기기’를 먼저 눌러 주세요.");
  const result=await chrome.runtime.sendMessage({type:"fill",channel:code?(tab.url?.includes(".tistory.com/")?"tistory":"naver"):pending?.channel,tabId:tab.id,base:code?$("base").value:pending.base,code:code||pending.code});
  if(result.codeConsumed)$("code").value="";$("status").textContent=result.message;await refresh();
 }catch(error){$("status").textContent=error.message;}finally{await refresh();}
});
async function copyFallback(field){
 try{const {fallbackText}=await chrome.storage.session.get("fallbackText");if(!fallbackText||fallbackText.expires<Date.now())throw Error("앱에서 글을 다시 선택해 주세요.");await navigator.clipboard.writeText(fallbackText[field]);$("status").textContent=(field==="title"?"제목":"본문")+"을 복사했어요. 편집기의 해당 칸을 눌러 붙여 넣어 주세요.";}
 catch(error){$("status").textContent=error.message;}
}
$("copyTitle").addEventListener("click",()=>copyFallback("title"));$("copyBody").addEventListener("click",()=>copyFallback("body"));
$("copyDiagnostic").addEventListener("click",async()=>{try{const {lastDiagnostic}=await chrome.storage.session.get("lastDiagnostic");await navigator.clipboard.writeText(JSON.stringify({version:chrome.runtime.getManifest().version,...lastDiagnostic},null,2));$("status").textContent="문제 확인용 정보를 복사했어요. 원고·사진·로그인 정보는 포함하지 않아요.";}catch(error){$("status").textContent=error.message;}});
$("formatOnly").addEventListener("click",async()=>{ $("formatOnly").disabled=true;try{const [tab]=await chrome.tabs.query({active:true,currentWindow:true});const result=await chrome.runtime.sendMessage({type:"format",tabId:tab.id});$("status").textContent=result.message;}catch(error){$("status").textContent=error.message;}finally{await refresh();}});
$("retryReport").addEventListener("click",async()=>{ $("retryReport").disabled=true;try{const result=await chrome.runtime.sendMessage({type:"retryReport"});$("status").textContent=result.message;}catch(error){$("status").textContent=error.message;}finally{await refresh();}});
$("showTarget").addEventListener("click",async()=>{try{const result=await chrome.runtime.sendMessage({type:"showTarget"});if(!result.ok)throw Error(result.message);}catch(error){$("status").textContent=error.message;}});
chrome.storage.onChanged.addListener(refresh);setInterval(refresh,1200);refresh();
