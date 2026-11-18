"use strict";
(()=>{
 const root=document.documentElement,key="mellow-theme",system=matchMedia("(prefers-color-scheme: dark)");
 let saved=null;try{saved=localStorage.getItem(key);}catch{}
 let manual=saved==="dark"||saved==="light";
 function apply(theme){
  root.dataset.theme=theme;root.style.colorScheme=theme;
  const button=document.getElementById("themeToggle");if(!button)return;
  const dark=theme==="dark";button.textContent=dark?"☀ 라이트 모드":"☾ 다크 모드";button.setAttribute("aria-pressed",String(dark));button.setAttribute("aria-label",dark?"라이트 모드로 바꾸기":"다크 모드로 바꾸기");
 }
 apply(manual?saved:system.matches?"dark":"light");
 document.addEventListener("DOMContentLoaded",()=>{
  apply(root.dataset.theme);document.getElementById("themeToggle").addEventListener("click",()=>{
   manual=true;const theme=root.dataset.theme==="dark"?"light":"dark";apply(theme);try{localStorage.setItem(key,theme);}catch{}
  });
 });
 system.addEventListener("change",event=>{if(!manual)apply(event.matches?"dark":"light");});
 window.addEventListener("storage",event=>{if(event.key!==key)return;manual=event.newValue==="dark"||event.newValue==="light";apply(manual?event.newValue:system.matches?"dark":"light");});
})();
