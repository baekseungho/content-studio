"use strict";
const $=id=>document.getElementById(id);
async function refresh(){
 const [current]=await chrome.tabs.query({active:true,currentWindow:true});$("formatOnly").hidden=Boolean(current?.url?.includes(".tistory.com/"));
 const result=await chrome.storage.session.get(["lastStatus","fallbackText","pending"]);
 const fallback=result.fallbackText;
 const working=Boolean(result.lastStatus?.busy&&Date.now()-(result.lastStatus.updated||0)<180000);
 $("fallback").hidden=!(fallback&&fallback.expires>Date.now());
 for(const id of ["copyTitle","copyBody","copyDiagnostic","formatOnly"])$(id).disabled=working;
 if(fallback)$("photoHint").textContent="사진 "+fallback.photoCount+"장은 네이버의 사진 버튼으로도 넣을 수 있어요.";
 if(result.lastStatus){$("status").textContent=result.lastStatus.message;$("detail").textContent="버전 "+(result.lastStatus.version||"이전 버전")+" · 단계: "+(result.lastStatus.stage||"확인 안 됨")+"\n"+(result.lastStatus.detail||"")+"\n"+(result.lastStatus.formatting?JSON.stringify(result.lastStatus.formatting,null,2):"");}
 $("fill").disabled=working;
 if(result.pending?.expires<Date.now())await chrome.storage.session.remove("pending");
}
$("connect").addEventListener("click",async()=>{
 await chrome.storage.local.set({pairedBase:"http://127.0.0.1:8787"});
 chrome.tabs.create({url:"http://127.0.0.1:8787/#extension="+chrome.runtime.id});
});
$("fill").addEventListener("click",async()=>{
 $("fill").disabled=true;
 try{
  const [tab]=await chrome.tabs.query({active:true,currentWindow:true});
  const code=$("code").value.trim();
  const {pending}=await chrome.storage.session.get("pending");
  if(!code&&(!pending||pending.expires<Date.now()))throw Error("앱에서 ‘블로그로 옮기기’를 먼저 눌러 주세요.");
  const result=await chrome.runtime.sendMessage({type:"fill",channel:code?(tab.url?.includes(".tistory.com/")?"tistory":"naver"):pending?.channel,tabId:tab.id,base:code?$("base").value:pending.base,code:code||pending.code});
  if(result.codeConsumed)$("code").value="";
  $("status").textContent=result.message;
  await refresh();
 }catch(error){$("status").textContent=error.message;}
 finally{$("fill").disabled=false;}
});
chrome.storage.onChanged.addListener(()=>refresh());
refresh();
async function copyFallback(field){
 try{
  const {fallbackText}=await chrome.storage.session.get("fallbackText");
  if(!fallbackText||fallbackText.expires<Date.now())throw Error("앱에서 글을 다시 선택해 주세요.");
  await navigator.clipboard.writeText(fallbackText[field]);
  $("status").textContent=(field==="title"?"제목":"본문")+"을 복사했어요. 네이버의 해당 칸을 누르고 Ctrl+V 하세요.";
 }catch(error){$("status").textContent=error.message;}
}
$("copyTitle").addEventListener("click",()=>copyFallback("title"));
$("copyBody").addEventListener("click",()=>copyFallback("body"));
$("copyDiagnostic").addEventListener("click",async()=>{
 const {lastDiagnostic}=await chrome.storage.session.get("lastDiagnostic");
 await navigator.clipboard.writeText(JSON.stringify({version:chrome.runtime.getManifest().version,...lastDiagnostic},null,2));
 $("status").textContent="문제 확인용 정보를 복사했어요. 글 내용이나 로그인 정보는 들어 있지 않아요.";
});

$("formatOnly").addEventListener("click",async()=>{
 $("formatOnly").disabled=true;
 try{const [tab]=await chrome.tabs.query({active:true,currentWindow:true});const result=await chrome.runtime.sendMessage({type:"format",tabId:tab.id});$("status").textContent=result.message;await refresh();}
 catch(error){$("status").textContent=error.message;}finally{$("formatOnly").disabled=false;}
});
