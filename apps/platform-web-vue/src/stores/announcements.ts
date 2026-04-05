import { defineStore } from 'pinia'
import {
  listAnnouncementsFeed,
  markAllAnnouncementsRead,
  markAnnouncementRead
} from '@/services/announcements/announcements.service'
import type { ManagementAnnouncement } from '@/types/management'

export type AnnouncementTone = 'info' | 'warning' | 'success'

export type AnnouncementItem = {
  id: string
  title: string
  summary: string
  body: string
  tone: AnnouncementTone
  createdAt: string
  isRead: boolean
}

const ANNOUNCEMENTS_STORAGE_KEY = 'pw:announcements:read-ids'

const ANNOUNCEMENT_SEED: AnnouncementItem[] = [
  {
    id: 'migration-shell',
    title: 'Agent Platform Console 品牌已更新',
    summary: '当前正式前端宿主已经统一为 Agent Platform Console。',
    body: '智能体平台控制台、Agent 页面和后续前端开发都以 platform-web-vue 为正式宿主，页面与工程规范按同一套基座继续演进。',
    tone: 'info',
    createdAt: '2026-04-05T09:00:00+08:00',
    isRead: false
  },
  {
    id: 'chat-history',
    title: 'Chat 历史时间线已补齐 checkpoint 可视化',
    summary: '会话详情里已经能直接查看当前快照、分叉组和分支切换入口。',
    body: '这轮补齐了 checkpoint history 时间线、小屏抽屉全屏展开与分支快照切换提示，chat/sql-agent 的产品完成度明显提高。',
    tone: 'success',
    createdAt: '2026-04-05T09:20:00+08:00',
    isRead: false
  },
  {
    id: 'demo-data',
    title: '公告中心提供稳定回退能力',
    summary: '公告中心优先读取真实后端，接口异常时自动回退到本地公告数据。',
    body: '为了保证正式工作台在异常场景下也能稳定展示，公告中心保留了回退公告数据与本地已读状态能力，但默认仍以真实后端数据为准。',
    tone: 'warning',
    createdAt: '2026-04-05T09:40:00+08:00',
    isRead: false
  }
]

function normalizeRemoteItem(item: ManagementAnnouncement): AnnouncementItem {
  return {
    id: item.id,
    title: item.title,
    summary: item.summary,
    body: item.body,
    tone: item.tone,
    createdAt: item.publish_at || '',
    isRead: Boolean(item.is_read)
  }
}

function withFallbackReadState(items: AnnouncementItem[], readIds: string[]) {
  return items.map((item) => ({
    ...item,
    isRead: readIds.includes(item.id)
  }))
}

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
    items: [] as AnnouncementItem[],
    readIds: [] as string[],
    mode: 'initial' as 'initial' | 'fallback' | 'remote',
    loading: false,
    currentProjectId: ''
  }),
  getters: {
    unreadCount(state) {
      return state.items.filter((item) => !item.isRead).length
    }
  },
  actions: {
    async init(projectId = '') {
      if (!this.hydrated) {
        this.readIds = readStoredIds()
        this.hydrated = true
      }

      await this.load(projectId)
    },
    async load(projectId = '') {
      const normalizedProjectId = projectId.trim()
      if (!this.hydrated) {
        this.readIds = readStoredIds()
        this.hydrated = true
      }

      this.loading = true
      this.currentProjectId = normalizedProjectId

      try {
        const payload = await listAnnouncementsFeed(normalizedProjectId || undefined)
        this.items = Array.isArray(payload.items) ? payload.items.map(normalizeRemoteItem) : []
        this.mode = 'remote'
      } catch {
        this.items = withFallbackReadState(ANNOUNCEMENT_SEED, this.readIds)
        this.mode = 'fallback'
      } finally {
        this.loading = false
      }
    },
    isRead(id: string) {
      return this.items.find((item) => item.id === id)?.isRead ?? this.readIds.includes(id)
    },
    async markRead(id: string) {
      if (!id.trim() || this.items.find((item) => item.id === id)?.isRead) {
        return
      }

      if (this.mode === 'remote') {
        try {
          await markAnnouncementRead(id)
        } catch {
          if (!this.readIds.includes(id)) {
            this.readIds = [...this.readIds, id]
            persistIds(this.readIds)
          }
        }
      } else if (!this.readIds.includes(id)) {
        this.readIds = [...this.readIds, id]
        persistIds(this.readIds)
      }

      this.items = this.items.map((item) =>
        item.id === id
          ? {
              ...item,
              isRead: true
            }
          : item
      )
    },
    async markAllRead(projectId = '') {
      if (this.mode === 'remote') {
        try {
          await markAllAnnouncementsRead(projectId || undefined)
        } catch {
          this.readIds = this.items.map((item) => item.id)
          persistIds(this.readIds)
        }
      } else {
        this.readIds = this.items.map((item) => item.id)
        persistIds(this.readIds)
      }

      this.items = this.items.map((item) => ({
        ...item,
        isRead: true
      }))
    }
  }
})
