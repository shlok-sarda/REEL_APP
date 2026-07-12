"""Standalone smart-folders page (v1, isolated from the main UI so it can't
break it). Search -> select -> create folder; view folders with auto-routed
suggestions to accept/reject. Served at /folders-app for beta users."""

from __future__ import annotations


def build_folders_html(user_id: str) -> str:
    safe = user_id.replace("\\", "\\\\").replace("'", "\\'")
    return """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<title>ClipNest — Smart Folders</title>
<style>
  :root { color-scheme: dark; --bg:#07090c; --panel:rgba(255,255,255,.06); --line:rgba(255,255,255,.1);
    --text:#f4f6f8; --muted:#9ca4af; --accent:#eed7a6; --green:#9fd5c5; --brown:#a9744a; }
  *{box-sizing:border-box;} body{margin:0;min-height:100vh;background:linear-gradient(180deg,#10141b,#07090c 55%,#060709);
    color:var(--text);font-family:ui-rounded,"SF Pro Rounded","Avenir Next",system-ui,sans-serif;padding:20px 14px 60px;}
  .wrap{width:min(760px,100%);margin:0 auto;}
  h1{font-size:1.3rem;font-weight:700;margin:6px 0 2px;} .sub{color:var(--muted);font-size:.82rem;margin-bottom:14px;}
  .tabs{display:flex;gap:8px;margin:14px 0;} .tab{padding:8px 16px;border-radius:20px;border:1px solid var(--line);
    color:var(--muted);cursor:pointer;font-size:.9rem;} .tab.active{color:var(--text);border-color:var(--accent);background:rgba(238,215,166,.08);}
  .searchbox{display:flex;gap:8px;background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:10px 14px;}
  .searchbox input{flex:1;background:none;border:none;outline:none;color:var(--text);font-size:1rem;}
  .newlist{background:var(--brown);color:#fff;border:none;border-radius:10px;padding:6px 12px;font-weight:600;cursor:pointer;font-size:.82rem;}
  .newlist.ghost{background:none;border:1px solid rgba(169,116,74,.6);color:var(--accent);}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:12px 14px;margin-top:10px;position:relative;}
  .card.sel{border-color:var(--brown);box-shadow:0 0 0 1px var(--brown);}
  .card h3{font-size:.98rem;margin:0 0 4px;} .card .cat{font-size:.72rem;color:var(--muted);}
  .card .sum{font-size:.82rem;color:var(--muted);margin-top:4px;line-height:1.4;}
  .row{display:flex;justify-content:space-between;align-items:center;gap:10px;}
  a.open{color:var(--green);font-size:.78rem;text-decoration:none;}
  .selbar{position:sticky;bottom:0;background:rgba(10,12,16,.95);border:1px solid var(--line);border-radius:14px;
    padding:10px 14px;margin-top:14px;display:none;justify-content:space-between;align-items:center;}
  .selbar.show{display:flex;}
  .modal-bg{position:fixed;inset:0;background:rgba(0,0,0,.6);display:none;align-items:center;justify-content:center;padding:16px;z-index:20;}
  .modal-bg.show{display:flex;} .modal{background:#12161d;border:1px solid var(--line);border-radius:16px;padding:18px;width:min(460px,100%);}
  .modal label{display:block;font-size:.75rem;color:var(--muted);margin:10px 0 4px;}
  .modal input,.modal textarea{width:100%;background:var(--panel);border:1px solid var(--line);border-radius:10px;
    padding:9px 11px;color:var(--text);font-size:.9rem;} .modal textarea{min-height:80px;resize:vertical;}
  .modal .hint{font-size:.72rem;color:var(--accent);margin-top:4px;} .actions{display:flex;gap:8px;justify-content:flex-end;margin-top:16px;}
  .pill{font-size:.68rem;padding:2px 8px;border-radius:20px;border:1px solid var(--line);color:var(--muted);}
  .pill.sug{color:#08121f;background:var(--accent);border:none;} .empty{color:var(--muted);text-align:center;padding:40px 0;}
  .drafting{color:var(--muted);font-size:.85rem;padding:6px 0;}
</style></head><body><div class="wrap">
  <h1>Smart Folders <span class="pill">beta</span></h1>
  <div class="sub">Search your reels, make a list, and new reels route in automatically.</div>
  <div class="tabs"><span class="tab active" data-v="create">Create</span><span class="tab" data-v="folders">My Folders</span></div>

  <div id="view-create">
    <div class="searchbox">
      <input id="q" placeholder="Search your saved reels…" autocomplete="off">
      <button class="newlist" id="startSel">＋ List</button>
    </div>
    <div class="sub" id="meta"></div>
    <div id="results"></div>
    <div class="selbar" id="selbar"><span id="selCount">0 selected</span>
      <span><button class="newlist ghost" id="cancelSel">Cancel</button>
      <button class="newlist" id="continueSel">Continue →</button></span></div>
  </div>

  <div id="view-folders" style="display:none"><div id="folders"></div></div>

  <div class="modal-bg" id="modalBg"><div class="modal">
    <h3 style="margin:0">New list</h3><div class="sub" id="modalSub"></div>
    <div class="drafting" id="drafting">✨ AI is drafting a name & description…</div>
    <div id="modalForm" style="display:none">
      <label>List name</label><input id="fName">
      <label>Description (this decides what auto-joins later)</label><textarea id="fDesc"></textarea>
      <div class="hint">Edit freely — the description is the rule for what belongs.</div>
      <div class="actions"><button class="newlist ghost" id="modalCancel">Cancel</button>
      <button class="newlist" id="modalCreate">Create list</button></div>
    </div>
  </div></div>
</div><script>
const USER_ID='""" + safe + """';
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
let selecting=false, selected=new Set(), lastQ='', results=[];
function esc(s){return (s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function nameOf(r){return r.name||(r.item_names&&r.item_names[0])||r.item_name||r.summary||'(untitled)';}

async function search(q){
  const r=await fetch(`/deep-search?q=${encodeURIComponent(q)}&user_id=${encodeURIComponent(USER_ID)}&limit=30`);
  const d=await r.json(); results=d.results||[]; lastQ=q;
  $('#meta').textContent=results.length?`${results.length} results`:'';
  $('#results').innerHTML=results.length?results.map(cardHtml).join(''):`<div class="empty">No matches for "${esc(q)}"</div>`;
}
function cardHtml(r){return `<div class="card ${selected.has(r.reel_id)?'sel':''}" data-id="${esc(r.reel_id)}" onclick="pick('${esc(r.reel_id)}')">
  <div class="row"><h3>${esc(nameOf(r))}</h3>${r.url?`<a class="open" href="${esc(r.url)}" target="_blank" onclick="event.stopPropagation()">open ↗</a>`:''}</div>
  ${r.primary_category?`<div class="cat">${esc(r.primary_category)}</div>`:''}
  ${r.summary?`<div class="sum">${esc(r.summary).slice(0,140)}</div>`:''}</div>`;}
function pick(id){ if(!selecting) return; selected.has(id)?selected.delete(id):selected.add(id);
  $('#selCount').textContent=`${selected.size} selected`; $('#continueSel').disabled=!selected.size;
  $(`.card[data-id="${id}"]`)?.classList.toggle('sel'); }
$('#startSel').onclick=()=>{selecting=true;selected.clear();$('#selbar').classList.add('show');$('#startSel').textContent='Selecting…';};
$('#cancelSel').onclick=()=>{selecting=false;selected.clear();$('#selbar').classList.remove('show');$('#startSel').textContent='＋ List';$$('.card.sel').forEach(c=>c.classList.remove('sel'));};
$('#q').addEventListener('input',e=>{const q=e.target.value.trim(); clearTimeout(window._t); if(!q){$('#results').innerHTML='';$('#meta').textContent='';return;} window._t=setTimeout(()=>search(q),260);});

$('#continueSel').onclick=async()=>{
  if(!selected.size) return; $('#modalBg').classList.add('show'); $('#drafting').style.display='block'; $('#modalForm').style.display='none';
  $('#modalSub').textContent=`${selected.size} reels · from "${lastQ}"`;
  const r=await fetch('/folders/suggest',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({user_id:USER_ID,query:lastQ,reel_ids:[...selected]})});
  const d=await r.json(); $('#fName').value=d.name||lastQ; $('#fDesc').value=d.description||'';
  $('#drafting').style.display='none'; $('#modalForm').style.display='block';
};
$('#modalCancel').onclick=()=>$('#modalBg').classList.remove('show');
$('#modalCreate').onclick=async()=>{
  await fetch('/folders',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({user_id:USER_ID,query:lastQ,name:$('#fName').value,description:$('#fDesc').value,reel_ids:[...selected]})});
  $('#modalBg').classList.remove('show'); $('#cancelSel').click(); switchView('folders'); loadFolders();
};

async function loadFolders(){
  const r=await fetch(`/folders?user_id=${encodeURIComponent(USER_ID)}`); const d=await r.json();
  const fs=d.folders||[];
  $('#folders').innerHTML=fs.length?fs.map(f=>`<div class="card" onclick="openFolder(${f.id})">
    <div class="row"><h3>${esc(f.name)}</h3><span class="pill">${f.item_count} reels</span></div>
    <div class="sum">${esc(f.description).slice(0,160)}</div></div>`).join(''):'<div class="empty">No folders yet — create one from the Create tab.</div>';
}
async function openFolder(id){
  const r=await fetch(`/folders/${id}?user_id=${encodeURIComponent(USER_ID)}`); const f=await r.json();
  const mem=(f.members||[]).map(m=>`<div class="card"><div class="row"><h3>${esc(nameOf(m))}</h3>${m.url?`<a class="open" href="${esc(m.url)}" target="_blank">open ↗</a>`:''}</div></div>`).join('');
  const sug=(f.suggestions||[]).map(m=>`<div class="card"><div class="row"><h3>${esc(nameOf(m))} <span class="pill sug">suggested</span></h3>
    <span><button class="newlist" onclick="decide(${id},'${esc(m.reel_id)}','accept')">Add</button>
    <button class="newlist ghost" onclick="decide(${id},'${esc(m.reel_id)}','reject')">No</button></span></div></div>`).join('');
  $('#folders').innerHTML=`<div class="row"><h1>${esc(f.name)}</h1><button class="newlist ghost" onclick="loadFolders()">← back</button></div>
    <div class="sub">${esc(f.description)}</div>
    ${sug?`<div class="sub" style="margin-top:12px">Suggested (auto-routed, needs your yes)</div>${sug}`:''}
    <div class="sub" style="margin-top:12px">In this folder</div>${mem||'<div class="empty">No reels yet.</div>'}`;
}
async function decide(id,reel,action){
  await fetch(`/folders/${id}/${action}`,{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({user_id:USER_ID,reel_id:reel})}); openFolder(id);
}
function switchView(v){$$('.tab').forEach(t=>t.classList.toggle('active',t.dataset.v===v));
  $('#view-create').style.display=v==='create'?'':'none'; $('#view-folders').style.display=v==='folders'?'':'none';}
$$('.tab').forEach(t=>t.onclick=()=>{switchView(t.dataset.v); if(t.dataset.v==='folders') loadFolders();});
</script></body></html>"""
