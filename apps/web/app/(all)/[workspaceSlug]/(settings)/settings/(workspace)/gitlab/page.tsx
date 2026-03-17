/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { observer } from "mobx-react";
import { ChevronDown, ChevronRight, Eye, EyeOff, RefreshCw } from "lucide-react";
// plane imports
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
// components
import { NotAuthorizedView } from "@/components/auth-screens/not-authorized-view";
import { PageHead } from "@/components/core/page-title";
import { SettingsHeading } from "@/components/settings/heading";
import { SettingsContentWrapper } from "@/components/settings/content-wrapper";
// hooks
import { useWorkspace } from "@/hooks/store/use-workspace";
import { useUserPermissions } from "@/hooks/store/user";
// services
import {
  gitLabBridgeService,
  type GitLabSettingsResponse,
  type GitLabRepo,
  type GitLabTestResponse,
} from "@/services/gitlab-bridge.service";
// local imports
import type { Route } from "./+types/page";
import { GitLabWorkspaceSettingsHeader } from "./header";

type ConnectionStatus = "idle" | "testing" | "success" | "error";

type ReposState = {
  loading: boolean;
  namespaces: Record<string, GitLabRepo[]>;
  error: string | null;
};

const GitLabSettingsPage = observer(function GitLabSettingsPage({ params: _params }: Route.ComponentProps) {
  const { workspaceSlug: _workspaceSlug } = _params;

  // store hooks
  const { workspaceUserInfo, allowPermissions } = useUserPermissions();
  const { currentWorkspace } = useWorkspace();

  // permission check
  const canPerformWorkspaceAdminActions = allowPermissions([EUserPermissions.ADMIN], EUserPermissionsLevel.WORKSPACE);

  // connection config state
  const [gitlabUrl, setGitlabUrl] = useState("");
  const [token, setToken] = useState("");
  const [showToken, setShowToken] = useState(false);
  const [tokenSet, setTokenSet] = useState(false);
  const [tokenPreview, setTokenPreview] = useState("");

  // connection test state
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>("idle");
  const [connectionResult, setConnectionResult] = useState<GitLabTestResponse | null>(null);

  // repos state
  const [repos, setRepos] = useState<ReposState>({ loading: false, namespaces: {}, error: null });
  const [enabledRepos, setEnabledRepos] = useState<Set<string>>(new Set());
  const [collapsedNamespaces, setCollapsedNamespaces] = useState<Set<string>>(new Set());

  // save state
  const [saving, setSaving] = useState(false);
  const [settingsLoading, setSettingsLoading] = useState(true);

  const pageTitle = currentWorkspace?.name ? `${currentWorkspace.name} - GitLab 集成` : undefined;

  // load existing settings on mount
  useEffect(() => {
    if (!canPerformWorkspaceAdminActions) return;

    setSettingsLoading(true);
    gitLabBridgeService
      .getSettings()
      .then((data: GitLabSettingsResponse) => {
        setGitlabUrl(data.gitlab_url || "");
        setTokenSet(data.token_set || false);
        setTokenPreview(data.token_preview || "");
        setEnabledRepos(new Set(data.enabled_repos || []));
        return undefined;
      })
      .catch(() => {
        // bridge may not be running yet, that's OK
      })
      .finally(() => {
        setSettingsLoading(false);
      });
  }, [canPerformWorkspaceAdminActions]);

  // load repos when token is set
  useEffect(() => {
    if (tokenSet && canPerformWorkspaceAdminActions) {
      handleRefreshRepos();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tokenSet]);

  const handleTestConnection = async () => {
    if (!gitlabUrl || !token) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "错误",
        message: "请填写 GitLab 地址和访问令牌",
      });
      return;
    }

    setConnectionStatus("testing");
    setConnectionResult(null);

    try {
      const result = await gitLabBridgeService.testConnection(gitlabUrl, token);
      setConnectionResult(result);
      if (result.success) {
        setConnectionStatus("success");
        setToast({
          type: TOAST_TYPE.SUCCESS,
          title: "连接成功",
          message: `已连接到 GitLab（用户：${result.username}）`,
        });
      } else {
        setConnectionStatus("error");
        setToast({
          type: TOAST_TYPE.ERROR,
          title: "连接失败",
          message: result.error || "无法连接到 GitLab",
        });
      }
    } catch {
      setConnectionStatus("error");
      setConnectionResult({ success: false, error: "无法连接到 bridge 服务，请确保其正在运行" });
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "连接失败",
        message: "无法连接到 bridge 服务，请确保其正在运行",
      });
    }
  };

  const handleRefreshRepos = async () => {
    setRepos({ loading: true, namespaces: {}, error: null });
    try {
      const data = await gitLabBridgeService.getRepos();
      setRepos({ loading: false, namespaces: data.namespaces || {}, error: null });
    } catch {
      setRepos({ loading: false, namespaces: {}, error: "获取仓库列表失败，请检查 Token 是否有效" });
    }
  };

  const handleToggleRepo = (repoPath: string) => {
    setEnabledRepos((prev) => {
      const next = new Set(prev);
      if (next.has(repoPath)) {
        next.delete(repoPath);
      } else {
        next.add(repoPath);
      }
      return next;
    });
  };

  const handleToggleNamespace = (namespace: string) => {
    setCollapsedNamespaces((prev) => {
      const next = new Set(prev);
      if (next.has(namespace)) {
        next.delete(namespace);
      } else {
        next.add(namespace);
      }
      return next;
    });
  };

  const handleSave = async () => {
    if (!gitlabUrl) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "错误",
        message: "请填写 GitLab 地址",
      });
      return;
    }

    setSaving(true);
    try {
      const payload: { gitlab_url: string; token?: string; enabled_repos: string[] } = {
        gitlab_url: gitlabUrl,
        enabled_repos: Array.from(enabledRepos),
      };
      if (token) {
        payload.token = token;
      }

      const result = await gitLabBridgeService.saveSettings(payload);
      setTokenSet(result.token_set);
      setTokenPreview(result.token_preview || "");
      setToken("");

      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "保存成功",
        message: "GitLab 集成配置已保存",
      });
    } catch {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "保存失败",
        message: "保存配置失败，请稍后重试",
      });
    } finally {
      setSaving(false);
    }
  };

  // not authorized
  if (workspaceUserInfo && !canPerformWorkspaceAdminActions) {
    return <NotAuthorizedView section="settings" className="h-auto" />;
  }

  const hasRepos = Object.keys(repos.namespaces).length > 0;

  return (
    <SettingsContentWrapper header={<GitLabWorkspaceSettingsHeader />}>
      <PageHead title={pageTitle} />

      <div className="w-full space-y-8">
        {/* Section 1: Connection */}
        <div>
          <SettingsHeading title="GitLab 连接配置" description="配置 GitLab 实例地址和访问令牌，用于同步仓库信息" />

          <div className="mt-6 space-y-5">
            {/* GitLab URL */}
            <div className="flex flex-col gap-1.5">
              <label htmlFor="gitlab-url" className="text-body-sm-medium text-primary">
                GitLab 地址
              </label>
              <input
                id="gitlab-url"
                type="text"
                value={gitlabUrl}
                onChange={(e) => setGitlabUrl(e.target.value)}
                placeholder="https://gitlab.example.com"
                disabled={settingsLoading}
                className="focus:border-accent-primary w-full max-w-lg rounded-md border border-subtle bg-surface-1 px-3 py-2 text-body-sm-regular text-primary transition-colors outline-none placeholder:text-placeholder disabled:opacity-60"
              />
              <p className="text-body-xs-regular text-tertiary">
                GitLab 实例的完整 URL，例如 https://gitlab.com 或私有部署地址
              </p>
            </div>

            {/* Access Token */}
            <div className="flex flex-col gap-1.5">
              <label htmlFor="gitlab-token" className="text-body-sm-medium text-primary">
                访问令牌（Access Token）
              </label>
              <div className="relative w-full max-w-lg">
                <input
                  id="gitlab-token"
                  type={showToken ? "text" : "password"}
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  placeholder={tokenSet ? `当前令牌：${tokenPreview}（留空则保持不变）` : "glpat-xxxxxxxxxxxxxxxxxxxx"}
                  disabled={settingsLoading}
                  className="focus:border-accent-primary w-full rounded-md border border-subtle bg-surface-1 px-3 py-2 pr-10 text-body-sm-regular text-primary transition-colors outline-none placeholder:text-placeholder disabled:opacity-60"
                />
                <button
                  type="button"
                  onClick={() => setShowToken((v) => !v)}
                  className="absolute top-1/2 right-3 -translate-y-1/2 text-tertiary transition-colors hover:text-primary"
                  tabIndex={-1}
                >
                  {showToken ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </div>
              <p className="text-body-xs-regular text-tertiary">
                GitLab Personal Access Token，需要 api 权限。
                {tokenSet && <span className="text-green-600 dark:text-green-400 ml-1">当前已配置令牌。</span>}
              </p>
            </div>

            {/* Test Connection */}
            <div className="flex items-center gap-3">
              <Button
                variant="neutral-primary"
                size="md"
                onClick={handleTestConnection}
                loading={connectionStatus === "testing"}
                disabled={settingsLoading || connectionStatus === "testing"}
              >
                测试连接
              </Button>

              {/* Connection status indicator */}
              {connectionStatus === "success" && connectionResult?.success && (
                <div className="flex items-center gap-2">
                  <span className="bg-green-500 size-2 shrink-0 rounded-full" />
                  <span className="text-green-600 dark:text-green-400 text-body-sm-regular">
                    连接成功 · 用户：{connectionResult.username}
                    {connectionResult.name && ` (${connectionResult.name})`}
                  </span>
                </div>
              )}
              {connectionStatus === "error" && (
                <div className="flex items-center gap-2">
                  <span className="bg-red-500 size-2 shrink-0 rounded-full" />
                  <span className="text-red-600 dark:text-red-400 text-body-sm-regular">
                    {connectionResult?.error || "连接失败"}
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Section 2: Repos (only shown when token_set) */}
        {tokenSet && (
          <div>
            <SettingsHeading
              title="可用仓库"
              description="勾选的仓库可在 Work Item 中被关联"
              control={
                <Button variant="neutral-primary" size="md" onClick={handleRefreshRepos} disabled={repos.loading}>
                  <RefreshCw className={`mr-1.5 size-3.5 ${repos.loading ? "animate-spin" : ""}`} />
                  刷新列表
                </Button>
              }
            />

            <div className="mt-4">
              {repos.loading && (
                <div className="flex items-center gap-3 py-8 text-tertiary">
                  <RefreshCw className="size-4 animate-spin" />
                  <span className="text-body-sm-regular">正在加载仓库列表...</span>
                </div>
              )}

              {repos.error && !repos.loading && (
                <div className="border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950/20 rounded-md border px-4 py-3">
                  <p className="text-red-600 dark:text-red-400 text-body-sm-regular">{repos.error}</p>
                </div>
              )}

              {!repos.loading && !repos.error && !hasRepos && (
                <div className="py-8 text-center">
                  <p className="text-body-sm-regular text-tertiary">暂无可用仓库，请点击「刷新列表」重试</p>
                </div>
              )}

              {!repos.loading && hasRepos && (
                <div className="space-y-2">
                  {Object.entries(repos.namespaces).map(([namespace, repoList]) => {
                    const isCollapsed = collapsedNamespaces.has(namespace);
                    const enabledCount = repoList.filter((r) => enabledRepos.has(r.path)).length;

                    return (
                      <div key={namespace} className="overflow-hidden rounded-md border border-subtle">
                        {/* Namespace Header */}
                        <button
                          type="button"
                          onClick={() => handleToggleNamespace(namespace)}
                          className="flex w-full items-center justify-between bg-surface-2 px-4 py-3 text-left transition-colors hover:bg-surface-1"
                        >
                          <div className="flex items-center gap-2">
                            {isCollapsed ? (
                              <ChevronRight className="size-4 shrink-0 text-tertiary" />
                            ) : (
                              <ChevronDown className="size-4 shrink-0 text-tertiary" />
                            )}
                            <span className="text-body-sm-medium text-primary">{namespace}</span>
                          </div>
                          <span className="shrink-0 text-body-xs-regular text-tertiary">
                            {enabledCount}/{repoList.length} 已启用
                          </span>
                        </button>

                        {/* Repo List */}
                        {!isCollapsed && (
                          <div className="divide-y divide-subtle">
                            {repoList.map((repo) => {
                              const isEnabled = enabledRepos.has(repo.path);
                              return (
                                <label
                                  key={repo.id}
                                  aria-label={repo.name}
                                  className="flex cursor-pointer items-center gap-3 px-4 py-2.5 transition-colors hover:bg-surface-2/50"
                                >
                                  <input
                                    type="checkbox"
                                    checked={isEnabled}
                                    onChange={() => handleToggleRepo(repo.path)}
                                    className="accent-accent-primary size-4 shrink-0 cursor-pointer rounded border-subtle"
                                  />
                                  <div className="flex min-w-0 flex-col">
                                    <span className="truncate text-body-sm-medium text-primary">{repo.name}</span>
                                    <span className="truncate text-body-xs-regular text-tertiary">{repo.path}</span>
                                  </div>
                                </label>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Save Button */}
        <div className="flex items-center gap-3 border-t border-subtle pt-2">
          <Button
            variant="primary"
            size="lg"
            onClick={handleSave}
            loading={saving}
            disabled={settingsLoading || saving}
          >
            保存配置
          </Button>
          <p className="text-body-xs-regular text-tertiary">保存后生效，Token 将加密存储</p>
        </div>
      </div>
    </SettingsContentWrapper>
  );
});

export default GitLabSettingsPage;
