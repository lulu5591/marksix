function qs(s){return document.querySelector(s)}
function ballsHtml(arr){
  if(!Array.isArray(arr)) return ''
  return '<div class="balls">'+arr.map(n=>`<span class="ball ball-d${Math.floor((n-1)/10)}">${n}</span>`).join('')+'</div>'
}
async function postForm(url, formEl){
  const fd = new FormData(formEl)
  const res = await fetch(url,{method:'POST',body:fd})
  const text = await res.text()
  try{return JSON.parse(text)}catch(_){return {ok:false,error:'Non-JSON response',raw:text}}
}
function wireSuggest(){
  const form = qs('#suggestForm'); const btn = qs('#suggestBtn'); const out = qs('#suggestResult')
  if(!form||!btn||!out) return
  form.addEventListener('submit', async (e)=>{
    e.preventDefault()
    btn.disabled=true; const old=btn.textContent; btn.textContent='Generating...'
    try{
      const data = await postForm('/api/suggest', form)
      if(data.ok){ out.hidden=false; out.innerHTML='Suggestion:'+ballsHtml(data.suggestion) }
      else{ out.hidden=false; out.textContent='Suggest failed: '+(data.error||'error') }
    }catch(err){ out.hidden=false; out.textContent='Suggest failed: '+err }
    finally{ btn.disabled=false; btn.textContent=old }
  })
}
function wireSmart(){
  const form = qs('#smartForm'); const btn = qs('#smartBtn'); const out = qs('#smartResult')
  if(!form||!btn||!out) return
  form.addEventListener('submit', async (e)=>{
    e.preventDefault()
    btn.disabled=true; const old=btn.textContent; btn.textContent='Generating...'
    try{
      const data = await postForm('/api/smart_unified', form)
      if(data.ok){ out.hidden=false; out.innerHTML='Smart Suggestion'+(data.label?` (${data.label})`:'')+': '+ballsHtml(data.smart) }
      else{ out.hidden=false; out.textContent='Smart failed: '+(data.error||'error') }
    }catch(err){ out.hidden=false; out.textContent='Smart failed: '+err }
    finally{ btn.disabled=false; btn.textContent=old }
  })
}
document.addEventListener('DOMContentLoaded', ()=>{ wireSuggest(); wireSmart() })
