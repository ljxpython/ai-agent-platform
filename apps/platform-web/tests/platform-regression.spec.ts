import { expect, test, type Page, type Route } from "@playwright/test";

type Project = {
  id: string;
  name: string;
  description: string;
  status: string;
};

type Assistant = {
  id: string;
  project_id: string;
  name: string;
  description: string;
  graph_id: string;
  langgraph_assistant_id: string;
  runtime_base_url: string;
  sync_status: string;
  status: "active" | "disabled";
  config: Record<string, unknown>;
  context: Record<string, unknown>;
  metadata: Record<string, unknown>;
};

function authSeed() {
  return {
    access_token: "test-access-token",
    refresh_token: "test-refresh-token",
    expires_at: Math.floor(Date.now() / 1000) + 3600,
  };
}

async function seedAuth(page: Page) {
  await page.addInitScript((tokenSet) => {
    window.localStorage.setItem("oidc:token_set", JSON.stringify(tokenSet));
    window.localStorage.setItem("lg:platform:apiUrl", "http://127.0.0.1:3010");
    window.localStorage.setItem("lg:chat:apiUrl", "http://127.0.0.1:3010");
  }, authSeed());
}

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

test.beforeEach(async ({ page }) => {
  await seedAuth(page);

  const projects: Project[] = [
    {
      id: "project-1",
      name: "Project One",
      description: "Primary workspace project",
      status: "active",
    },
    {
      id: "project-2",
      name: "Project Two",
      description: "Secondary workspace project",
      status: "active",
    },
  ];

  const assistants: Assistant[] = [
    {
      id: "assistant-1",
      project_id: "project-1",
      name: "Support Assistant",
      description: "Support workflows",
      graph_id: "assistant",
      langgraph_assistant_id: "runtime-assistant-1",
      runtime_base_url: "http://127.0.0.1:8123",
      sync_status: "ready",
      status: "active",
      config: {},
      context: {},
      metadata: {},
    },
  ];

  await page.route("**/_management/projects?*", async (route) => {
    await fulfillJson(route, { items: projects, total: projects.length });
  });

  await page.route("**/_management/projects/*", async (route) => {
    if (route.request().method() === "DELETE") {
      const projectId = route.request().url().split("/").pop() ?? "";
      const index = projects.findIndex((item) => item.id === projectId);
      if (index >= 0) {
        projects.splice(index, 1);
      }
      await fulfillJson(route, { ok: true });
      return;
    }
    await route.fallback();
  });

  await page.route("**/_management/projects/project-1/assistants?*", async (route) => {
    await fulfillJson(route, { items: assistants, total: assistants.length });
  });

  await page.route("**/_management/assistants/assistant-1/resync", async (route) => {
    assistants[0] = {
      ...assistants[0],
      sync_status: "ready",
      description: "Support workflows (resynced)",
    };
    await fulfillJson(route, assistants[0]);
  });

  await page.route("**/_management/assistants/assistant-1?delete_runtime=true", async (route) => {
    assistants.splice(0, 1);
    await fulfillJson(route, { ok: true });
  });

  await page.route("**/_management/runtime/models", async (route) => {
    await fulfillJson(route, {
      count: 2,
      last_synced_at: "2026-03-13T10:00:00Z",
      models: [
        {
          id: "model-row-1",
          runtime_id: "runtime-local",
          model_id: "openai:gpt-4.1",
          display_name: "GPT-4.1",
          is_default: true,
          sync_status: "ready",
          last_seen_at: "2026-03-13T10:00:00Z",
          last_synced_at: "2026-03-13T10:00:00Z",
        },
        {
          id: "model-row-2",
          runtime_id: "runtime-local",
          model_id: "anthropic:claude-3-7-sonnet",
          display_name: "Claude 3.7 Sonnet",
          is_default: false,
          sync_status: "ready",
          last_seen_at: "2026-03-13T10:00:00Z",
          last_synced_at: "2026-03-13T10:00:00Z",
        },
      ],
    });
  });

  await page.route("**/_management/catalog/models/refresh", async (route) => {
    await fulfillJson(route, {
      ok: true,
      count: 2,
      last_synced_at: "2026-03-13T10:05:00Z",
    });
  });

  await page.route("**/_management/runtime/tools", async (route) => {
    await fulfillJson(route, {
      count: 2,
      last_synced_at: "2026-03-13T10:00:00Z",
      tools: [
        {
          id: "tool-row-1",
          runtime_id: "runtime-local",
          tool_key: "search",
          name: "search",
          source: "builtin",
          description: "General web search",
          sync_status: "ready",
          last_seen_at: "2026-03-13T10:00:00Z",
          last_synced_at: "2026-03-13T10:00:00Z",
        },
        {
          id: "tool-row-2",
          runtime_id: "runtime-local",
          tool_key: "mcp:chart",
          name: "mcp:chart",
          source: "mcp",
          description: "Chart renderer",
          sync_status: "ready",
          last_seen_at: "2026-03-13T10:00:00Z",
          last_synced_at: "2026-03-13T10:00:00Z",
        },
      ],
    });
  });

  await page.route("**/_management/catalog/tools/refresh", async (route) => {
    await fulfillJson(route, {
      ok: true,
      count: 2,
      last_synced_at: "2026-03-13T10:05:00Z",
    });
  });

  await page.route("**/_management/audit?*", async (route) => {
    await fulfillJson(route, {
      items: [
        {
          id: "audit-1",
          request_id: "req-1",
          action: "assistant.resync",
          target_type: "assistant",
          target_id: "assistant-1",
          method: "POST",
          path: "/_management/assistants/assistant-1/resync",
          status_code: 200,
          created_at: "2026-03-13T10:00:00Z",
          user_id: "user-1",
        },
      ],
      total: 1,
    });
  });
});

