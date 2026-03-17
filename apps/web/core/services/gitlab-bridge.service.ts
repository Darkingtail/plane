/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

const BRIDGE_BASE_URL =
  (typeof process !== "undefined" ? process.env.VITE_GITLAB_BRIDGE_URL : "") || "http://localhost:8080";

export type GitLabSettingsResponse = {
  gitlab_url: string;
  token_set: boolean;
  token_preview: string;
  enabled_repos: string[];
};

export type GitLabRepo = {
  id: number;
  name: string;
  path: string;
  ssh_url: string;
  http_url: string;
  enabled: boolean;
};

export type GitLabReposResponse = {
  api_version: string;
  namespaces: Record<string, GitLabRepo[]>;
};

export type GitLabTestResponse = {
  success: boolean;
  username?: string;
  name?: string;
  api_version?: string;
  error?: string;
};

class GitLabBridgeService {
  private baseUrl: string;

  constructor() {
    this.baseUrl = BRIDGE_BASE_URL;
  }

  async getSettings(): Promise<GitLabSettingsResponse> {
    const res = await fetch(`${this.baseUrl}/api/v1/settings/gitlab`);
    if (!res.ok) throw new Error("Failed to fetch GitLab settings");
    return res.json();
  }

  async saveSettings(data: {
    gitlab_url: string;
    token?: string;
    enabled_repos: string[];
  }): Promise<GitLabSettingsResponse> {
    const res = await fetch(`${this.baseUrl}/api/v1/settings/gitlab`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error("Failed to save GitLab settings");
    return res.json();
  }

  async testConnection(gitlab_url: string, token: string): Promise<GitLabTestResponse> {
    const res = await fetch(`${this.baseUrl}/api/v1/settings/gitlab/test`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ gitlab_url, token }),
    });
    return res.json();
  }

  async getRepos(): Promise<GitLabReposResponse> {
    const res = await fetch(`${this.baseUrl}/api/v1/settings/gitlab/repos`);
    if (!res.ok) throw new Error("Failed to fetch GitLab repos");
    return res.json();
  }
}

export const gitLabBridgeService = new GitLabBridgeService();
