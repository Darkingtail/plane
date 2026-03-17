# Custom Fields + Issue Type System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 Plane CE 中实现完整的自定义字段系统，与 Issue Type 绑定，使每种 Issue Type 展示不同字段集。

**Architecture:**

- Issue Type（工作区级）已有 Model，需补齐 API + 前端；Custom Field 需从零新建 Model + API + 前端。
- 字段值用 `JSONField` 存储，兼容 text/number/date/option 等多类型。
- 前端遵循 Plane 已有的 Mobx Store + Service 模式，CE 目录下实现（替换现有空壳）。

**Tech Stack:** Django 4.2, DRF, Python 3.11, React 19, TypeScript, MobX, SWR

---

## 现有代码基础（勿重复创建）

| 已存在                          | 路径                                     |
| ------------------------------- | ---------------------------------------- |
| `IssueType` Model               | `apps/api/plane/db/models/issue_type.py` |
| `ProjectIssueType` Model        | 同上                                     |
| `Issue.type` FK                 | `apps/api/plane/db/models/issue.py`      |
| `Project.is_issue_type_enabled` | `apps/api/plane/db/models/project.py`    |
| CE Issue Type 前端空壳          | `apps/web/ce/components/issues/`         |
| 最新迁移编号                    | `0118_...` → 新建从 `0119` 开始          |

---

## Phase 1：Issue Type 后端 API

### Task 1：IssueType Serializer

**Files:**

- Create: `apps/api/plane/app/serializers/issue_type.py`
- Modify: `apps/api/plane/app/serializers/__init__.py`

**Step 1: 创建 Serializer 文件**

```python
# apps/api/plane/app/serializers/issue_type.py
from .base import BaseSerializer
from plane.db.models import IssueType, ProjectIssueType


class IssueTypeSerializer(BaseSerializer):
    class Meta:
        model = IssueType
        fields = [
            "id",
            "workspace_id",
            "name",
            "description",
            "logo_props",
            "is_epic",
            "is_default",
            "is_active",
            "level",
        ]
        read_only_fields = ["workspace", "id"]


class ProjectIssueTypeSerializer(BaseSerializer):
    issue_type_detail = IssueTypeSerializer(source="issue_type", read_only=True)

    class Meta:
        model = ProjectIssueType
        fields = [
            "id",
            "project_id",
            "workspace_id",
            "issue_type",
            "issue_type_detail",
            "level",
            "is_default",
        ]
        read_only_fields = ["workspace", "project", "id"]
```

**Step 2: 注册到 `__init__.py`**

在 `apps/api/plane/app/serializers/__init__.py` 末尾添加：

```python
from .issue_type import IssueTypeSerializer, ProjectIssueTypeSerializer
```

**Step 3: 验证导入**

```bash
cd /Users/wisedu/Documents/GitHub/plane/apps/api
python -c "from plane.app.serializers import IssueTypeSerializer; print('OK')"
```

Expected: `OK`

**Step 4: Commit**

```bash
git add apps/api/plane/app/serializers/issue_type.py apps/api/plane/app/serializers/__init__.py
git commit -m "feat: add IssueType and ProjectIssueType serializers"
```

---

### Task 2：IssueType ViewSet（工作区级）

**Files:**

- Create: `apps/api/plane/app/views/issue_type/`
- Create: `apps/api/plane/app/views/issue_type/__init__.py`
- Create: `apps/api/plane/app/views/issue_type/base.py`
- Modify: `apps/api/plane/app/views/__init__.py`

**Step 1: 创建 View**

```python
# apps/api/plane/app/views/issue_type/base.py
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import WorkSpaceAdminPermission, allow_permission, ROLE
from plane.app.serializers import IssueTypeSerializer, ProjectIssueTypeSerializer
from plane.db.models import IssueType, ProjectIssueType, Workspace
from ..base import BaseViewSet, BaseAPIView


class WorkspaceIssueTypeViewSet(BaseViewSet):
    """工作区级 Issue Type CRUD"""
    serializer_class = IssueTypeSerializer
    model = IssueType

    def get_queryset(self):
        return (
            self.filter_queryset(super().get_queryset())
            .filter(workspace__slug=self.kwargs.get("slug"))
            .order_by("level", "name")
        )

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def list(self, request, slug):
        issue_types = self.get_queryset()
        serializer = IssueTypeSerializer(issue_types, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN])
    def create(self, request, slug):
        workspace = Workspace.objects.get(slug=slug)
        serializer = IssueTypeSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(workspace=workspace)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @allow_permission([ROLE.ADMIN])
    def partial_update(self, request, slug, pk):
        issue_type = IssueType.objects.get(pk=pk, workspace__slug=slug)
        serializer = IssueTypeSerializer(issue_type, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @allow_permission([ROLE.ADMIN])
    def destroy(self, request, slug, pk):
        issue_type = IssueType.objects.get(pk=pk, workspace__slug=slug)
        if issue_type.is_default:
            return Response(
                {"error": "Cannot delete the default issue type"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        issue_type.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProjectIssueTypeViewSet(BaseViewSet):
    """项目级 Issue Type 配置"""
    serializer_class = ProjectIssueTypeSerializer
    model = ProjectIssueType

    def get_queryset(self):
        return (
            self.filter_queryset(super().get_queryset())
            .filter(
                workspace__slug=self.kwargs.get("slug"),
                project_id=self.kwargs.get("project_id"),
            )
            .select_related("issue_type")
            .order_by("level")
        )

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def list(self, request, slug, project_id):
        project_issue_types = self.get_queryset()
        serializer = ProjectIssueTypeSerializer(project_issue_types, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN])
    def create(self, request, slug, project_id):
        serializer = ProjectIssueTypeSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(project_id=project_id)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @allow_permission([ROLE.ADMIN])
    def destroy(self, request, slug, project_id, pk):
        ProjectIssueType.objects.get(pk=pk, project_id=project_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
```

```python
# apps/api/plane/app/views/issue_type/__init__.py
from .base import WorkspaceIssueTypeViewSet, ProjectIssueTypeViewSet
```

**Step 2: 注册到 views `__init__.py`**

在 `apps/api/plane/app/views/__init__.py` 中添加：

```python
from .issue_type import WorkspaceIssueTypeViewSet, ProjectIssueTypeViewSet
```

**Step 3: 验证导入**

```bash
cd /Users/wisedu/Documents/GitHub/plane/apps/api
python -c "from plane.app.views import WorkspaceIssueTypeViewSet; print('OK')"
```

**Step 4: Commit**

```bash
git add apps/api/plane/app/views/issue_type/ apps/api/plane/app/views/__init__.py
git commit -m "feat: add IssueType ViewSets for workspace and project level"
```

---

### Task 3：IssueType URL 路由

**Files:**

- Create: `apps/api/plane/app/urls/issue_type.py`
- Modify: `apps/api/plane/app/urls/__init__.py`

**Step 1: 创建 URL 文件**

```python
# apps/api/plane/app/urls/issue_type.py
from django.urls import path
from plane.app.views import WorkspaceIssueTypeViewSet, ProjectIssueTypeViewSet

urlpatterns = [
    # 工作区级 Issue Types
    path(
        "workspaces/<str:slug>/issue-types/",
        WorkspaceIssueTypeViewSet.as_view({"get": "list", "post": "create"}),
        name="workspace-issue-types",
    ),
    path(
        "workspaces/<str:slug>/issue-types/<uuid:pk>/",
        WorkspaceIssueTypeViewSet.as_view({"patch": "partial_update", "delete": "destroy"}),
        name="workspace-issue-type",
    ),
    # 项目级 Issue Types
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/issue-types/",
        ProjectIssueTypeViewSet.as_view({"get": "list", "post": "create"}),
        name="project-issue-types",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/issue-types/<uuid:pk>/",
        ProjectIssueTypeViewSet.as_view({"delete": "destroy"}),
        name="project-issue-type",
    ),
]
```

**Step 2: 注册到 `urls/__init__.py`**

在 `apps/api/plane/app/urls/__init__.py` 中：

```python
from .issue_type import urlpatterns as issue_type_urls
# 在 urlpatterns 列表中加入：
urlpatterns = [
    *issue_type_urls,
    # ... 其他 ...
]
```

