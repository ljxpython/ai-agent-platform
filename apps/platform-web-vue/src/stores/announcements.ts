import { defineStore } from 'pinia'

export type AnnouncementTone = 'info' | 'warning' | 'success'

export type AnnouncementItem = {
  id: string
  title: string
  summary: string
  body: string
  tone: AnnouncementTone
  createdAt: string
}

const ANNOUNCEMENTS_STORAGE_KEY = 'pw:announcements:read-ids'

const ANNOUNCEMENT_SEED: AnnouncementItem[] = [
  {
    id: 'migration-shell',
    title: 'Platform Web Vue 已切为正式迁移前端',
    summary: '页面迁移主线已经稳定，当前进入系统级一致性和演示硬化阶段。',
    body: '当前工作台已完成页面迁移主线，后续重点转向 chat/sql-agent 收口、系统级一致性和最终汇报硬化。',
    tone: 'info',
    createdAt: '2026-04-05T09:00:00+08:00'
  },
  {
    id: 'chat-history',
    title: 'Chat 历史时间线已补齐 checkpoint 可视化',
    summary: '会话详情里已经能直接查看当前快照、分叉组和分支切换入口。',
    body: '这轮补齐了 checkpoint history 时间线、小屏抽屉全屏展开与分支快照切换提示，chat/sql-agent 的产品完成度明显提高。',
    tone: 'success',
    createdAt: '2026-04-05T09:20:00+08:00'
  },
  {
    id: 'demo-data',
    title: '公告中心当前使用演示数据',
    summary: '真实公告接口和已读状态回写还需要后端配合，当前先提供稳定演示壳层。',
    body: '为了保证汇报链路稳定，当前公告中心先采用前端演示数据 + 本地已读状态持久化方案，不依赖后端接口也能完整展示交互。',
    tone: 'warning',
    createdAt: '2026-04-05T09:40:00+08:00'
  }
]

function readStoredIds() {
  if (typeof window === 'undefined') {
    return [] as string[]
  }

  const raw = window.localStorage.getItem(ANNOUNCEMENTS_STORAGE_KEY)
  if (!raw) {
    return []
  }

  try {
    const parsed = JSON.parse(raw) as unknown
    return Array.isArray(parsed) ? parsed.map(String) : []
  } catch {
    return []
  }
}

function persistIds(ids: string[]) {
  if (typeof window === 'undefined') {
    return
  }

  window.localStorage.setItem(ANNOUNCEMENTS_STORAGE_KEY, JSON.stringify(ids))
}

export const useAnnouncementsStore = defineStore('announcements', {
  state: () => ({
    hydrated: false,
    items: ANNOUNCEMENT_SEED as AnnouncementItem[],
    readIds: [] as string[]
  }),
  getters: {
    unreadCount(state) {
      return state.items.filter((item) => !state.readIds.includes(item.id)).length
    }
  },
  actions: {
    init() {
      if (this.hydrated) {
        return
      }

      this.readIds = readStoredIds()
      this.hydrated = true
    },
    isRead(id: string) {
      return this.readIds.includes(id)
    },
    markRead(id: string) {
      if (!id.trim() || this.readIds.includes(id)) {
        return
      }

      this.readIds = [...this.readIds, id]
      persistIds(this.readIds)
    },
    markAllRead() {
      this.readIds = this.items.map((item) => item.id)
      persistIds(this.readIds)
    }
  }
})
