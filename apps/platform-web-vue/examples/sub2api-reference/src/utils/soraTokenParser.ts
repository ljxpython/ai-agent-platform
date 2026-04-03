export interface ParsedSoraTokens {
  sessionTokens: string[]
  accessTokens: string[]
}

const sessionKeyNames = new Set(['sessiontoken', 'session_token', 'st'])
const accessKeyNames = new Set(['accesstoken', 'access_token', 'at'])

const sessionRegexes = [
  /\bsessionToken\b\s*:\s*["']([^"']+)["']/gi,
  /\bsession_token\b\s*:\s*["']([^"']+)["']/gi
]

const accessRegexes = [
  /\baccessToken\b\s*:\s*["']([^"']+)["']/gi,
  /\baccess_token\b\s*:\s*["']([^"']+)["']/gi
]

const sessionCookieRegex =
  /(?:^|[\n\r;])\s*(?:(?:set-cookie|cookie)\s*:\s*)?__Secure-(?:next-auth|authjs)\.session-token(?:\.(\d+))?=([^;\r\n]+)/gi

interface SessionCookieChunk {
  index: number
  value: string
}

const ignoredPlainLines = new Set([
  'set-cookie',
  'cookie',
  'strict-transport-security',
  'vary',
  'x-content-type-options',
  'x-openai-proxy-wasm'
])

