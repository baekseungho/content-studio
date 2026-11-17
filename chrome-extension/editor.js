"use strict";
// executeScript로 전달되므로 이 함수는 외부 변수나 라이브러리에 의존하지 않는다.
async function editorAction(mode,payload){
 const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
 const sectionText=el=>{
  const clone=el.cloneNode(true);clone.querySelectorAll(".se-placeholder,.se-help-placeholder,.se-guide").forEach(n=>n.remove());
  clone.querySelectorAll('img[alt]').forEach(img=>{if(/\p{Extended_Pictographic}/u.test(img.alt))img.replaceWith(clone.ownerDocument.createTextNode(img.alt));});
  return (clone.textContent||"").replace(/[\u200b\ufeff]/g,"").trim();
 };
 const security=()=>relatedDocs().some(doc=>{
  const text=doc.body?.innerText||"";
  return Boolean(doc.querySelector('#captchaimg,input#captcha,img[alt*="자동입력"]'))||
   ["보호조치","보호 조치","비정상적인 활동","자동입력 방지문자","2단계 인증","이용이 제한"].some(value=>text.includes(value));
 });
 const focusPath=()=>{
  const path=[];let doc=document;
  for(let depth=0;depth<5;depth++){
   const active=doc.activeElement;
   path.push({tag:active?.tagName||"",editable:Boolean(active?.isContentEditable),
     designMode:doc.designMode,editableCount:doc.querySelectorAll('[contenteditable="true"]').length});
   if(active?.tagName!=="IFRAME")break;
   try{
    const nested=active.contentDocument;
    if(!nested){path.push({inaccessible:true});break;}
    doc=nested;
   }catch{path.push({inaccessible:true});break;}
  }
  return path;
 };
 const relatedDocs=()=>{
  let root=window;
  for(let depth=0;depth<5;depth++){
   try{if(root.parent===root)break;void root.parent.document;root=root.parent;}catch{break;}
  }
  const docs=[],seen=new Set();
  const walk=(view,depth)=>{
   if(depth>5)return;
   let doc;try{doc=view.document;}catch{return;}
   if(!doc||seen.has(doc))return;seen.add(doc);docs.push(doc);
   for(const frame of doc.querySelectorAll("iframe")){try{if(frame.contentWindow)walk(frame.contentWindow,depth+1);}catch{}}
  };
  walk(root,0);
  return docs;
 };
 let uploadStage="not-started",activeStep="편집기 확인";
 const formatAttempts=[];let textSync=null;
 const uploadDiagnostic=()=>({
  stage:uploadStage,
  documents:relatedDocs().map(doc=>({
   fileInputs:[...doc.querySelectorAll('input[type="file"]')].map(input=>({
    accept:input.accept,multiple:input.multiple,disabled:input.disabled})).slice(0,8),
   imageButtons:doc.querySelectorAll('[data-name="image"],.se-toolbar-item-image,.se-image-toolbar-button,button[title*="사진"],button[aria-label*="사진"]').length,
   iframeCount:doc.querySelectorAll("iframe").length
  }))
 });
 const resourceImages=()=>{
  let images=[...document.querySelectorAll("img.se-image-resource")];
  if(!images.length)images=[...document.querySelectorAll(".se-component.se-image img,.se-component.se-imageStrip img,.se-component.se-imageGroup img")];
  return images.filter(img=>img.complete&&img.naturalWidth>0);
 };
 const photoCount=()=>resourceImages().length;
 const visible=el=>Boolean(el&&el.getClientRects().length);
 const title=[...document.querySelectorAll(".se-section-documentTitle")].find(visible);
 const body=[...document.querySelectorAll(".se-section-text")].find(visible);
 const blocked=security();
 const existing=Boolean(title&&sectionText(title)||body&&sectionText(body)||document.querySelector(".se-component.se-image,.se-component.se-imageStrip"));
 const toolbarDiagnostic=()=>relatedDocs().flatMap((doc,index)=>[...doc.querySelectorAll('button,[role="option"]')]
  .filter(el=>visible(el)&&(/se-/.test(el.className)||el.hasAttribute("data-name")||el.closest('[role="toolbar"]')))
  .slice(0,60).map(el=>({document:index,class:String(el.className).slice(0,180),name:el.getAttribute("data-name"),value:el.getAttribute("data-value"),label:(el.getAttribute("title")||el.getAttribute("aria-label")||el.textContent||"").trim().slice(0,50),disabled:Boolean(el.disabled)}))).slice(0,100);
 if(mode==="probe")return {blocked,eligible:Boolean(title&&body&&!existing&&!blocked),titleFound:Boolean(title),bodyFound:Boolean(body),existing,iframeCount:document.querySelectorAll("iframe").length};
 let changed=false;
 try{
  if(blocked)throw Object.assign(Error("보호조치·추가 인증이 보여 중단했어요. 공식 네이버에서 직접 확인해 주세요."),{blocked:true});
  if(!title||!body||(existing&&mode!=="format"))throw Error("빈 글쓰기 영역이 아니어서 입력하지 않았어요.");
  if(!payload||(mode!=="format"&&(!Array.isArray(payload.photos)||payload.photos.length>10||typeof payload.title!=="string"||typeof payload.body!=="string")))throw Error("전달된 초안 형식이 올바르지 않아요.");
  const paragraphFormat=el=>{
   const format=payload.format,style=getComputedStyle(el);
   const leaves=[];const walker=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);let textNode;
   while(textNode=walker.nextNode())if(textNode.textContent.trim()&&!textNode.parentElement.closest('.se-placeholder,.se-guide'))leaves.push(textNode.parentElement);
   const nodes=leaves.length?leaves:[el];
   const font=nodes.every(node=>{
    const family=getComputedStyle(node).fontFamily.toLowerCase().replace(/[\s_-]/g,"");
    return family.includes(format.font_key.toLowerCase().replace(/[\s_-]/g,""))||(format.font_key==="nanummaruburi"&&family.includes("maruburi"))||family.includes(format.font.toLowerCase().replace(/\s/g,""));
   });
   return {alignment:style.textAlign===format.align||(format.align==="left"&&style.textAlign==="start"),font,
    size:nodes.every(node=>Math.abs(parseFloat(getComputedStyle(node).fontSize)-format.size)<.5),
    actual:{align:style.textAlign,font:getComputedStyle(nodes[0]).fontFamily,size:getComputedStyle(nodes[0]).fontSize}};
  };
  const formatCheck=()=>{
   if(!payload.format)return {requested:false,verified:true};
   const paragraphs=[...document.querySelectorAll(".se-section-text .se-text-paragraph")].filter(el=>visible(el)&&sectionText(el));
   const checks=paragraphs.map(paragraphFormat);
   const alignment=checks.length>0&&checks.every(item=>item.alignment),font=checks.length>0&&checks.every(item=>item.font),size=checks.length>0&&checks.every(item=>item.size);
   return {requested:true,expected:payload.format,paragraphs:checks.length,alignment,font,size,verified:alignment&&font&&size,samples:checks.slice(0,6)};
  };
  const applyFormat=async(inputDoc)=>{
   const format=payload.format;if(!format)return;
   const active=inputDoc.activeElement;
   const find=(selector,predicate=()=>true)=>relatedDocs().flatMap(doc=>[...doc.querySelectorAll(selector)]).find(el=>visible(el)&&!el.disabled&&predicate(el));
   const click=el=>{const view=el.ownerDocument.defaultView;el.dispatchEvent(new view.MouseEvent("mousedown",{bubbles:true,cancelable:true}));el.dispatchEvent(new view.MouseEvent("mouseup",{bubbles:true,cancelable:true}));el.click();};
   const attempt={fontMenu:false,fontOption:false,sizeMenu:false,sizeOption:false,alignmentMenu:false,alignmentOption:false};
   const menuChoice=async(openSelector,labels,kind)=>{
    const opener=find(openSelector,el=>!el.hasAttribute('data-value'));attempt[kind+"Menu"]=Boolean(opener);if(!opener)return false;
    click(opener);await pause(120);
    const normalized=labels.map(value=>value.replace(/\s/g,""));
    const options=relatedDocs().flatMap(doc=>[...doc.querySelectorAll('[role="option"],.se-toolbar-option,li,button')]).filter(el=>el!==opener&&visible(el)&&!el.disabled);
    if(formatAttempts.length<2)attempt[kind+"Choices"]=options.filter(el=>el.hasAttribute("data-value")||el.matches('[role="option"],.se-toolbar-option')).slice(0,35).map(el=>({class:String(el.className).slice(0,160),name:el.getAttribute("data-name"),value:el.getAttribute("data-value"),label:(el.textContent||"").trim().slice(0,60)}));
    // Prefer the exact model value: Naver repeats the visible label for accessibility.
    const option=options.find(el=>normalized.includes(el.getAttribute("data-value")))||options.find(el=>
      !el.querySelector('button,[role="option"]')&&normalized.includes((el.textContent||"").replace(/\s/g,"")));
    if(option){click(option);await pause(100);attempt[kind+"Option"]=true;return true;}
    click(opener);return false;
   };
   await menuChoice('button[data-name="fontFamily"],button[data-name="font-family"],.se-font-family-toolbar-button',
       [format.font,format.font_key,...(format.font_key==="nanumbareunhipi"?["바른히피","나눔 바른히피"]:format.font_key==="nanummaruburi"?["마루 부리","마루부리","나눔마루부리"]:["나눔고딕"])],"font");
   await menuChoice('button[data-name="fontSize"],button[data-name="font-size"],.se-font-size-toolbar-button,.se-font-size-code-toolbar-button',[String(format.size),format.size+"px","fs"+format.size],"size");
   const alignSelector=format.align==="center"?
       '.se-toolbar-option-align-center-button,.se-toolbar-option-align-center,.se-align-center-toolbar-button,button[data-name="alignCenter"],button[data-name="align-center"],[data-name="align"][data-value="center"],button[title="가운데 정렬"],button[aria-label="가운데 정렬"]':
       '.se-toolbar-option-align-left-button,.se-toolbar-option-align-left,.se-align-left-toolbar-button,button[data-name="alignLeft"],button[data-name="align-left"],[data-name="align"][data-value="left"],button[title="왼쪽 정렬"]';
   const isAlignmentOption=el=>!el.matches('.se-property-toolbar-drop-down-button');
   let align=find(alignSelector,isAlignmentOption);
   if(!align){
    const opener=find('button[data-name^="align-drop-down"]:not([data-value]),.se-property-toolbar-drop-down-button[class*="se-align-"],button[data-name="align"],.se-align-toolbar-button,.se-text-align-toolbar-button,button[title="문단 정렬"],button[aria-label="문단 정렬"]');
    attempt.alignmentMenu=Boolean(opener);
    if(opener){click(opener);await pause(100);if(formatAttempts.length<2)attempt.alignmentChoices=relatedDocs().flatMap(doc=>[...doc.querySelectorAll('button,[role="option"]')]).filter(el=>visible(el)&&(/align/.test(el.className)||el.getAttribute("data-name")==="align")).slice(0,16).map(el=>({class:String(el.className).slice(0,160),name:el.getAttribute("data-name"),value:el.getAttribute("data-value"),label:(el.textContent||"").trim().slice(0,50)}));
     align=find(alignSelector,isAlignmentOption);if(!align)click(opener);}
   }
   if(align){click(align);await pause(100);attempt.alignmentOption=true;}
   if(active?.isConnected)active.focus();
   if(inputDoc===document&&active?.isContentEditable){
    if(!align)inputDoc.execCommand(format.align==="center"?"justifyCenter":"justifyLeft",false,null);
    inputDoc.execCommand("fontName",false,format.font);
   }
   if(formatAttempts.length<100)formatAttempts.push(attempt);
  };
  const repairFormat=async()=>{
   if(!payload.format||formatCheck().verified)return;
   activeStep="문단별 서식 적용·검증";
   const count=document.querySelectorAll(".se-section-text .se-text-paragraph").length;
   for(let index=0;index<count;index++){
    if(security())throw Object.assign(Error("서식 적용 중 본인 인증 화면이 보여 중단했어요."),{blocked:true});
    const paragraph=[...document.querySelectorAll(".se-section-text .se-text-paragraph")][index];
    if(!visible(paragraph)||!sectionText(paragraph))continue;
    const check=paragraphFormat(paragraph);if(check.alignment&&check.font&&check.size)continue;
    paragraph.scrollIntoView({block:"center"});
    const rect=paragraph.getBoundingClientRect(),options={bubbles:true,cancelable:true,view:window,clientX:rect.left+5,clientY:rect.top+5,button:0};
    paragraph.dispatchEvent(new PointerEvent("pointerdown",{...options,pointerType:"mouse",isPrimary:true}));
    paragraph.dispatchEvent(new MouseEvent("mousedown",options));
    paragraph.dispatchEvent(new MouseEvent("mouseup",options));paragraph.click();await pause(80);
    let inputDoc=document;
    for(let depth=0;depth<5&&inputDoc.activeElement?.tagName==="IFRAME";depth++){
     let next;try{next=inputDoc.activeElement.contentDocument;}catch{}if(!next)break;inputDoc=next;
    }
    const active=inputDoc.activeElement;
    if(inputDoc!==document&&active?.isContentEditable){
     // The hidden input's DOM Range is not the editor model's character selection.
     // Let the editor handle Select All before applying character-level font/size.
     const keys={key:"a",code:"KeyA",keyCode:65,which:65,ctrlKey:true,bubbles:true,cancelable:true};
     const down=new inputDoc.defaultView.KeyboardEvent("keydown",keys);active.dispatchEvent(down);
     active.dispatchEvent(new inputDoc.defaultView.KeyboardEvent("keyup",keys));
     if(!down.defaultPrevented){
      const range=inputDoc.createRange();range.selectNodeContents(active);
      const selection=inputDoc.getSelection();selection.removeAllRanges();selection.addRange(range);
     }
     await pause(100);
    }else if(paragraph.isContentEditable){
     const range=document.createRange();range.selectNodeContents(paragraph);
     const selection=document.getSelection();selection.removeAllRanges();selection.addRange(range);
    }
    await pause(100);
    await applyFormat(inputDoc);
    if(formatCheck().verified)break;
   }
  };
  if(mode==="format"){
   const textOnly=()=>[...document.querySelectorAll(".se-section-documentTitle,.se-section-text")].map(sectionText).join("\n");
   const before=textOnly();await repairFormat();
   if(textOnly()!==before)throw Error("서식 적용 중 글 내용이 바뀌어 중단했어요. 열린 편집기를 확인해 주세요.");
   const formatting=formatCheck();
   return {state:formatting.verified?"ready":"partial",stage:activeStep,count:photoCount(),formatting,
    diagnostics:{textSync,formatAttempts,toolbar:toolbarDiagnostic()},
    message:formatting.verified?"기존 글의 정렬·글꼴·크기를 적용하고 확인했어요. 글·사진은 다시 넣지 않았어요.":"글·사진은 다시 넣지 않았어요. 요청한 서식을 모두 확인하지 못했어요. 아래 서식 진단을 확인해 주세요."};
  }
  const insert=async(section,value)=>{
   activeStep=section.matches(".se-section-documentTitle")?"제목 입력":"본문 입력";
   const paragraph=[...section.querySelectorAll(".se-text-paragraph")].find(visible)||section;
   paragraph.scrollIntoView({block:"center"});
   const rect=paragraph.getBoundingClientRect();
   const eventOptions={bubbles:true,cancelable:true,view:window,clientX:rect.left+Math.min(12,rect.width/2),clientY:rect.top+Math.min(12,rect.height/2),button:0,buttons:1};
   // 단순 click만으로 편집기를 활성화하지 않는 버전의 실제 이벤트 흐름을 따른다.
   paragraph.dispatchEvent(new PointerEvent("pointerdown",{...eventOptions,pointerType:"mouse",isPrimary:true}));
   paragraph.dispatchEvent(new MouseEvent("mousedown",eventOptions));
   paragraph.dispatchEvent(new PointerEvent("pointerup",{...eventOptions,buttons:0,pointerType:"mouse",isPrimary:true}));
   paragraph.dispatchEvent(new MouseEvent("mouseup",{...eventOptions,buttons:0}));
   paragraph.click();
   await pause(120);
   let inputDoc=document,inputTarget=null;
   // 문단 클릭이 실제 입력 iframe으로 포커스를 옮겼다면 해당 문서의 선택 범위를 보존한다.
   // 부모의 표시용 문단에 Range를 만들면 iframe의 정상 키보드 포커스를 잃는다.
   for(let depth=0;depth<5;depth++){
    const active=inputDoc.activeElement;
    if(active?.tagName!=="IFRAME")break;
    let nested;
    try{nested=active.contentDocument;}catch{}
    if(!nested)throw Error("입력 iframe에 접근할 수 없어요. 직접 복사 기능을 사용하고 입력 상태 진단을 확인해 주세요.");
    inputDoc=nested;
   }
   const active=inputDoc.activeElement;
   if(inputDoc!==document){
    if(active?.isContentEditable||active?.tagName==="TEXTAREA")inputTarget=active;
    else if(inputDoc.body?.isContentEditable||inputDoc.designMode==="on")inputTarget=inputDoc.body;
    if(!inputTarget)throw Error("포커스된 iframe 안에 편집 가능한 입력 영역이 없어요. 입력 상태 진단을 확인해 주세요.");
    inputTarget.focus();
    if(inputTarget.tagName!=="TEXTAREA"){
     const selection=inputDoc.defaultView.getSelection();
     if(!selection.rangeCount||!inputTarget.contains(selection.anchorNode)){
      const range=inputDoc.createRange();range.selectNodeContents(inputTarget);range.collapse(false);
      selection.removeAllRanges();selection.addRange(range);
     }
    }
   }else if(paragraph.isContentEditable){
    let editable=paragraph;
    while(editable.parentElement?.isContentEditable)editable=editable.parentElement;
    editable.focus();
    const range=document.createRange();range.selectNodeContents(paragraph);range.collapse(false);
    const selection=window.getSelection();selection.removeAllRanges();selection.addRange(range);
   }else if(active?.isContentEditable&&active.closest(".se-editor,.se-container")){
    // 같은 문서의 입력 프록시 역시 편집기가 정한 선택 범위를 바꾸지 않는다.
    inputTarget=active;
   }else{
    throw Error("표시용 문단과 실제 입력 영역의 연결을 확인하지 못했어요. 입력 상태 진단을 확인해 주세요.");
   }
   if(!value)return;
   const isTitle=section.matches(".se-section-documentTitle");
   const sections=()=>[...document.querySelectorAll(isTitle?".se-section-documentTitle":".se-section-text")].filter(visible);
   const normal=text=>text.normalize("NFC").replace(/[\s\u200b\ufeff\ufe0e\ufe0f]/g,"");
   const readModel=()=>normal(sections().map(sectionText).join(""));
   const lineCount=()=>{
    const paragraphs=sections().flatMap(el=>[...el.querySelectorAll(".se-text-paragraph")]).filter(el=>visible(el)&&sectionText(el));
    return paragraphs.reduce((count,el)=>count+Math.max(1,(el.innerText||"").split(/\n+/).filter(text=>text.trim()).length),0);
   };
   const structure=()=>document.querySelectorAll(".se-section-text .se-text-paragraph,.se-section-text p,.se-section-text br").length;
   const findInputDoc=()=>{
    let doc=document;
    for(let depth=0;depth<5&&doc.activeElement?.tagName==="IFRAME";depth++){
     let next;try{next=doc.activeElement.contentDocument;}catch{}if(!next)break;doc=next;
    }
    return doc;
   };
   const baseline=readModel(),baselineLines=lineCount();
   let written="",accepted=true;
   const lines=value.replace(/\r\n?/g,"\n").split("\n");
   const segmenter=new Intl.Segmenter("ko",{granularity:"grapheme"});
   const chunksFor=line=>{
    const chunks=[];let plain="",length=0;
    const flush=()=>{if(plain){chunks.push(plain);plain="";length=0;}};
    for(const {segment} of segmenter.segment(line)){
     if(/[\p{Extended_Pictographic}\p{Regional_Indicator}\u20e3]/u.test(segment)){flush();chunks.push(segment);}
     else{plain+=segment;length++;if(length>=12)flush();}
    }
    flush();return chunks;
   };
   for(let i=0;i<lines.length;i++){
    if(security())throw Object.assign(Error("글 입력 중 보호조치·추가 인증이 보여 중단했어요."),{blocked:true});
    inputDoc=findInputDoc();
    textSync={line:i+1,totalLines:lines.length,chunk:0,expectedLineCharacters:[...lines[i]].length,confirmedCharacters:normal(written).length,phase:"줄 시작"};
    if(i){
     const before=structure(),beforeLines=lineCount();
     const target=inputDoc.activeElement||inputDoc.body;
     const options={key:"Enter",code:"Enter",keyCode:13,which:13,bubbles:true,cancelable:true};
     const down=new inputDoc.defaultView.KeyboardEvent("keydown",options);target.dispatchEvent(down);
     let pressed=null;
     if(!down.defaultPrevented){pressed=new inputDoc.defaultView.KeyboardEvent("keypress",{...options,charCode:13});target.dispatchEvent(pressed);}
     target.dispatchEvent(new inputDoc.defaultView.KeyboardEvent("keyup",options));await pause(70);
     if(!down.defaultPrevented&&!pressed?.defaultPrevented&&structure()===before&&lineCount()===beforeLines){
      inputDoc=findInputDoc();inputDoc.execCommand("insertParagraph",false,null);await pause(70);
     }
     written+="\n";
    }
    const chunks=chunksFor(lines[i]);let lineWritten="";
    for(let chunkIndex=0;chunkIndex<chunks.length;chunkIndex++){
     inputDoc=findInputDoc();const target=inputDoc.activeElement;
     if(inputDoc!==document){
      if(!target?.isContentEditable&&target?.tagName!=="TEXTAREA")throw Error("글 입력 중 실제 입력 프레임의 초점을 잃었어요. 열린 편집기를 확인해 주세요.");
      if(target.isContentEditable){
       const selection=inputDoc.getSelection();
       if(!selection.rangeCount||!target.contains(selection.anchorNode)||(!isTitle&&normal(target.textContent||"")===normal(lineWritten))){
        const range=inputDoc.createRange();range.selectNodeContents(target);range.collapse(false);selection.removeAllRanges();selection.addRange(range);
       }
      }
     }else if(!target?.isContentEditable)throw Error("글 입력 중 편집 초점을 잃었어요. 열린 편집기를 확인해 주세요.");
     const chunk=chunks[chunkIndex],emoji=/[\p{Extended_Pictographic}\p{Regional_Indicator}\u20e3]/u.test(chunk);
     const expected=baseline+normal(written+chunk);
     textSync={...textSync,chunk:chunkIndex+1,totalChunks:chunks.length,phase:"화면 반영 확인",emoji,expectedCharacters:expected.length,observedCharacters:readModel().length};
     accepted=inputDoc.execCommand("insertText",false,chunk)&&accepted;
     await pause(emoji?180:30);
     const deadline=Date.now()+3000;let actual=readModel();
     while(actual!==expected&&Date.now()<deadline){await pause(40);actual=readModel();}
     textSync.observedCharacters=actual.length;textSync.prefixPreserved=actual.startsWith(baseline);textSync.exact=actual===expected;
     if(actual!==expected){
      textSync.phase="불일치로 중단";
      throw Error((isTitle?"제목":"본문")+" "+(i+1)+"번째 줄 "+(chunkIndex+1)+"번째 조각의 반영을 확인하지 못했어요. "+(emoji?"이모지":"문자")+" 입력 이후 화면과 초안이 달라 추가 입력을 중단했어요. 이미 입력된 글은 다시 넣지 않았어요.");
     }
     written+=chunk;lineWritten+=chunk;textSync.confirmedCharacters=normal(written).length;
    }
   }
   const wantedLines=lines.filter(line=>line.trim()).length;
   if(wantedLines>1&&lineCount()<baselineLines+wantedLines)throw Error("본문 글자는 입력됐지만 문단 구분을 확인하지 못했어요. 사진 입력 전에 중단했어요. 본문 복사로 직접 붙여 넣거나 진단을 확인해 주세요.");
   textSync={...textSync,phase:"본문 반영 확인 완료",exact:true};
   return;
  };
  const uploadPhotos=async(photos,expectedTotal)=>{
   activeStep="사진 업로드";uploadStage="finding-toolbar";
   const preventPicker=event=>{if(event.target?.tagName==="INPUT"&&event.target.type==="file")event.preventDefault();};
   const observed=new Set();
   const observe=()=>{for(const doc of relatedDocs()){if(!observed.has(doc)){doc.addEventListener("click",preventPicker,true);observed.add(doc);}}};
   observe();
   const previous=new Set(relatedDocs().flatMap(doc=>[...doc.querySelectorAll('input[type="file"]')]));
   const imageAccept=accept=>/image|jpe?g|png|gif|webp|bmp|heic/i.test(accept);
   const inputs=()=>relatedDocs().flatMap(doc=>[...doc.querySelectorAll('input[type="file"]')])
      .filter(input=>!input.disabled&&(imageAccept(input.accept)||(!input.accept&&!previous.has(input))));
   const choose=()=>inputs().find(input=>input.multiple)||inputs()[0];
   const clickControl=control=>{
    const doc=control.ownerDocument,view=doc.defaultView,rect=control.getBoundingClientRect();
    const opts={bubbles:true,cancelable:true,view,clientX:rect.left+4,clientY:rect.top+4,button:0};
    control.dispatchEvent(new view.MouseEvent("mousedown",opts));
    control.dispatchEvent(new view.MouseEvent("mouseup",opts));
    control.click();
   };
   const findToolbar=()=>{
    for(const doc of relatedDocs()){
     const known=[...doc.querySelectorAll('button[data-name="image"],[data-name="image"] button,.se-toolbar-item-image button,.se-toolbar-item-image,.se-image-toolbar-button,button.se-toolbar-button-image')].find(visible);
     if(known)return known.matches("button,a,[role=button]")?known:known.querySelector("button,a,[role=button]")||known;
     const candidate=[...doc.querySelectorAll("button,[role=button],a")].find(el=>visible(el)&&
       [el.getAttribute("title"),el.getAttribute("aria-label"),el.textContent].some(label=>["사진","사진 추가","사진 업로드","사진 첨부","이미지","이미지 추가","이미지 업로드"].includes((label||"").replace(/\s+/g," ").trim())));
     if(candidate)return candidate;
    }
    return null;
   };
   let input;
   try{
    const toolbar=findToolbar();
    if(toolbar){clickControl(toolbar);uploadStage="waiting-upload-dialog";}
    const deadline=Date.now()+7000;
    let menuClicked=false;
    while(Date.now()<deadline){
     observe();input=choose();if(input)break;
     if(!menuClicked){
      let menu;
      for(const doc of relatedDocs()){
       menu=[...doc.querySelectorAll("button,a,[role=button],li,span")].find(el=>visible(el)&&
         ["내 컴퓨터","내 컴퓨터에서","컴퓨터에서 사진 선택","PC에서 선택","사진 올리기"].includes((el.textContent||"").replace(/\s+/g," ").trim()));
       if(menu)break;
      }
      if(menu){clickControl(menu.closest("button,a,[role=button],li")||menu);menuClicked=true;uploadStage="waiting-file-input";}
     }
     if(security())throw Object.assign(Error("사진 창에서 보호조치가 감지되어 중단했어요."),{blocked:true});
     await pause(180);
    }
   }finally{for(const doc of observed)doc.removeEventListener("click",preventPicker,true);}
   if(!input){
    uploadStage="file-input-not-found";
    throw Error("사진 버튼·업로드 창에서 파일 선택 영역을 찾지 못했어요. 새 버전의 입력 상태 진단을 확인해 주세요. 별도 사진 창이 떴다면 그 창은 닫지 말아 주세요.");
   }
   if(photos.length>1&&!input.multiple)throw Error("여러 장 사진 선택을 지원하지 않는 입력이에요. 직접 사진을 추가해 주세요.");
   uploadStage="transferring-files";
   const uploadWindow=input.ownerDocument.defaultView;
   const transfer=new uploadWindow.DataTransfer();
   for(const photo of photos){
    const binary=atob(photo.base64),bytes=new Uint8Array(binary.length);
    for(let i=0;i<binary.length;i++)bytes[i]=binary.charCodeAt(i);
    transfer.items.add(new uploadWindow.File([bytes],photo.name,{type:"image/jpeg"}));
   }
   input.files=transfer.files;input.dispatchEvent(new uploadWindow.Event("change",{bubbles:true}));
   uploadStage="waiting-images";
   const deadline=Date.now()+45000;
   let confirmedPhotoDialog=false;
   while(Date.now()<deadline){
    if(security())throw Object.assign(Error("사진 입력 중 보호조치·추가 인증을 감지해 중단했어요."),{blocked:true});
    if(photoCount()===expectedTotal)break;
    // 별도 파일 업로드 문서의 사진 확인만 처리한다. 블로그의 최종 발행은 누르지 않는다.
    const uploadDoc=input.ownerDocument;
    if(!confirmedPhotoDialog&&uploadDoc!==document&&!uploadDoc.querySelector(".se-section-documentTitle,.se-section-text")&&input.files.length===photos.length){
     const scope=input.closest("form")||uploadDoc.body;
     const confirm=[...scope.querySelectorAll('button,[role="button"],input[type="button"],input[type="submit"]')].find(button=>
       visible(button)&&!button.disabled&&["사진 등록","사진 넣기","선택 완료","첨부 완료","등록","확인"].includes((button.textContent||button.value||"").trim()));
     if(confirm){clickControl(confirm);confirmedPhotoDialog=true;uploadStage="photo-dialog-confirmed";}
    }
    await pause(350);
   }
   if(photoCount()!==expectedTotal)throw Error("사진 "+photos.length+"장 중 로딩 확인은 "+photoCount()+"장이에요. 자동 재시도하지 말고 열린 편집기를 확인해 주세요.");
  };
  const help=document.querySelector(".se-help-panel-close-button");if(visible(help))help.click();
  await insert(title,payload.title);changed=true;
  if(sectionText(title)!==payload.title.trim())throw Error("제목 입력이 확인되지 않았어요.");
  const plan=[],used=new Set();
  const plain=text=>text.replace(/^##\s+/gm,"").trim();
  const pattern=/\[\[photo:(\d+)\]\]/g;
  let cursor=0,match;
  while((match=pattern.exec(payload.body))){
   const text=plain(payload.body.slice(cursor,match.index));if(text)plan.push({text});
   const index=Number(match[1])-1;
   if(index<0||index>=payload.photos.length||used.has(index))throw Error("사진 위치 표시가 중복되거나 범위를 벗어났어요. 앱에서 초안을 다시 저장해 주세요.");
   used.add(index);plan.push({photo:index});cursor=pattern.lastIndex;
  }
  const tail=plain(payload.body.slice(cursor));if(tail)plan.push({text:tail});
  payload.photos.forEach((photo,index)=>{if(!used.has(index))plan.push({photo:index});});
  const afterImage=img=>[...document.querySelectorAll(".se-section-text .se-text-paragraph")]
     .find(paragraph=>visible(paragraph)&&Boolean(img.compareDocumentPosition(paragraph)&Node.DOCUMENT_POSITION_FOLLOWING));
  const followingSection=async img=>{
   let paragraph=afterImage(img);if(paragraph)return paragraph.closest(".se-section-text");
   // 편집기가 업로드 후 비어 있는 다음 문단을 아직 만들지 않았다면 실제 선택 이벤트로 한 번 요청한다.
   const component=img.closest(".se-component")||img;
   component.scrollIntoView({block:"center"});
   const rect=component.getBoundingClientRect(),opts={bubbles:true,cancelable:true,view:window,clientX:rect.left+5,clientY:rect.top+5};
   component.dispatchEvent(new MouseEvent("mousedown",opts));component.dispatchEvent(new MouseEvent("mouseup",opts));component.click();
   let doc=document;
   for(let depth=0;depth<5&&doc.activeElement?.tagName==="IFRAME";depth++){
    let next;try{next=doc.activeElement.contentDocument;}catch{}if(!next)break;doc=next;
   }
   const target=doc.activeElement||doc.body;
   for(const key of ["ArrowDown","Enter"]){
    const options={key,code:key,keyCode:key==="Enter"?13:40,which:key==="Enter"?13:40,bubbles:true,cancelable:true};
    const down=new doc.defaultView.KeyboardEvent("keydown",options);target.dispatchEvent(down);
    target.dispatchEvent(new doc.defaultView.KeyboardEvent("keyup",options));
    if(key==="Enter"&&!down.defaultPrevented)doc.execCommand("insertParagraph",false,null);
    await pause(100);
   }
   const deadline=Date.now()+1200;
   do{paragraph=afterImage(img);if(paragraph)return paragraph.closest(".se-section-text");await pause(80);}while(Date.now()<deadline);
   throw Error("사진 뒤에 다음 글을 넣을 문단을 확인하지 못했어요. 사진을 끝에 몰아넣지 않고 중단했습니다. 열린 편집기에서 배치를 확인해 주세요.");
  };
  let targetBody=body,lastBoundary=null;
  for(let step=0;step<plan.length;step++){
   if(security())throw Object.assign(Error("보호조치를 감지해 중단했어요."),{blocked:true});
   const block=plan[step];
   if(block.text){
    await insert(targetBody,block.text);
    const paragraphs=[...document.querySelectorAll(".se-section-text .se-text-paragraph")].filter(el=>visible(el)&&sectionText(el));
    lastBoundary=paragraphs.at(-1)||targetBody;
   }else{
    if(step===0||plan[step-1].photo!==undefined)await insert(targetBody,"");
    const before=photoCount();
    await uploadPhotos([payload.photos[block.photo]],before+1);
    const img=resourceImages()[before];
    if(!img||lastBoundary&&!(lastBoundary.compareDocumentPosition(img)&Node.DOCUMENT_POSITION_FOLLOWING)){
     throw Error("사진이 요청한 문단 뒤에 배치됐는지 확인하지 못했어요. 추가 입력을 중단했으니 열린 편집기를 확인해 주세요.");
    }
    if(step<plan.length-1)targetBody=await followingSection(img);
   }
  }
  if(photoCount()!==payload.photos.length)throw Error("사진 수가 일치하지 않아 완료로 처리하지 않았어요.");
  const beforeRepair=[...document.querySelectorAll(".se-section-text")].map(el=>sectionText(el)).join("\n");
  await repairFormat();
  if([...document.querySelectorAll(".se-section-text")].map(el=>sectionText(el)).join("\n")!==beforeRepair)throw Error("서식 확인 중 본문이 바뀌어 완료로 기록하지 않았어요. 열린 편집기를 확인해 주세요.");
  const formatting=formatCheck();
  return {state:formatting.verified?"ready":"partial",stage:"입력·서식 결과 확인",count:photoCount(),formatting,
    diagnostics:{textSync,formatAttempts,toolbar:toolbarDiagnostic()},
    message:formatting.verified?"글·사진 전달과 정렬·글꼴·크기 적용을 확인했어요. 네이버에서 내용을 확인한 뒤 발행해 주세요.":"글과 사진은 입력됐지만 요청한 서식을 모두 확인하지 못했어요. 정렬·글꼴·크기 진단을 확인하고, 필요하면 확장에서 ‘서식만 다시 적용’을 눌러 주세요. 글은 다시 넣지 마세요."};
 }catch(error){
  return {state:error.blocked?"blocked":"failed",stage:activeStep,count:photoCount(),
    diagnostics:{textSync,formatAttempts,toolbar:toolbarDiagnostic(),titleEditable:Boolean(title?.isContentEditable),bodyEditable:Boolean(body?.isContentEditable),
      activeTag:document.activeElement?.tagName||"",activeEditable:Boolean(document.activeElement?.isContentEditable),
      editableCount:document.querySelectorAll('[contenteditable="true"]').length,focusPath:focusPath(),upload:uploadDiagnostic(),requestedTemplate:payload?.format?.label||""},
    message:error.message+(changed?" 일부 내용이 남아 있을 수 있어요.":"")};
 }
}
