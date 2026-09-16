import { expect, it } from 'vitest'
import { contextFields, parseAgentContext } from './context'

it('uses only context schema fields, preserves empty tools and validates numbers', () => {
  const fields = contextFields({ sections: [
    { key: 'config', properties: { recursion_limit: {} } },
    { key: 'context', properties: { temperature: {}, model_id: {}, principal: {}, execution_mode: {} } }
  ] })
  expect(fields.map(field => field.key)).toEqual(['model_id', 'temperature', 'execution_mode'])
  expect(parseAgentContext({ temperature: '0', tools: [], execution_mode: 'pro', principal: 'forged' }, fields)).toEqual({ temperature: 0, tools: [], execution_mode: 'pro' })
  expect(parseAgentContext({})).toEqual({})
  for (const value of [{ temperature: 3 }, { max_tokens: 2.5 }, { top_p: 'oops' }, { model_id: 'gpt-4' }, { execution_mode: 'invalid_mode' }]) expect(() => parseAgentContext(value)).toThrow()
})
