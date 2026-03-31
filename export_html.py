"""スタンドアロンHTML書き出しスクリプト（クライアント限定）"""
import sqlite3, json, os
from datetime import date, datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "templates", "index_standalone.html")

# 共有対象クライアント
TARGET_CLIENT_ID = 1  # 日産神奈川

def export():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row

    client = dict(db.execute("SELECT * FROM clients WHERE id=?", (TARGET_CLIENT_ID,)).fetchone())
    projects = [dict(r) for r in db.execute("""SELECT p.*, c.name as client_name FROM projects p
        JOIN clients c ON p.client_id=c.id WHERE p.client_id=? AND p.status != '完了'
        ORDER BY CASE WHEN p.status='保留' THEN 1 ELSE 0 END, p.sort_order""", (TARGET_CLIENT_ID,)).fetchall()]

    pids = [p["id"] for p in projects]
    pid_placeholders = ",".join("?" * len(pids)) if pids else "0"

    deliverables = [dict(r) for r in db.execute(f"""
        SELECT d.*, p.name as project_name, c.name as client_name
        FROM deliverables d JOIN projects p ON d.project_id=p.id JOIN clients c ON p.client_id=c.id
        WHERE d.project_id IN ({pid_placeholders})
        ORDER BY d.done ASC, d.urgent DESC""", pids).fetchall()] if pids else []

    gantt_rows = [dict(r) for r in db.execute(f"""
        SELECT * FROM gantt_rows WHERE project_id IN ({pid_placeholders})
        ORDER BY project_id, sort_order""", pids).fetchall()] if pids else []

    # 共有向け: 「自分」→「谷井」に変換
    for d in deliverables:
        if d.get("ball") == "自分":
            d["ball"] = "谷井"

    # ダッシュボード用
    today = date.today().isoformat()
    active = [d for d in deliverables if not d.get("done") and d.get("phase") != "完了"]
    urgent = [d for d in active if d.get("urgent")]
    today_tasks = [d for d in active if not d.get("urgent") and d.get("due_date") and d["due_date"] <= today]
    upcoming = [d for d in active if d not in urgent and d not in today_tasks and d.get("due_date")]

    db.close()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    html = generate_html(client, projects, deliverables, gantt_rows, urgent, today_tasks, upcoming, now)

    with open(OUTPUT_PATH, 'w') as f:
        f.write(html)

    print(f"Exported: {OUTPUT_PATH} ({now})")
    return OUTPUT_PATH

