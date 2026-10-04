'use strict';
const DATA = window.TAFEL_DATA;
const $ = id => document.getElementById(id);
const GROUPS = ['nonPGM', 'PGM', 'PtC', 'unknown'];
const LABELS = {PtC:'Pt/C', PGM:'PGM (non-Pt/C)', nonPGM:'non-PGM', unknown:'Unknown composition'};
const COLORS = {PtC:'#555d62', PGM:'#d94368', nonPGM:'#2187a6', unknown:'#a17527'};
const rich = new Set(DATA.rich);
const escape = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const config = {responsive:true, displaylogo:false, toImageButtonOptions:{format:'png',scale:3}, modeBarButtonsToRemove:['lasso2d','select2d']};
let selected = [], catalog = [], page = 0, focus = null, renderToken = 0;
const isDistribution = () => document.querySelector('input[name=view]:checked').value === 'distribution';
const edges = () => DATA.windows[$('axis').value];
const label = i => `${edges()[i]}-${edges()[i+1]}`;
const conditionName = v => ({acidic:'Acidic',alkaline:'Alkaline',other_or_unclear:'Other / unclear',saline_or_seawater:'Saline / seawater'}[v] || v);
const fmt = v => Number.isFinite(v) ? v.toFixed(1) : 'N/A';

