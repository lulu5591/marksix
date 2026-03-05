function qs(s){return document.querySelector(s)}
function qsa(s){return Array.from(document.querySelectorAll(s))}
function niceStep(x){
  // Return a "nice" step size around x (e.g., 1,2,5,10,20...)
  const pow = Math.pow(10, Math.floor(Math.log10(x||1)));
  const d = x / pow;
  let step = 1;
  if (d <= 1) step = 1;
  else if (d <= 2) step = 2;
  else if (d <= 5) step = 5;
  else step = 10;
  return step * pow;
}
function niceMax(max){
  const step = niceStep(max/5);
  return Math.ceil(max/step)*step;
}
var trendChart, coChart, colorPie, colorByYear
async function loadTrend(n){
  const t = await fetch('/api/number-trend?num='+n).then(r=>r.json())
  if(!t.ok){return}
  const ctx = qs('#trendChart').getContext('2d')
  if(trendChart){trendChart.destroy()}
  const maxVal = Math.max(...t.main, ...t.extra, 0);
  const sMax = niceMax(maxVal);
  trendChart = new Chart(ctx, {
    type:'bar',
    data:{
      labels:t.years,
      datasets:[
        {label:'Main count', data:t.main, backgroundColor:'rgba(58,210,159,0.6)'},
        {label:'Extra count', data:t.extra, backgroundColor:'rgba(43,179,230,0.6)'}
      ]
    },
    options:{
      plugins:{legend:{labels:{color:'#e7eef6', font:{size:12}}}},
      scales:{
        x:{
          ticks:{color:'#d0d7e1', autoSkip:true, maxTicksLimit:12, maxRotation:0, minRotation:0, font:{size:12}},
          grid:{color:'#243243'}
        },
        y:{
          ticks:{color:'#d0d7e1', stepSize: niceStep(sMax/5), font:{size:12}},
          grid:{color:'#243243'},
          beginAtZero:true,
          suggestedMax: sMax,
          title:{display:true, text:'Count', color:'#a4b1c0', font:{size:12, weight:'bold'}}
        }
      }
    }
  })
}
async function loadCo(n){
  const t = await fetch('/api/number-cooccur?num='+n).then(r=>r.json())
  if(!t.ok){return}
  const labels = t.pairs.map(p=>p.n)
  const data = t.pairs.map(p=>p.count)
  const ctx = qs('#coChart').getContext('2d')
  if(coChart){coChart.destroy()}
  const maxVal = Math.max(...data, 0);
  const sMax = niceMax(maxVal);
  coChart = new Chart(ctx, {
    type:'bar',
    data:{labels, datasets:[{label:'Co-occurrence count', data, backgroundColor:'rgba(255,183,3,0.7)'}]},
    options:{
      indexAxis:'y',
      plugins:{legend:{labels:{color:'#e7eef6', font:{size:12}}}},
      scales:{
        x:{
          ticks:{color:'#d0d7e1', stepSize: niceStep(sMax/5), font:{size:12}},
          grid:{color:'#243243'},
          beginAtZero:true,
          suggestedMax: sMax,
          title:{display:true, text:'Count', color:'#a4b1c0', font:{size:12, weight:'bold'}}
        },
        y:{
          ticks:{color:'#d0d7e1', font:{size:12}},
          grid:{color:'#243243'}
        }
      }
    }
  })
}
async function loadColorTotals(){
  const t = await fetch('/api/color-totals').then(r=>r.json())
  if(!t.ok) return
  const ctx = qs('#colorPie').getContext('2d')
  if(colorPie){colorPie.destroy()}
  colorPie = new Chart(ctx, {
    type:'doughnut',
    data:{
      labels:['Red','Blue','Green'],
      datasets:[{data:[t.totals.red, t.totals.blue, t.totals.green], backgroundColor:['#ef4444','#3b82f6','#10b981']}]
    },
    options:{plugins:{legend:{labels:{color:'#e7eef6'}}}}
  })
}
async function loadColorByYear(){
  const t = await fetch('/api/color-by-year').then(r=>r.json())
  if(!t.ok) return
  const ctx = qs('#colorByYear').getContext('2d')
  if(colorByYear){colorByYear.destroy()}
  colorByYear = new Chart(ctx, {
    type:'bar',
    data:{
      labels:t.years,
      datasets:[
        {label:'Red', data:t.red, backgroundColor:'rgba(239,68,68,0.6)', stack:'c'},
        {label:'Blue', data:t.blue, backgroundColor:'rgba(59,130,246,0.6)', stack:'c'},
        {label:'Green', data:t.green, backgroundColor:'rgba(16,185,129,0.6)', stack:'c'}
      ]
    },
    options:{
      plugins:{legend:{labels:{color:'#e7eef6'}}},
      scales:{
        x:{ticks:{color:'#d0d7e1', maxTicksLimit:12, autoSkip:true, maxRotation:0, minRotation:0}, grid:{color:'#243243'}},
        y:{ticks:{color:'#d0d7e1'}, grid:{color:'#243243'}, beginAtZero:true}
      }
    }
  })
}
function init(){
  const grid = qs('#numGrid')
  if(!grid) return
  const pills = Array.from(grid.querySelectorAll('.pill'))
  function activate(n){
    pills.forEach(p=>p.classList.toggle('active', parseInt(p.dataset.n,10)===n))
    loadTrend(n); loadCo(n)
  }
  pills.forEach(p=>{
    p.addEventListener('click',()=>activate(parseInt(p.dataset.n,10)))
    // prevent accidental scroll changing selection by focusing
    p.addEventListener('wheel', (e)=>{ e.preventDefault() }, {passive:false})
  })
  activate(1)
  loadColorTotals(); loadColorByYear()
}
document.addEventListener('DOMContentLoaded', init)
