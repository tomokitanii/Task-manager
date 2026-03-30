"""タスク管理ツール — 制作進行管理"""
import os
import sqlite3
from datetime import datetime, date
from flask import Flask, render_template, request, jsonify, g

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript("""
        -- クライアント
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0
        );

        -- 案件
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            zac_number TEXT DEFAULT '',
            backlog_url TEXT DEFAULT '',
            backlog_url_outsource TEXT DEFAULT '',
            drive_url TEXT DEFAULT '',
            drive_url_outsource TEXT DEFAULT '',
            closing_month TEXT DEFAULT '',
            status TEXT DEFAULT '進行中',
            purchased INTEGER DEFAULT 0,
            figma_stored INTEGER DEFAULT 0,
            zac_url TEXT DEFAULT '',
            sales_person TEXT DEFAULT '',
            memo TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
        );

        -- 成果物
        CREATE TABLE IF NOT EXISTS deliverables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            spec TEXT DEFAULT '',
            phase TEXT DEFAULT '未着手',
            due_date TEXT DEFAULT '',
            ball TEXT DEFAULT '自分',
            ball_since TEXT DEFAULT '',
            designer TEXT DEFAULT '',
            coder TEXT DEFAULT '',
            sales_person TEXT DEFAULT '',
            outsource_status TEXT DEFAULT '',
            outsource_name TEXT DEFAULT '',
            outsource_amount INTEGER DEFAULT 0,
            outsource_zac_url TEXT DEFAULT '',
            outsource_backlog_label TEXT DEFAULT '',
            outsource_backlog_url TEXT DEFAULT '',
            order_due_date TEXT DEFAULT '',
            invoice_due_date TEXT DEFAULT '',
            progress TEXT DEFAULT '',
            urgent INTEGER DEFAULT 0,
            urgent_note TEXT DEFAULT '',
            remind_time TEXT DEFAULT '',
            done INTEGER DEFAULT 0,
            memo TEXT DEFAULT '',
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        -- ガントチャート行
        CREATE TABLE IF NOT EXISTS gantt_rows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            deliverable_type TEXT DEFAULT '',
            label TEXT NOT NULL DEFAULT '',
            hours REAL DEFAULT 0,
            start_date TEXT DEFAULT '',
            end_date TEXT DEFAULT '',
            cell_texts TEXT DEFAULT '{}',
            sort_order INTEGER DEFAULT 0,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        -- 案件リンク（自由追加）
        CREATE TABLE IF NOT EXISTS project_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            link_type TEXT DEFAULT 'other',
            label TEXT NOT NULL DEFAULT '',
            url TEXT DEFAULT '',
            sort_order INTEGER DEFAULT 0,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        -- 独自タスク（MTG等、案件に紐づかないダッシュボード用）
        CREATE TABLE IF NOT EXISTS quick_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            section TEXT DEFAULT 'today',
            done INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        -- 発注管理
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            name TEXT NOT NULL DEFAULT '',
            vendor TEXT DEFAULT '',
            amount INTEGER DEFAULT 0,
            outsource_status TEXT DEFAULT '発注前',
            order_due_date TEXT DEFAULT '',
            invoice_due_date TEXT DEFAULT '',
            backlog_url TEXT DEFAULT '',
            zac_order_url TEXT DEFAULT '',
            memo TEXT DEFAULT '',
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        -- 日報
        CREATE TABLE IF NOT EXISTS daily_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_date TEXT NOT NULL,
            zac_number TEXT DEFAULT '',
            project_name TEXT DEFAULT '',
            hours REAL DEFAULT 0,
            memo TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
    """)
    # マイグレーション
    for stmt in [
        "ALTER TABLE projects ADD COLUMN zac_url TEXT DEFAULT ''",
        "ALTER TABLE deliverables ADD COLUMN order_due_date TEXT DEFAULT ''",
        "ALTER TABLE deliverables ADD COLUMN invoice_due_date TEXT DEFAULT ''",
        "ALTER TABLE deliverables ADD COLUMN outsource_backlog_url TEXT DEFAULT ''",
        "ALTER TABLE gantt_rows ADD COLUMN cell_texts TEXT DEFAULT '{}'",
        "ALTER TABLE deliverables ADD COLUMN sales_person TEXT DEFAULT ''",
        "ALTER TABLE deliverables ADD COLUMN outsource_name TEXT DEFAULT ''",
        "ALTER TABLE deliverables ADD COLUMN outsource_amount INTEGER DEFAULT 0",
        "ALTER TABLE deliverables ADD COLUMN outsource_zac_url TEXT DEFAULT ''",
        "ALTER TABLE deliverables ADD COLUMN outsource_backlog_label TEXT DEFAULT ''",
        "ALTER TABLE projects ADD COLUMN sales_person TEXT DEFAULT ''",
    ]:
        try:
            db.execute(stmt)
        except Exception:
            pass
    db.close()