**Step 3: 测试 API**

```bash
# 启动服务后
curl -s -H "X-Api-Key: plane_api_59786d0e610c4a509026bce45734f68a" \
  "http://localhost:8000/api/v1/workspaces/wisfe/issue-types/" | python3 -m json.tool
```

Expected: 返回 JSON 数组（初始为空或已有默认类型）

**Step 4: Commit**

```bash
git add apps/api/plane/app/urls/issue_type.py apps/api/plane/app/urls/__init__.py
git commit -m "feat: add IssueType API URL routes"
```

---

## Phase 2：Custom Field 后端 Model

### Task 4：CustomField Django Models + Migration

**Files:**

- Create: `apps/api/plane/db/models/custom_field.py`
- Modify: `apps/api/plane/db/models/__init__.py`
- Create: `apps/api/plane/db/migrations/0119_custom_field.py`

**Step 1: 创建 Model**

```python
# apps/api/plane/db/models/custom_field.py
from django.db import models
from django.db.models import Q
from .base import BaseModel
from .project import ProjectBaseModel


class FieldType(models.TextChoices):
    TEXT = "text", "Text"
    NUMBER = "number", "Number"
    DATE = "date", "Date"
    OPTION = "option", "Single Select"
    # Phase 2 追加：
    # MULTI_OPTION = "multi_option", "Multi Select"
    # USER = "user", "User"
    # DATETIME = "datetime", "DateTime"
    # URL = "url", "URL"
    # CHECKBOX = "checkbox", "Checkbox"


class CustomField(BaseModel):
    """工作区级别的自定义字段定义"""
    workspace = models.ForeignKey(
        "db.Workspace",
        related_name="custom_fields",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    field_type = models.CharField(
        max_length=50,
        choices=FieldType.choices,
        default=FieldType.TEXT,
    )
    is_required = models.BooleanField(default=False)
    default_value = models.JSONField(null=True, blank=True)
    extra = models.JSONField(default=dict, blank=True)  # 预留扩展

    class Meta:
        verbose_name = "Custom Field"
        verbose_name_plural = "Custom Fields"
        db_table = "custom_fields"
        ordering = ("name",)

    def __str__(self):
        return f"{self.workspace.slug} - {self.name} ({self.field_type})"


class CustomFieldOption(BaseModel):
    """单选/多选字段的选项"""
    field = models.ForeignKey(
        "db.CustomField",
        related_name="options",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=255)
    color = models.CharField(max_length=7, default="#6b7280")
    sort_order = models.FloatField(default=65536)

    class Meta:
        verbose_name = "Custom Field Option"
        verbose_name_plural = "Custom Field Options"
        db_table = "custom_field_options"
        ordering = ("sort_order", "name")
        unique_together = ["field", "name"]

    def __str__(self):
        return f"{self.field.name} - {self.name}"


class IssueTypeCustomField(BaseModel):
    """Issue Type 与 Custom Field 的绑定关系"""
    issue_type = models.ForeignKey(
        "db.IssueType",
        related_name="custom_field_bindings",
        on_delete=models.CASCADE,
    )
    field = models.ForeignKey(
        "db.CustomField",
        related_name="issue_type_bindings",
        on_delete=models.CASCADE,
    )
    sort_order = models.FloatField(default=65536)
    is_required = models.BooleanField(default=False)  # 可覆盖字段级别的 is_required

    class Meta:
        verbose_name = "Issue Type Custom Field"
        verbose_name_plural = "Issue Type Custom Fields"
        db_table = "issue_type_custom_fields"
        constraints = [
            models.UniqueConstraint(
                fields=["issue_type", "field"],
                condition=Q(deleted_at__isnull=True),
                name="issue_type_custom_field_unique",
            )
        ]
        ordering = ("sort_order",)

    def __str__(self):
        return f"{self.issue_type.name} - {self.field.name}"


class CustomFieldValue(ProjectBaseModel):
    """Issue 上某个自定义字段的值"""
    issue = models.ForeignKey(
        "db.Issue",
        related_name="custom_field_values",
        on_delete=models.CASCADE,
    )
    field = models.ForeignKey(
        "db.CustomField",
        related_name="issue_values",
        on_delete=models.CASCADE,
    )
    value = models.JSONField(null=True, blank=True)

    class Meta:
        verbose_name = "Custom Field Value"
        verbose_name_plural = "Custom Field Values"
        db_table = "custom_field_values"
        constraints = [
            models.UniqueConstraint(
                fields=["issue", "field"],
                condition=Q(deleted_at__isnull=True),
                name="custom_field_value_unique_issue_field",
            )
        ]

    def __str__(self):
        return f"{self.issue_id} - {self.field.name}: {self.value}"
```

**Step 2: 注册到 models `__init__.py`**

在 `apps/api/plane/db/models/__init__.py` 中添加：

```python
from .custom_field import CustomField, CustomFieldOption, IssueTypeCustomField, CustomFieldValue
```

**Step 3: 生成并检查迁移**

```bash
cd /Users/wisedu/Documents/GitHub/plane/apps/api
python manage.py makemigrations db --name custom_field
```

Expected: 生成 `0119_custom_field.py`

检查生成的迁移文件是否正确包含 4 个新表。

**Step 4: 应用迁移**

```bash
# 在容器内执行（或本地）
docker exec plane-api-1 python manage.py migrate db 0119
# 或本地
python manage.py migrate
```

Expected: `OK`

**Step 5: Commit**

```bash
git add apps/api/plane/db/models/custom_field.py apps/api/plane/db/models/__init__.py apps/api/plane/db/migrations/0119_custom_field.py
git commit -m "feat: add CustomField, CustomFieldOption, IssueTypeCustomField, CustomFieldValue models"
```

---

## Phase 3：Custom Field 后端 API

### Task 5：Custom Field Serializers

**Files:**

- Create: `apps/api/plane/app/serializers/custom_field.py`
- Modify: `apps/api/plane/app/serializers/__init__.py`

**Step 1: 创建 Serializers**

```python
# apps/api/plane/app/serializers/custom_field.py
from rest_framework import serializers
from .base import BaseSerializer
from plane.db.models import CustomField, CustomFieldOption, IssueTypeCustomField, CustomFieldValue


class CustomFieldOptionSerializer(BaseSerializer):
    class Meta:
        model = CustomFieldOption
        fields = ["id", "field", "name", "color", "sort_order"]
        read_only_fields = ["id"]


class CustomFieldSerializer(BaseSerializer):
    options = CustomFieldOptionSerializer(many=True, read_only=True)

    class Meta:
        model = CustomField
        fields = [
            "id",
            "workspace_id",
            "name",
            "description",
            "field_type",
            "is_required",
            "default_value",
            "extra",
            "options",
        ]
        read_only_fields = ["workspace", "id"]


class IssueTypeCustomFieldSerializer(BaseSerializer):
    field_detail = CustomFieldSerializer(source="field", read_only=True)

    class Meta:
        model = IssueTypeCustomField
        fields = [
            "id",
            "issue_type",
            "field",
            "field_detail",
            "sort_order",
            "is_required",
        ]
        read_only_fields = ["id"]


class CustomFieldValueSerializer(BaseSerializer):
    class Meta:
        model = CustomFieldValue
        fields = [
            "id",
            "issue",
            "field",
            "value",
            "project_id",
            "workspace_id",
        ]
        read_only_fields = ["workspace", "project", "id"]
```

**Step 2: 注册到 `__init__.py`**

```python
from .custom_field import (
    CustomFieldSerializer,
    CustomFieldOptionSerializer,
    IssueTypeCustomFieldSerializer,
    CustomFieldValueSerializer,
)
```

**Step 3: 验证**

```bash
python -c "from plane.app.serializers import CustomFieldSerializer; print('OK')"
```

**Step 4: Commit**

```bash
git add apps/api/plane/app/serializers/custom_field.py apps/api/plane/app/serializers/__init__.py
git commit -m "feat: add Custom Field serializers"
```

---

### Task 6：Custom Field ViewSets

**Files:**

- Create: `apps/api/plane/app/views/custom_field/`
- Create: `apps/api/plane/app/views/custom_field/__init__.py`
- Create: `apps/api/plane/app/views/custom_field/base.py`
- Modify: `apps/api/plane/app/views/__init__.py`