test("root redirect sends authenticated users into workspace", async ({ page }) => {
  await page.goto("/");
  await page.waitForURL("**/workspace/projects");
  await expect(page.getByRole("link", { name: "Projects" })).toBeVisible();
  await expect(page.getByText("Project One")).toBeVisible();
});

test("workspace routes redirect unauthenticated users to login", async ({ page, context }) => {
  await context.clearCookies();
  await page.addInitScript(() => {
    window.localStorage.clear();
  });
  await page.goto("/workspace/projects");
  await page.waitForURL("**/auth/login?*");
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
});

test("projects page renders current project list and delete flow", async ({ page }) => {
  await page.goto("/workspace/projects?projectId=project-1");

  await expect(page.getByRole("heading", { name: "Projects" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "Project One" })).toBeVisible();

  await page.getByRole("button", { name: "Delete" }).first().click();
  await page.getByRole("button", { name: "Delete" }).last().click();

  await expect(page.getByRole("cell", { name: "Project One" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Projects" })).toBeVisible();
});

test("assistants page renders list and resync flow", async ({ page }) => {
  await page.goto("/workspace/assistants?projectId=project-1");

  await expect(page.getByRole("heading", { name: "Assistants" })).toBeVisible();
  await expect(page.getByText("Support Assistant")).toBeVisible();

  await page.getByRole("button", { name: "Resync" }).click();

  await expect(page.getByText("Assistant resynced: Support Assistant")).toBeVisible();
});

test("runtime models page renders catalog and refresh action", async ({ page }) => {
  await page.goto("/workspace/runtime/models?projectId=project-1");

  await expect(page.getByRole("heading", { name: "Models" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "GPT-4.1", exact: true })).toBeVisible();
  await expect(page.getByRole("cell", { name: "Claude 3.7 Sonnet", exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Refresh" }).click();
  await expect(page.getByText(/Last synced:/)).toBeVisible();
});

test("runtime tools page renders searchable tool catalog", async ({ page }) => {
  await page.goto("/workspace/runtime/tools?projectId=project-1");

  await expect(page.getByRole("heading", { name: "Tools" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "search", exact: true })).toBeVisible();
  await expect(page.getByText("Chart renderer")).toBeVisible();
});

test("audit page renders project-scoped audit rows", async ({ page }) => {
  await page.goto("/workspace/audit?projectId=project-1");

  await expect(page.getByRole("heading", { name: "Audit" })).toBeVisible();
  await expect(page.getByText("assistant.resync")).toBeVisible();
  await expect(page.getByText("/_management/assistants/assistant-1/resync")).toBeVisible();
});
