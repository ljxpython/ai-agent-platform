"use client";

import { ChevronDown } from "lucide-react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import type { ReactNode } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import { AuthControls } from "./auth-controls";


const HEADER_COLLAPSED_STORAGE_KEY = "ui:workspaceHeaderCollapsed";
const HEADER_TOGGLE_POSITION_STORAGE_KEY = "ui:workspaceHeaderTogglePosition";


type TogglePosition = {
  x: number;
  y: number;
};

type NavChildItem = {
  href: string;
  label: string;
  description?: string;
};

type NavItem = {
  href: string;
  label: string;
  children?: NavChildItem[];
};

const NAV_ITEMS: NavItem[] = [
  { href: "/workspace/chat", label: "Chat" },
  { href: "/workspace/threads", label: "Threads" },
  { href: "/workspace/graphs", label: "Graphs" },
  { href: "/workspace/assistants", label: "Assistants" },
  { href: "/workspace/runtime", label: "Runtime" },
  {
    href: "/workspace/testcase",
    label: "Testcase",
    children: [
      {
        href: "/workspace/testcase/generate",
        label: "AI 对话生成",
        description: "固定连接到 test_case_agent 的生成会话。",
      },
      {
        href: "/workspace/testcase/cases",
        label: "用例管理",
        description: "查看和管理正式保存的测试用例。",
      },
      {
        href: "/workspace/testcase/documents",
        label: "PDF 解析",
        description: "查看已保存文档的解析结果。",
      },
    ],
  },
  { href: "/workspace/projects", label: "Projects" },
  { href: "/workspace/users", label: "Users" },
  { href: "/workspace/sql-agent", label: "SQL Agent" },
  { href: "/workspace/me", label: "My Profile" },
  { href: "/workspace/security", label: "Security" },
  { href: "/workspace/audit", label: "Audit" },
];