**Step 1: 创建 Views**

```python
# apps/api/plane/app/views/custom_field/base.py
from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import allow_permission, ROLE
from plane.app.serializers import (
    CustomFieldSerializer,
    CustomFieldOptionSerializer,
    IssueTypeCustomFieldSerializer,
    CustomFieldValueSerializer,
)
from plane.db.models import (
    CustomField, CustomFieldOption,
    IssueTypeCustomField, CustomFieldValue, Workspace,
)
from ..base import BaseViewSet


class WorkspaceCustomFieldViewSet(BaseViewSet):
    """工作区级自定义字段 CRUD"""
    serializer_class = CustomFieldSerializer
    model = CustomField

    def get_queryset(self):
        return (
            self.filter_queryset(super().get_queryset())
            .filter(workspace__slug=self.kwargs.get("slug"))
            .prefetch_related("options")
            .order_by("name")
        )

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def list(self, request, slug):
        fields = self.get_queryset()
        return Response(CustomFieldSerializer(fields, many=True).data)

    @allow_permission([ROLE.ADMIN])
    def create(self, request, slug):
        workspace = Workspace.objects.get(slug=slug)
        serializer = CustomFieldSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(workspace=workspace)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @allow_permission([ROLE.ADMIN])
    def partial_update(self, request, slug, pk):
        field = CustomField.objects.get(pk=pk, workspace__slug=slug)
        serializer = CustomFieldSerializer(field, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @allow_permission([ROLE.ADMIN])
    def destroy(self, request, slug, pk):
        CustomField.objects.get(pk=pk, workspace__slug=slug).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CustomFieldOptionViewSet(BaseViewSet):
    """字段选项 CRUD"""
    serializer_class = CustomFieldOptionSerializer
    model = CustomFieldOption

    def get_queryset(self):
        return (
            self.filter_queryset(super().get_queryset())
            .filter(field_id=self.kwargs.get("field_id"))
            .order_by("sort_order")
        )

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def list(self, request, slug, field_id):
        return Response(CustomFieldOptionSerializer(self.get_queryset(), many=True).data)

    @allow_permission([ROLE.ADMIN])
    def create(self, request, slug, field_id):
        serializer = CustomFieldOptionSerializer(data={**request.data, "field": field_id})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @allow_permission([ROLE.ADMIN])
    def partial_update(self, request, slug, field_id, pk):
        option = CustomFieldOption.objects.get(pk=pk, field_id=field_id)
        serializer = CustomFieldOptionSerializer(option, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @allow_permission([ROLE.ADMIN])
    def destroy(self, request, slug, field_id, pk):
        CustomFieldOption.objects.get(pk=pk, field_id=field_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class IssueTypeCustomFieldViewSet(BaseViewSet):
    """Issue Type ↔ Custom Field 绑定"""
    serializer_class = IssueTypeCustomFieldSerializer
    model = IssueTypeCustomField

    def get_queryset(self):
        return (
            self.filter_queryset(super().get_queryset())
            .filter(issue_type_id=self.kwargs.get("issue_type_id"))
            .select_related("field")
            .prefetch_related("field__options")
            .order_by("sort_order")
        )

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def list(self, request, slug, issue_type_id):
        return Response(IssueTypeCustomFieldSerializer(self.get_queryset(), many=True).data)

    @allow_permission([ROLE.ADMIN])
    def create(self, request, slug, issue_type_id):
        serializer = IssueTypeCustomFieldSerializer(
            data={**request.data, "issue_type": issue_type_id}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @allow_permission([ROLE.ADMIN])
    def destroy(self, request, slug, issue_type_id, pk):
        IssueTypeCustomField.objects.get(pk=pk, issue_type_id=issue_type_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @allow_permission([ROLE.ADMIN])
    def partial_update(self, request, slug, issue_type_id, pk):
        binding = IssueTypeCustomField.objects.get(pk=pk, issue_type_id=issue_type_id)
        serializer = IssueTypeCustomFieldSerializer(binding, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class IssueCustomFieldValueViewSet(BaseViewSet):
    """Issue 上的字段值 CRUD"""
    serializer_class = CustomFieldValueSerializer
    model = CustomFieldValue

    def get_queryset(self):
        return (
            self.filter_queryset(super().get_queryset())
            .filter(
                issue_id=self.kwargs.get("issue_id"),
                workspace__slug=self.kwargs.get("slug"),
            )
            .select_related("field")
        )

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def list(self, request, slug, project_id, issue_id):
        return Response(CustomFieldValueSerializer(self.get_queryset(), many=True).data)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def create(self, request, slug, project_id, issue_id):
        serializer = CustomFieldValueSerializer(
            data={**request.data, "issue": issue_id}
        )
        if serializer.is_valid():
            serializer.save(project_id=project_id)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def partial_update(self, request, slug, project_id, issue_id, pk):
        cfv = CustomFieldValue.objects.get(pk=pk, issue_id=issue_id)
        serializer = CustomFieldValueSerializer(cfv, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def destroy(self, request, slug, project_id, issue_id, pk):
        CustomFieldValue.objects.get(pk=pk, issue_id=issue_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
```

```python
# apps/api/plane/app/views/custom_field/__init__.py
from .base import (
    WorkspaceCustomFieldViewSet,
    CustomFieldOptionViewSet,
    IssueTypeCustomFieldViewSet,
    IssueCustomFieldValueViewSet,
)
```

**Step 2: 注册到 views `__init__.py`**

```python
from .custom_field import (
    WorkspaceCustomFieldViewSet,
    CustomFieldOptionViewSet,
    IssueTypeCustomFieldViewSet,
    IssueCustomFieldValueViewSet,
)
```

**Step 3: Commit**

```bash
git add apps/api/plane/app/views/custom_field/ apps/api/plane/app/views/__init__.py
git commit -m "feat: add Custom Field ViewSets"
```

---

### Task 7：Custom Field URL 路由

**Files:**

- Create: `apps/api/plane/app/urls/custom_field.py`
- Modify: `apps/api/plane/app/urls/__init__.py`

**Step 1: 创建路由**

```python
# apps/api/plane/app/urls/custom_field.py
from django.urls import path
from plane.app.views import (
    WorkspaceCustomFieldViewSet,
    CustomFieldOptionViewSet,
    IssueTypeCustomFieldViewSet,
    IssueCustomFieldValueViewSet,
)

urlpatterns = [
    # 工作区级自定义字段
    path(
        "workspaces/<str:slug>/custom-fields/",
        WorkspaceCustomFieldViewSet.as_view({"get": "list", "post": "create"}),
        name="workspace-custom-fields",
    ),
    path(
        "workspaces/<str:slug>/custom-fields/<uuid:pk>/",
        WorkspaceCustomFieldViewSet.as_view({
            "patch": "partial_update",
            "delete": "destroy",
        }),
        name="workspace-custom-field",
    ),
    # 字段选项
    path(
        "workspaces/<str:slug>/custom-fields/<uuid:field_id>/options/",
        CustomFieldOptionViewSet.as_view({"get": "list", "post": "create"}),
        name="custom-field-options",
    ),
    path(
        "workspaces/<str:slug>/custom-fields/<uuid:field_id>/options/<uuid:pk>/",
        CustomFieldOptionViewSet.as_view({
            "patch": "partial_update",
            "delete": "destroy",
        }),
        name="custom-field-option",
    ),
    # Issue Type ↔ 字段绑定
    path(
        "workspaces/<str:slug>/issue-types/<uuid:issue_type_id>/custom-fields/",
        IssueTypeCustomFieldViewSet.as_view({"get": "list", "post": "create"}),
        name="issue-type-custom-fields",
    ),
    path(
        "workspaces/<str:slug>/issue-types/<uuid:issue_type_id>/custom-fields/<uuid:pk>/",
        IssueTypeCustomFieldViewSet.as_view({
            "patch": "partial_update",
            "delete": "destroy",
        }),
        name="issue-type-custom-field",
    ),
    # Issue 字段值
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/issues/<uuid:issue_id>/custom-field-values/",
        IssueCustomFieldValueViewSet.as_view({"get": "list", "post": "create"}),
        name="issue-custom-field-values",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/issues/<uuid:issue_id>/custom-field-values/<uuid:pk>/",
        IssueCustomFieldValueViewSet.as_view({
            "patch": "partial_update",
            "delete": "destroy",
        }),
        name="issue-custom-field-value",
    ),
]
```

