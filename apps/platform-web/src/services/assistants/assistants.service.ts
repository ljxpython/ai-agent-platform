/**
 * @deprecated 正式产品命名已统一为 Agent，请直接使用 `@/services/agents/agents.service`
 */
export {
  listAgents as listAssistantsPage,
  createAgent as createAssistant,
  getAgent as getAssistant,
  updateAgent as updateAssistant,
  getAgentParameterSchema as getAssistantParameterSchema,
} from '@/services/agents/agents.service'
