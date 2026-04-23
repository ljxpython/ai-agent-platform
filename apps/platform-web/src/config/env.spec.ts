import { describe, expect, it } from 'vitest'

import { resolveBrowserApiBaseUrl } from './env'

describe('resolveBrowserApiBaseUrl', () => {
  it('keeps an explicit loopback API origin outside dev proxy mode', () => {
    expect(
      resolveBrowserApiBaseUrl('http://127.0.0.1:2142', {
        preferSameOriginLoopbackProxy: false
      })
    ).toBe('http://127.0.0.1:2142')
  })

  it('rewrites loopback API origins to same-origin only in dev proxy mode', () => {
    expect(
      resolveBrowserApiBaseUrl('http://127.0.0.1:2142', {
        preferSameOriginLoopbackProxy: true
      })
    ).toBe(window.location.origin)
  })
})