**Step 2: 注册**

```python
# apps/api/plane/app/urls/__init__.py
from .custom_field import urlpatterns as custom_field_urls
# 加到 urlpatterns
```

**Step 3: 端对端测试**

```bash
# 创建字段
curl -s -X POST \
  -H "X-Api-Key: plane_api_59786d0e610c4a509026bce45734f68a" \
  -H "Content-Type: application/json" \
  -d '{"name": "严重等级", "field_type": "option", "is_required": false}' \
  "http://localhost:8000/api/v1/workspaces/wisfe/custom-fields/" | python3 -m json.tool
```

Expected: 201 Created with field data including `id`

**Step 4: Commit**

```bash
git add apps/api/plane/app/urls/custom_field.py apps/api/plane/app/urls/__init__.py
git commit -m "feat: add Custom Field API URL routes"
```

---

## Phase 4：前端 TypeScript 类型

### Task 8：TypeScript 接口定义

**Files:**

- Create: `packages/types/src/custom-field.ts`
- Modify: `packages/types/src/index.ts`

**Step 1: 创建类型文件**

```typescript
// packages/types/src/custom-field.ts

export type TCustomFieldType = "text" | "number" | "date" | "option";

export interface ICustomFieldOption {
  id: string;
  field: string;
  name: string;
  color: string;
  sort_order: number;
}

export interface ICustomField {
  id: string;
  workspace_id: string;
  name: string;
  description: string;
  field_type: TCustomFieldType;
  is_required: boolean;
  default_value: string | number | null;
  extra: Record<string, unknown>;
  options: ICustomFieldOption[];
}

export interface IIssueTypeCustomField {
  id: string;
  issue_type: string;
  field: string;
  field_detail: ICustomField;
  sort_order: number;
  is_required: boolean;
}

export interface ICustomFieldValue {
  id: string;
  issue: string;
  field: string;
  value: string | number | null;
  project_id: string;
  workspace_id: string;
}

export interface IIssueType {
  id: string;
  workspace_id: string;
  name: string;
  description: string;
  logo_props: Record<string, unknown>;
  is_epic: boolean;
  is_default: boolean;
  is_active: boolean;
  level: number;
}

export interface IProjectIssueType {
  id: string;
  project_id: string;
  workspace_id: string;
  issue_type: string;
  issue_type_detail: IIssueType;
  level: number;
  is_default: boolean;
}
```

**Step 2: 注册到 index**

```typescript
// packages/types/src/index.ts 末尾添加
export * from "./custom-field";
```

**Step 3: 验证类型编译**

```bash
cd /Users/wisedu/Documents/GitHub/plane
pnpm --filter @plane/types build
```

Expected: 无 TypeScript 错误

**Step 4: Commit**

```bash
git add packages/types/src/custom-field.ts packages/types/src/index.ts
git commit -m "feat: add Custom Field and IssueType TypeScript interfaces"
```

---

## Phase 5：前端 Services + Store

### Task 9：前端 API Services

**Files:**

- Create: `apps/web/core/services/custom-field.service.ts`
- Create: `apps/web/core/services/issue-type.service.ts`

**Step 1: Custom Field Service**

```typescript
// apps/web/core/services/custom-field.service.ts
import { API_BASE_URL } from "@/helpers/common.helper";
import { APIService } from "./api.service";
import type { ICustomField, ICustomFieldOption, IIssueTypeCustomField, ICustomFieldValue } from "@plane/types";

export class CustomFieldService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async listFields(workspaceSlug: string): Promise<ICustomField[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/custom-fields/`)
      .then((res) => res?.data)
      .catch((err) => {
        throw err?.response?.data;
      });
  }

  async createField(workspaceSlug: string, data: Partial<ICustomField>): Promise<ICustomField> {
    return this.post(`/api/workspaces/${workspaceSlug}/custom-fields/`, data)
      .then((res) => res?.data)
      .catch((err) => {
        throw err?.response?.data;
      });
  }

  async updateField(workspaceSlug: string, fieldId: string, data: Partial<ICustomField>): Promise<ICustomField> {
    return this.patch(`/api/workspaces/${workspaceSlug}/custom-fields/${fieldId}/`, data)
      .then((res) => res?.data)
      .catch((err) => {
        throw err?.response?.data;
      });
  }

  async deleteField(workspaceSlug: string, fieldId: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/custom-fields/${fieldId}/`)
      .then((res) => res?.data)
      .catch((err) => {
        throw err?.response;
      });
  }

  // 选项 CRUD
  async createOption(
    workspaceSlug: string,
    fieldId: string,
    data: Partial<ICustomFieldOption>
  ): Promise<ICustomFieldOption> {
    return this.post(`/api/workspaces/${workspaceSlug}/custom-fields/${fieldId}/options/`, data)
      .then((res) => res?.data)
      .catch((err) => {
        throw err?.response?.data;
      });
  }

  async updateOption(
    workspaceSlug: string,
    fieldId: string,
    optionId: string,
    data: Partial<ICustomFieldOption>
  ): Promise<ICustomFieldOption> {
    return this.patch(`/api/workspaces/${workspaceSlug}/custom-fields/${fieldId}/options/${optionId}/`, data)
      .then((res) => res?.data)
      .catch((err) => {
        throw err?.response?.data;
      });
  }

  async deleteOption(workspaceSlug: string, fieldId: string, optionId: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/custom-fields/${fieldId}/options/${optionId}/`)
      .then((res) => res?.data)
      .catch((err) => {
        throw err?.response;
      });
  }

  // Issue Type 绑定
  async listIssueTypeFields(workspaceSlug: string, issueTypeId: string): Promise<IIssueTypeCustomField[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/issue-types/${issueTypeId}/custom-fields/`)
      .then((res) => res?.data)
      .catch((err) => {
        throw err?.response?.data;
      });
  }

  async addFieldToIssueType(
    workspaceSlug: string,
    issueTypeId: string,
    data: { field: string; sort_order?: number }
  ): Promise<IIssueTypeCustomField> {
    return this.post(`/api/workspaces/${workspaceSlug}/issue-types/${issueTypeId}/custom-fields/`, data)
      .then((res) => res?.data)
      .catch((err) => {
        throw err?.response?.data;
      });
  }

  async removeFieldFromIssueType(workspaceSlug: string, issueTypeId: string, bindingId: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/issue-types/${issueTypeId}/custom-fields/${bindingId}/`)
      .then((res) => res?.data)
      .catch((err) => {
        throw err?.response;
      });
  }

  // Issue 字段值
  async getIssueFieldValues(workspaceSlug: string, projectId: string, issueId: string): Promise<ICustomFieldValue[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/issues/${issueId}/custom-field-values/`)
      .then((res) => res?.data)
      .catch((err) => {
        throw err?.response?.data;
      });
  }

  async setIssueFieldValue(
    workspaceSlug: string,
    projectId: string,
    issueId: string,
    data: { field: string; value: unknown }
  ): Promise<ICustomFieldValue> {
    return this.post(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/issues/${issueId}/custom-field-values/`,
      data
    )
      .then((res) => res?.data)
      .catch((err) => {
        throw err?.response?.data;
      });
  }

  async updateIssueFieldValue(
    workspaceSlug: string,
    projectId: string,
    issueId: string,
    valueId: string,
    data: { value: unknown }
  ): Promise<ICustomFieldValue> {
    return this.patch(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/issues/${issueId}/custom-field-values/${valueId}/`,
      data
    )
      .then((res) => res?.data)
      .catch((err) => {
        throw err?.response?.data;
      });
  }
}

export const customFieldService = new CustomFieldService();
```

**Step 2: Issue Type Service**

```typescript
// apps/web/core/services/issue-type.service.ts
import { API_BASE_URL } from "@/helpers/common.helper";
import { APIService } from "./api.service";
import type { IIssueType, IProjectIssueType } from "@plane/types";

export class IssueTypeService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async listWorkspaceIssueTypes(workspaceSlug: string): Promise<IIssueType[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/issue-types/`)
      .then((res) => res?.data)
      .catch((err) => {
        throw err?.response?.data;
      });
  }

  async createIssueType(workspaceSlug: string, data: Partial<IIssueType>): Promise<IIssueType> {
    return this.post(`/api/workspaces/${workspaceSlug}/issue-types/`, data)
      .then((res) => res?.data)
      .catch((err) => {
        throw err?.response?.data;
      });
  }

  async updateIssueType(workspaceSlug: string, typeId: string, data: Partial<IIssueType>): Promise<IIssueType> {
    return this.patch(`/api/workspaces/${workspaceSlug}/issue-types/${typeId}/`, data)
      .then((res) => res?.data)
      .catch((err) => {
        throw err?.response?.data;
      });
  }

  async deleteIssueType(workspaceSlug: string, typeId: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/issue-types/${typeId}/`)
      .then((res) => res?.data)
      .catch((err) => {
        throw err?.response;
      });
  }

  async listProjectIssueTypes(workspaceSlug: string, projectId: string): Promise<IProjectIssueType[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/issue-types/`)
      .then((res) => res?.data)
      .catch((err) => {
        throw err?.response?.data;
      });
  }
}