function weights(rows, mode) {
  if (!rows.length) return [];
  if (mode === 'curve') return rows.map(() => 1/rows.length);
  const count = new Map();
  rows.forEach(r => count.set(r.paper,(count.get(r.paper)||0)+1));
  return rows.map(r => 1/(count.size*count.get(r.paper)));
}
function quantiles(values, ws, qs=[.05,.25,.5,.75,.95]) {
  const order = values.map((v,i)=>({v,w:ws[i]})).sort((a,b)=>a.v-b.v);
  const total = ws.reduce((a,b)=>a+b,0);
  return qs.map(q=>{let cumulative=0; for(const r of order){cumulative+=r.w/total;if(cumulative>=q-1e-12)return r.v;}return order.at(-1)?.v;});
}
function density(values, ws, xs, h) {
  const factor=1/(h*Math.sqrt(2*Math.PI));
  return xs.map(x=>values.reduce((v,y,i)=>v+ws[i]*Math.exp(-.5*((x-y)/h)**2)*factor,0));
}
window.TafelStats = {weights,quantiles,density};
function windowOptions() {
  const old=$('window').value;
  $('window').replaceChildren();
  if(!isDistribution()) $('window').add(new Option(`All windows (${edges()[0]}-${edges().at(-1)})`,'all'));
  edges().slice(0,-1).forEach((_,i)=>$('window').add(new Option(label(i),String(i))));
  $('window').value=[...$('window').options].some(o=>o.value===old) ? old : isDistribution()?'2':'all';
}
function filterRecords() {
  const c=$('condition').value, e=$('element').value, composition=$('composition').value;
  const t=$('template').value, basis=$('basis').value, query=$('search').value.trim().toLowerCase();
  return DATA.records.filter(r=>
    (c==='all'||(c==='other'?!['acidic','alkaline'].includes(r.condition):r.condition===c)) &&
    (e==='all'||r.elements.includes(e)) &&
    (basis==='all'||r.basis===basis) &&
    (composition==='all'||(composition==='ptc'?r.group==='PtC':composition==='pgm'?r.pgm:(r.elements.length>0&&!r.pgm))) &&
    (t==='all'||t==='any'&&r.templates.length>0||t==='rich'&&r.templates.some(x=>rich.has(x))||t==='other'&&r.templates.some(x=>!rich.has(x))||r.templates.includes(t)) &&
    (!query||`${r.material} ${r.paper} ${r.id} ${r.electrolyte} ${r.elements.join(' ')}`.toLowerCase().includes(query)));
}
function selectedPoints(r) {
  const wi=$('window').value, axis=$('axis').value, es=edges();
  const lo=wi==='all'?es[0]:es[Number(wi)], hi=wi==='all'?es.at(-1):es[Number(wi)+1];
  return r.points.filter(p=>{const x=p[axis==='eta'?1:0];return x>=lo&&(x<hi||(hi===es.at(-1)&&x<=hi));});
}
function rowsInWindow(wi, group) {
  return selected.filter(r=>(!group||r.group===group)&&r.windows[$('axis').value][wi]).map(r=>({
    ...r,slope:r.windows[$('axis').value][wi][0],centers:r.windows[$('axis').value][wi][1]
  }));
}
function stats(rows) {
  const ws=weights(rows,$('weight').value), values=rows.map(r=>r.slope);
  return {rows,weights:ws,values,q:quantiles(values,ws),papers:new Set(rows.map(r=>r.paper)).size,centers:rows.reduce((s,r)=>s+r.centers,0)};
}
function baseLayout() {
  const mobile=window.innerWidth<600;
  return {font:{family:'Arial, Helvetica, sans-serif',size:mobile?12:13,color:'#20282d'},paper_bgcolor:'#fff',plot_bgcolor:'#fff',
    margin:{l:mobile?57:70,r:20,t:20,b:64},showlegend:false,hovermode:'closest',
    xaxis:{showline:true,linecolor:'#9dabb2',gridcolor:'#e8edf0',zeroline:false},
    yaxis:{showline:true,linecolor:'#9dabb2',gridcolor:'#e8edf0',zeroline:false}};
}
function emptyLayout(layout,message) {
  layout.annotations=[{text:message,x:.5,y:.5,xref:'paper',yref:'paper',showarrow:false,font:{size:15,color:'#596871'}}];
  return layout;
}
function plotCurves() {
  const traces=[];
  const contributing=selected.map(r=>({record:r,points:selectedPoints(r)})).filter(r=>r.points.length);
  for(const group of GROUPS) {
    const xs=[],ys=[],custom=[],singletons=[];
    for(const {record:r,points} of contributing.filter(x=>x.record.group===group)) {
      if(points.length===1)singletons.push({record:r,point:points[0]});
      for(const p of points){xs.push(p[0]);ys.push(p[1]);custom.push([r.id,r.material,r.paper]);}
      xs.push(null);ys.push(null);custom.push(null);
    }
    if(xs.length)traces.push({type:'scattergl',mode:$('markers').checked?'lines+markers':'lines',x:xs,y:ys,
      customdata:custom,name:LABELS[group],line:{color:COLORS[group],width:focus ? .5 : 1},marker:{size:3,color:COLORS[group]},
      opacity:focus ? .09 : Math.min(.7,Math.max(.14,25/Math.sqrt(contributing.length))),connectgaps:false,
      hovertemplate:'%{customdata[1]}<br>|j| = %{x:.3g} mA/cm²<br>|η| = %{y:.1f} mV<br>%{customdata[2]}<extra>'+LABELS[group]+'</extra>'});
    if(singletons.length&&!$('markers').checked)traces.push({type:'scattergl',mode:'markers',
      x:singletons.map(r=>r.point[0]),y:singletons.map(r=>r.point[1]),
      customdata:singletons.map(({record:r})=>[r.id,r.material,r.paper]),
      marker:{size:4,color:COLORS[group]},opacity:focus ? .09 : .6,
      hovertemplate:'%{customdata[1]}<br>Single observed point in window<br>|j| = %{x:.3g} mA/cm²<br>|η| = %{y:.1f} mV<extra>'+LABELS[group]+'</extra>'});
  }
  const focused=contributing.find(x=>x.record.id===focus);
  if(focused){const {record:r,points}=focused;traces.push({type:'scatter',mode:'lines+markers',x:points.map(p=>p[0]),y:points.map(p=>p[1]),
    name:r.material,customdata:points.map(()=>[r.id,r.material,r.paper]),line:{color:COLORS[r.group],width:2.5},marker:{size:5},
    hovertemplate:'%{customdata[1]}<br>|j| = %{x:.3g} mA/cm²<br>|η| = %{y:.1f} mV<extra></extra>'});}
  const layout=baseLayout();layout.xaxis={...layout.xaxis,type:'log',title:{text:'|j| (mA cm⁻², logarithmic scale)'},
    tickmode:'array',tickvals:[.2,.5,1,2,5,10,20,50,100,200,500],ticktext:['0.2','0.5','1','2','5','10','20','50','100','200','500']};
  layout.yaxis={...layout.yaxis,title:{text:'|η| (mV)'}};
  if(!traces.length)emptyLayout(layout,'No observed points match these filters');
  $('clear-focus').hidden=!focused;
  $('curve-note').textContent=`${contributing.length.toLocaleString()} curves / ${new Set(contributing.map(x=>x.record.paper)).size} papers; ${contributing.reduce((s,r)=>s+r.points.length,0).toLocaleString()} native points in the selected range.${focused?' Selected: '+focused.record.material+' ('+focused.record.paper+').':''}`;
  catalog=contributing.map(x=>x.record);
  $('records-note').textContent='Native observations in the selected range. A curve can appear here without enough local support for a slope estimate.';
  return Plotly.react('curve-plot',traces,layout,config).then(()=>{
    $('curve-plot').removeAllListeners('plotly_click');
    $('curve-plot').on('plotly_click',ev=>{const id=ev.points[0]?.customdata?.[0];if(id){focus=id;plotCurves().then(renderCatalog);}});
  });
}
function jitter(uid) { let h=0;for(const c of uid)h=(h*31+c.charCodeAt(0))>>>0;return (h%1001/1000-.5)*.09; }
function plotDistributions() {
  const wi=Number($('window').value), count=edges().length-1, full=$('slope-range').value==='full';
  const chosen=GROUPS.map(group=>({group,...stats(rowsInWindow(wi,group))}));
  const allStats=GROUPS.map(group=>Array.from({length:count},(_,i)=>stats(rowsInWindow(i,group))));
  const allValues=allStats.flatMap(gs=>gs.flatMap(s=>s.values));
  const h=Number($('bandwidth').value), selectedValues=chosen.flatMap(s=>s.values);
  const logAxis=$('density-scale').value==='log';
  const range=full?[Math.min(0,...selectedValues)-4*h,Math.max(1,...selectedValues)+4*h]:[0,Number($('slope-range').value)];
  if(logAxis)range[0]=Math.min(1,...selectedValues.filter(v=>v>0).map(v=>v/10));
  const traces=[];
  GROUPS.forEach((group,gi)=>{
    const xs=[],ys=[],minus=[],plus=[],custom=[];
    allStats[gi].forEach((s,i)=>{if(!s.rows.length)return;xs.push(i+(gi-1)*.15);ys.push(s.q[2]);minus.push(s.q[2]-s.q[1]);plus.push(s.q[3]-s.q[2]);custom.push([label(i),s.rows.length,s.papers,s.q[1],s.q[3]]);});
    if(xs.length)traces.push({type:'scatter',mode:'markers',x:xs,y:ys,name:LABELS[group],customdata:custom,marker:{size:8,color:COLORS[group]},error_y:{type:'data',symmetric:false,array:plus,arrayminus:minus,color:COLORS[group],thickness:1.5,width:3},
      hovertemplate:LABELS[group]+'<br>%{customdata[0]}<br>Median %{y:.1f} mV/dec<br>IQR %{customdata[3]:.1f} - %{customdata[4]:.1f}<br>%{customdata[1]} curves / %{customdata[2]} papers<extra></extra>'});
    if($('slope-points').checked){const x=[],y=[],c=[];allStats[gi].forEach((s,i)=>s.rows.forEach(r=>{x.push(i+(gi-1)*.15+jitter(r.id));y.push(r.slope);c.push([r.material,r.paper]);}));
      if(x.length)traces.unshift({type:'scattergl',mode:'markers',x,y,customdata:c,marker:{size:3,color:COLORS[group],opacity:.3},hovertemplate:'%{customdata[0]}<br>%{y:.1f} mV/dec<br>%{customdata[1]}<extra></extra>'});}
  });
  const layout=baseLayout();layout.xaxis={...layout.xaxis,title:{text:$('axis').value==='eta'?'|η| window (mV)':'|j| window (mA cm⁻²)'},tickmode:'array',tickvals:Array.from({length:count},(_,i)=>i),ticktext:Array.from({length:count},(_,i)=>label(i)),tickangle:-35,range:[-.6,count-.4]};
  const yrange=full?[Math.min(0,...allValues),Math.max(100,...allValues)*1.04]:[0,Number($('slope-range').value)];
  layout.yaxis={...layout.yaxis,title:{text:'Local slope (mV dec⁻¹)'},range:yrange};
  layout.shapes=[{type:'rect',xref:'x',yref:'paper',x0:wi-.48,x1:wi+.48,y0:0,y1:1,fillcolor:'#f2f6f8',line:{width:0},layer:'below'}];
  if(!traces.length)emptyLayout(layout,'No eligible local slopes');
  const densityTraces=[];const ecdf=$('density-mode').value==='ecdf';
  $('bandwidth-label').hidden=ecdf;
  // Include points close to every component even when outliers make the full range wide.
  const grid=new Set(Array.from({length:501},(_,i)=>logAxis
    ? 10**(Math.log10(range[0])+(Math.log10(range[1])-Math.log10(range[0]))*i/500)
    : range[0]+(range[1]-range[0])*i/500));
  if(full)selectedValues.forEach(v=>{for(let k=-12;k<=12;k++){const x=v+k*h/3;if(x>=range[0]&&x<=range[1])grid.add(x);}});
  const xs=[...grid].sort((a,b)=>a-b);
  chosen.forEach(s=>{
    if(!s.rows.length)return;
    const color=COLORS[s.group];
    if(ecdf){const order=s.values.map((v,i)=>({v,w:s.weights[i]})).sort((a,b)=>a.v-b.v);let sum=0;
      const x=[range[0]],y=[s.weights.reduce((v,w,i)=>v+w*(s.values[i]<=range[0]),0)];
      for(const r of order){sum+=r.w;if(r.v>range[0]&&r.v<range[1]){x.push(r.v);y.push(sum);}}
      x.push(range[1]);y.push(s.weights.reduce((v,w,i)=>v+w*(s.values[i]<=range[1]),0));
      densityTraces.push({type:'scatter',mode:'lines',x,y,line:{color,width:2,shape:'hv'},name:LABELS[s.group],hovertemplate:LABELS[s.group]+'<br>%{x:.1f} mV/dec<br>Cumulative fraction %{y:.3f}<extra></extra>'});
    }else if(s.rows.length>=2){densityTraces.push({type:'scatter',mode:'lines',x:xs,y:density(s.values,s.weights,xs,h),line:{color,width:2},fill:'tozeroy',fillcolor:color+'12',name:LABELS[s.group],hovertemplate:LABELS[s.group]+'<br>%{x:.1f} mV/dec<br>Density %{y:.5f}<extra></extra>'});}
    else if(!logAxis||s.values[0]>0)densityTraces.push({type:'scatter',mode:'markers',x:s.values,y:[0],marker:{symbol:'line-ns-open',size:14,color},hovertemplate:LABELS[s.group]+'<br>Single curve: %{x:.1f} mV/dec<extra></extra>'});
  });
  const dl=baseLayout();dl.xaxis={...dl.xaxis,title:{text:'Local slope (mV dec⁻¹)'},type:logAxis?'log':'linear',
    range:logAxis?range.map(Math.log10):range,...(logAxis?{dtick:1,tickformat:'~g'}:{})};
  dl.yaxis={...dl.yaxis,title:{text:ecdf?'Cumulative probability':'Density (mV/dec)⁻¹'},rangemode:'tozero'};
  if(ecdf)dl.yaxis.range=[0,1.03];if(!densityTraces.length)emptyLayout(dl,logAxis&&selectedValues.length?'No positive slopes for logarithmic display':'No eligible local slopes in this window');
  $('density-title').textContent=`${label(wi)} ${$('axis').value==='eta'?'mV':'mA/cm²'}`;
  const outside=chosen.map(s=>({label:LABELS[s.group],fraction:s.weights.reduce((v,w,i)=>v+w*(s.values[i]<range[0]||s.values[i]>range[1]),0)})).filter(s=>s.fraction>0);
  $('distribution-note').textContent=`Median and 25-75% interval across windows. ${ecdf?'Weighted empirical cumulative distribution.':`Gaussian density, common bandwidth ${h} mV/dec; not a confidence interval.`}${logAxis?' Log x axis: non-positive slopes cannot be displayed. Density remains per mV/dec, not per log-slope unit.':''}${outside.length?' Outside selected-window display: '+outside.map(s=>`${s.label} ${(100*s.fraction).toFixed(1)}%`).join(';')+'.':''} No estimates are excluded from the statistics.`;
  $('statistics').tBodies[0].innerHTML=chosen.filter(s=>s.rows.length).map(s=>`<tr><td>${LABELS[s.group]}</td><td>${s.rows.length}</td><td>${s.papers}</td><td>${s.centers}</td><td>${fmt(s.q[2])}</td><td>${fmt(s.q[1])}-${fmt(s.q[3])}</td><td>${fmt(s.q[0])}-${fmt(s.q[4])}</td><td>${(100*s.weights.reduce((v,w,i)=>v+w*(s.values[i]<range[0]||s.values[i]>range[1]),0)).toFixed(1)}%</td></tr>`).join('')||'<tr><td colspan="8">No eligible local slopes</td></tr>';
  catalog=chosen.flatMap(s=>s.rows);
  $('records-note').textContent=`${catalog.length} curve-window medians from ${new Set(catalog.map(r=>r.paper)).size} papers. Native-center counts describe support for each median.`;
  return Promise.all([Plotly.react('overview-plot',traces,layout,config),Plotly.react('density-plot',densityTraces,dl,config)]).then(()=>{
    $('overview-plot').removeAllListeners('plotly_click');$('overview-plot').on('plotly_click',ev=>{const i=Math.round(ev.points[0]?.x);if(i>=0&&i<count){$('window').value=String(i);render();}});
  });
}
function renderCatalog() {
  const rows=focus?catalog.filter(r=>r.id===focus):catalog;
  const pages=Math.max(1,Math.ceil(rows.length/25));page=Math.min(page,pages-1);
  $('catalog').innerHTML=rows.slice(page*25,(page+1)*25).map(r=>`<tr><td><button class="curve-link" data-id="${escape(r.id)}">${escape(r.material)}</button><small>${escape(r.id)}</small></td><td>${escape(r.elements.join(', ')||'Not recorded')}</td><td>${escape(conditionName(r.condition))}<small>${LABELS[r.group]}</small></td><td><a href="https://doi.org/${encodeURI(r.paper)}" target="_blank" rel="noopener">${escape(r.paper)}</a></td><td>${escape(r.templates.join(', ')||'No membership')}</td><td>${r.slope==null?'N/A':fmt(r.slope)+' / '+r.centers}</td></tr>`).join('')||'<tr><td colspan="6">No contributing curves for this selection.</td></tr>';
  $('page-status').textContent=`${rows.length.toLocaleString()} records · Page ${page+1} / ${pages}`;
  $('prev').disabled=page===0;$('next').disabled=page>=pages-1;
}
function updateURL() {
  const url=new URL(location.href);
  for(const id of ['condition','element','composition','template','basis','weight','axis','window','density-scale'])url.searchParams.set(id,$(id).value);
  url.searchParams.set('view',isDistribution()?'distribution':'curves');
  try{history.replaceState(null,'',url);}catch{}
  const back=new URL('../index.html',location.href);for(const id of ['condition','composition','weight','element','template'])back.searchParams.set(id,$(id).value);back.searchParams.set('view','bubble');
  $('composition-link').href=back.href;
}
async function render() {
  const token=++renderToken;selected=filterRecords();
  $('summary').textContent=`${selected.length.toLocaleString()} curves / ${new Set(selected.map(r=>r.paper)).size} papers selected`;
  $('unknown-key').hidden=!selected.some(r=>r.group==='unknown');$('basis-note').hidden=$('basis').value!=='all';
  $('curves-panel').hidden=isDistribution();$('distribution-panel').hidden=!isDistribution();
  updateURL();
  if(isDistribution())await plotDistributions();else await plotCurves();
  if(token===renderToken){renderCatalog();document.body.dataset.ready=String(token);}
}
function downloadCSV(name, columns, rows) {
  const cell=x=>'"'+String(x??'').replace(/"/g,'""')+'"';
  const text=[columns.map(cell).join(','),...rows.map(r=>columns.map(c=>cell(r[c])).join(','))].join('\r\n');
  const a=document.createElement('a'),url=URL.createObjectURL(new Blob(['\ufeff',text],{type:'text/csv;charset=utf-8'}));a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function common(r){return {curve_uid:r.id,paper_doi:r.paper,material:r.material,elements:r.elements.join(';'),condition:r.condition,group:LABELS[r.group],current_basis:r.basis,templates:r.templates.join(';')};}
$('export-statistics').onclick=()=>{
  const rows=[],indices=$('window').value==='all'?edges().slice(0,-1).map((_,i)=>i):[Number($('window').value)];
  for(const wi of indices)for(const group of GROUPS){const s=stats(rowsInWindow(wi,group));s.rows.forEach((r,i)=>rows.push({...common(r),axis:$('axis').value,window:label(wi),slope_mV_dec:r.slope,derivative_centers:r.centers,weight_mode:$('weight').value,within_group_window_weight:s.weights[i]}));}
  downloadCSV('selected_tafel_slopes.csv',['curve_uid','paper_doi','material','elements','condition','group','current_basis','templates','axis','window','slope_mV_dec','derivative_centers','weight_mode','within_group_window_weight'],rows);
};
$('export-points').onclick=()=>downloadCSV('selected_native_points.csv',['curve_uid','paper_doi','material','elements','condition','group','current_basis','templates','j_mA_cm2','eta_mV'],selected.flatMap(r=>selectedPoints(r).map(p=>({...common(r),j_mA_cm2:p[0],eta_mV:p[1]}))));
$('catalog').onclick=event=>{const button=event.target.closest('[data-id]');if(!button)return;focus=button.dataset.id;document.querySelector('input[name=view][value=curves]').checked=true;windowOptions();render();$('curves-panel').scrollIntoView({behavior:'smooth',block:'start'});};
$('clear-focus').onclick=()=>{focus=null;render();};
$('prev').onclick=()=>{page--;renderCatalog();};$('next').onclick=()=>{page++;renderCatalog();};
DATA.elements.forEach(e=>$('element').add(new Option(e,e)));
[...DATA.rich,...Array.from({length:16},(_,i)=>'T'+String(i+1).padStart(2,'0')).filter(t=>!rich.has(t))].forEach(t=>$('template').add(new Option(t+(rich.has(t)?' (PGM-rich)':' (other)'),t)));
const params=new URLSearchParams(location.search);
for(const id of ['condition','element','composition','template','basis','weight','axis','density-scale']){const value=params.get(id);if([...$(id).options].some(o=>o.value===value))$(id).value=value;}
if(params.get('view')==='distribution')document.querySelector('input[name=view][value=distribution]').checked=true;
windowOptions();if([...$('window').options].some(o=>o.value===params.get('window')))$('window').value=params.get('window');
for(const id of ['condition','element','composition','template','basis','weight','axis','window','markers','density-mode','density-scale','bandwidth','slope-range','slope-points'])$(id).addEventListener('change',()=>{page=0;focus=null;if(id==='axis')windowOptions();render();});
document.querySelectorAll('input[name=view]').forEach(el=>el.addEventListener('change',()=>{page=0;focus=null;windowOptions();render();}));
let searchTimer;$('search').addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>{page=0;focus=null;render();},180);});
$('reset').onclick=()=>{for(const id of ['condition','element','composition','template'])$(id).value='all';$('basis').value='geometric_area';$('weight').value='paper';$('search').value='';focus=null;page=0;render();};
render().catch(error=>{$('summary').textContent='Unable to load plots: '+error.message;console.error(error);});
