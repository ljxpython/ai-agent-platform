"use client";

import { ThemeToggle } from "@/components/platform/theme-toggle";
import { useWorkspaceContext } from "@/providers/WorkspaceProvider";

export function TopContextBar() {
  const {
    currentProject,
    currentRoleLabel,
    currentUser,
    loading,
    projectId,
    projects,
    setProjectId,
  } = useWorkspaceContext();

  return (
    <header className="workspace-shell__topbar">
      <div className="workspace-shell__context">
        <span className="workspace-shell__chip">Workspace</span>
        <span className="workspace-shell__chip">
          {loading
            ? "User: loading..."
            : `User: ${currentUser?.username || "unknown"}`}
        </span>
        <span className="workspace-shell__chip">
          {loading
            ? "Project: loading..."
            : `Project: ${currentProject?.name || "未选择项目"}`}
        </span>
        <span className="workspace-shell__chip">
          {loading ? "Role: loading..." : `Role: ${currentRoleLabel}`}
        </span>
      </div>

      <div className="workspace-shell__topbar-actions">
        <label className="workspace-shell__select-field">
          <span className="workspace-shell__select-label">Project</span>
          <select
            className="workspace-shell__topbar-select"
            value={projectId}
            onChange={(event) => setProjectId(event.target.value)}
            disabled={loading || projects.length === 0}
          >
            {projects.length === 0 ? (
              <option value="">No project</option>
            ) : null}
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </label>
        <ThemeToggle />
      </div>
    </header>
  );
}