# ======================= Routes =======================

@app.route("/")
def index():
    return render_template("index.html")


# --- Dashboard ---

@app.route("/api/dashboard")
def dashboard():
    db = get_db()
    today = date.today().isoformat()

    # 全アクティブタスク
    all_active = [dict(r) for r in db.execute("""
        SELECT d.*, p.name as project_name, p.zac_number, p.zac_url, c.name as client_name
        FROM deliverables d
        JOIN projects p ON d.project_id = p.id
        JOIN clients c ON p.client_id = c.id
        WHERE d.done = 0
        ORDER BY d.urgent DESC, CASE WHEN d.due_date='' THEN 1 ELSE 0 END, d.due_date
    """).fetchall()]

    # 緊急
    urgent = [t for t in all_active if t["urgent"]]
    # 今日のタスク（期日が今日以前、緊急以外）
    today_tasks = [t for t in all_active if not t["urgent"]
                   and t["due_date"] and t["due_date"] <= today]
    # 自分のボール（上記以外でボール=自分）
    my_ball = [t for t in all_active if t["ball"] == "自分"
               and t not in urgent and t not in today_tasks]

    # 催促リスト（ボールが自分以外で2日以上経過）
    remind = [dict(r) for r in db.execute("""
        SELECT d.*, p.name as project_name, c.name as client_name,
               julianday('now','localtime') - julianday(d.ball_since) as days_held
        FROM deliverables d
        JOIN projects p ON d.project_id = p.id
        JOIN clients c ON p.client_id = c.id
        WHERE d.ball != '自分' AND d.ball != '' AND d.done = 0
              AND d.ball_since != '' AND julianday('now','localtime') - julianday(d.ball_since) >= 1
        ORDER BY days_held DESC
    """).fetchall()]

    # 仕入れ未済
    purchase_alert = [dict(r) for r in db.execute("""
        SELECT p.*, c.name as client_name
        FROM projects p JOIN clients c ON p.client_id = c.id
        WHERE p.purchased = 0 AND p.status != '完了'
              AND EXISTS (SELECT 1 FROM deliverables d WHERE d.project_id = p.id AND d.outsource_status = '請求前')
    """).fetchall()]

    # 今月締め案件
    this_month = date.today().strftime("%Y-%m")
    closing = [dict(r) for r in db.execute("""
        SELECT p.*, c.name as client_name
        FROM projects p JOIN clients c ON p.client_id = c.id
        WHERE p.closing_month = ? AND p.status != '完了'
    """, (this_month,)).fetchall()]

    # 請求・発注期日（ordersテーブルから）
    outsource_dates = [dict(r) for r in db.execute("""
        SELECT o.*, p.name as project_name, c.name as client_name
        FROM orders o
        JOIN projects p ON o.project_id = p.id
        JOIN clients c ON p.client_id = c.id
        WHERE (o.order_due_date != '' OR o.invoice_due_date != '')
        ORDER BY COALESCE(NULLIF(o.order_due_date,''), o.invoice_due_date)
    """).fetchall()]

    return jsonify({
        "urgent": urgent,
        "today_tasks": today_tasks,
        "my_ball": my_ball,
        "remind": remind,
        "purchase_alert": purchase_alert,
        "closing_this_month": closing,
        "outsource_dates": outsource_dates,
    })