def generate_html(client, projects, deliverables, gantt_rows, urgent, today_tasks, upcoming, now):
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{client['name']} — 進捗共有</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Hiragino Sans','Yu Gothic',sans-serif;background:#f9f9f8;color:#37352f}}
.header{{padding:16px 24px;border-bottom:1px solid #e8e8e5;background:#fff;display:flex;align-items:center;gap:12px}}
.header h1{{font-size:18px;font-weight:700}}
.header .time{{font-size:11px;color:#888;margin-left:auto}}
.tabs{{display:flex;gap:2px;padding:12px 24px;background:#fff;border-bottom:1px solid #e8e8e5}}
.tab{{padding:8px 20px;border-radius:6px;font-size:14px;font-weight:600;cursor:pointer;color:#888;transition:all .15s}}
.tab.on{{background:#1a73e8;color:#fff}}
.content{{padding:24px;max-width:1400px;margin:0 auto}}
.panel{{display:none}}.panel.on{{display:block}}

.tbl{{width:100%;border-collapse:collapse}}
.tbl th{{text-align:left;font-size:12px;font-weight:700;color:#999;padding:8px 12px;border-bottom:2px solid #e8e8e5}}
.tbl td{{padding:8px 12px;border-bottom:1px solid #f0f0ee;vertical-align:middle;font-size:14px}}
.tbl tr:hover td{{background:#f5f7fa}}
.tbl .row-done td{{opacity:.5}}
.tbl .row-done .deliv-name{{text-decoration:line-through}}

.ph-pill{{display:inline-block;padding:4px 12px;border-radius:10px;font-size:12px;font-weight:600;white-space:nowrap}}
.pc-未着手{{background:#e8e8e5;color:#666}}.pc-見積中{{background:#f5a623;color:#fff}}.pc-素材待ち{{background:#f5a623;color:#fff}}
.pc-構成{{background:#4a90d9;color:#fff}}.pc-発注{{background:#e53935;color:#fff}}.pc-請求処理{{background:#f5a623;color:#fff}}
.pc-デザイン{{background:#d45d79;color:#fff}}.pc-ナレーション{{background:#9c27b0;color:#fff}}
.pc-校正{{background:#e6a817;color:#fff}}.pc-検品{{background:#e6a817;color:#fff}}.pc-社内確認{{background:#e6a817;color:#fff}}
.pc-先方確認{{background:#f5a623;color:#fff}}.pc-最終確認{{background:#f5a623;color:#fff}}
.pc-修正{{background:#d45d79;color:#fff}}.pc-FIX{{background:#4caf50;color:#fff}}.pc-コーディング{{background:#4a90d9;color:#fff}}
.pc-入稿{{background:#4caf50;color:#fff}}.pc-公開{{background:#2e7d32;color:#fff}}
.pc-事務局確認{{background:#f5a623;color:#fff}}.pc-配信{{background:#2e7d32;color:#fff}}.pc-完了{{background:#e8e8e5;color:#aaa}}

.proj-card{{margin-bottom:12px;border:1px solid #e8e8e5;border-radius:8px;background:#fff;overflow:hidden}}
.proj-header{{padding:14px 18px;display:flex;align-items:center;gap:8px;cursor:pointer;user-select:none}}
.proj-header:hover{{background:#f5f7fa}}
.proj-title{{font-weight:700;font-size:15px}}
.badge{{font-size:11px;padding:2px 8px;border-radius:4px;font-weight:600}}
.b-blue{{background:#e8f0fe;color:#1a73e8}}.b-gray{{background:#e8e8e5;color:#888}}.b-yellow{{background:#fff3e0;color:#e65100}}
.proj-body{{padding:0 18px 18px}}
.proj-body.collapsed{{display:none}}

.proj-link{{font-size:12px;color:#1a73e8;text-decoration:none;padding:3px 10px;border:1px solid #d4e4f7;border-radius:4px;display:inline-flex;align-items:center;gap:3px;transition:all .15s}}
.proj-link:hover{{background:#e8f0fe;border-color:#1a73e8}}
.bl-b{{display:inline-block;width:16px;height:16px;line-height:16px;text-align:center;border-radius:3px;background:#42ce9f;color:#fff;font-weight:700;font-size:10px}}

.due-over{{color:#c62828;font-weight:700}}
.due-soon{{color:#e65100;font-weight:600}}
.due-note{{font-size:11px;color:#1a73e8;margin-left:2px}}

.dsec{{margin-bottom:16px;border:1px solid #e8e8e5;border-radius:8px;background:#fff;overflow:hidden}}
.dsec-t{{padding:12px 16px;font-size:14px;font-weight:700;display:flex;align-items:center;gap:8px;border-bottom:1px solid #f0f0ee}}
.dot{{width:8px;height:8px;border-radius:50%;display:inline-block}}
.cnt{{font-size:11px;background:#e8f0fe;color:#1a73e8;padding:1px 6px;border-radius:8px;font-weight:600}}
.empty{{padding:20px;text-align:center;color:#aaa;font-size:13px}}

.g-wrap{{overflow-x:auto}}
.g-tbl{{border-collapse:collapse}}
.g-tbl th,.g-tbl td{{padding:3px 5px;border:1px solid #e8e8e5;white-space:nowrap;font-size:12px}}
.gc{{width:26px;min-width:26px;height:22px}}
.gc-today{{background:#dbeafe !important}}
.gc-we{{background:#f5f5f3}}
.gc-hol{{background:#fce4ec}}
.gf-design{{background:#f48fb1 !important}}
.gf-coding{{background:#64b5f6 !important}}
.gf-check{{background:#fff176 !important}}
.gf-fix{{background:#e53935 !important;color:#fff}}
.gf-other{{background:#a5d6a7 !important}}
.g-sel{{padding:6px 10px;border:1px solid #ddd;border-radius:6px;font-size:13px;margin-bottom:12px}}
</style>
</head>
<body>

<div class="header">
    <h1>{client['name']}</h1>
    <span class="time">最終更新: {now}</span>
</div>

<div class="tabs">
    <div class="tab on" onclick="showTab('dash',this)">ダッシュボード</div>
    <div class="tab" onclick="showTab('tasks',this)">案件管理</div>
    <div class="tab" onclick="showTab('gantt',this)">ガントチャート</div>
</div>

<div class="content">
    <div id="s-dash" class="panel on"></div>
    <div id="s-tasks" class="panel"></div>
    <div id="s-gantt" class="panel"></div>
</div>

<script>
const PROJECTS = {json.dumps(projects, ensure_ascii=False)};
const DELIVERABLES = {json.dumps(deliverables, ensure_ascii=False)};
const GANTT_ROWS = {json.dumps(gantt_rows, ensure_ascii=False)};
const URGENT = {json.dumps(urgent, ensure_ascii=False)};
const TODAY_TASKS = {json.dumps(today_tasks, ensure_ascii=False)};
const UPCOMING = {json.dumps(upcoming, ensure_ascii=False)};
const DOW = ['日','月','火','水','木','金','土'];

function showTab(t,el){{
    document.querySelectorAll('.tab').forEach(b=>b.classList.remove('on'));
    document.querySelectorAll('.panel').forEach(p=>p.classList.remove('on'));
    el.classList.add('on');
    document.getElementById('s-'+t).classList.add('on');
}}

function fmtD(ds){{if(!ds)return'';const d=new Date(ds+'T00:00:00');return(d.getMonth()+1)+'/'+d.getDate()+'('+DOW[d.getDay()]+')'}}

function dueHtml(ds){{
    if(!ds)return'<span style="color:#ccc">—</span>';
    const t=new Date();t.setHours(0,0,0,0);
    const nd=new Date(ds+'T00:00:00');
    const diff=Math.round((nd-t)/864e5);
    let cls='';
    if(diff<0)cls='due-over';else if(diff<=3)cls='due-soon';
    return'<span class="'+cls+'">'+fmtD(ds)+'</span>';
}}

function toggleBody(el){{
    const body=el.closest('.proj-card').querySelector('.proj-body');
    body.classList.toggle('collapsed');
    el.querySelector('.arrow').textContent=body.classList.contains('collapsed')?'▶':'▼';
}}

function delivRow(d){{
    const rowCls=(d.done||d.phase==='完了')?'row-done':'';
    let h='<tr class="'+rowCls+'">';
    h+='<td style="white-space:nowrap">'+dueHtml(d.due_date)+(d.due_note?'<span class="due-note">'+d.due_note+'</span>':'')+'</td>';
    h+='<td>'+(d.project_name?'<span style="color:#1a73e8;font-size:12px">'+d.project_name+'</span> ':'')+'<span style="font-weight:600">'+d.type+'</span>'+(d.spec?' <span style="color:#888;font-size:12px">'+d.spec+'</span>':'');
    if(d.outsource_status){{
        const oc=['発注前','見積中','見積済','発注申請中'].includes(d.outsource_status)?'#e53935':['発注済','仕入済'].includes(d.outsource_status)?'#4caf50':d.outsource_status==='請求書待'?'#f5a623':'#4a90d9';
        h+='<br><span style="font-size:12px;color:'+oc+';font-weight:600">●'+d.outsource_status+'</span>';
        if(d.outsource_name)h+=' <span style="font-size:12px;color:#888">'+d.outsource_name+'</span>';
    }}
    h+='</td>';
    h+='<td><span class="ph-pill pc-'+d.phase+'">'+d.phase+'</span></td>';
    h+='<td>'+d.ball+'</td>';
    h+='<td style="font-weight:600">'+(d.progress||'')+'</td>';
    return h+'</tr>';
}}

// === ダッシュボード ===
function renderDash(){{
    let h='';
    if(URGENT.length){{
        h+='<div class="dsec" style="border-left:4px solid #c62828"><div class="dsec-t"><span class="dot" style="background:#c62828"></span>緊急<span class="cnt" style="background:#c62828;color:#fff">'+URGENT.length+'</span></div>';
        h+='<table class="tbl"><thead><tr><th>期日</th><th>成果物</th><th>フェーズ</th><th>ボール</th><th>進捗</th></tr></thead><tbody>';
        URGENT.forEach(d=>{{h+=delivRow(d)}});
        h+='</tbody></table></div>';
    }}
    if(TODAY_TASKS.length){{
        h+='<div class="dsec" style="border-left:4px solid #e65100"><div class="dsec-t"><span class="dot" style="background:#e65100"></span>本日のタスク<span class="cnt">'+TODAY_TASKS.length+'</span></div>';
        h+='<table class="tbl"><thead><tr><th>期日</th><th>成果物</th><th>フェーズ</th><th>ボール</th><th>進捗</th></tr></thead><tbody>';
        TODAY_TASKS.forEach(d=>{{h+=delivRow(d)}});
        h+='</tbody></table></div>';
    }}
    if(UPCOMING.length){{
        h+='<div class="dsec" style="border-left:4px solid #1a73e8"><div class="dsec-t"><span class="dot" style="background:#1a73e8"></span>今後の予定<span class="cnt">'+UPCOMING.length+'</span></div>';
        h+='<table class="tbl"><thead><tr><th>期日</th><th>成果物</th><th>フェーズ</th><th>ボール</th><th>進捗</th></tr></thead><tbody>';
        UPCOMING.sort((a,b)=>(a.due_date||'').localeCompare(b.due_date||'')).forEach(d=>{{h+=delivRow(d)}});
        h+='</tbody></table></div>';
    }}
    if(!URGENT.length&&!TODAY_TASKS.length&&!UPCOMING.length)h='<div class="empty">タスクなし</div>';
    document.getElementById('s-dash').innerHTML=h;
}}

// === 案件管理 ===
function renderTasks(){{
    let h='';
    PROJECTS.forEach(p=>{{
        const pd=DELIVERABLES.filter(d=>d.project_id===p.id).sort((a,b)=>{{
            const ad=a.done||a.phase==='完了'?1:0,bd=b.done||b.phase==='完了'?1:0;
            return ad!==bd?ad-bd:0;
        }});
        const sc=p.status==='完了'?'b-gray':p.status==='保留'?'b-yellow':'b-blue';
        const doneCount=pd.filter(d=>d.done||d.phase==='完了').length;
        h+='<div class="proj-card">';
        h+='<div class="proj-header" onclick="toggleBody(this)">';
        h+='<span class="arrow">▼</span> <span class="proj-title">'+p.name+'</span>';
        h+='<span class="badge '+sc+'">'+p.status+'</span>';
        if(pd.length)h+='<span style="font-size:12px;color:#888;margin-left:auto">'+doneCount+'/'+pd.length+'</span>';
        h+='</div><div class="proj-body">';
        h+='<div style="display:flex;align-items:center;gap:6px;padding:8px 0;flex-wrap:wrap">';
        if(p.zac_number&&p.zac_url)h+='<a href="'+p.zac_url+'" target="_blank" class="proj-link" style="font-weight:600">zac:'+p.zac_number+'</a>';
        if(p.backlog_url)h+='<a href="'+p.backlog_url+'" target="_blank" class="proj-link"><span class="bl-b">B</span>親</a>';
        if(p.backlog_url_outsource)h+='<a href="'+p.backlog_url_outsource+'" target="_blank" class="proj-link"><span class="bl-b">B</span>外注</a>';
        pd.filter(d=>d.outsource_backlog_url).forEach(d=>{{
            h+='<a href="'+d.outsource_backlog_url+'" target="_blank" class="proj-link"><span class="bl-b">B</span>'+(d.outsource_backlog_label||d.type)+'</a>';
        }});
        if(p.drive_url)h+='<a href="'+p.drive_url+'" target="_blank" class="proj-link">📁社内</a>';
        if(p.drive_url_outsource)h+='<a href="'+p.drive_url_outsource+'" target="_blank" class="proj-link">📁外注</a>';
        h+='</div>';
        if(pd.length){{
            h+='<table class="tbl"><thead><tr><th>期日</th><th>成果物</th><th>フェーズ</th><th>ボール</th><th>進捗</th></tr></thead><tbody>';
            pd.forEach(d=>{{h+=delivRow(d)}});
            h+='</tbody></table>';
        }}else{{h+='<div class="empty">成果物なし</div>'}}
        h+='</div></div>';
    }});
    document.getElementById('s-tasks').innerHTML=h||'<div class="empty">案件なし</div>';
}}

// === ガントチャート ===
let currentGanttPid=null;
function renderGantt(){{
    const rows=currentGanttPid?GANTT_ROWS.filter(r=>r.project_id===currentGanttPid):GANTT_ROWS;
    let sel='';
    if(PROJECTS.length>1){{
        sel='<select class="g-sel" onchange="currentGanttPid=+this.value||null;renderGantt()"><option value="">全案件</option>';
        PROJECTS.forEach(p=>{{sel+='<option value="'+p.id+'"'+(currentGanttPid===p.id?' selected':'')+'>'+p.name+'</option>'}});
        sel+='</select>';
    }}
    if(!rows.length){{document.getElementById('s-gantt').innerHTML=sel+'<div class="empty">ガントデータなし</div>';return}}
    const dates=rows.filter(r=>r.start_date).map(r=>[r.start_date,r.end_date||r.start_date]).flat();
    if(!dates.length){{document.getElementById('s-gantt').innerHTML=sel+'<div class="empty">日程未設定</div>';return}}
    dates.sort();
    const minD=new Date(dates[0]+'T00:00:00'),maxD=new Date(dates[dates.length-1]+'T00:00:00');
    const nDays=Math.ceil((maxD-minD)/864e5)+3;
    const today=new Date();const todayStr=today.getFullYear()+'-'+String(today.getMonth()+1).padStart(2,'0')+'-'+String(today.getDate()).padStart(2,'0');
    const dhs=[];
    for(let i=0;i<nDays;i++){{const d=new Date(minD);d.setDate(d.getDate()+i);const dt=d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');dhs.push({{dt,day:d.getDate(),dow:DOW[d.getDay()],we:d.getDay()===0||d.getDay()===6,mon:d.getMonth()+1,isToday:dt===todayStr}})}}
    const monthSpans=[];let curMon=dhs[0].mon,monStart=0;
    for(let i=1;i<dhs.length;i++){{if(dhs[i].mon!==curMon){{monthSpans.push({{mon:curMon,span:i-monStart}});curMon=dhs[i].mon;monStart=i}}}}
    monthSpans.push({{mon:curMon,span:dhs.length-monStart}});
    const WC={{'デザイン':'gf-design','コーディング':'gf-coding','FIX':'gf-fix','入稿':'gf-fix','公開':'gf-fix','校正':'gf-check','検品':'gf-check','社内確認':'gf-check'}};
    let h=sel+'<div class="g-wrap"><table class="g-tbl"><thead>';
    h+='<tr><th></th><th></th><th></th><th></th>';
    monthSpans.forEach(ms=>{{h+='<th colspan="'+ms.span+'" style="text-align:left;font-size:13px;font-weight:700">'+ms.mon+'月</th>'}});
    h+='</tr><tr><th>No</th><th>作業</th><th>開始</th><th>終了</th>';
    dhs.forEach(dh=>{{let st='';if(dh.isToday)st='color:#1a73e8;font-weight:700';else if(dh.we)st='color:#999';h+='<th class="gc'+(dh.isToday?' gc-today':dh.we?' gc-we':'')+'"'+(st?' style="'+st+'"':'')+'>'+dh.day+'<br><span style="font-size:9px">'+dh.dow+'</span></th>'}});
    h+='</tr></thead><tbody>';
    let curType='',no=0,curPid=null;
    rows.forEach(r=>{{
        // 案件が変わったらヘッダー行を挿入
        if(!currentGanttPid&&r.project_id!==curPid){{
            curPid=r.project_id;
            const proj=PROJECTS.find(p=>p.id===curPid);
            if(proj)h+='<tr><td colspan="'+(4+dhs.length)+'" style="background:#e8f0fe;font-weight:700;font-size:13px;padding:8px 12px;color:#1a73e8">📁 '+proj.name+'</td></tr>';
        }}
        const isNew=r.deliverable_type&&r.deliverable_type!==curType;
        if(isNew)curType=r.deliverable_type;no++;
        h+='<tr'+(isNew?' style="background:#f7f7f5"':'')+'>';
        h+='<td style="text-align:center;color:#888;font-size:11px">'+no+'</td>';
        if(isNew)h+='<td style="font-weight:700;font-size:13px;background:#f7f7f5">'+r.deliverable_type+(r.label?' — '+r.label:'')+' <span onclick="copyDelivText(\\''+r.deliverable_type+'\\',event)" style="font-size:10px;color:#1a73e8;cursor:pointer;border:1px solid #d4e4f7;border-radius:3px;padding:1px 6px">📋</span></td>';
        else h+='<td>'+r.label+'</td>';
        h+='<td style="font-size:11px">'+(r.start_date?fmtD(r.start_date):'')+'</td>';
        h+='<td style="font-size:11px">'+(r.end_date?fmtD(r.end_date):'')+'</td>';
        const ct=JSON.parse(r.cell_texts||'{{}}');
        dhs.forEach(dh=>{{let cls='';const inRange=r.start_date&&r.start_date<=dh.dt&&(r.end_date||r.start_date)>=dh.dt;if(inRange){{let f=false;for(const[k,v]of Object.entries(WC)){{if(r.label&&r.label.includes(k)){{cls=v;f=true;break}}}}if(!f)cls='gf-other'}}const offCls=!cls?(dh.isToday?' gc-today':dh.we?' gc-we':''):'';const cv=ct[dh.dt]||'';h+='<td class="gc '+cls+offCls+'" style="font-size:9px;text-align:center">'+cv+'</td>'}});
        h+='</tr>';
    }});
    h+='</tbody></table></div>';
    h+='<div style="padding:12px 0"><button onclick="copyAllGantt()" style="padding:6px 16px;border:1px solid #d4e4f7;border-radius:4px;background:#fff;color:#1a73e8;font-size:12px;font-weight:600;cursor:pointer">📋 全スケジュールをコピー</button></div>';
    document.getElementById('s-gantt').innerHTML=h;
}}

function copyDelivText(type,e){{
    if(e)e.stopPropagation();
    const rows=currentGanttPid?GANTT_ROWS.filter(r=>r.project_id===currentGanttPid):GANTT_ROWS;
    let text='【'+type+'】\\n',inSec=false;
    rows.forEach(r=>{{if(r.deliverable_type===type)inSec=true;else if(r.deliverable_type&&r.deliverable_type!==type&&inSec)inSec=false;if(!inSec)return;if(!r.label&&!r.start_date)return;const sd=r.start_date?fmtD(r.start_date):'';const ed=r.end_date&&r.end_date!==r.start_date?'〜'+fmtD(r.end_date):'';if(sd)text+=sd+ed+'：'+(r.label||'')+'\\n';else if(r.label)text+=r.label+'\\n'}});
    navigator.clipboard.writeText(text.trim());alert(type+' コピーしました');
}}

function copyAllGantt(){{
    const rows=currentGanttPid?GANTT_ROWS.filter(r=>r.project_id===currentGanttPid):GANTT_ROWS;
    let text='',ct='';
    rows.forEach(r=>{{if(r.deliverable_type&&r.deliverable_type!==ct){{ct=r.deliverable_type;text+='\\n【'+ct+'】\\n'}}if(!r.label&&!r.start_date)return;const sd=r.start_date?fmtD(r.start_date):'';const ed=r.end_date&&r.end_date!==r.start_date?'〜'+fmtD(r.end_date):'';if(sd)text+=sd+ed+'：'+(r.label||'')+'\\n';else if(r.label)text+=r.label+'\\n'}});
    navigator.clipboard.writeText(text.trim());alert('コピーしました');
}}

// === パスワード認証 ===
function checkAuth(){{
    if(sessionStorage.getItem('authed')==='1')return true;
    document.querySelector('.tabs').style.display='none';
    document.querySelector('.content').style.display='none';
    document.querySelector('.header').innerHTML='<div style="width:100%;text-align:center;padding:40px 0"><h2 style="font-size:18px;margin-bottom:16px">進捗共有</h2><div><input id="authPw" type="password" placeholder="パスワード" style="padding:8px 16px;border:1px solid #ddd;border-radius:6px;font-size:14px;width:180px" onkeydown="if(event.key===\\'Enter\\')doAuth()"><button onclick="doAuth()" style="margin-left:8px;padding:8px 20px;background:#1a73e8;color:#fff;border:none;border-radius:6px;font-size:14px;cursor:pointer">ログイン</button></div><p id="authErr" style="color:#e53935;font-size:12px;margin-top:8px"></p></div>';
    return false;
}}
function doAuth(){{
    if(document.getElementById('authPw').value==='kanagawa'){{
        sessionStorage.setItem('authed','1');
        location.reload();
    }}else{{
        document.getElementById('authErr').textContent='パスワードが違います';
    }}
}}
if(checkAuth()){{renderDash();renderTasks();renderGantt();}}
</script>
</body>
</html>"""


SFTP_HOST = "35.74.50.218"
SFTP_USER = "oro-inner"
SFTP_KEY = "/Users/tomoki.tanii/.ssh/himitsu_openssh"
SFTP_REMOTE = "/home/mirko-group/oro-inner/home/oro-inner/tool/tt/task/taskmanager/templates/index.html"
LAST_UPLOAD_PATH = os.path.join(os.path.dirname(__file__), ".last_upload")

def upload():
    import subprocess
    r = subprocess.run([
        "scp", "-i", SFTP_KEY,
        OUTPUT_PATH,
        f"{SFTP_USER}@{SFTP_HOST}:{SFTP_REMOTE}"
    ], capture_output=True, text=True)
    if r.returncode == 0:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        with open(LAST_UPLOAD_PATH, 'w') as f:
            f.write(now)
        print(f"Uploaded to server ({now})")
    else:
        print(f"Upload failed: {r.stderr}")
    return r.returncode == 0

if __name__ == "__main__":
    export()
    upload()
