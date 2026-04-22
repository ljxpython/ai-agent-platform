type BaseIconName = 'activity' | 'eye' | 'alert'

type ChatLiveFollowTone = 'success' | 'warning' | 'info'

export type ChatLiveFollowView = {
  visible: boolean
  tone: ChatLiveFollowTone
  icon: BaseIconName
  pillLabel: string
  noticeVisible: boolean
  title: string
  description: string
  showStopAction: boolean
}

export function buildChatLiveFollowView(options: {
  autoFollowEnabled: boolean
  isRunning: boolean
  unreadMessageCount: number
  bufferedStreamActivity: boolean
}): ChatLiveFollowView {
  const unreadMessageCount = Math.max(0, Math.floor(options.unreadMessageCount))
  const hasPendingUpdates = unreadMessageCount > 0 || options.bufferedStreamActivity

  if (options.autoFollowEnabled) {
    if (!options.isRunning) {
      return {
        visible: false,
        tone: 'info',
        icon: 'activity',
        pillLabel: '',
        noticeVisible: false,
        title: '',
        description: '',
        showStopAction: false
      }
    }

    return {
      visible: true,
      tone: 'success',
      icon: 'activity',
      pillLabel: '实时跟随中',
      noticeVisible: false,
      title: '',
      description: '最新输出会自动保持在可见区域。',
      showStopAction: false
    }
  }

  if (!options.isRunning && !hasPendingUpdates) {
    return {
      visible: false,
      tone: 'info',
      icon: 'eye',
      pillLabel: '',
      noticeVisible: false,
      title: '',
      description: '',
      showStopAction: false
    }
  }

  if (!hasPendingUpdates) {
    return {
      visible: true,
      tone: 'warning',
      icon: 'eye',
      pillLabel: '已暂停跟随',
      noticeVisible: false,
      title: '',
      description: '你正在查看历史内容，新输出不会强制打断当前阅读。',
      showStopAction: options.isRunning
    }
  }

  const title = unreadMessageCount > 0 ? `有 ${unreadMessageCount} 条新消息` : '有新的执行更新'
  const description = options.isRunning
    ? '你正在查看历史内容。可以回到底部继续实时跟随，或直接停止生成。'
    : '你正在查看历史内容。回到底部即可查看最新消息。'

  return {
    visible: true,
    tone: 'warning',
    icon: unreadMessageCount > 0 ? 'alert' : 'eye',
    pillLabel: unreadMessageCount > 0 ? '已暂停跟随' : '有新的执行更新',
    noticeVisible: true,
    title,
    description,
    showStopAction: options.isRunning
  }
}
