"""仮データ投入"""
import requests
B = "http://127.0.0.1:5052/api"

for name in ["日産神奈川", "日産", "その他"]:
    requests.post(B+"/clients", json={"name": name})

projects = [
    {"client_id":1, "name":"試乗フェア", "zac_number":"2938358",
     "backlog_url":"https://dennoutai.backlog.com/view/DEALER-100",
     "backlog_url_outsource":"https://dennoutai.backlog.com/view/DEALER-101",
     "drive_url":"https://drive.google.com/drive/folders/abc",
     "drive_url_outsource":"https://drive.google.com/drive/folders/xyz",
     "closing_month":"2026-03"},
    {"client_id":1, "name":"4月フェア", "zac_number":"2845488",
     "backlog_url":"https://dennoutai.backlog.com/view/DEALER-200",
     "closing_month":"2026-04"},
    {"client_id":2, "name":"P大分_5月キャンペーン", "zac_number":"2935451",
     "backlog_url":"https://dennoutai.backlog.com/view/NISSAN-300"},
    {"client_id":3, "name":"効率化PJ", "memo":"社内ツール開発"},
]
for p in projects:
    requests.post(B+"/projects", json=p)

delivs = [
    # 試乗フェア
    {"project_id":1,"type":"LP","spec":"SP+PC新規","phase":"コーディング","due_date":"2026-03-30",
     "designer":"ツクリテ","coder":"社内","outsource_status":"発注済","progress":"コーディング中"},
    {"project_id":1,"type":"バナー","spec":"×6サイズ","phase":"先方確認","due_date":"2026-03-29",
     "designer":"ツクリテ","outsource_status":"発注済","progress":"FB待ち"},
    {"project_id":1,"type":"チラシ","spec":"A4両面","phase":"デザイン","due_date":"2026-03-28",
     "designer":"ツクリテ","outsource_status":"発注済","urgent":1,"urgent_note":"AM対応","remind_time":"10:00","progress":"修正中"},
    {"project_id":1,"type":"動画","spec":"15s×1","phase":"構成","due_date":"2026-04-10",
     "designer":"ハルノデザイン","outsource_status":"発注申請中","progress":"構成作成中"},
    # 4月フェア
    {"project_id":2,"type":"メルマガ","phase":"素材待ち","due_date":"2026-03-30",
     "designer":"インぐら","outsource_status":"発注前","progress":"素材待ち"},
    {"project_id":2,"type":"バナー","spec":"×4サイズ","phase":"未着手","due_date":"2026-04-01",
     "outsource_status":"見積中","progress":""},
    # P大分
    {"project_id":3,"type":"LP","spec":"SP+PC","phase":"デザイン","due_date":"2026-04-05",
     "designer":"ツクリテ","outsource_status":"発注済","progress":"デザイン中"},
    {"project_id":3,"type":"バナー","spec":"×4サイズ","phase":"デザイン","due_date":"2026-04-05",
     "designer":"ツクリテ","outsource_status":"発注済","progress":"デザイン中"},
    {"project_id":3,"type":"チラシ","phase":"未着手","due_date":"2026-04-10",
     "outsource_status":"発注前","progress":""},
]
for d in delivs:
    requests.post(B+"/deliverables", json=d)

