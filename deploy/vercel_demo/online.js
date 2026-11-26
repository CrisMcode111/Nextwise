'use strict';
const $=s=>document.querySelector(s), project=$('#project-text'), status=$('#status');
const STORE='nextwise.online.project.v1';
let choices={}, history=[];
try { const saved=JSON.parse(localStorage.getItem(STORE)||'{}'); project.value=saved.project||''; choices=saved.choices||{}; history=Array.isArray(saved.history)?saved.history:[]; } catch (_) { status.textContent='Browser storage is unavailable.'; }
function save(){try{localStorage.setItem(STORE,JSON.stringify({project:project.value,choices,history}));}catch(_){status.textContent='Browser storage is unavailable; changes are not saved.';}}
function discoveryHistory(){
  const entries=history.slice(-10).map(({innovation,source_url,decision})=>({innovation,source_url,decision}));
  for(const [id,decision] of Object.entries(choices)){
    const prefix=project.value.trim()+'\n';
    if(id.startsWith(prefix)&&['remember','explore','dismiss'].includes(decision)){
      const source_url=id.slice(prefix.length);if(source_url.length<=300&&!entries.some(x=>x.source_url===source_url))entries.push({innovation:'Previously reviewed opportunity',source_url,decision});
    }
  }
  return entries.slice(-10);
}
project.addEventListener('input',save);
function add(tag,text,parent){const e=document.createElement(tag);e.textContent=text;parent.append(e);return e;}
$('#project-file').onchange=async e=>{const file=e.target.files?.[0];if(!file)return;try{project.value=await readProjectFile(file);save();status.textContent='Review the extracted text before discovery.';}catch(error){status.textContent=error.message;}finally{e.target.value='';}};
$('#read-github').onclick=async()=>{const button=$('#read-github');button.disabled=true;status.textContent='Reading public repository…';try{const r=await fetch('/api/github',{method:'POST',headers:{'Content-Type':'application/json','X-Nextwise-Access':$('#access-code').value},body:JSON.stringify({url:$('#github-url').value})});const data=await r.json();if(!r.ok)throw new Error(data.message);project.value=data.text;save();status.textContent=data.notice;}catch(error){status.textContent=error.message||'Repository could not be read.';}finally{button.disabled=false;}};
$('#discover').onclick=async()=>{
  if(project.value.trim().length<20){status.textContent='Describe your project in at least 20 characters.';return;}
  const button=$('#discover');button.disabled=true;status.textContent='Understanding your project and researching public sources…';
  $('#recommendations').replaceChildren();$('#understanding').replaceChildren();$('#clarifications').replaceChildren();
  try{
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),55000);
    let response;
    try{response=await fetch('/api/discover',{method:'POST',headers:{'Content-Type':'application/json','X-Nextwise-Access':$('#access-code').value},body:JSON.stringify({project:project.value,history:discoveryHistory()}),signal:controller.signal});}finally{clearTimeout(timer);}
    const result=await response.json();if(!response.ok)throw new Error(result.message||'Discovery did not complete.');
    add('h2','Project understanding',$('#understanding'));add('p',result.understanding,$('#understanding'));
    if(result.clarifications.length){add('p','Please add answers to your project description and discover again.',$('#clarifications'));for(const q of result.clarifications)add('p',q,$('#clarifications'));}
    for(const item of result.recommendations){
      const card=add('article','',$('#recommendations'));card.className='card recommendation';
      add('h2',item.innovation,card);
      for(const [label,key] of [['What is new','novelty'],['Project area','project_area'],['Potential improvement','improvement'],['Next action','next_action']]){if(item[key]){add('h3',label,card);add('p',item[key],card);}}
      const details=add('details','',card);details.className='lens-details';add('summary','Analysis & evidence',details);
      for(const [label,key] of [['Why it matters','relevance'],['How to apply','application'],['Why this opportunity','comparison'],['Feasibility','feasibility'],['Cost','cost'],['Integration effort','effort'],['Uncertainty','uncertainty']]){if(item[key]){add('h3',label,details);add('p',item[key],details);}}
      add('p',item.publication_date?'Publication date reported by search provider: '+item.publication_date+' (not independently verified).':'Publication date: not verified.',details);add('blockquote',item.source_quote,details);
      const link=add('a',item.source_title||'Source',details);link.href=item.source_url;link.target='_blank';link.rel='noopener noreferrer';
      const id=project.value.trim()+'\n'+item.source_url;
      let previous=history.find(x=>x.source_url===item.source_url);
      if(!previous){previous={innovation:item.innovation.slice(0,300),source_url:item.source_url.slice(0,300),decision:choices[id]||'seen'};history.push(previous);history=history.slice(-10);save();}
      const actions=add('div','',card);actions.className='lens-actions';
      for(const [label,value] of [['Remember','remember'],['Explore','explore'],['Dismiss','dismiss']]){const b=add('button',label,actions);b.type='button';b.className='button quiet';b.onclick=()=>{choices[id]=value;previous.decision=value;save();if(value==='dismiss')card.hidden=true;else status.textContent='Choice saved in this browser.';};}
      if(choices[id]==='dismiss')card.hidden=true;
    }
    status.textContent=result.notice|| (result.clarifications.length?'More context is needed.':result.recommendations.length?'Potential opportunities are ready to review.':'No supported opportunities found.');
  }catch(error){status.textContent=error.message||'Discovery failed; no recommendations were substituted.';}
  finally{button.disabled=false;}
};

