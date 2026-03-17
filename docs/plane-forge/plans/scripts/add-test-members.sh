#!/usr/bin/env bash
# 一键向 wisfe workspace 添加 15 个测试成员
# 用法: bash docs/plane-forge/scripts/add-test-members.sh [docker-container-name]
#
# 默认容器: plane-api-1
# 密码: 统一使用预设 hash（pbkdf2_sha256），无需明文
# 角色: Member (15)
# 邮箱: test1@example.com ~ test15@example.com

set -euo pipefail

CONTAINER="${1:-plane-api-1}"
WORKSPACE_SLUG="wisfe"
MEMBER_COUNT=15
ROLE=15  # 15=Member, 20=Admin, 10=Viewer, 5=Guest

# 预设密码 hash（Django pbkdf2_sha256 格式）
PASSWORD_HASH='pbkdf2_sha256$600000$P4wxr5cDyhvLsPmeotekes$AF+UZzvwpxYwebGxcllGz8x5nxNhW2DM3sNhbj1NX64='

echo "=== Add Test Members to '$WORKSPACE_SLUG' ==="
echo "Container: $CONTAINER"
echo "Members:   test1@example.com ~ test${MEMBER_COUNT}@example.com"
echo "Role:      Member ($ROLE)"
echo ""

docker exec "$CONTAINER" python manage.py shell -c "
from plane.db.models import Workspace, WorkspaceMember, User
import uuid

ws = Workspace.objects.get(slug='${WORKSPACE_SLUG}')
before = WorkspaceMember.objects.filter(workspace=ws).count()
print(f'Workspace: {ws.slug}')
print(f'Before: {before} members')
print()

created = 0
existed = 0
for i in range(1, ${MEMBER_COUNT} + 1):
    email = f'test{i}@example.com'
    user, user_created = User.objects.get_or_create(
        email=email,
        defaults={
            'username': str(uuid.uuid4())[:8],
            'password': '${PASSWORD_HASH}',
        }
    )
    if not user_created:
        # 确保已有用户的密码也更新
        user.password = '${PASSWORD_HASH}'
        user.save(update_fields=['password'])

    _, member_created = WorkspaceMember.objects.get_or_create(
        workspace=ws,
        member=user,
        defaults={'role': ${ROLE}}
    )
    if member_created:
        created += 1
        print(f'  + {email}')
    else:
        existed += 1

after = WorkspaceMember.objects.filter(workspace=ws).count()
print()
print(f'Created: {created}, Already existed: {existed}')
print(f'After: {after} members')
print(f'Result: {\"PASS\" if after > 12 else \"CHECK\"} - Total {after} members (> 12)')
"
