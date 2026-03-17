#!/bin/bash
# Plane 项目初始化脚本 - 在 plane-api 容器内执行
# 用途：DB 重置后恢复必要配置
# 执行方式：docker exec plane-api-1 bash /path/to/plane-setup.sh

set -e

API_KEY="plane_api_59786d0e610c4a509026bce45734f68a"
BASE="http://localhost:8000/api/v1/workspaces/wisfe"
PROJECT_ID="2708a857-969f-4408-86e8-e70b1db65f7d"
STATES_BASE="$BASE/projects/$PROJECT_ID/states"

echo "=== 1. 创建自定义状态 ==="
create_state() {
  curl -s -X POST -H "X-Api-Key: $API_KEY" -H "Content-Type: application/json" \
    -d "{\"name\": \"$1\", \"group\": \"$2\", \"color\": \"$3\", \"sequence\": $4}" \
    "$STATES_BASE/" | python3 -c "import json,sys; d=json.load(sys.stdin); print('Created:', d.get('name'), d.get('id', d.get('detail','error')))"
}

create_state "Integrating"  "started"   "#f39c12" 55000
create_state "Testing"      "started"   "#3498db" 65000
create_state "To Publish"   "started"   "#2ecc71" 75000

echo ""
echo "=== 2. 调整原有状态排序 ==="
# 需要先查出各状态 UUID，这里用脚本动态获取
python3 - <<'PYEOF'
import json, urllib.request

API_KEY = "plane_api_59786d0e610c4a509026bce45734f68a"
BASE = "http://localhost:8000/api/v1/workspaces/wisfe/projects/2708a857-969f-4408-86e8-e70b1db65f7d"

def api(method, path, data=None):
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(data).encode() if data else None,
        headers={"X-Api-Key": API_KEY, "Content-Type": "application/json"},
        method=method
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

states = api("GET", "/states/")
states = states.get("results", states)
seq_map = {"Done": 85000, "Cancelled": 95000, "Integrating": 55000, "Testing": 65000, "To Publish": 75000}
for s in states:
    name = s["name"]
    if name in seq_map:
        api("PATCH", f"/states/{s['id']}/", {"sequence": seq_map[name]})
        print(f"Updated sequence: {name} -> {seq_map[name]}")
PYEOF

echo ""
echo "=== 3. 创建仓库 Labels ==="
create_label() {
  curl -s -X POST -H "X-Api-Key: $API_KEY" -H "Content-Type: application/json" \
    -d "{\"name\": \"$1\", \"color\": \"$2\"}" \
    "$BASE/projects/$PROJECT_ID/labels/" | python3 -c "import json,sys; d=json.load(sys.stdin); print('Label:', d.get('name'), d.get('id','error'))"
}
create_label "repo:jira1"    "#e74c3c"
create_label "repo:jpom-demo" "#9b59b6"

echo ""
echo "=== 4. 修复 Webhook URL ==="
python3 -c "
import django, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'plane.settings.local'
django.setup()
from plane.db.models import Webhook
qs = Webhook.objects.filter(url__contains='gitlab-bridge')
if qs.exists():
    w = qs.first()
    w.url = 'http://gitlab-bridge:8080/api/v1/webhooks/plane/issue'
    w.save()
    print('Webhook URL updated:', w.url)
else:
    print('No webhook found, creating...')
    from plane.db.models import Workspace
    ws = Workspace.objects.get(slug='wisfe')
    w = Webhook.objects.create(
        workspace=ws,
        url='http://gitlab-bridge:8080/api/v1/webhooks/plane/issue',
        is_active=True,
        secret_key='plane_wh_cd31510f50aa4c5096282bafaae965e5',
        issue=True,
    )
    print('Webhook created:', w.id, w.url)
"

echo ""
echo "=== 完成 ==="