# --- Clients CRUD ---

@app.route("/api/clients")
def list_clients():
    db = get_db()
    rows = db.execute("SELECT * FROM clients ORDER BY sort_order, name").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/clients", methods=["POST"])
def create_client():
    db = get_db()
    d = request.get_json()
    db.execute("INSERT INTO clients (name) VALUES (?)", (d["name"],))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/clients/<int:cid>", methods=["PUT"])
def update_client(cid):
    db = get_db()
    d = request.get_json()
    db.execute("UPDATE clients SET name=? WHERE id=?", (d["name"], cid))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/clients/<int:cid>", methods=["DELETE"])
def delete_client(cid):
    db = get_db()
    db.execute("DELETE FROM clients WHERE id=?", (cid,))
    db.commit()
    return jsonify({"ok": True})


# --- Projects CRUD ---

@app.route("/api/projects")
def list_projects():
    db = get_db()
    cid = request.args.get("client_id")
    if cid:
        rows = db.execute("""SELECT p.*, c.name as client_name FROM projects p
                            JOIN clients c ON p.client_id=c.id
                            WHERE p.client_id=? ORDER BY p.created_at DESC""", (cid,)).fetchall()
    else:
        rows = db.execute("""SELECT p.*, c.name as client_name FROM projects p
                            JOIN clients c ON p.client_id=c.id
                            ORDER BY c.sort_order, c.name, p.created_at DESC""").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/projects", methods=["POST"])
def create_project():
    db = get_db()
    d = request.get_json()
    db.execute("""INSERT INTO projects (client_id, name, zac_number, zac_url, backlog_url,
                  backlog_url_outsource, drive_url, drive_url_outsource, closing_month, memo)
                  VALUES (?,?,?,?,?,?,?,?,?,?)""",
               (d["client_id"], d["name"], d.get("zac_number", ""),
                d.get("zac_url", ""),
                d.get("backlog_url", ""), d.get("backlog_url_outsource", ""),
                d.get("drive_url", ""), d.get("drive_url_outsource", ""),
                d.get("closing_month", ""), d.get("memo", "")))
    db.commit()
    return jsonify({"ok": True, "id": db.execute("SELECT last_insert_rowid()").fetchone()[0]})


@app.route("/api/projects/<int:pid>", methods=["PUT"])
def update_project(pid):
    db = get_db()
    d = request.get_json()
    db.execute("""UPDATE projects SET name=?, zac_number=?, zac_url=?, backlog_url=?,
                  backlog_url_outsource=?, drive_url=?, drive_url_outsource=?,
                  closing_month=?, status=?, purchased=?, figma_stored=?, sales_person=?, memo=?
                  WHERE id=?""",
               (d["name"], d.get("zac_number", ""), d.get("zac_url", ""),
                d.get("backlog_url", ""),
                d.get("backlog_url_outsource", ""), d.get("drive_url", ""),
                d.get("drive_url_outsource", ""), d.get("closing_month", ""),
                d.get("status", "進行中"), d.get("purchased", 0),
                d.get("figma_stored", 0), d.get("sales_person", ""), d.get("memo", ""), pid))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/projects/<int:pid>", methods=["DELETE"])
def delete_project(pid):
    db = get_db()
    db.execute("DELETE FROM projects WHERE id=?", (pid,))
    db.commit()
    return jsonify({"ok": True})


# --- Deliverables CRUD ---

PHASE_BALL_MAP = {
    "未着手": "自分",
    "素材待ち": "先方",
    "構成": "自分",
    "発注": "自分",
    "請求処理": "自分",
    "ナレーション": "自分",
    "デザイン": "__designer__",
    "校正": "__inspector__",
    "検品": "__inspector__",
    "社内確認": "__sales__",
    "先方確認": "先方",
    "最終確認": "先方",
    "修正": "",
    "FIX": "自分",
    "コーディング": "__coder__",
    "入稿": "自分",
    "公開": "自分",
    "事務局確認": "先方",
    "配信": "自分",
    "完了": "",
}


