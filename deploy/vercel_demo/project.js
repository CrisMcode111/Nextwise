'use strict';
const MAX_PROJECT_TEXT=12000,MAX_PROJECT_FILE=2_000_000,MAX_PDF_PAGES=20;
const DEMO_NEEDS={
  structured_extraction:{label:'Turn free text into structured information',
    pattern:/\bstructured (?:data|outputs?|information|requirements)\b|\b(?:extract|parse|convert|turn)\b.{0,100}\b(?:free text|messages?|documents?|pdf|requests?|requirements|preferences)\b/i},
  constraint_validation:{label:'Check the format and completeness of collected data',
    pattern:/\b(?:validat\w*|check)\b.{0,80}\b(?:data|schemas?|types?|fields?|structured|requirements)\b/i},
  extraction_evaluation:{label:'Test whether AI outputs preserve the right details',
    pattern:/\b(?:evaluat\w*|test\w*|check)\b.{0,100}\b(?:llms?|ai|models?|prompts?|extraction)\b|\b(?:llms?|ai|models?|prompts?)\b.{0,100}\b(?:evaluat\w*|test\w*)\b/i}
};
const EXAMPLE_PROJECT='I run a meal-planning business. My goal is to help busy parents choose meal plans that fit their food preferences.';

function isGuidedRawGourmet(text){
  // Explicit name AND the supported goal are required. This recognizes a prepared
  // scenario, not semantic reasoning or a universal recommendation rule.
  const affirmed=String(text).split(/[\n.!?]+/).filter(line=>!/\b(?:not|never|unlike|without|don't|do not)\b/i.test(line)).join(' ');
  return /\bAI[ -]+Raw[ -]+Gourmet\b/i.test(affirmed)
    && /\brecipes?\b/i.test(affirmed) && /\bmeal[ -]+plans?\b/i.test(affirmed)
    && /\b(?:generat\w*|adapt\w*|personaliz\w*|personalis\w*)\b/i.test(affirmed)
    && /\b(?:constraints?|preferences?|dietary|requirements?)\b/i.test(affirmed);
}

function extractProject(text){
  const cleaned=String(text).trim();
  if(!cleaned||cleaned.length>MAX_PROJECT_TEXT)throw new Error('Please enter up to 12,000 characters about your project.');
  const lines=cleaned.split(/[\n.!?]+/).map(line=>line.trim()).filter(Boolean);
  const negated=line=>/\b(?:do not|don't|don’t|never)\s+(?:want|need|use|build|integrate|extract|validate|check|evaluate|test|answer|schedule|promote|process)\b|\b(?:no need for|not interested in|not looking for)\b|\b(?:no|without)\s+(?:ai|artificial intelligence|automation)\b/i.test(line);
  const affirmed=lines.filter(line=>!negated(line));
  const technicalRequested=affirmed.some(line=>/\b(?:need|want|looking for|recommend|use|integrate)\b.{0,100}\b(?:libraries|library|sdk|api|framework|developer tools?)\b/i.test(line));
  const needs=[];
  for(const [id,rule] of Object.entries(BUSINESS_NEEDS)){
    const evidence=affirmed.find(line=>new RegExp(rule.project_pattern,'i').test(line));
    if(evidence)needs.push({id,label:rule.label,evidence:evidence.slice(0,300)});
  }
  for(const [id,rule] of Object.entries(technicalRequested?DEMO_NEEDS:{})){
    // Conservative local matching, not model analysis. Negated lines are not evidence.
    const evidence=affirmed.find(line=>rule.pattern.test(line));
    if(evidence)needs.push({id,label:rule.label,evidence:evidence.slice(0,300)});
  }
  const goal=affirmed.find(line=>/\b(?:goal|want to|aim to|hope to|need to|grow|launch|sell|offer)\b/i.test(line))||lines[0];
  const challenges=affirmed.filter(line=>/\b(?:struggl\w*|takes? too|too much|too many|hard to|difficult|missed|need help|time[- ]consuming|keeps? me)\b/i.test(line)).slice(0,3);
  const technicalNeeds=needs.filter(need=>Object.hasOwn(DEMO_NEEDS,need.id));
  return {summary:lines.slice(0,2).join('. ').slice(0,400),goal:goal.slice(0,400),challenges,
    needs:technicalRequested&&technicalNeeds.length?technicalNeeds:needs,technicalRequested};
}

async function readPdfText(bytes,pdf){
  const task=pdf.getDocument({data:bytes,isEvalSupported:false,useWasm:false,
    useWorkerFetch:false,disableFontFace:true,useSystemFonts:false,enableXfa:false,
    stopAtErrors:true,disableAutoFetch:true,disableStream:true,disableRange:true,maxImageSize:0});
  let timer;
  task.onPassword=()=>{void task.destroy();};
  try{
    return await Promise.race([(async()=>{
      const document=await task.promise;
      if(document.numPages>MAX_PDF_PAGES)throw new Error('Please use a PDF with at most 20 pages.');
      let text='';
      for(let pageNumber=1;pageNumber<=document.numPages;pageNumber++){
        const page=await document.getPage(pageNumber);
        const content=await page.getTextContent();
        text+=content.items.map(item=>item.str+(item.hasEOL?'\n':' ')).join('')+'\n';
        page.cleanup();
        if(text.length>MAX_PROJECT_TEXT)throw new Error('This PDF has too much text. Please use a shorter document or paste an excerpt.');
      }
      if(!text.trim())throw new Error('I couldn’t find readable text in this PDF. Scanned files need OCR; please paste the text instead.');
      return text.trim();
    })(),new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('This PDF took too long to read. Please paste a short excerpt instead.')),15000);})]);
  }finally{clearTimeout(timer);await task.destroy();}
}

async function readProjectFile(file,pdfLoader=()=>import('/pdfjs/pdf.mjs')){
  if(!file||file.size>MAX_PROJECT_FILE)throw new Error('Please choose a PDF or TXT file smaller than 2 MB.');
  const extension=file.name.toLowerCase().split('.').pop();
  if(extension==='txt'){
    const text=await file.text();
    if(!text.trim()||text.length>MAX_PROJECT_TEXT||text.includes('\u0000'))throw new Error('Please use readable text with up to 12,000 characters.');
    return text;
  }
  if(extension!=='pdf')throw new Error('Please choose a PDF or TXT file.');
  const bytes=new Uint8Array(await file.arrayBuffer());
  if(new TextDecoder().decode(bytes.slice(0,5))!=='%PDF-')throw new Error('This file is not a readable PDF.');
  const pdf=await pdfLoader();pdf.GlobalWorkerOptions.workerSrc='/pdfjs/pdf.worker.mjs';
  try{return await readPdfText(bytes,pdf);}
  catch(error){throw new Error(error.message?.startsWith('Please')||error.message?.startsWith('I couldn’t')?error.message:'I couldn’t read this PDF. It may be encrypted, damaged or unsupported. Please paste its text instead.');}
}
