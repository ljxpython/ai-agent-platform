import type { ContentBlock } from '@langchain/core/messages'
import type { AssembledToolCall } from '@langchain/vue'
import type { Chunk, DiffData, AgentDisplayMessage, ToolExecutionChunk, AcpToolKind } from './agent-types'

const READ_TOOLS = new Set(['read_file', 'read', 'ls', 'cat', 'head', 'tail'])
const EDIT_TOOLS = new Set(['write_file', 'edit_file', 'str_replace', 'write', 'edit', 'patch', 'replace_file_content'])
const EXECUTE_TOOLS = new Set(['execute', 'bash', 'shell', 'run_terminal_cmd', 'run_command'])
const SEARCH_TOOLS = new Set(['glob', 'grep', 'web_search', 'search', 'grep_search', 'find_by_name'])
const FETCH_TOOLS = new Set(['fetch', 'fetch_url', 'http_request', 'read_url_content'])
const INTERNAL_TOOLS = new Set(['confirming_completion', 'no_op'])

function toolKind(name: string): AcpToolKind {
  const lowered = name.toLowerCase()
  if (lowered === 'task' || lowered.includes('invoke_subagent')) return 'task'
  if (lowered === 'slack_thread_reply') return 'slack'
  if (lowered === 'linear_comment') return 'linear'
  if (EDIT_TOOLS.has(lowered) || ['edit', 'write', 'replace'].some((t) => lowered.includes(t))) return 'edit'
  if (EXECUTE_TOOLS.has(lowered)) return 'execute'
  if (FETCH_TOOLS.has(lowered)) return 'fetch'
  if (SEARCH_TOOLS.has(lowered)) return 'search'
  if (READ_TOOLS.has(lowered) || lowered.includes('read') || lowered.includes('view')) return 'read'
  if (lowered === 'think') return 'think'
  return 'other'
}

function toolTitle(name: string, args: Record<string, unknown>): string {
  const path = args.path ?? args.file_path ?? args.target_file ?? args.AbsolutePath ?? args.TargetFile ?? args.SearchDirectory
  if (typeof path === 'string' && path.trim()) return `${name} ${path.trim()}`
  const command = args.command ?? args.CommandLine
  if (typeof command === 'string' && command.trim()) {
    return command.trim().split('\n')[0]?.slice(0, 120) ?? ''
  }
  return name.replace(/_/g, ' ')
}

function parseToolArgs(raw: unknown): Record<string, unknown> {
  if (raw && typeof raw === 'object' && !Array.isArray(raw)) return raw as Record<string, unknown>
  if (typeof raw === 'string') {
    try {
      const parsed = JSON.parse(raw)
      return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
        ? (parsed as Record<string, unknown>)
        : { raw }
    } catch {
      return { raw }
    }
  }
  return {}
}

function maybeDiffFromArgs(args: Record<string, unknown>): DiffData | null {
  const path = args.path ?? args.file_path ?? args.target_file ?? args.TargetFile
  if (typeof path !== 'string' || !path.trim()) return null
  const oldContent = args.old_string ?? args.original_content ?? args.TargetContent
  const newContent = args.new_string ?? args.content ?? args.new_content ?? args.ReplacementContent
  if (typeof newContent !== 'string') return null
  const original = typeof oldContent === 'string' ? oldContent : null
  return {
    originalContent: original,
    newContent,
    filePath: path.trim(),
    isNewFile: original === null,
    isBinary: false,
    isTruncated: false,
    totalLines: Math.max(newContent.split('\n').length, 1)
  }
}

function mergeTextChunks(chunks: Array<Chunk>): Array<Chunk> {
  const textIndices = chunks.flatMap((c, i) => (c.kind === 'text' ? [i] : []))
  if (textIndices.length <= 1) return chunks
  const lastText = textIndices[textIndices.length - 1]
  return chunks.filter((c, i) => c.kind !== 'text' || i === lastText)
}