export const issueTypeService = new IssueTypeService();
```

**Step 3: Commit**

```bash
git add apps/web/core/services/custom-field.service.ts apps/web/core/services/issue-type.service.ts
git commit -m "feat: add CustomFieldService and IssueTypeService"
```

---

### Task 10：Mobx Store

**Files:**

- Create: `apps/web/core/store/custom-field.store.ts`
- Create: `apps/web/core/store/issue-type.store.ts`
- Modify: `apps/web/core/store/root.store.ts`

**Step 1: Issue Type Store**

```typescript
// apps/web/core/store/issue-type.store.ts
import { action, makeObservable, observable, runInAction, computed } from "mobx";
import { set } from "lodash";
import type { IIssueType } from "@plane/types";
import { issueTypeService } from "@/services/issue-type.service";

export interface IIssueTypeStore {
  issueTypeMap: Record<string, IIssueType>;
  fetchedWorkspaces: Record<string, boolean>;
  // computed
  getIssueTypeById: (id: string) => IIssueType | undefined;
  getWorkspaceIssueTypes: (workspaceSlug: string) => IIssueType[];
  // actions
  fetchWorkspaceIssueTypes: (workspaceSlug: string) => Promise<IIssueType[]>;
  createIssueType: (workspaceSlug: string, data: Partial<IIssueType>) => Promise<IIssueType>;
  updateIssueType: (workspaceSlug: string, typeId: string, data: Partial<IIssueType>) => Promise<IIssueType>;
  deleteIssueType: (workspaceSlug: string, typeId: string) => Promise<void>;
}

export class IssueTypeStore implements IIssueTypeStore {
  issueTypeMap: Record<string, IIssueType> = {};
  fetchedWorkspaces: Record<string, boolean> = {};

  constructor() {
    makeObservable(this, {
      issueTypeMap: observable,
      fetchedWorkspaces: observable,
      getIssueTypeById: computed.struct,
      fetchWorkspaceIssueTypes: action,
      createIssueType: action,
      updateIssueType: action,
      deleteIssueType: action,
    });
  }

  getIssueTypeById = (id: string) => this.issueTypeMap[id];

  getWorkspaceIssueTypes = (workspaceSlug: string) =>
    Object.values(this.issueTypeMap).filter(
      (t) => t.workspace_id === workspaceSlug || true // workspace_id is UUID, need slug lookup
    );

  fetchWorkspaceIssueTypes = async (workspaceSlug: string) => {
    const types = await issueTypeService.listWorkspaceIssueTypes(workspaceSlug);
    runInAction(() => {
      types.forEach((t) => set(this.issueTypeMap, t.id, t));
      this.fetchedWorkspaces[workspaceSlug] = true;
    });
    return types;
  };

  createIssueType = async (workspaceSlug: string, data: Partial<IIssueType>) => {
    const type = await issueTypeService.createIssueType(workspaceSlug, data);
    runInAction(() => set(this.issueTypeMap, type.id, type));
    return type;
  };

  updateIssueType = async (workspaceSlug: string, typeId: string, data: Partial<IIssueType>) => {
    const original = this.issueTypeMap[typeId];
    try {
      runInAction(() => set(this.issueTypeMap, typeId, { ...original, ...data }));
      const updated = await issueTypeService.updateIssueType(workspaceSlug, typeId, data);
      runInAction(() => set(this.issueTypeMap, typeId, updated));
      return updated;
    } catch (e) {
      runInAction(() => set(this.issueTypeMap, typeId, original));
      throw e;
    }
  };

  deleteIssueType = async (workspaceSlug: string, typeId: string) => {
    await issueTypeService.deleteIssueType(workspaceSlug, typeId);
    runInAction(() => delete this.issueTypeMap[typeId]);
  };
}
```

**Step 2: Custom Field Store**

```typescript
// apps/web/core/store/custom-field.store.ts
import { action, makeObservable, observable, runInAction } from "mobx";
import { set, keyBy } from "lodash";
import type { ICustomField, ICustomFieldValue } from "@plane/types";
import { customFieldService } from "@/services/custom-field.service";

export interface ICustomFieldStore {
  fieldMap: Record<string, ICustomField>;
  // issue_id → field_id → value
  valueMap: Record<string, Record<string, ICustomFieldValue>>;
  fetchWorkspaceFields: (workspaceSlug: string) => Promise<ICustomField[]>;
  createField: (workspaceSlug: string, data: Partial<ICustomField>) => Promise<ICustomField>;
  updateField: (workspaceSlug: string, fieldId: string, data: Partial<ICustomField>) => Promise<ICustomField>;
  deleteField: (workspaceSlug: string, fieldId: string) => Promise<void>;
  fetchIssueFieldValues: (workspaceSlug: string, projectId: string, issueId: string) => Promise<ICustomFieldValue[]>;
  setFieldValue: (
    workspaceSlug: string,
    projectId: string,
    issueId: string,
    fieldId: string,
    value: unknown
  ) => Promise<void>;
}

export class CustomFieldStore implements ICustomFieldStore {
  fieldMap: Record<string, ICustomField> = {};
  valueMap: Record<string, Record<string, ICustomFieldValue>> = {};

  constructor() {
    makeObservable(this, {
      fieldMap: observable,
      valueMap: observable,
      fetchWorkspaceFields: action,
      createField: action,
      updateField: action,
      deleteField: action,
      fetchIssueFieldValues: action,
      setFieldValue: action,
    });
  }

  fetchWorkspaceFields = async (workspaceSlug: string) => {
    const fields = await customFieldService.listFields(workspaceSlug);
    runInAction(() => {
      fields.forEach((f) => set(this.fieldMap, f.id, f));
    });
    return fields;
  };

  createField = async (workspaceSlug: string, data: Partial<ICustomField>) => {
    const field = await customFieldService.createField(workspaceSlug, data);
    runInAction(() => set(this.fieldMap, field.id, field));
    return field;
  };

  updateField = async (workspaceSlug: string, fieldId: string, data: Partial<ICustomField>) => {
    const original = this.fieldMap[fieldId];
    try {
      runInAction(() => set(this.fieldMap, fieldId, { ...original, ...data }));
      const updated = await customFieldService.updateField(workspaceSlug, fieldId, data);
      runInAction(() => set(this.fieldMap, fieldId, updated));
      return updated;
    } catch (e) {
      runInAction(() => set(this.fieldMap, fieldId, original));
      throw e;
    }
  };

  deleteField = async (workspaceSlug: string, fieldId: string) => {
    await customFieldService.deleteField(workspaceSlug, fieldId);
    runInAction(() => delete this.fieldMap[fieldId]);
  };

  fetchIssueFieldValues = async (workspaceSlug: string, projectId: string, issueId: string) => {
    const values = await customFieldService.getIssueFieldValues(workspaceSlug, projectId, issueId);
    runInAction(() => {
      const byField = keyBy(values, "field");
      set(this.valueMap, issueId, byField);
    });
    return values;
  };

