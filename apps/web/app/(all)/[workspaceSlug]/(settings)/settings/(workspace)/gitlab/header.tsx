/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// plane imports
import { Breadcrumbs } from "@plane/ui";
// components
import { BreadcrumbLink } from "@/components/common/breadcrumb-link";
import { SettingsPageHeader } from "@/components/settings/page-header";
import { WORKSPACE_SETTINGS_ICONS } from "@/components/settings/workspace/sidebar/item-icon";

export const GitLabWorkspaceSettingsHeader = observer(function GitLabWorkspaceSettingsHeader() {
  // derived values
  const Icon = WORKSPACE_SETTINGS_ICONS.gitlab;

  return (
    <SettingsPageHeader
      leftItem={
        <div className="flex items-center gap-2">
          <Breadcrumbs>
            <Breadcrumbs.Item
              component={<BreadcrumbLink label="GitLab 集成" icon={<Icon className="size-4 text-tertiary" />} />}
            />
          </Breadcrumbs>
        </div>
      }
    />
  );
});
