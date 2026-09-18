import { describe, expect, it } from 'vitest'
import { increasedForkTitle } from './threads'

describe('increasedForkTitle', () => {
  it('handles empty or blank titles with default "新对话 (1)"', () => {
    expect(increasedForkTitle()).toBe('新对话 (1)')
    expect(increasedForkTitle(null)).toBe('新对话 (1)')
    expect(increasedForkTitle('')).toBe('新对话 (1)')
    expect(increasedForkTitle('   ')).toBe('新对话 (1)')
  })

  it('appends " (1)" to unnumbered titles', () => {
    expect(increasedForkTitle('架构重构方案')).toBe('架构重构方案 (1)')
    expect(increasedForkTitle('Chat with Agent')).toBe('Chat with Agent (1)')
  })

  it('increments ASCII parenthesized numbers', () => {
    expect(increasedForkTitle('架构重构方案 (1)')).toBe('架构重构方案 (2)')
    expect(increasedForkTitle('架构重构方案 (9)')).toBe('架构重构方案 (10)')
    expect(increasedForkTitle('架构重构方案(1)')).toBe('架构重构方案 (2)')
  })

  it('increments full-width parenthesized numbers', () => {
    expect(increasedForkTitle('架构重构方案（1）')).toBe('架构重构方案（2）')
    expect(increasedForkTitle('架构重构方案（9）')).toBe('架构重构方案（10）')
  })
})