  setFieldValue = async (
    workspaceSlug: string,
    projectId: string,
    issueId: string,
    fieldId: string,
    value: unknown
  ) => {
    const existing = this.valueMap[issueId]?.[fieldId];
    if (existing) {
      const updated = await customFieldService.updateIssueFieldValue(workspaceSlug, projectId, issueId, existing.id, {
        value,
      });
      runInAction(() => set(this.valueMap, [issueId, fieldId], updated));
    } else {
      const created = await customFieldService.setIssueFieldValue(workspaceSlug, projectId, issueId, {
        field: fieldId,
        value,
      });
      runInAction(() => set(this.valueMap, [issueId, fieldId], created));
    }
  };
}
```

**Step 3: 注册到 root.store.ts**

找到 `apps/web/core/store/root.store.ts`，添加：

```typescript
import { IssueTypeStore } from "./issue-type.store";
import { CustomFieldStore } from "./custom-field.store";

export class CoreRootStore {
  // ...existing stores...
  issueType: IssueTypeStore;
  customField: CustomFieldStore;

  constructor() {
    // ...existing...
    this.issueType = new IssueTypeStore();
    this.customField = new CustomFieldStore();
  }
}
```

**Step 4: Commit**

```bash
git add apps/web/core/store/issue-type.store.ts apps/web/core/store/custom-field.store.ts apps/web/core/store/root.store.ts
git commit -m "feat: add IssueTypeStore and CustomFieldStore (MobX)"
```

---

## Phase 6：Settings UI

### Task 11：Workspace Settings - Issue Types 页面

**Files:**

- Create: `apps/web/core/components/workspace/settings/issue-types/`
- Create: `apps/web/core/components/workspace/settings/issue-types/root.tsx`
- Create: `apps/web/core/components/workspace/settings/issue-types/issue-type-item.tsx`
- Create: `apps/web/core/components/workspace/settings/issue-types/create-update-form.tsx`
- Create: `apps/web/app/(all)/[workspaceSlug]/(settings)/settings/issue-types/page.tsx`

**Step 1: IssueType Item 组件**

```tsx
// apps/web/core/components/workspace/settings/issue-types/issue-type-item.tsx
"use client";
import { useState } from "react";
import { Pencil, Trash2 } from "lucide-react";
import type { IIssueType } from "@plane/types";

type Props = {
  issueType: IIssueType;
  onEdit: (type: IIssueType) => void;
  onDelete: (typeId: string) => void;
};

export const IssueTypeItem = ({ issueType, onEdit, onDelete }: Props) => (
  <div className="flex items-center justify-between p-3 rounded border border-custom-border-200 bg-custom-background-100">
    <div className="flex items-center gap-3">
      <span className="font-medium text-sm text-custom-text-200">{issueType.name}</span>
      {issueType.is_default && (
        <span className="text-xs px-2 py-0.5 rounded bg-custom-primary-100/20 text-custom-primary-100">默认</span>
      )}
    </div>
    <div className="flex items-center gap-2">
      <button onClick={() => onEdit(issueType)} className="p-1 text-custom-text-300 hover:text-custom-text-100">
        <Pencil size={14} />
      </button>
      {!issueType.is_default && (
        <button onClick={() => onDelete(issueType.id)} className="p-1 text-custom-text-300 hover:text-red-500">
          <Trash2 size={14} />
        </button>
      )}
    </div>
  </div>
);
```

**Step 2: Create/Update Form**

```tsx
// apps/web/core/components/workspace/settings/issue-types/create-update-form.tsx
"use client";
import { useState } from "react";
import { Button, Input } from "@plane/ui";
import type { IIssueType } from "@plane/types";

type Props = {
  data?: IIssueType;
  onSubmit: (data: Partial<IIssueType>) => Promise<void>;
  onCancel: () => void;
};

export const IssueTypeForm = ({ data, onSubmit, onCancel }: Props) => {
  const [name, setName] = useState(data?.name ?? "");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (!name.trim()) return;
    setLoading(true);
    await onSubmit({ name: name.trim() });
    setLoading(false);
  };

  return (
    <div className="p-3 rounded border border-custom-border-200 bg-custom-background-90 space-y-2">
      <Input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Issue Type 名称（如：Bug、Story、Epic）"
        autoFocus
      />
      <div className="flex gap-2">
        <Button onClick={handleSubmit} variant="primary" size="sm" loading={loading}>
          {data ? "更新" : "创建"}
        </Button>
        <Button onClick={onCancel} variant="neutral-primary" size="sm">
          取消
        </Button>
      </div>
    </div>
  );
};
```

**Step 3: Root 组件**

```tsx
// apps/web/core/components/workspace/settings/issue-types/root.tsx
"use client";
import { useEffect, useState } from "react";
import { observer } from "mobx-react";
import { Plus } from "lucide-react";
import { Button } from "@plane/ui";
import { useStore } from "@/hooks/store";
import type { IIssueType } from "@plane/types";
import { IssueTypeItem } from "./issue-type-item";
import { IssueTypeForm } from "./create-update-form";

type Props = { workspaceSlug: string };

export const WorkspaceIssueTypesRoot = observer(({ workspaceSlug }: Props) => {
  const { issueType } = useStore();
  const [showCreate, setShowCreate] = useState(false);
  const [editingType, setEditingType] = useState<IIssueType | null>(null);

  useEffect(() => {
    issueType.fetchWorkspaceIssueTypes(workspaceSlug);
  }, [workspaceSlug]);

  const issueTypes = Object.values(issueType.issueTypeMap);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">Issue Types</h3>
          <p className="text-sm text-custom-text-300">
            定义工作区的 Issue 类型（如 Story、Bug、Epic），每种类型可配置不同的自定义字段。
          </p>
        </div>
        <Button onClick={() => setShowCreate(true)} size="sm">
          <Plus size={14} className="mr-1" /> 添加类型
        </Button>
      </div>

      <div className="space-y-2">
        {showCreate && (
          <IssueTypeForm
            onSubmit={async (data) => {
              await issueType.createIssueType(workspaceSlug, data);
              setShowCreate(false);
            }}
            onCancel={() => setShowCreate(false)}
          />
        )}
        {issueTypes.map((type) =>
          editingType?.id === type.id ? (
            <IssueTypeForm
              key={type.id}
              data={type}
              onSubmit={async (data) => {
                await issueType.updateIssueType(workspaceSlug, type.id, data);
                setEditingType(null);
              }}
              onCancel={() => setEditingType(null)}
            />
          ) : (
            <IssueTypeItem
              key={type.id}
              issueType={type}
              onEdit={setEditingType}
              onDelete={(id) => issueType.deleteIssueType(workspaceSlug, id)}
            />
          )
        )}
        {issueTypes.length === 0 && !showCreate && (
          <p className="text-sm text-custom-text-400 py-4 text-center">暂无 Issue Types，点击右上角添加</p>
        )}
      </div>
    </div>
  );
});
```

**Step 4: 页面路由文件**

```tsx
// apps/web/app/(all)/[workspaceSlug]/(settings)/settings/issue-types/page.tsx
import type { Metadata } from "next";
import { WorkspaceIssueTypesRoot } from "@/components/workspace/settings/issue-types/root";

export const metadata: Metadata = { title: "Issue Types - Workspace Settings" };

export default function IssueTypesPage({ params }: { params: { workspaceSlug: string } }) {
  return (
    <div className="w-full overflow-y-auto py-8 px-9">
      <WorkspaceIssueTypesRoot workspaceSlug={params.workspaceSlug} />
    </div>
  );
}
```

**Step 5: 添加导航菜单项**

找到 Workspace Settings 的导航配置文件（通常在 `apps/web/app/(all)/[workspaceSlug]/(settings)/` 目录下的布局或配置文件），在 States/Labels/Members 等菜单项附近添加：

```tsx
{ label: "Issue Types", href: `/settings/issue-types`, Icon: List }
```

**Step 6: Commit**

```bash
git add apps/web/core/components/workspace/settings/issue-types/ apps/web/app/(all)/[workspaceSlug]/(settings)/settings/issue-types/
git commit -m "feat: add Workspace Settings - Issue Types page"
```

---

### Task 12：Workspace Settings - Custom Fields 页面

**Files:**

- Create: `apps/web/core/components/workspace/settings/custom-fields/`
- Create: `apps/web/core/components/workspace/settings/custom-fields/root.tsx`
- Create: `apps/web/core/components/workspace/settings/custom-fields/field-item.tsx`
- Create: `apps/web/core/components/workspace/settings/custom-fields/create-update-form.tsx`
- Create: `apps/web/app/(all)/[workspaceSlug]/(settings)/settings/custom-fields/page.tsx`

**Step 1: Field Form（支持 P0 四种类型）**

```tsx
// apps/web/core/components/workspace/settings/custom-fields/create-update-form.tsx
"use client";
import { useState } from "react";
import { Button, Input } from "@plane/ui";
import type { ICustomField, TCustomFieldType } from "@plane/types";

