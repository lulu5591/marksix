function qs(s){return document.querySelector(s)}
function showToast(t){
  var el=qs('#toast');if(!el)return;
  el.textContent=t;el.hidden=false;el.classList.add('show');
  setTimeout(function(){el.classList.remove('show');el.hidden=true},4500)
}
var updateBtn=qs('#updateBtn');
if(updateBtn){
  updateBtn.addEventListener('click',async function(e){
    e.preventDefault();
    var url=updateBtn.getAttribute('data-url')||'/update.json';
    var statusEl=qs('#updateStatus');
    function setStatus(m){ if(statusEl){ statusEl.textContent=m } }
    updateBtn.disabled=true;
    var old=updateBtn.textContent; updateBtn.textContent='Updating...';
    setStatus('Updating records...');
    try{
      var res=await fetch(url,{method:'POST'});
      var text=await res.text(); let data;
      try{ data=JSON.parse(text) }catch(_){ data={ok:false,error:'Non-JSON response',raw:text} }
      if(data.ok){
        setStatus('Updated: +'+data.added+' (total '+data.total+')');
        // Refresh the page to show latest numbers/table
        location.reload();
      }else{
        var msg=data.error||'error';
        if(data.diagnostics){
          msg+=' | diag: '+(data.diagnostics.error || ('ips='+data.diagnostics.ips));
        }
        showToast('Update failed: '+msg);
        setStatus('Update failed: '+msg);
      }
    }catch(err){
      showToast('Update failed: '+err);
      setStatus('Update failed: '+err);
    }finally{
      updateBtn.disabled=false;
      updateBtn.textContent=old;
    }
  })
}