@app.route("/api/deliverables")
def list_deliverables():
    db = get_db()
    pid = request.args.get("project_id")
    if pid:
        rows = db.execute("""SELECT d.*, p.name as project_name, c.name as client_name
                            FROM deliverables d
                            JOIN projects p ON d.project_id=p.id
                            JOIN clients c ON p.client_id=c.id
                            WHERE d.project_id=?""", (pid,)).fetchall()
    else:
        rows = db.execute("""SELECT d.*, p.name as project_name, c.name as client_name
                            FROM deliverables d
                            JOIN projects p ON d.project_id=p.id
                            JOIN clients c ON p.client_id=c.id
                            ORDER BY d.done ASC, d.urgent DESC""").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/deliverables", methods=["POST"])
def create_deliverable():
    db = get_db()
    d = request.get_json()
    assignee = d.get("assignee", "")
    phase = d.get("phase", "未着手")
    # フェーズからボールを自動設定（担当者が設定されていればそちらを使う）
    ball = PHASE_BALL_MAP.get(phase, "自分")
    if ball == "" and assignee:
        ball = assignee
    elif ball == "":
        ball = "自分"

    db.execute("""INSERT INTO deliverables (project_id, type, spec, phase, due_date, ball, ball_since,
                  designer, coder, sales_person, outsource_name, outsource_amount, outsource_zac_url, outsource_backlog_label, outsource_status, outsource_backlog_url,
                  order_due_date, invoice_due_date,
                  progress, urgent, urgent_note, remind_time, memo)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
               (d["project_id"], d["type"], d.get("spec", ""), phase,
                d.get("due_date", ""), ball, date.today().isoformat(),
                d.get("designer", ""), d.get("coder", ""), d.get("sales_person", ""),
                d.get("outsource_name", ""), d.get("outsource_amount", 0), d.get("outsource_zac_url", ""),
                d.get("outsource_backlog_label", ""), d.get("outsource_status", ""), d.get("outsource_backlog_url", ""),
                d.get("order_due_date", ""), d.get("invoice_due_date", ""),
                d.get("progress", ""),
                d.get("urgent", 0), d.get("urgent_note", ""),
                d.get("remind_time", ""), d.get("memo", "")))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/deliverables/<int:did>", methods=["PUT"])
def update_deliverable(did):
    db = get_db()
    d = request.get_json()
    old = db.execute("SELECT * FROM deliverables WHERE id=?", (did,)).fetchone()
    if not old:
        return jsonify({"error": "not found"}), 404

    new_phase = d.get("phase", old["phase"])
    assignee = d.get("designer", old["designer"]) or d.get("coder", old["coder"]) or ""

    # フェーズが変わったらボールを自動更新
    if new_phase != old["phase"]:
        ball = PHASE_BALL_MAP.get(new_phase, "自分")
        if ball == "__designer__":
            ball = old["designer"] or "自分"
        elif ball == "__coder__":
            ball = old["coder"] or "自分"
        elif ball == "__inspector__":
            ball = "検品チーム"
        elif ball == "__sales__":
            proj = db.execute("SELECT sales_person FROM projects WHERE id=?", (old["project_id"],)).fetchone()
            ball = (proj["sales_person"] if proj and proj["sales_person"] else "") or "営業"
        elif ball == "" and assignee:
            ball = assignee
        elif ball == "":
            ball = "自分"
        ball_since = date.today().isoformat()
    else:
        ball = d.get("ball", old["ball"])
        ball_since = d.get("ball_since", old["ball_since"])

    done = 1 if new_phase == "完了" else d.get("done", old["done"])

    db.execute("""UPDATE deliverables SET type=?, spec=?, phase=?, due_date=?, ball=?, ball_since=?,
                  designer=?, coder=?, sales_person=?, outsource_name=?, outsource_amount=?, outsource_zac_url=?, outsource_backlog_label=?, outsource_status=?, outsource_backlog_url=?,
                  order_due_date=?, invoice_due_date=?,
                  progress=?,
                  urgent=?, urgent_note=?, remind_time=?, done=?, memo=?
                  WHERE id=?""",
               (d.get("type", old["type"]), d.get("spec", old["spec"]),
                new_phase, d.get("due_date", old["due_date"]), ball, ball_since,
                d.get("designer", old["designer"]), d.get("coder", old["coder"]),
                d.get("sales_person", old["sales_person"] if "sales_person" in old.keys() else ""),
                d.get("outsource_name", old["outsource_name"] if "outsource_name" in old.keys() else ""),
                d.get("outsource_amount", old["outsource_amount"] if "outsource_amount" in old.keys() else 0),
                d.get("outsource_zac_url", old["outsource_zac_url"] if "outsource_zac_url" in old.keys() else ""),
                d.get("outsource_backlog_label", old["outsource_backlog_label"] if "outsource_backlog_label" in old.keys() else ""),
                d.get("outsource_status", old["outsource_status"]),
                d.get("outsource_backlog_url", old["outsource_backlog_url"]),
                d.get("order_due_date", old["order_due_date"]),
                d.get("invoice_due_date", old["invoice_due_date"]),
                d.get("progress", old["progress"]),
                d.get("urgent", old["urgent"]),
                d.get("urgent_note", old["urgent_note"]),
                d.get("remind_time", old["remind_time"]),
                done, d.get("memo", old["memo"]), did))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/deliverables/<int:did>", methods=["DELETE"])
def delete_deliverable(did):
    db = get_db()
    db.execute("DELETE FROM deliverables WHERE id=?", (did,))
    db.commit()
    return jsonify({"ok": True})


# --- Project Links CRUD ---

@app.route("/api/project-links")
def list_project_links():
    db = get_db()
    pid = request.args.get("project_id")
    if pid:
        rows = db.execute("SELECT * FROM project_links WHERE project_id=? ORDER BY sort_order, id", (pid,)).fetchall()
    else:
        rows = db.execute("SELECT * FROM project_links ORDER BY sort_order, id").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/project-links", methods=["POST"])
def create_project_link():
    db = get_db()
    d = request.get_json()
    db.execute("INSERT INTO project_links (project_id, link_type, label, url, sort_order) VALUES (?,?,?,?,?)",
               (d["project_id"], d.get("link_type", "other"), d.get("label", ""),
                d.get("url", ""), d.get("sort_order", 0)))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/project-links/<int:lid>", methods=["PUT"])
def update_project_link(lid):
    db = get_db()
    d = request.get_json()
    db.execute("UPDATE project_links SET link_type=?, label=?, url=?, sort_order=? WHERE id=?",
               (d.get("link_type", "other"), d.get("label", ""), d.get("url", ""),
                d.get("sort_order", 0), lid))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/project-links/<int:lid>", methods=["DELETE"])
def delete_project_link(lid):
    db = get_db()
    db.execute("DELETE FROM project_links WHERE id=?", (lid,))
    db.commit()
    return jsonify({"ok": True})


# --- Orders CRUD ---

@app.route("/api/orders")
def list_orders():
    db = get_db()
    pid = request.args.get("project_id")
    if pid:
        rows = db.execute("SELECT * FROM orders WHERE project_id=? ORDER BY id", (pid,)).fetchall()
    else:
        rows = db.execute("SELECT * FROM orders ORDER BY id").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/orders", methods=["POST"])
def create_order():
    db = get_db()
    d = request.get_json()
    db.execute("""INSERT INTO orders (project_id, name, vendor, amount, outsource_status,
                  order_due_date, invoice_due_date, backlog_url, zac_order_url, memo)
                  VALUES (?,?,?,?,?,?,?,?,?,?)""",
               (d["project_id"], d.get("name", ""), d.get("vendor", ""),
                d.get("amount", 0), d.get("outsource_status", "発注前"),
                d.get("order_due_date", ""), d.get("invoice_due_date", ""),
                d.get("backlog_url", ""), d.get("zac_order_url", ""),
                d.get("memo", "")))
    db.commit()
    return jsonify({"ok": True, "id": db.execute("SELECT last_insert_rowid()").fetchone()[0]})


@app.route("/api/orders/<int:oid>", methods=["PUT"])
def update_order(oid):
    db = get_db()
    d = request.get_json()
    old = db.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
    if not old:
        return jsonify({"error": "not found"}), 404
    db.execute("""UPDATE orders SET name=?, vendor=?, amount=?, outsource_status=?,
                  order_due_date=?, invoice_due_date=?, backlog_url=?, zac_order_url=?, memo=?
                  WHERE id=?""",
               (d.get("name", old["name"]), d.get("vendor", old["vendor"]),
                d.get("amount", old["amount"]), d.get("outsource_status", old["outsource_status"]),
                d.get("order_due_date", old["order_due_date"]),
                d.get("invoice_due_date", old["invoice_due_date"]),
                d.get("backlog_url", old["backlog_url"]),
                d.get("zac_order_url", old["zac_order_url"]),
                d.get("memo", old["memo"]), oid))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/orders/<int:oid>", methods=["DELETE"])
def delete_order(oid):
    db = get_db()
    db.execute("DELETE FROM orders WHERE id=?", (oid,))
    db.commit()
    return jsonify({"ok": True})


# --- Gantt ---

@app.route("/api/gantt")
def list_gantt():
    db = get_db()
    pid = request.args.get("project_id")
    if not pid:
        return jsonify([])
    rows = db.execute("""SELECT * FROM gantt_rows WHERE project_id=?
                        ORDER BY sort_order, start_date""", (pid,)).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/gantt", methods=["POST"])
def create_gantt_row():
    db = get_db()
    d = request.get_json()
    db.execute("""INSERT INTO gantt_rows (project_id, deliverable_type, label,
                  hours, start_date, end_date, cell_texts, sort_order)
                  VALUES (?,?,?,?,?,?,?,?)""",
               (d["project_id"], d.get("deliverable_type", ""),
                d.get("label", ""), d.get("hours", 0),
                d.get("start_date", ""), d.get("end_date", ""),
                d.get("cell_texts", "{}"),
                d.get("sort_order", 0)))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/gantt/<int:gid>", methods=["PUT"])
def update_gantt_row(gid):
    db = get_db()
    d = request.get_json()
    hours = max(0, float(d.get("hours", 0) or 0))
    sd = d.get("start_date", "")
    ed = d.get("end_date", "")
    if sd and ed and sd > ed:
        sd, ed = ed, sd
    db.execute("""UPDATE gantt_rows SET deliverable_type=?, label=?, hours=?,
                  start_date=?, end_date=?, cell_texts=?, sort_order=?
                  WHERE id=?""",
               (d.get("deliverable_type", ""), d.get("label", ""),
                hours, sd, ed, d.get("cell_texts", "{}"),
                d.get("sort_order", 0), gid))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/gantt/<int:gid>/cell-text", methods=["PUT"])
def update_gantt_cell_text(gid):
    db = get_db()
    d = request.get_json()
    import json as _json
    row = db.execute("SELECT cell_texts FROM gantt_rows WHERE id=?", (gid,)).fetchone()
    if not row:
        return jsonify({"error": "not found"}), 404
    texts = _json.loads(row["cell_texts"] or "{}")
    dt = d.get("date", "")
    val = d.get("text", "")
    if val:
        texts[dt] = val
    else:
        texts.pop(dt, None)
    db.execute("UPDATE gantt_rows SET cell_texts=? WHERE id=?", (_json.dumps(texts), gid))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/gantt/insert-after/<int:gid>", methods=["POST"])
def insert_gantt_after(gid):
    """指定行の後に新しい行を挿入"""
    db = get_db()
    ref = db.execute("SELECT * FROM gantt_rows WHERE id=?", (gid,)).fetchone()
    if not ref:
        return jsonify({"error": "not found"}), 404
    new_order = ref["sort_order"] + 1
    # 後続の行のsort_orderを+1
    db.execute("UPDATE gantt_rows SET sort_order=sort_order+1 WHERE project_id=? AND sort_order>=?",
               (ref["project_id"], new_order))
    db.execute("""INSERT INTO gantt_rows (project_id, label, sort_order) VALUES (?,?,?)""",
               (ref["project_id"], "", new_order))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/gantt/<int:gid>", methods=["DELETE"])
def delete_gantt_row(gid):
    db = get_db()
    db.execute("DELETE FROM gantt_rows WHERE id=?", (gid,))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/gantt/backlog-text")
def gantt_backlog_text():
    """ガントチャートからBacklog投稿用テキストを生成"""
    db = get_db()
    pid = request.args.get("project_id")
    if not pid:
        return jsonify({"text": ""})

    project = db.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    rows = db.execute("""SELECT * FROM gantt_rows WHERE project_id=?
                        ORDER BY sort_order, start_date""", (pid,)).fetchall()

    DOW = ['月','火','水','木','金','土','日']
    def fmt_date(ds):
        if not ds: return ""
        from datetime import datetime as dt
        d = dt.strptime(ds, "%Y-%m-%d")
        return f"{d.month}/{d.day}({DOW[d.weekday()]})"

    lines = ["【スケジュール】"]
    cur_type = ""
    for r in rows:
        # 成果物が変わったら見出し追加
        if r["deliverable_type"] and r["deliverable_type"] != cur_type:
            cur_type = r["deliverable_type"]
            lines.append(f"\n▼{cur_type}")
        line = ""
        if r["start_date"]:
            sd_fmt = fmt_date(r["start_date"])
            ed_fmt = fmt_date(r["end_date"]) if r["end_date"] and r["end_date"] != r["start_date"] else ""
            if ed_fmt:
                line = f"{sd_fmt} ~ {ed_fmt} : {r['label']}"
            else:
                line = f"{sd_fmt} : {r['label']}"
            if r["hours"]:
                line += f" ({r['hours']}h)"
        else:
            if r["label"]:
                line = r["label"]
        if line:
            lines.append(line)

    return jsonify({"text": "\n".join(lines)})


# --- Daily Report ---

@app.route("/api/daily-reports")
def list_daily_reports():
    db = get_db()
    d = request.args.get("date", date.today().isoformat())
    rows = db.execute("SELECT * FROM daily_reports WHERE report_date=? ORDER BY id", (d,)).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/daily-reports", methods=["POST"])
def create_daily_report():
    db = get_db()
    d = request.get_json()
    db.execute("""INSERT INTO daily_reports (report_date, zac_number, project_name, hours, memo)
                  VALUES (?,?,?,?,?)""",
               (d.get("report_date", date.today().isoformat()),
                d.get("zac_number", ""), d.get("project_name", ""),
                d.get("hours", 0), d.get("memo", "")))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/daily-reports/<int:rid>", methods=["DELETE"])
def delete_daily_report(rid):
    db = get_db()
    db.execute("DELETE FROM daily_reports WHERE id=?", (rid,))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/quick-tasks")
def list_quick_tasks():
    db = get_db()
    rows = db.execute("SELECT * FROM quick_tasks WHERE done=0 ORDER BY id").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/quick-tasks", methods=["POST"])
def create_quick_task():
    db = get_db()
    d = request.get_json()
    db.execute("INSERT INTO quick_tasks (title, section) VALUES (?,?)",
               (d["title"], d.get("section", "today")))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/quick-tasks/<int:qid>/done", methods=["POST"])
def complete_quick_task(qid):
    db = get_db()
    db.execute("UPDATE quick_tasks SET done=1 WHERE id=?", (qid,))
    db.commit()
    return jsonify({"ok": True})


init_db()

if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=5052)
