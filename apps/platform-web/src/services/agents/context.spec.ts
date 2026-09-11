import { expect, it } from 'vitest'
import { contextFields, parseAgentContext } from './context'

it('uses only context schema fields, preserves empty tools and validates numbers', () => {
  const fields = contextFields({ sections: [
    { key: 'config', properties: { recursion_limit: {} } },
    { key: 'context', properties: { temperature: {}, model_id: {}, principal: {} } }
  ] })
  expect(fields.map(field => field.key)).toEqual(['model_id', 'temperature'])
  expect(parseAgentContext({ temperature: '0', tools: [], principal: 'forged' }, fields)).toEqual({ temperature: 0, tools: [] })
  expect(parseAgentContext({})).toEqual({})
  for (const value of [{ temperature: 3 }, { max_tokens: 2.5 }, { top_p: 'oops' }, { model_id: 'gpt-4' }]) expect(() => parseAgentContext(value)).toThrow()
})