function getMessageType(raw: unknown): string {
  if (!raw || typeof raw !== 'object') return ''
  if (typeof (raw as any)._getType === 'function') {
    return (raw as any)._getType()
  }
  if (typeof (raw as any).getType === 'function') {
    return (raw as any).getType()
  }
  const type = (raw as any).type
  if (typeof type === 'string') {
    if (type === 'human' || type === 'user') return 'human'
    if (type === 'ai' || type === 'assistant') return 'ai'
    if (type === 'tool') return 'tool'
    if (type === 'system') return 'system'
    return type
  }
  return ''
}

function reasoningText(raw: any): string {
  let blocks: Array<ContentBlock> = []
  try {
    blocks = raw.contentBlocks || []
  } catch {
    blocks = []
  }
  let text = ''
  for (const block of blocks) {
    if (block.type !== 'reasoning') continue
    const reasoning = (block as any).reasoning
    if (typeof reasoning === 'string') text += reasoning
  }
  if (!text && raw.additional_kwargs?.reasoning_content) {
    text = String(raw.additional_kwargs.reasoning_content)
  }
  if (!text && raw.response_metadata?.reasoning_content) {
    text = String(raw.response_metadata.reasoning_content)
  }
  return text.trim()
}

function imageChunks(content: unknown): Array<Chunk> {
  if (!Array.isArray(content)) return []

  const chunks: Array<Chunk> = []
  for (const item of content) {
    if (!item || typeof item !== 'object' || Array.isArray(item)) continue
    const block = item as Record<string, unknown>
    const type = block.type
    let base64: string | undefined
    let mimeType: string | undefined

    if (type === 'image') {
      const data = block.data ?? block.base64
      const mime = block.mime_type ?? block.mimeType
      if (typeof data === 'string' && typeof mime === 'string') {
        base64 = data
        mimeType = mime
      }
    } else if (type === 'image_url') {
      const imageUrl = block.image_url
      const url =
        imageUrl && typeof imageUrl === 'object' ? (imageUrl as Record<string, unknown>).url : undefined
      if (typeof url === 'string') {
        const match = /^data:(image\/[^;]+);base64,(.+)$/s.exec(url)
        if (match) {
          mimeType = match[1]
          base64 = match[2]
        }
      }
    }

    if (base64 && mimeType) {
      const fileName = block.fileName ?? block.file_name
      chunks.push({
        kind: 'image',
        base64,
        mimeType,
        ...(typeof fileName === 'string' && fileName ? { fileName } : {})
      })
    }
  }
  return chunks
}

function toolStatus(
  assembled: AssembledToolCall | undefined,
  toolMessage: any | undefined
): ToolExecutionChunk['status'] {
  if (assembled) {
    if (assembled.status === 'finished') return 'completed'
    if (assembled.status === 'error') return 'error'
    return 'in_progress'
  }
  if (toolMessage) return toolMessage.status === 'error' ? 'error' : 'completed'
  return 'in_progress'
}

function toolOutputText(
  assembled: AssembledToolCall | undefined,
  toolMessage: any | undefined
): string | undefined {
  const value = assembled?.output
  if (value != null) {
    if (typeof value === 'string') return value.trim() || undefined
    try {
      return JSON.stringify(value)
    } catch {
      return String(value)
    }
  }
  const text = toolMessage?.content
  if (typeof text === 'string') return text.trim() || undefined
  return undefined
}