# ガント - 試乗フェア（LP→バナー→チラシ→動画）
gantt = [
    # LP
    {"project_id":1,"deliverable_type":"LP","label":"構成FIX","start_date":"2026-03-10","end_date":"2026-03-10","sort_order":10},
    {"project_id":1,"deliverable_type":"LP","label":"発注準備・着手準備","start_date":"2026-03-11","end_date":"2026-03-11","sort_order":11},
    {"project_id":1,"deliverable_type":"LP","label":"SPデザイン・PCデザイン","hours":16,"start_date":"2026-03-12","end_date":"2026-03-17","sort_order":12},
    {"project_id":1,"deliverable_type":"LP","label":"先方確認","start_date":"2026-03-18","end_date":"2026-03-19","sort_order":13},
    {"project_id":1,"deliverable_type":"LP","label":"社内校正","start_date":"2026-03-20","end_date":"2026-03-20","sort_order":14},
    {"project_id":1,"deliverable_type":"LP","label":"デザイン修正","hours":2,"start_date":"2026-03-23","end_date":"2026-03-24","sort_order":15},
    {"project_id":1,"deliverable_type":"LP","label":"デザインFIX","hours":1,"start_date":"2026-03-25","end_date":"2026-03-25","sort_order":16},
    {"project_id":1,"deliverable_type":"LP","label":"コーディング","hours":15,"start_date":"2026-03-26","end_date":"2026-03-30","sort_order":17},
    {"project_id":1,"deliverable_type":"LP","label":"検品","start_date":"2026-03-30","end_date":"2026-03-30","sort_order":18},
    {"project_id":1,"deliverable_type":"LP","label":"コーディング修正","hours":1,"start_date":"2026-03-31","end_date":"2026-03-31","sort_order":19},
    {"project_id":1,"deliverable_type":"LP","label":"公開","start_date":"2026-04-01","end_date":"2026-04-01","sort_order":20},
    # バナー
    {"project_id":1,"deliverable_type":"バナー","label":"バナーデザイン","hours":14,"start_date":"2026-03-17","end_date":"2026-03-18","sort_order":30},
    {"project_id":1,"deliverable_type":"バナー","label":"校正/検品","start_date":"2026-03-19","end_date":"2026-03-19","sort_order":31},
    {"project_id":1,"deliverable_type":"バナー","label":"先方確認","start_date":"2026-03-20","end_date":"2026-03-20","sort_order":32},
    {"project_id":1,"deliverable_type":"バナー","label":"デザイン修正","hours":3,"start_date":"2026-03-23","end_date":"2026-03-23","sort_order":33},
    {"project_id":1,"deliverable_type":"バナー","label":"デザインFIX","hours":1,"start_date":"2026-03-24","end_date":"2026-03-24","sort_order":34},
    {"project_id":1,"deliverable_type":"バナー","label":"入稿","start_date":"2026-03-25","end_date":"2026-03-26","sort_order":35},
    # チラシ
    {"project_id":1,"deliverable_type":"チラシ","label":"構成作成","start_date":"2026-03-12","end_date":"2026-03-16","sort_order":40},
    {"project_id":1,"deliverable_type":"チラシ","label":"先方確認","start_date":"2026-03-17","end_date":"2026-03-17","sort_order":41},
    {"project_id":1,"deliverable_type":"チラシ","label":"デザイン","hours":10,"start_date":"2026-03-18","end_date":"2026-03-19","sort_order":42},
    {"project_id":1,"deliverable_type":"チラシ","label":"校正/検品","start_date":"2026-03-20","end_date":"2026-03-20","sort_order":43},
    {"project_id":1,"deliverable_type":"チラシ","label":"デザイン修正","hours":2,"start_date":"2026-03-23","end_date":"2026-03-23","sort_order":44},
    {"project_id":1,"deliverable_type":"チラシ","label":"デザインFIX","start_date":"2026-03-24","end_date":"2026-03-24","sort_order":45},
    {"project_id":1,"deliverable_type":"チラシ","label":"入稿","start_date":"2026-03-25","end_date":"2026-03-27","sort_order":46},
    # 動画
    {"project_id":1,"deliverable_type":"動画","label":"素材提供","start_date":"2026-03-28","end_date":"2026-03-28","sort_order":50},
    {"project_id":1,"deliverable_type":"動画","label":"構成作成","start_date":"2026-03-30","end_date":"2026-04-02","sort_order":51},
    {"project_id":1,"deliverable_type":"動画","label":"先方確認","start_date":"2026-04-03","end_date":"2026-04-03","sort_order":52},
    {"project_id":1,"deliverable_type":"動画","label":"デザイン","hours":12,"start_date":"2026-04-06","end_date":"2026-04-08","sort_order":53},
    {"project_id":1,"deliverable_type":"動画","label":"先方確認","start_date":"2026-04-09","end_date":"2026-04-10","sort_order":54},
    {"project_id":1,"deliverable_type":"動画","label":"修正","hours":3,"start_date":"2026-04-13","end_date":"2026-04-14","sort_order":55},
    {"project_id":1,"deliverable_type":"動画","label":"入稿","start_date":"2026-04-15","end_date":"2026-04-15","sort_order":56},
]
for g in gantt:
    requests.post(B+"/gantt", json=g)

print("Seed complete!")
