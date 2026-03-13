"use client";

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

const NAV_ITEMS = [
  { href: "/workspace/chat", label: "Chat" },
  { href: "/workspace/sql-agent", label: "SQL Agent" },
  { href: "/workspace/threads", label: "Threads" },
  { href: "/workspace/graphs", label: "Graphs" },
  { href: "/workspace/assistants", label: "Assistants" },
  { href: "/workspace/runtime", label: "Runtime" },
  { href: "/workspace/projects", label: "Projects" },
  { href: "/workspace/users", label: "Users" },
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
  const dragRef = useRef<{ offsetX: number; offsetY: number; moved: boolean } | null>(null);
  const ignoreClickRef = useRef(false);

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

  const canCollapseHeader = desktopMode;
  const collapsed = canCollapseHeader && headerCollapsed;

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

            <nav data-testid="workspace-nav" aria-label="Workspace sections" className="flex flex-wrap items-center gap-2">
              {NAV_ITEMS.map((item) => {
                const active = pathname?.startsWith(item.href);
                return (
                  <Link
                    key={item.href}
                    href={query ? `${item.href}?${query}` : item.href}
                    aria-current={active ? "page" : undefined}
                    className={[
                      "inline-flex items-center rounded-md border px-3 py-1.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
                      active
                        ? "border-sidebar-primary/60 bg-sidebar-primary text-sidebar-primary-foreground shadow-sm"
                        : "border-border bg-card text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                    ].join(" ")}
                  >
                    {item.label}
                  </Link>
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