export function WorkspaceShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const query = searchParams.toString();
  const [headerCollapsed, setHeaderCollapsed] = useState(false);
  const [desktopMode, setDesktopMode] = useState(true);
  const [togglePosition, setTogglePosition] = useState<TogglePosition | null>(null);
  const [dragging, setDragging] = useState(false);
  const [openMenuHref, setOpenMenuHref] = useState<string | null>(null);
  const dragRef = useRef<{ offsetX: number; offsetY: number; moved: boolean } | null>(null);
  const ignoreClickRef = useRef(false);
  const navRef = useRef<HTMLElement | null>(null);

  const clampPosition = useCallback((position: TogglePosition): TogglePosition => {
    if (typeof window === "undefined") {
      return position;
    }
    const buttonSize = 36;
    const margin = 8;
    return {
      x: Math.max(margin, Math.min(position.x, window.innerWidth - buttonSize - margin)),
      y: Math.max(margin, Math.min(position.y, window.innerHeight - buttonSize - margin)),
    };
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const media = window.matchMedia("(min-width: 768px)");
    const applyDesktopMode = () => {
      const isDesktop = media.matches;
      setDesktopMode(isDesktop);
      if (!isDesktop) {
        setHeaderCollapsed(false);
      }
    };

    applyDesktopMode();
    media.addEventListener("change", applyDesktopMode);
    return () => {
      media.removeEventListener("change", applyDesktopMode);
    };
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const raw = window.localStorage.getItem(HEADER_COLLAPSED_STORAGE_KEY);
    setHeaderCollapsed(raw === "true");

    const rawPosition = window.localStorage.getItem(HEADER_TOGGLE_POSITION_STORAGE_KEY);
    if (rawPosition) {
      try {
        const parsed = JSON.parse(rawPosition) as TogglePosition;
        if (typeof parsed?.x === "number" && typeof parsed?.y === "number") {
          setTogglePosition(clampPosition(parsed));
          return;
        }
      } catch {
        window.localStorage.removeItem(HEADER_TOGGLE_POSITION_STORAGE_KEY);
      }
    }

    setTogglePosition(clampPosition({ x: window.innerWidth - 56, y: 84 }));
  }, [clampPosition]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    window.localStorage.setItem(HEADER_COLLAPSED_STORAGE_KEY, String(headerCollapsed));
  }, [headerCollapsed]);

  useEffect(() => {
    if (typeof window === "undefined" || !togglePosition) {
      return;
    }
    window.localStorage.setItem(HEADER_TOGGLE_POSITION_STORAGE_KEY, JSON.stringify(togglePosition));
  }, [togglePosition]);

  useEffect(() => {
    if (!dragging) {
      return;
    }

    const onPointerMove = (event: PointerEvent) => {
      const dragMeta = dragRef.current;
      if (!dragMeta) {
        return;
      }
      const next = clampPosition({
        x: event.clientX - dragMeta.offsetX,
        y: event.clientY - dragMeta.offsetY,
      });
      if (Math.abs(next.x - (togglePosition?.x ?? next.x)) > 2 || Math.abs(next.y - (togglePosition?.y ?? next.y)) > 2) {
        dragMeta.moved = true;
      }
      setTogglePosition(next);
    };

    const onPointerUp = () => {
      if (dragRef.current?.moved) {
        ignoreClickRef.current = true;
      }
      dragRef.current = null;
      setDragging(false);
    };

    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);

    return () => {
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
    };
  }, [clampPosition, dragging, togglePosition]);

  useEffect(() => {
    setOpenMenuHref(null);
  }, [pathname, query]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const handlePointerDown = (event: MouseEvent) => {
      if (!navRef.current) {
        return;
      }
      if (!navRef.current.contains(event.target as Node)) {
        setOpenMenuHref(null);
      }
    };
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpenMenuHref(null);
      }
    };
    window.addEventListener("mousedown", handlePointerDown);
    window.addEventListener("keydown", handleEscape);
    return () => {
      window.removeEventListener("mousedown", handlePointerDown);
      window.removeEventListener("keydown", handleEscape);
    };
  }, []);

  const canCollapseHeader = desktopMode;
  const collapsed = canCollapseHeader && headerCollapsed;

  const buildHref = useCallback(
    (href: string) => (query ? `${href}?${query}` : href),
    [query],
  );

  const isNavItemActive = useCallback(
    (item: NavItem) => {
      if (item.children && item.children.length > 0) {
        return item.children.some((child) => pathname?.startsWith(child.href));
      }
      return pathname?.startsWith(item.href);
    },
    [pathname],
  );

  return (
    <div className="bg-background text-foreground flex min-h-dvh flex-col">
      {!collapsed ? (
        <header id="workspace-header" className="bg-background/95 sticky top-0 z-20 border-b border-border/80 px-4 py-3 backdrop-blur supports-[backdrop-filter]:bg-background/80 sm:px-6">
          <div className="mx-auto flex max-w-[1400px] flex-col gap-3">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div className="min-w-0">
                <h1 className="text-base font-semibold tracking-tight sm:text-lg">Agent Platform</h1>
                <p className="text-muted-foreground text-xs sm:text-sm">Workspace scope: project</p>
              </div>
              <div className="flex flex-wrap items-center gap-2 sm:gap-3">
                <AuthControls />
              </div>
            </div>

            <nav
              ref={navRef}
              data-testid="workspace-nav"
              aria-label="Workspace sections"
              className="flex flex-wrap items-center gap-2"
            >
              {NAV_ITEMS.map((item) => {
                const active = isNavItemActive(item);
                const sharedClassName = [
                  "inline-flex items-center rounded-md border px-3 py-1.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
                  active
                    ? "border-sidebar-primary/60 bg-sidebar-primary text-sidebar-primary-foreground shadow-sm"
                    : "border-border bg-card text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                ].join(" ");
                if (!item.children || item.children.length === 0) {
                  return (
                    <Link
                      key={item.href}
                      href={buildHref(item.href)}
                      aria-current={active ? "page" : undefined}
                      className={sharedClassName}
                    >
                      {item.label}
                    </Link>
                  );
                }
                const open = openMenuHref === item.href;
                return (
                  <div
                    key={item.href}
                    className="relative flex items-center gap-1"
                  >
                    <Link
                      href={buildHref(item.href)}
                      aria-current={active ? "page" : undefined}
                      className={sharedClassName}
                      onClick={() => setOpenMenuHref(null)}
                    >
                      {item.label}
                    </Link>
                    <button
                      type="button"
                      aria-label={`${item.label} sections`}
                      aria-expanded={open}
                      aria-haspopup="menu"
                      className={[
                        "inline-flex h-9 w-8 items-center justify-center rounded-md transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
                        active
                          ? "text-sidebar-primary-foreground hover:bg-sidebar-primary/80"
                          : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                      ].join(" ")}
                      onClick={() => setOpenMenuHref((current) => (current === item.href ? null : item.href))}
                    >
                      <ChevronDown
                        className={[
                          "h-4 w-4 transition-transform",
                          open ? "rotate-180" : "rotate-0",
                        ].join(" ")}
                      />
                    </button>
                    {open ? (
                      <div
                        role="menu"
                        className="bg-popover text-popover-foreground absolute left-0 top-full z-30 mt-2 w-72 rounded-xl border border-border p-2 shadow-xl"
                      >
                        {item.children.map((child) => {
                          const childActive = pathname?.startsWith(child.href);
                          return (
                            <Link
                              key={child.href}
                              href={buildHref(child.href)}
                              role="menuitem"
                              aria-current={childActive ? "page" : undefined}
                              className={[
                                "flex rounded-lg px-3 py-2 transition-colors",
                                childActive
                                  ? "bg-sidebar-primary/10 text-foreground"
                                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                              ].join(" ")}
                              onClick={() => setOpenMenuHref(null)}
                            >
                              <span className="flex flex-col">
                                <span className="text-sm font-medium">{child.label}</span>
                                {child.description ? (
                                  <span className="text-xs text-muted-foreground">{child.description}</span>
                                ) : null}
                              </span>
                            </Link>
                          );
                        })}
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </nav>
          </div>
        </header>
      ) : null}

      {canCollapseHeader ? (
        <button
          type="button"
          aria-controls="workspace-header"
          aria-expanded={!collapsed}
          title={collapsed ? "Show Header" : "Hide Header"}
          className="fixed z-30 inline-flex h-9 w-9 cursor-grab items-center justify-center rounded-full border border-border bg-background/95 text-sm shadow-md backdrop-blur hover:bg-accent active:cursor-grabbing"
          style={togglePosition ? { left: `${togglePosition.x}px`, top: `${togglePosition.y}px` } : { right: "20px", top: "84px" }}
          onPointerDown={(event) => {
            const current = togglePosition ?? { x: event.clientX - 18, y: event.clientY - 18 };
            dragRef.current = {
              offsetX: event.clientX - current.x,
              offsetY: event.clientY - current.y,
              moved: false,
            };
            setDragging(true);
          }}
          onClick={() => {
            if (ignoreClickRef.current) {
              ignoreClickRef.current = false;
              return;
            }
            setHeaderCollapsed((prev) => !prev);
          }}
        >
          {collapsed ? "▴" : "▾"}
        </button>
      ) : null}

      <main className="mx-auto flex min-h-0 w-full max-w-[1400px] flex-1 flex-col">{children}</main>
    </div>
  );
}