function sanitizeToken(raw: string): string {
  return raw.trim().replace(/^["'`]+|["'`,;]+$/g, '')
}

function addUnique(list: string[], seen: Set<string>, rawValue: string): void {
  const token = sanitizeToken(rawValue)
  if (!token || seen.has(token)) {
    return
  }
  seen.add(token)
  list.push(token)
}

function isLikelyJWT(token: string): boolean {
  if (!token.startsWith('eyJ')) {
    return false
  }
  return token.split('.').length === 3
}

function collectFromObject(
  value: unknown,
  sessionTokens: string[],
  sessionSeen: Set<string>,
  accessTokens: string[],
  accessSeen: Set<string>
): void {
  if (Array.isArray(value)) {
    for (const item of value) {
      collectFromObject(item, sessionTokens, sessionSeen, accessTokens, accessSeen)
    }
    return
  }
  if (!value || typeof value !== 'object') {
    return
  }

  for (const [key, fieldValue] of Object.entries(value as Record<string, unknown>)) {
    if (typeof fieldValue === 'string') {
      const normalizedKey = key.toLowerCase()
      if (sessionKeyNames.has(normalizedKey)) {
        addUnique(sessionTokens, sessionSeen, fieldValue)
      }
      if (accessKeyNames.has(normalizedKey)) {
        addUnique(accessTokens, accessSeen, fieldValue)
      }
      continue
    }
    collectFromObject(fieldValue, sessionTokens, sessionSeen, accessTokens, accessSeen)
  }
}

function collectFromJSONString(
  raw: string,
  sessionTokens: string[],
  sessionSeen: Set<string>,
  accessTokens: string[],
  accessSeen: Set<string>
): void {
  const trimmed = raw.trim()
  if (!trimmed) {
    return
  }

  const candidates = [trimmed]
  const firstBrace = trimmed.indexOf('{')
  const lastBrace = trimmed.lastIndexOf('}')
  if (firstBrace >= 0 && lastBrace > firstBrace) {
    candidates.push(trimmed.slice(firstBrace, lastBrace + 1))
  }

  for (const candidate of candidates) {
    try {
      const parsed = JSON.parse(candidate)
      collectFromObject(parsed, sessionTokens, sessionSeen, accessTokens, accessSeen)
      return
    } catch {
      // ignore and keep trying other candidates
    }
  }
}

function collectByRegex(
  raw: string,
  regexes: RegExp[],
  tokens: string[],
  seen: Set<string>
): void {
  for (const regex of regexes) {
    regex.lastIndex = 0
    let match: RegExpExecArray | null
    match = regex.exec(raw)
    while (match) {
      if (match[1]) {
        addUnique(tokens, seen, match[1])
      }
      match = regex.exec(raw)
    }
  }
}

function collectFromSessionCookies(
  raw: string,
  sessionTokens: string[],
  sessionSeen: Set<string>
): void {
  const chunkMatches: SessionCookieChunk[] = []
  const singleValues: string[] = []

  sessionCookieRegex.lastIndex = 0
  let match: RegExpExecArray | null
  match = sessionCookieRegex.exec(raw)
  while (match) {
    const chunkIndex = match[1]
    const rawValue = match[2]
    const value = sanitizeToken(rawValue || '')
    if (value) {
      if (chunkIndex !== undefined && chunkIndex !== '') {
        const idx = Number.parseInt(chunkIndex, 10)
        if (Number.isInteger(idx) && idx >= 0) {
          chunkMatches.push({ index: idx, value })
        }
      } else {
        singleValues.push(value)
      }
    }
    match = sessionCookieRegex.exec(raw)
  }

  const mergedChunkToken = mergeLatestChunkedSessionToken(chunkMatches)
  if (mergedChunkToken) {
    addUnique(sessionTokens, sessionSeen, mergedChunkToken)
  }

  for (const value of singleValues) {
    addUnique(sessionTokens, sessionSeen, value)
  }
}

function mergeChunkSegment(
  chunks: SessionCookieChunk[],
  requiredMaxIndex: number,
  requireComplete: boolean
): string {
  if (chunks.length === 0) {
    return ''
  }

  const byIndex = new Map<number, string>()
  for (const chunk of chunks) {
    byIndex.set(chunk.index, chunk.value)
  }

  if (!byIndex.has(0)) {
    return ''
  }
  if (requireComplete) {
    for (let i = 0; i <= requiredMaxIndex; i++) {
      if (!byIndex.has(i)) {
        return ''
      }
    }
  }

  const orderedIndexes = Array.from(byIndex.keys()).sort((a, b) => a - b)
  return orderedIndexes.map((idx) => byIndex.get(idx) || '').join('')
}

function mergeLatestChunkedSessionToken(chunks: SessionCookieChunk[]): string {
  if (chunks.length === 0) {
    return ''
  }

  const requiredMaxIndex = chunks.reduce((max, chunk) => Math.max(max, chunk.index), 0)

  const groupStarts: number[] = []
  chunks.forEach((chunk, idx) => {
    if (chunk.index === 0) {
      groupStarts.push(idx)
    }
  })

  if (groupStarts.length === 0) {
    return mergeChunkSegment(chunks, requiredMaxIndex, false)
  }

  for (let i = groupStarts.length - 1; i >= 0; i--) {
    const start = groupStarts[i]
    const end = i + 1 < groupStarts.length ? groupStarts[i + 1] : chunks.length
    const merged = mergeChunkSegment(chunks.slice(start, end), requiredMaxIndex, true)
    if (merged) {
      return merged
    }
  }

  return mergeChunkSegment(chunks, requiredMaxIndex, false)
}

function collectPlainLines(
  raw: string,
  sessionTokens: string[],
  sessionSeen: Set<string>,
  accessTokens: string[],
  accessSeen: Set<string>
): void {
  const lines = raw
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.length > 0)

  for (const line of lines) {
    const normalized = line.toLowerCase()
    if (ignoredPlainLines.has(normalized)) {
      continue
    }
    if (/^__secure-(next-auth|authjs)\.session-token(\.\d+)?=/i.test(line)) {
      continue
    }
    if (line.includes(';')) {
      continue
    }

    if (/^[a-zA-Z_][a-zA-Z0-9_]*=/.test(line)) {
      const parts = line.split('=', 2)
      const key = parts[0]?.trim().toLowerCase()
      const value = parts[1]?.trim() || ''
      if (key && sessionKeyNames.has(key)) {
        addUnique(sessionTokens, sessionSeen, value)
        continue
      }
      if (key && accessKeyNames.has(key)) {
        addUnique(accessTokens, accessSeen, value)
        continue
      }
    }

    if (line.includes('{') || line.includes('}') || line.includes(':') || /\s/.test(line)) {
      continue
    }

    if (isLikelyJWT(line)) {
      addUnique(accessTokens, accessSeen, line)
      continue
    }
    addUnique(sessionTokens, sessionSeen, line)
  }
}

export function parseSoraRawTokens(rawInput: string): ParsedSoraTokens {
  const raw = rawInput.trim()
  if (!raw) {
    return {
      sessionTokens: [],
      accessTokens: []
    }
  }

  const sessionTokens: string[] = []
  const accessTokens: string[] = []
  const sessionSeen = new Set<string>()
  const accessSeen = new Set<string>()

  collectFromJSONString(raw, sessionTokens, sessionSeen, accessTokens, accessSeen)
  collectByRegex(raw, sessionRegexes, sessionTokens, sessionSeen)
  collectByRegex(raw, accessRegexes, accessTokens, accessSeen)
  collectFromSessionCookies(raw, sessionTokens, sessionSeen)
  collectPlainLines(raw, sessionTokens, sessionSeen, accessTokens, accessSeen)

  return {
    sessionTokens,
    accessTokens
  }
}