const FIELD_TYPES: { value: TCustomFieldType; label: string }[] = [
  { value: "text", label: "文本" },
  { value: "number", label: "数字" },
  { value: "date", label: "日期" },
  { value: "option", label: "单选" },
];

type Props = {
  data?: ICustomField;
  onSubmit: (data: Partial<ICustomField>) => Promise<void>;
  onCancel: () => void;
};

export const CustomFieldForm = ({ data, onSubmit, onCancel }: Props) => {
  const [name, setName] = useState(data?.name ?? "");
  const [fieldType, setFieldType] = useState<TCustomFieldType>(data?.field_type ?? "text");
  const [isRequired, setIsRequired] = useState(data?.is_required ?? false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (!name.trim()) return;
    setLoading(true);
    await onSubmit({ name: name.trim(), field_type: fieldType, is_required: isRequired });
    setLoading(false);
  };

  return (
    <div className="p-4 rounded border border-custom-border-200 bg-custom-background-90 space-y-3">
      <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="字段名称（如：严重等级）" autoFocus />

      <div className="flex gap-2">
        {FIELD_TYPES.map((t) => (
          <button
            key={t.value}
            onClick={() => setFieldType(t.value)}
            className={`px-3 py-1 text-sm rounded border ${
              fieldType === t.value
                ? "border-custom-primary-100 bg-custom-primary-100/10 text-custom-primary-100"
                : "border-custom-border-200 text-custom-text-300"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <label className="flex items-center gap-2 text-sm text-custom-text-200">
        <input type="checkbox" checked={isRequired} onChange={(e) => setIsRequired(e.target.checked)} />
        必填字段
      </label>

      <div className="flex gap-2">
        <Button onClick={handleSubmit} variant="primary" size="sm" loading={loading}>
          {data ? "更新" : "创建"}
        </Button>
        <Button onClick={onCancel} variant="neutral-primary" size="sm">
          取消
        </Button>
      </div>
    </div>
  );
};
```

**Step 2: Field Item 组件（含选项管理入口）**

```tsx
// apps/web/core/components/workspace/settings/custom-fields/field-item.tsx
"use client";
import { Pencil, Trash2, ChevronDown } from "lucide-react";
import type { ICustomField } from "@plane/types";

const FIELD_TYPE_LABEL: Record<string, string> = {
  text: "文本",
  number: "数字",
  date: "日期",
  option: "单选",
};

type Props = {
  field: ICustomField;
  onEdit: (field: ICustomField) => void;
  onDelete: (fieldId: string) => void;
};

export const CustomFieldItem = ({ field, onEdit, onDelete }: Props) => (
  <div className="flex items-center justify-between p-3 rounded border border-custom-border-200">
    <div className="flex items-center gap-3">
      <span className="text-xs px-2 py-0.5 rounded bg-custom-background-90 text-custom-text-300 font-mono">
        {FIELD_TYPE_LABEL[field.field_type] ?? field.field_type}
      </span>
      <span className="font-medium text-sm">{field.name}</span>
      {field.is_required && <span className="text-xs text-red-500">必填</span>}
      {field.options?.length > 0 && <span className="text-xs text-custom-text-400">{field.options.length} 个选项</span>}
    </div>
    <div className="flex items-center gap-2">
      <button onClick={() => onEdit(field)} className="p-1 text-custom-text-300 hover:text-custom-text-100">
        <Pencil size={14} />
      </button>
      <button onClick={() => onDelete(field.id)} className="p-1 text-custom-text-300 hover:text-red-500">
        <Trash2 size={14} />
      </button>
    </div>
  </div>
);
```

**Step 3: Root 组件**

```tsx
// apps/web/core/components/workspace/settings/custom-fields/root.tsx
"use client";
import { useEffect, useState } from "react";
import { observer } from "mobx-react";
import { Plus } from "lucide-react";
import { Button } from "@plane/ui";
import { useStore } from "@/hooks/store";
import type { ICustomField } from "@plane/types";
import { CustomFieldItem } from "./field-item";
import { CustomFieldForm } from "./create-update-form";

export const WorkspaceCustomFieldsRoot = observer(({ workspaceSlug }: { workspaceSlug: string }) => {
  const { customField } = useStore();
  const [showCreate, setShowCreate] = useState(false);
  const [editingField, setEditingField] = useState<ICustomField | null>(null);

  useEffect(() => {
    customField.fetchWorkspaceFields(workspaceSlug);
  }, [workspaceSlug]);

  const fields = Object.values(customField.fieldMap);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">自定义字段</h3>
          <p className="text-sm text-custom-text-300">
            定义工作区的自定义字段，并在 Issue Types 中为每种类型配置所需字段。
          </p>
        </div>
        <Button onClick={() => setShowCreate(true)} size="sm">
          <Plus size={14} className="mr-1" /> 添加字段
        </Button>
      </div>

      <div className="space-y-2">
        {showCreate && (
          <CustomFieldForm
            onSubmit={async (data) => {
              await customField.createField(workspaceSlug, data);
              setShowCreate(false);
            }}
            onCancel={() => setShowCreate(false)}
          />
        )}
        {fields.map((field) =>
          editingField?.id === field.id ? (
            <CustomFieldForm
              key={field.id}
              data={field}
              onSubmit={async (data) => {
                await customField.updateField(workspaceSlug, field.id, data);
                setEditingField(null);
              }}
              onCancel={() => setEditingField(null)}
            />
          ) : (
            <CustomFieldItem
              key={field.id}
              field={field}
              onEdit={setEditingField}
              onDelete={(id) => customField.deleteField(workspaceSlug, id)}
            />
          )
        )}
        {fields.length === 0 && !showCreate && (
          <p className="text-sm text-custom-text-400 py-4 text-center">暂无自定义字段</p>
        )}
      </div>
    </div>
  );
});
```

**Step 4: 页面路由**

```tsx
// apps/web/app/(all)/[workspaceSlug]/(settings)/settings/custom-fields/page.tsx
import { WorkspaceCustomFieldsRoot } from "@/components/workspace/settings/custom-fields/root";

export default function CustomFieldsPage({ params }: { params: { workspaceSlug: string } }) {
  return (
    <div className="w-full overflow-y-auto py-8 px-9">
      <WorkspaceCustomFieldsRoot workspaceSlug={params.workspaceSlug} />
    </div>
  );
}
```

**Step 5: Commit**

```bash
git add apps/web/core/components/workspace/settings/custom-fields/ apps/web/app/(all)/[workspaceSlug]/(settings)/settings/custom-fields/
git commit -m "feat: add Workspace Settings - Custom Fields page"
```

---

## Phase 7：Issue Detail 自定义字段渲染

### Task 13：Issue Detail Sidebar 集成

**Files:**

- Create: `apps/web/core/components/issues/issue-detail/custom-fields-section.tsx`
- Modify: `apps/web/core/components/issues/issue-detail/sidebar.tsx`（或等效的 detail 组件）

**Step 1: 自定义字段渲染组件**

```tsx
// apps/web/core/components/issues/issue-detail/custom-fields-section.tsx
"use client";
import { useEffect } from "react";
import { observer } from "mobx-react";
import { useStore } from "@/hooks/store";
import type { ICustomField } from "@plane/types";

type FieldInputProps = {
  field: ICustomField;
  value: unknown;
  onChange: (value: unknown) => void;
  disabled?: boolean;
};

const FieldInput = ({ field, value, onChange, disabled }: FieldInputProps) => {
  if (field.field_type === "text") {
    return (
      <input
        className="w-full text-sm bg-transparent border-none outline-none text-custom-text-100 placeholder:text-custom-text-400"
        value={(value as string) ?? ""}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        placeholder="输入文本..."
      />
    );
  }
  if (field.field_type === "number") {
    return (
      <input
        type="number"
        className="w-full text-sm bg-transparent border-none outline-none text-custom-text-100"
        value={(value as number) ?? ""}
        onChange={(e) => onChange(e.target.valueAsNumber || null)}
        disabled={disabled}
      />
    );
  }
  if (field.field_type === "date") {
    return (
      <input
        type="date"
        className="text-sm bg-transparent border-none outline-none text-custom-text-100"
        value={(value as string) ?? ""}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
      />
    );
  }
  if (field.field_type === "option") {
    return (
      <select
        className="text-sm bg-custom-background-100 border border-custom-border-200 rounded px-2 py-1 text-custom-text-100"
        value={(value as string) ?? ""}
        onChange={(e) => onChange(e.target.value || null)}
        disabled={disabled}
      >
        <option value="">-- 选择 --</option>
        {field.options?.map((opt) => (
          <option key={opt.id} value={opt.id}>
            {opt.name}
          </option>
        ))}
      </select>
    );
  }
  return null;
};

type Props = {
  workspaceSlug: string;
  projectId: string;
  issueId: string;
  issueTypeId: string | null;
  disabled?: boolean;
};

export const IssueCustomFieldsSection = observer(
  ({ workspaceSlug, projectId, issueId, issueTypeId, disabled }: Props) => {
    const { customField } = useStore();

    useEffect(() => {
      if (issueId) {
        customField.fetchIssueFieldValues(workspaceSlug, projectId, issueId);
      }
    }, [issueId]);

    // 获取该 Issue Type 绑定的字段（目前简化：展示所有工作区字段）
    // TODO: Task 14 - 按 IssueType 过滤
    const fields = Object.values(customField.fieldMap);
    if (fields.length === 0) return null;

    return (
      <div className="space-y-3 pt-3 border-t border-custom-border-200">
        <h4 className="text-xs font-semibold text-custom-text-300 uppercase tracking-wider">自定义字段</h4>
        {fields.map((field) => {
          const valueObj = customField.valueMap[issueId]?.[field.id];
          return (
            <div key={field.id} className="flex items-start gap-3">
              <span className="text-sm text-custom-text-300 w-24 flex-shrink-0 pt-1">
                {field.name}
                {field.is_required && <span className="text-red-500 ml-0.5">*</span>}
              </span>
              <div className="flex-1">
                <FieldInput
                  field={field}
                  value={valueObj?.value ?? null}
                  disabled={disabled}
                  onChange={(val) => customField.setFieldValue(workspaceSlug, projectId, issueId, field.id, val)}
                />
              </div>
            </div>
          );
        })}
      </div>
    );
  }
);
```

**Step 2: 集成到 Issue Detail Sidebar**

找到 `apps/web/core/components/issues/issue-detail/sidebar.tsx`（或 `right-sidebar.tsx` / `detail-widget.tsx`），在属性列表末尾添加：

```tsx
import { IssueCustomFieldsSection } from "./custom-fields-section";

// 在 render 函数中，State/Labels/Assignees 等字段之后添加：
<IssueCustomFieldsSection
  workspaceSlug={workspaceSlug}
  projectId={issue.project_id}
  issueId={issue.id}
  issueTypeId={issue.type_id}
  disabled={!canEditProperties}
/>;
```

**Step 3: 验证**

浏览器打开任意 Issue：

1. Settings → Custom Fields 创建一个「严重等级」（option 类型）
2. 打开 Issue Detail
3. 确认右侧栏底部出现「自定义字段」区块
4. 选择选项后刷新，确认值已持久化

**Step 4: Commit**

```bash
git add apps/web/core/components/issues/issue-detail/custom-fields-section.tsx
git commit -m "feat: add IssueCustomFieldsSection to issue detail sidebar"
```

---

### Task 14：按 Issue Type 过滤字段（IssueTypeCustomField 绑定）

**Files:**

- Modify: `apps/web/core/store/custom-field.store.ts`（添加 issueTypeFieldMap）
- Modify: `apps/web/core/components/issues/issue-detail/custom-fields-section.tsx`（改为按 type 过滤）
- Create: `apps/web/core/components/workspace/settings/issue-types/field-binding.tsx`（字段绑定 UI）

**Step 1: Store 添加 issueTypeFieldMap**

在 `CustomFieldStore` 中添加：

```typescript
// issueTypeId → IIssueTypeCustomField[]
issueTypeFieldMap: Record<string, IIssueTypeCustomField[]> = {};

fetchIssueTypeFields = async (workspaceSlug: string, issueTypeId: string) => {
  const bindings = await customFieldService.listIssueTypeFields(workspaceSlug, issueTypeId);
  runInAction(() => set(this.issueTypeFieldMap, issueTypeId, bindings));
  return bindings;
};

addFieldToIssueType = async (workspaceSlug: string, issueTypeId: string, fieldId: string) => {
  const binding = await customFieldService.addFieldToIssueType(workspaceSlug, issueTypeId, { field: fieldId });
  runInAction(() => {
    const existing = this.issueTypeFieldMap[issueTypeId] ?? [];
    set(this.issueTypeFieldMap, issueTypeId, [...existing, binding]);
  });
};

removeFieldFromIssueType = async (workspaceSlug: string, issueTypeId: string, bindingId: string) => {
  await customFieldService.removeFieldFromIssueType(workspaceSlug, issueTypeId, bindingId);
  runInAction(() => {
    const existing = this.issueTypeFieldMap[issueTypeId] ?? [];
    set(
      this.issueTypeFieldMap,
      issueTypeId,
      existing.filter((b) => b.id !== bindingId)
    );
  });
};
```

**Step 2: IssueCustomFieldsSection 改为按 IssueType 过滤**

```tsx
// 替换 "获取该 Issue Type 绑定的字段" 部分
useEffect(() => {
  if (issueTypeId) {
    customField.fetchIssueTypeFields(workspaceSlug, issueTypeId);
  }
}, [issueTypeId]);

const bindings = issueTypeId ? (customField.issueTypeFieldMap[issueTypeId] ?? []) : [];
const fields = bindings.map((b) => ({ ...customField.fieldMap[b.field], is_required: b.is_required })).filter(Boolean);
```

**Step 3: Issue Types Settings 页面添加字段绑定 UI**

在 `IssueTypeItem` 上添加"管理字段"入口，点击后展开字段绑定面板（参考 Labels 页面的层级交互模式）。

**Step 4: Commit**

```bash
git commit -am "feat: filter custom fields by issue type binding"
```

---

## 验收标准

完成所有 Task 后，以下场景应可正常工作：

| 场景                                                                          | 预期结果                                 |
| ----------------------------------------------------------------------------- | ---------------------------------------- |
| 工作区设置 → Issue Types → 创建「Bug」                                        | Issue Type 列表显示「Bug」               |
| 工作区设置 → Custom Fields → 创建「严重等级」（option）+ 添加选项「高/中/低」 | 字段列表显示「严重等级」，3 个选项       |
| Issue Types → Bug → 绑定「严重等级」字段                                      | Bug 类型绑定成功                         |
| 创建 Issue 时选择 type=Bug，打开 Issue Detail                                 | 右侧栏底部显示「严重等级」下拉           |
| 选择「高」后刷新页面                                                          | 「严重等级」仍显示「高」（已持久化）     |
| 创建 type=Story 的 Issue，打开 Detail                                         | 不显示「严重等级」（Story 未绑定该字段） |

---

## 后续迭代（Phase 2）

| 功能                        | 优先级 | 说明                           |
| --------------------------- | ------ | ------------------------------ |
| P1 字段类型：user、datetime | P1     | 测试人、时间类字段             |
| 单选选项的颜色标签渲染      | P1     | Issue 列表里展示彩色 Tag       |
| 自定义字段筛选/分组         | P2     | Issue 列表按字段值过滤         |
| 字段必填验证                | P2     | Issue 提交时检查必填字段       |
| 字段排序拖拽                | P2     | 调整 Issue Detail 中的字段顺序 |
| 批量编辑自定义字段          | P3     | 多选 Issue 批量设值            |
