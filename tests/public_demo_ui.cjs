// Execute the real generated UI offline; no browser/network packages.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const fixture=JSON.parse(fs.readFileSync(0,'utf8')),bundle=process.argv[2],store=new Map();
const storageKey='nextwise.public-demo.decisions.v1';
class Element{
  constructor(tag){this.tagName=tag.toUpperCase();this.children=[];this.ownText='';this.dataset={};this.attributes={};this.value='';this.hidden=false;this.classList={add(){},toggle(){}};}
  set textContent(text){this.ownText=String(text);this.children=[];}
  get textContent(){return this.ownText+this.children.map(n=>n.textContent).join(' ');}
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(...nodes){this.ownText='';this.children=nodes;}
  setAttribute(name,value){this.attributes[name]=String(value);}
  querySelectorAll(selector){return this.children.flatMap(node=>[...(node.tagName===selector.toUpperCase()?[node]:[]),...node.querySelectorAll(selector)]);}
  querySelector(selector){return this.querySelectorAll(selector)[0]||null;}
}
async function start({failStorage=false,failSource=null,empty=false,failInit=false,projectText='I need developer libraries. Extract user requirements from free text. Validate schema and types of data. Evaluate LLM outputs.'}={}){
  const nodes=new Map(),calls=[];
  const html=fs.readFileSync(path.join(bundle,'public/index.html'),'utf8');
  for(const match of html.matchAll(/<([a-z]+)\b[^>]*\bid="([^"]+)"[^>]*>/g)){
    const node=new Element(match[1]);node.hidden=/\bhidden\b/.test(match[0]);nodes.set('#'+match[2],node);
  }
  nodes.get('#project-text').value=projectText;
  const document={querySelector:selector=>nodes.get(selector)||null,createElement:tag=>new Element(tag)};
  const localStorage={getItem:key=>store.get(key)||null,setItem(key,value){if(failStorage)throw new Error('Blocked storage');store.set(key,value);},removeItem:key=>store.delete(key)};
  let active=0,maximumActive=0;
  const context=vm.createContext({document,localStorage,URL,AbortController,Date,TextDecoder,TextEncoder,Uint8Array,crypto:require('node:crypto').webcrypto,setTimeout:()=>1,clearTimeout(){},
    fetch:async(url,options)=>{
      calls.push({url,options});assert.equal(options.credentials,'omit');assert(!options.body);
      if(url==='/api/demo'){
        if(failInit)throw new Error('Initialization failure');
        return {ok:true,json:async()=>fixture.demo};
      }
      assert.equal(nodes.get('#search-progress').hidden,false,'Search copy only accompanies an actual pending source request');
      assert.equal(nodes.get('#assistant-identity').dataset.processing,'true');
      assert(nodes.get('#progress-message').textContent.includes('Searching public repositories'));
      assert.equal(nodes.get('#project-text').disabled,true);
      active++;maximumActive=Math.max(maximumActive,active);
      // Re-entrant checks while loading must not start any extra requests.
      await vm.runInContext('checkDemoSources()',context);
      await Promise.resolve();active--;
      const source=new URL(url,'https://demo.example').searchParams.get('need');
      assert(url.startsWith('/api/discover?need='));assert(Object.hasOwn(fixture.previews,source));
      if(source===failSource)throw new Error('Offline source failure');
      const result=structuredClone(fixture.previews[source]);if(empty)result.candidates=[];
      return {ok:true,json:async()=>result};
    }});
  vm.runInContext(fs.readFileSync(path.join(bundle,'public/app.js'),'utf8'),context);
  vm.runInContext(fs.readFileSync(path.join(bundle,'public/project.js'),'utf8'),context);
  await vm.runInContext(fs.readFileSync(path.join(bundle,'public/demo.js'),'utf8'),context);
  assert(maximumActive<=1,'Source checks must remain sequential');
  assert.equal(nodes.get('#search-progress').hidden,true,'No search copy when checking finishes or fails');
  assert.equal(nodes.get('#assistant-identity').dataset.processing||'false','false','Identity returns to its idle state after processing');
  return {nodes,calls,context};
}
function cards(app){return app.nodes.get('#tool-candidates').querySelectorAll('article');}
(async()=>{
  const app=await start();
  assert.equal(app.calls.length,4,'One metadata request and three automatic source checks');
  assert.equal(app.calls[0].url,'/api/demo');
  assert.equal(cards(app).length,2);
  assert(app.nodes.get('#state').textContent.includes('two possible opportunities'));
  assert(app.nodes.get('#demo-evidence').textContent.includes('What I checked'));
  // The automatic pass has already populated the cache. A real button click
  // must acknowledge applying the needs instead of looking like a no-op.
  await app.nodes.get('#find-ideas').onclick();
  assert(app.nodes.get('#project-status').textContent.includes('Applied your selected needs'));
  assert(app.nodes.get('#project-status').textContent.includes('no new search'));
  assert.equal(app.calls.length,4,'Acknowledging the cached click must not repeat searches');
  for(const card of cards(app)){
    assert(card.textContent.includes('This may help'));
    assert(card.textContent.includes('A small next step:'));
    assert.equal(card.querySelectorAll('a').length,2);
    assert.equal(card.querySelector('a').textContent,'Source');
    assert.equal(card.querySelectorAll('button').length,3);
    assert.equal(card.querySelectorAll('button')[0].textContent,'Explore this');
    assert.equal(card.querySelectorAll('button')[1].textContent,'Explain why');
    assert.equal(card.querySelectorAll('button')[2].textContent,'Not interested');
    assert.equal(card.querySelectorAll('form').length,0);
    const evidence=card.children.find(node=>node.className==='suggestion-evidence');
    assert.equal(evidence.hidden,true,'Evidence and limitations start collapsed');
    assert(evidence.textContent.includes('not a tested recommendation'));
    assert(evidence.textContent.includes('What we still need to check'));
    assert(!card.children.filter(node=>node!==evidence).map(node=>node.textContent).join(' ').includes('Discovery candidate'));
  }
  const instructor=cards(app)[0],explain=instructor.querySelectorAll('button')[1];
  const evidence=instructor.children.find(node=>node.className==='suggestion-evidence');
  assert.equal(explain.attributes['aria-controls'],evidence.id);
  assert.equal(explain.attributes['aria-expanded'],'false');
  explain.onclick();
  assert.equal(evidence.hidden,false);
  assert.equal(explain.attributes['aria-expanded'],'true');
  assert(evidence.textContent.includes(fixture.previews.instructor.candidates[0].description));
  assert(evidence.textContent.includes(fixture.previews.instructor.candidates[0].limitations[0]));
  const source=evidence.querySelector('a');
  assert.equal(source.href,'https://github.com/fixture-owner/Instructor');
  assert.equal(source.target,'_blank');assert.equal(source.rel,'noopener noreferrer');
  assert.equal(store.size,0,'An explanation must not imply a saved decision');
  assert.equal(app.calls.length,4,'Explaining uses existing evidence, with no extra request');
  explain.onclick();assert.equal(evidence.hidden,true);assert.equal(explain.attributes['aria-expanded'],'false');
  instructor.querySelectorAll('button')[2].onclick();
  const savedId=fixture.previews.instructor.candidates[0].demo_source_id;
  assert.equal(JSON.parse(store.get(storageKey))[savedId].choice,'Defer');
  assert.equal(cards(app).length,2);
  assert.equal(app.calls.length,4,'Choices must not cause API calls');
  await vm.runInContext('checkDemoSources()',app.context);
  assert.equal(app.calls.length,4,'No repeat automatic pass or retry');
  const reload=await start();
  assert.equal(reload.calls.length,4);assert.equal(cards(reload).length,2);
  assert(!cards(reload).some(card=>card.textContent.includes('I found Instructor.')));
  assert(reload.nodes.get('#demo-choices').textContent.includes('Not interested'));
  reload.nodes.get('#clear-choices').onclick();
  assert.equal(reload.calls.length,4);assert.equal(store.size,0);
  assert(reload.nodes.get('#choice-status').textContent.includes('reused'));

  const partial=await start({failSource:'pydantic'});
  assert.equal(cards(partial).length,2);assert.equal(partial.calls.length,4);
  assert(partial.nodes.get('#discovery-status').textContent.includes('incomplete'));
  assert(partial.nodes.get('#demo-evidence').textContent.includes('No retry'));
  const zero=await start({empty:true});
  assert.equal(cards(zero).length,0);assert.equal(zero.calls.length,4);
  assert(zero.nodes.get('#state').textContent.includes('I don’t have a usable product'));
  const blocked=await start({failStorage:true});
  cards(blocked)[0].querySelectorAll('button')[2].onclick();
  assert(blocked.nodes.get('#choice-status').textContent.includes('not saved'));
  assert.equal(cards(blocked).length,2);assert.equal(blocked.calls.length,4);assert.equal(store.size,0);
  cards(blocked)[0].querySelectorAll('button')[0].onclick();
  assert.equal(blocked.nodes.get('#selection-status').hidden,false);
  assert(blocked.nodes.get('#selection-status').textContent.includes('not saved'));
  assert.equal(store.size,0);

  store.set(storageKey,JSON.stringify(Object.fromEntries(['instructor','pydantic','promptfoo'].map(id=>
    [id,{choice:'Reject',rationale:'<script>Private browser text</script>',saved_at:'2026-10-27'}]))));
  const skipped=await start();
  assert.equal(skipped.calls.length,4);assert.equal(cards(skipped).length,0);
  assert(!skipped.nodes.get('#demo-choices').textContent.includes('Private browser text'));
  assert.equal(skipped.nodes.get('#demo-choices').querySelectorAll('script').length,0);
  store.clear();
  const failed=await start({failInit:true});
  assert.equal(failed.calls.length,1);assert.equal(cards(failed).length,0);
  assert(failed.nodes.get('#state').textContent.includes('could not initialize'));

  const validation='Confidential violet ledger project. I need a Python library. Validate the schema and types of collected data.';
  const tailored=await start({projectText:validation});
  assert.equal(tailored.calls.length,2,'A validation-only project checks only Pydantic');
  assert(tailored.calls[1].url.endsWith('need=pydantic'));assert.equal(cards(tailored).length,1);
  assert(cards(tailored)[0].textContent.includes('Pydantic'));
  assert(cards(tailored)[0].textContent.includes('Check the details before using your data'));
  assert(!cards(tailored)[0].textContent.includes(validation),'Explanation summarizes the need, without repeating the project');
  tailored.nodes.get('#project-text').value='Open a flower shop and design seasonal bouquets.';
  tailored.nodes.get('#review-project').onclick();await tailored.nodes.get('#find-ideas').onclick();
  assert.equal(tailored.calls.length,2);assert.equal(cards(tailored).length,0);
  assert(tailored.nodes.get('#state').textContent.includes('not a search of all commercial products'));
  tailored.nodes.get('#project-text').value='I need a Python library. Extract requirements from customer messages.';
  tailored.nodes.get('#review-project').onclick();await tailored.nodes.get('#find-ideas').onclick();
  assert.equal(tailored.calls.length,3);assert.equal(cards(tailored).length,1);
  assert(cards(tailored)[0].textContent.includes('Instructor'));
  // Users review text; they never have to classify technical needs.
  assert.equal(tailored.nodes.get('#project-review').querySelectorAll('input').length,0);
  tailored.nodes.get('#project-text').value='Record a phone number.';
  tailored.nodes.get('#review-project').onclick();
  await tailored.nodes.get('#find-ideas').onclick();assert.equal(cards(tailored).length,0);assert.equal(tailored.calls.length,3);
  tailored.nodes.get('#project-text').value='I need a Python library. Evaluate LLM outputs against sample requests.';
  tailored.nodes.get('#review-project').onclick();await tailored.nodes.get('#find-ideas').onclick();
  assert.equal(tailored.calls.length,4);assert.equal(cards(tailored).length,1);
  assert(cards(tailored)[0].textContent.includes('promptfoo'));
  // Local TXT extraction populates the editable review; it never starts discovery by itself.
  tailored.nodes.get('#project-file').files=[{name:'private.txt',size:validation.length,text:async()=>validation}];
  await tailored.nodes.get('#project-file').onchange();
  assert.equal(tailored.nodes.get('#project-text').value,validation);
  assert.equal(tailored.calls.length,4);assert.equal(cards(tailored).length,0);
  await tailored.nodes.get('#find-ideas').onclick();assert.equal(cards(tailored).length,1);
  assert.equal(tailored.calls.length,4,'All source results are reused within the three-request budget');
  tailored.nodes.get('#project-text').value='Do not validate schema data.';
  tailored.nodes.get('#review-project').onclick();await tailored.nodes.get('#find-ideas').onclick();
  assert.equal(cards(tailored).length,0,'Negated needs cannot qualify a tool');
  assert.equal(vm.runInContext("extractProject('Plan a marketing campaign.').needs[0].id",tailored.context),'marketing_content');
  await vm.runInContext('checkDemoSources()',partial.context);
  assert.equal(partial.calls.length,4,'Failed sources are not retried');

  // Business users receive automatically inferred jobs, never library categories.
  const food=await start({projectText:'I sell meal plans for busy parents with food preferences. Answering customer questions takes too much time.'});
  assert.equal(food.calls.length,3);assert.equal(cards(food).length,2);
  assert(food.calls.some(call=>call.url.endsWith('need=meal_planning')));
  assert(food.calls.some(call=>call.url.endsWith('need=customer_support')));
  assert(!food.calls.some(call=>/need=(instructor|pydantic|promptfoo)/.test(call.url)));
  assert.equal(food.nodes.get('#project-review').querySelectorAll('input').length,0);
  assert(food.nodes.get('#project-review').textContent.includes('Your business goal'));
  assert(food.nodes.get('#project-review').textContent.includes('Challenges you mentioned'));
  assert(food.nodes.get('#project-review').textContent.includes('not AI reasoning'));
  for(const card of cards(food)){
    const evidence=card.children.find(node=>node.className==='suggestion-evidence');
    assert(evidence.textContent.includes('Your stated goal'));
    assert(evidence.textContent.includes('not independently checked'));
    assert.equal(evidence.querySelectorAll('a').length,2,'Product access and source evidence remain distinct');
    assert(card.textContent.includes('product website'));
  }
  const foodText=food.nodes.get('#project-text').value;
  const foodFirst=cards(food)[0];foodFirst.querySelectorAll('button')[0].onclick();
  assert.equal(food.nodes.get('#selection-status').hidden,false);
  assert(food.nodes.get('#selection-status').textContent.includes('You chose Fixture-meal_planning'));
  assert(food.nodes.get('#selection-status').textContent.includes('No trial has been started'));
  assert.equal(cards(food)[0].querySelectorAll('button')[0].attributes['aria-pressed'],'true');
  cards(food)[1].querySelectorAll('button')[0].onclick();
  let selections=Object.values(JSON.parse(store.get(storageKey))).filter(record=>record.selected);
  assert.equal(selections.length,1,'Selecting another opportunity replaces the active choice for this project');
  const foodReload=await start({projectText:foodText});
  assert(foodReload.nodes.get('#selection-status').textContent.includes('Fixture-customer_support'));
  assert.equal(foodReload.calls.length,3,'Restoring a choice adds no selection request');
  const salon=await start({projectText:'I run a hair salon. I want fewer missed appointments. Answering customer questions keeps me from serving clients.'});
  assert.equal(salon.calls.length,3);assert.equal(cards(salon).length,2);
  assert(salon.calls.some(call=>call.url.endsWith('need=appointments')));
  assert(!salon.calls.some(call=>call.url.endsWith('need=meal_planning')));
  assert(salon.nodes.get('#project-review').textContent.includes('fewer missed appointments'));
  assert(!salon.nodes.get('#tool-candidates').textContent.includes('meal plans'));
  assert.equal(salon.nodes.get('#selection-status').hidden,true,'A choice for another project is not presented as this project’s choice');
  cards(salon).find(card=>card.textContent.includes('Fixture-appointments')).querySelectorAll('button')[0].onclick();
  assert(salon.nodes.get('#selection-status').textContent.includes('You chose Fixture-appointments'));
  const salonReload=await start({projectText:salon.nodes.get('#project-text').value});
  assert(salonReload.nodes.get('#selection-status').textContent.includes('Fixture-appointments'));
  assert(!JSON.stringify([...store.values()]).includes(foodText),'Raw project text must not enter saved choices');
  assert(!JSON.stringify([...store.values()]).includes('I run a hair salon'));
  const ordinary=vm.runInContext("extractProject('I want to process customer invoices and receipts. I am not a developer.')",salon.context);
  assert.equal(ordinary.technicalRequested,false);assert(ordinary.needs.some(need=>need.id==='business_admin'));
  assert.equal(vm.runInContext("extractProject('Validate schema data.').needs.length",salon.context),0,'Technical terms alone must not invite libraries');
  assert(vm.runInContext("extractProject('I have no time to answer customer questions.').needs.some(n=>n.id==='customer_support')",salon.context));
  // Changing industries cannot silently reset the original three-search budget.
  food.nodes.get('#project-text').value='I need help with customer bookings and marketing content.';
  food.nodes.get('#review-project').onclick();await food.nodes.get('#find-ideas').onclick();
  assert.equal(food.calls.length,4);assert(food.nodes.get('#demo-evidence').textContent.includes('three-search limit'));
  await food.nodes.get('#find-ideas').onclick();assert.equal(food.calls.length,4);
  const blank=await start({projectText:''});
  assert.equal(blank.calls.length,1,'No hardcoded profile or automatic search before the user provides input');
  assert.equal(blank.nodes.get('#project-text').value,'');assert.equal(cards(blank).length,0);
  assert.equal(blank.nodes.get('#search-progress').hidden,true);
  const single=await start({projectText:'I run a salon and want fewer missed appointments.'});
  assert.equal(cards(single).length,1);assert(single.nodes.get('#state').textContent.includes('not two'));
  // Upload completes the same reviewed-text -> discovery -> selection flow.
  blank.nodes.get('#project-file').files=[{name:'my-business.txt',size:foodText.length,text:async()=>foodText}];
  await blank.nodes.get('#project-file').onchange();assert.equal(blank.calls.length,1);
  await blank.nodes.get('#find-ideas').onclick();assert.equal(cards(blank).length,2);
  cards(blank)[0].querySelectorAll('button')[0].onclick();
  assert.equal(blank.nodes.get('#selection-status').hidden,false);

  // Bounded file and PDF pipeline checks. The real vendored PDF parser is also browser-tested separately.
  const parser=tailored.context;
  parser.file={name:'large.pdf',size:2_000_001};
  await assert.rejects(vm.runInContext('readProjectFile(file)',parser),/2 MB/);
  parser.file={name:'image.png',size:2};await assert.rejects(vm.runInContext('readProjectFile(file)',parser),/PDF or TXT/);
  parser.file={name:'fake.pdf',size:4,arrayBuffer:async()=>new TextEncoder().encode('bad!').buffer};
  await assert.rejects(vm.runInContext('readProjectFile(file)',parser),/readable PDF/);
  parser.file={name:'large.txt',size:13000,text:async()=>'x'.repeat(13000)};
  await assert.rejects(vm.runInContext('readProjectFile(file)',parser),/12,000/);
  let destroyed=0;
  const fakePdf={getDocument(options){assert.equal(options.isEvalSupported,false);assert.equal(options.useWorkerFetch,false);
    return {promise:Promise.resolve({numPages:1,getPage:async()=>({getTextContent:async()=>({items:[{str:validation,hasEOL:true}]}),cleanup(){}})}),destroy:async()=>{destroyed++;}};}};
  parser.pdf=fakePdf;
  assert.equal(await vm.runInContext('readPdfText(new Uint8Array(),pdf)',parser),validation);
  assert.equal(destroyed,1);
  parser.pdf={getDocument:()=>({promise:Promise.resolve({numPages:21}),destroy:async()=>{destroyed++;}})};
  await assert.rejects(vm.runInContext('readPdfText(new Uint8Array(),pdf)',parser),/20 pages/);
  parser.pdf={getDocument:()=>({promise:Promise.resolve({numPages:1,getPage:async()=>({getTextContent:async()=>({items:[]}),cleanup(){}})}),destroy:async()=>{destroyed++;}})};
  await assert.rejects(vm.runInContext('readPdfText(new Uint8Array(),pdf)',parser),/OCR/);
  assert.equal(destroyed,3,'PDF tasks are destroyed on success and failure');
  for(const instance of [app,reload,partial,zero,blocked,skipped,failed,tailored,food,salon,foodReload,salonReload,blank,single]){
    assert(instance.calls.every(call=>call.url==='/api/demo'||call.url.startsWith('/api/discover?need=')));
    assert(!JSON.stringify(instance.calls).includes('Private browser text'));
    assert(!JSON.stringify(instance.calls).includes('violet ledger'));
  }
  assert(!JSON.stringify([...store.values()]).includes('violet ledger'));
  salonReload.nodes.get('#clear-choices').onclick();
  assert.equal(store.size,0);assert.equal(salonReload.nodes.get('#selection-status').hidden,true);
  assert(cards(salonReload).every(card=>card.querySelector('button').attributes['aria-pressed']==='false'));
  // Guided mode uses the retained, genuinely checked official product evidence,
  // not synthetic GitHub product fixtures and not a live model judgement.
  const guidedText='AI Raw Gourmet is an application that generates and adapts recipes and meal plans to user constraints.';
  const guided=await start({projectText:guidedText});
  assert.equal(guided.calls.length,1,'Guided mode makes no discovery or model request');
  assert.equal(cards(guided).length,2);
  assert(guided.nodes.get('#guided-notice').textContent.startsWith('Guided demo — pre-verified opportunities'));
  assert.equal(guided.nodes.get('#guided-notice').hidden,false);
  assert(guided.nodes.get('#guided-notice').textContent.includes('not tested outcomes'));
  const guidedSources=['https://www.dishgen.com/','https://samsungfood.com/food-plus/'];
  for(const [index,card] of cards(guided).entries()){
    assert.equal(card.querySelector('a').href,guidedSources[index]);
    assert(card.textContent.includes('Could'));
    assert(card.textContent.includes('A small next step:'));
    assert(card.textContent.includes('remain untested'));
  }
  cards(guided)[0].querySelector('button').onclick();
  assert(guided.nodes.get('#selection-status').textContent.includes('You chose DishGen'));
  assert.equal(JSON.parse(store.get(storageKey))['guided-dishgen'].choice,'Test');
  assert.equal(guided.nodes.get('#selection-status').querySelector('h2').textContent,'You chose DishGen to explore.');
  assert(guided.nodes.get('#selection-status').querySelectorAll('p')[0].textContent.startsWith('Next step:'));
  assert(!cards(guided)[0].textContent.includes(guidedText),'Expanded explanation does not repeat the complete guided brief');
  assert(cards(guided)[0].textContent.includes('Generate and adapt recipes and meal plans to user constraints.'));
  const guidedReload=await start({projectText:guidedText});
  assert(guidedReload.nodes.get('#selection-status').textContent.includes('You chose DishGen'));
  assert.equal(guidedReload.calls.length,1);
  assert.equal(guidedReload.nodes.get('#search-progress').hidden,true,'No fake waiting for prepared recommendations');
  cards(guidedReload)[0].querySelectorAll('button')[2].onclick();
  assert.equal(cards(guidedReload).length,1,'Browser rejection still applies to prepared opportunities');
  assert(guidedReload.nodes.get('#state').textContent.includes('browser preferences'));
  guidedReload.nodes.get('#clear-choices').onclick();assert.equal(cards(guidedReload).length,2);
  const nameOnly=await start({projectText:'AI Raw Gourmet is a shop for repairing bicycles.'});
  assert.equal(nameOnly.nodes.get('#guided-notice').hidden,true);assert.equal(cards(nameOnly).length,0);
  assert.equal(vm.runInContext("isGuidedRawGourmet('My business is not AI Raw Gourmet. I generate recipes and meal plans to user preferences.')",nameOnly.context),false);
  guidedReload.nodes.get('#project-text').value='I run a salon and want fewer missed appointments.';
  guidedReload.nodes.get('#review-project').onclick();await guidedReload.nodes.get('#find-ideas').onclick();
  assert.equal(guidedReload.nodes.get('#guided-notice').hidden,true);
  assert.equal(cards(guidedReload).length,1);assert(cards(guidedReload)[0].textContent.includes('Fixture-appointments'));
  assert.equal(guidedReload.calls.length,2,'Other projects continue through ordinary, bounded discovery');
  console.log('PASS MOCKED sources: own-project review/TXT/PDF, two-opportunity cap and honest shortfalls, project-scoped selection/reload/replacement/clear/storage failure, real-request-only progress, capped source caching, explanations and privacy');
  console.log('PASS guided mode with retained real official evidence: DishGen and Samsung Food+, explicit scope, no live search, selection persistence, preferences and unsupported-scenario fallback');
})().catch(error=>{console.error(error);process.exitCode=1;});
