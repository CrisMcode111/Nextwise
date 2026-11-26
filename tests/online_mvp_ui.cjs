const fs=require('fs'), vm=require('vm');
const payload=JSON.parse(fs.readFileSync(0,'utf8'));
class Element {
  constructor(tag){this.tag=tag;this.children=[];this.value='';this.textContent='';this.hidden=false;this.disabled=false;}
  append(e){this.children.push(e);}
  replaceChildren(){this.children=[];}
  addEventListener(){}
}
const elements={}; for(const id of ['project-text','status','project-file','github-url','read-github','discover','access-code','recommendations','understanding','clarifications']) elements[id]=new Element(id);
elements['project-text'].value='A small clinic needs help with appointment scheduling.';elements['access-code'].value='x'.repeat(32);
let stored=null, request=null;
const context={document:{querySelector:s=>elements[s.slice(1)],createElement:t=>new Element(t)},
  localStorage:{getItem:()=>stored,setItem:(k,v)=>{stored=v;}},AbortController,setTimeout,clearTimeout,
  fetch:async(url,options)=>{request=JSON.parse(options.body);return {ok:true,json:async()=>payload.result};},readProjectFile:async()=>'',console};
vm.runInNewContext(fs.readFileSync(payload.script,'utf8'),context);
elements['project-text'].value='A small clinic needs help with appointment scheduling.';
(async()=>{await elements.discover.onclick();
 const cards=elements.recommendations.children;
 if(cards.length!==1 || cards[0].children[0].textContent!=='Synthetic scheduling innovation')throw Error('Recommendation did not render');
 if(!cards[0].children.some(e=>e.tag==='a'&&e.href==='https://example.com/source'))throw Error('Source link missing');
 const dismiss=cards[0].children.find(e=>e.tag==='button'&&e.textContent==='Dismiss');dismiss.onclick();
 if(JSON.parse(stored).history[0].decision!=='dismiss')throw Error('Decision was not persisted');
 await elements.discover.onclick();
 if(request.history[0].decision!=='dismiss'||request.history[0].source_url!=='https://example.com/source')throw Error('Decision history not sent');
 console.log('PASS: actual packaged frontend renders handler recommendation');
})().catch(e=>{console.error(e);process.exitCode=1});