export function streamMessagesToUi(
  messages: Array<any>,
  toolCalls: ReadonlyArray<AssembledToolCall> = []
): Array<AgentDisplayMessage> {
  const toolCallsById = new Map<string, AssembledToolCall>()
  for (const toolCall of toolCalls) {
    const id = toolCall.id || toolCall.callId
    if (id) toolCallsById.set(id, toolCall)
  }

  const toolMessagesById = new Map<string, any>()
  for (const raw of messages) {
    if (getMessageType(raw) === 'tool') {
      const toolCallId = (raw as any).tool_call_id || (raw as any).toolCallId
      if (typeof toolCallId === 'string') {
        toolMessagesById.set(toolCallId, raw)
      }
    }
  }

  const uiMessages: Array<AgentDisplayMessage> = []
  let agentTurn: Partial<AgentDisplayMessage> | null = null

  const flushAgentTurn = () => {
    if (!agentTurn) return
    uiMessages.push({
      id: agentTurn.id || '',
      author: agentTurn.author || 'agent',
      timestamp: agentTurn.timestamp || new Date().toISOString(),
      startedAt: agentTurn.startedAt,
      timestampIsFallback: agentTurn.timestampIsFallback,
      chunks: mergeTextChunks(agentTurn.chunks || [])
    })
    agentTurn = null
  }

  const appendAgentChunks = (
    msgId: string,
    timestamp: string,
    timestampIsFallback: boolean,
    chunks: Array<Chunk>
  ) => {
    if (!agentTurn) {
      agentTurn = {
        id: msgId,
        author: 'agent',
        timestamp,
        startedAt: timestamp,
        timestampIsFallback,
        chunks: [...chunks]
      }
    } else {
      agentTurn.timestamp = timestamp
      agentTurn.timestampIsFallback = agentTurn.timestampIsFallback || timestampIsFallback
      agentTurn.chunks!.push(...chunks)
    }
  }

  messages.forEach((raw, index) => {
    const msgId = typeof raw.id === 'string' && raw.id ? raw.id : `msg-${index}`
    const timestamp = typeof raw.timestamp === 'string' && raw.timestamp ? raw.timestamp : new Date().toISOString()
    const timestampIsFallback = !raw.timestamp
    const msgType = getMessageType(raw)

    if (msgType === 'human') {
      flushAgentTurn()
      const content = raw.content
      const chunks = imageChunks(content)
      const text = typeof content === 'string' ? content : (Array.isArray(content) ? content.filter((c: any) => c && c.type === 'text').map((c: any) => c.text).join('') : '')
      
      if (text.trim()) chunks.push({ kind: 'text', text: text.trim() })
      if (!chunks.length) return
      
      uiMessages.push({
        id: msgId,
        author: 'user',
        timestamp,
        timestampIsFallback,
        chunks
      })
      return
    }

    if (msgType === 'ai') {
      const chunks: Array<Chunk> = []
      const reasoning = reasoningText(raw)
      if (reasoning) chunks.push({ kind: 'reasoning', text: reasoning })
      const text = typeof raw.content === 'string' ? raw.content.trim() : ''
      if (text) {
        const name = typeof raw.name === 'string' ? raw.name.trim() : ''
        if (name) {
          chunks.push({ kind: 'text', text: `**[${name}]**\n${text}` })
        } else {
          chunks.push({ kind: 'text', text })
        }
      }

      const rawToolCalls = raw.tool_calls || raw.additional_kwargs?.tool_calls || []
      for (const toolCall of rawToolCalls) {
        const name = toolCall.name || toolCall.function?.name || 'tool'
        if (INTERNAL_TOOLS.has(name)) continue
        const toolCallId = toolCall.id || `tool-${index}-${chunks.length}`
        const rawArgs = toolCall.args ?? toolCall.function?.arguments
        const args = parseToolArgs(rawArgs)
        const assembled = toolCallsById.get(toolCallId)
        const toolMessage = toolMessagesById.get(toolCallId)
        const chunk: ToolExecutionChunk = {
          kind: 'tool-execution',
          toolCallId,
          timestamp,
          title: toolTitle(name, args),
          toolKind: toolKind(name),
          input: args,
          status: toolStatus(assembled, toolMessage)
        }
        const output = toolOutputText(assembled, toolMessage)
        if (output) chunk.output = output
        const diffData = maybeDiffFromArgs(args)
        if (diffData) chunk.diffData = diffData
        chunks.push(chunk)
      }

      if (chunks.length) {
        appendAgentChunks(msgId, timestamp, timestampIsFallback, chunks)
      }
    }
  })

  flushAgentTurn()
  return uiMessages
}