// Ambient sculpture: no project data, requests, or application-state dependencies.
(() => {
  const canvas = document.querySelector('#intelligence-field');
  if (!canvas || typeof canvas.getContext !== 'function') return;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  canvas.parentElement.classList.add('field-ready');
  const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let width = 0, height = 0, frame = 0, previous = 0, time = 0, visible = true;
  let seed = 74193;
  const random = () => { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return seed / 4294967296; };
  // A folded, open membrane, rather than nodes joined by proximity or orbital paths.
  const threads = Array.from({length:76}, (_, i) => ({v:i / 75, phase:random()*6.28, weight:.35+random()*.5}));
  const motes = Array.from({length:29}, () => ({x:random(),y:random(),phase:random()*6.28,speed:.025+random()*.035}));
  const bridges = Array.from({length:3}, (_, i) => ({from:.12+random()*.25,to:.61+random()*.28,birth:-i*8,life:15+random()*12}));
  function point(u, v, t) {
    u = .035 + .93*u + .035*Math.sin(v*7.1+1.2)*(1-2*u);
    const envelope = .18+.82*Math.pow(Math.sin(Math.PI*u),.5);
    const fold = Math.sin(v*5.8+u*3.4+t*.075);
    const wave = Math.sin(u*8.2-v*3.7-t*.16)*Math.sin(Math.PI*u);
    return [width*(.06+.87*u+.045*Math.sin(v*6.1+t*.047)*Math.sin(Math.PI*u)),
      height*(.51+(v-.5)*(.16+.65*Math.pow(Math.abs(u-.49)*2, .7))*envelope+
        .21*Math.sin(u*6.3+v*2.7+t*.06)*Math.sin(Math.PI*u)+.06*fold+.025*wave)];
  }
  function draw(t) {
    ctx.clearRect(0,0,width,height);
    const core = [width*.485,height*.515];
    const aura = ctx.createRadialGradient(...core,0,...core,width*.4);
    aura.addColorStop(0,'rgba(224,207,157,.105)'); aura.addColorStop(.3,'rgba(126,172,135,.055)'); aura.addColorStop(1,'rgba(126,172,135,0)');
    ctx.fillStyle=aura;ctx.fillRect(0,0,width,height);
    threads.forEach(({v,phase,weight}, i) => {
      const selected = Math.pow(Math.max(0, Math.sin(t*.17+phase)),18);
      ctx.beginPath();
      for(let j=0;j<=42;j++) {
        const u=j/42, p=point(u,v,t);
        if(j===0)ctx.moveTo(...p);else ctx.lineTo(...p);
      }
      ctx.strokeStyle=i%4===0 ? `rgba(140,186,156,${.09+selected*.13})` : `rgba(222,202,158,${.10+selected*.25})`;
      ctx.lineWidth=weight;ctx.stroke();
    });
    // Rare cross-fold connections grow, persist and dissolve at independent intervals.
    bridges.forEach(b => {
      if(t-b.birth>b.life){b.birth=t;b.life=17+random()*18;b.from=.08+random()*.35;b.to=.6+random()*.3;}
      const age=Math.max(0,(t-b.birth)/b.life), light=Math.pow(Math.sin(Math.PI*Math.min(1,age)),3);
      const a=point(b.from,.15,t), z=point(b.to,.85,t);
      ctx.beginPath();ctx.moveTo(...a);ctx.bezierCurveTo(width*.36,height*.04,width*.66,height*.94,...z);
      ctx.strokeStyle=`rgba(232,214,175,${light*.34})`;ctx.lineWidth=.65;ctx.stroke();
    });
    // A second veil interrupts the main fold, creating depth and asymmetric tension.
    for(let i=0;i<16;i++) {
      const v=i/15;ctx.beginPath();
      ctx.moveTo(width*(.16+v*.16),height*(.20+v*.11));
      ctx.bezierCurveTo(width*(.75-v*.2),height*(.06+v*.18),width*(.19+v*.18),height*(.85-v*.19),width*(.86-v*.13),height*(.68+v*.08));
      ctx.strokeStyle=`rgba(200,185,145,${.045+Math.sin(t*.09+v*2)*.018})`;ctx.lineWidth=.45;ctx.stroke();
    }
    motes.forEach(m => {
      const x=width*(.07+m.x*.86+.015*Math.sin(t*m.speed+m.phase));
      const y=height*(.12+m.y*.75+.022*Math.sin(t*m.speed*.71+m.phase*2));
      ctx.beginPath();ctx.arc(x,y,.45+.45*m.x,0,Math.PI*2);
      ctx.fillStyle=`rgba(231,215,176,${.18+.32*(.5+.5*Math.sin(t*.11+m.phase))})`;ctx.fill();
    });
    const glow=ctx.createRadialGradient(...core,0,...core,22);
    glow.addColorStop(0,'rgba(247,232,195,.8)');glow.addColorStop(.12,'rgba(232,210,161,.32)');glow.addColorStop(1,'rgba(232,210,161,0)');
    ctx.fillStyle=glow;ctx.fillRect(core[0]-22,core[1]-22,44,44);
    ctx.save();ctx.translate(...core);ctx.rotate(-.38);ctx.beginPath();ctx.ellipse(0,0,2.3,4.8,0,0,Math.PI*2);ctx.fillStyle='#f3e6c5';ctx.fill();ctx.restore();
  }
  function tick(now) {
    frame=0;
    if(document.hidden || !visible || motion.matches)return;
    if(now-previous>=1000/30){time+=Math.min((now-previous)/1000,.06);previous=now;draw(time);}
    frame=requestAnimationFrame(tick);
  }
  function sync() {
    cancelAnimationFrame(frame);frame=0;previous=performance.now();
    if(motion.matches)draw(0);
    else if(visible && !document.hidden)frame=requestAnimationFrame(tick);
  }
  function resize() {
    const bounds=canvas.getBoundingClientRect(), ratio=Math.min(window.devicePixelRatio||1,1.5);
    width=bounds.width;height=bounds.height;
    canvas.width=Math.round(width*ratio);canvas.height=Math.round(height*ratio);
    ctx.setTransform(ratio,0,0,ratio,0,0);draw(motion.matches?0:time);sync();
  }
  new ResizeObserver(resize).observe(canvas);
  new IntersectionObserver(entries => {visible=entries[0].isIntersecting;sync();}).observe(canvas);
  document.addEventListener('visibilitychange',sync);
  motion.addEventListener('change',sync);
  resize();
})();
