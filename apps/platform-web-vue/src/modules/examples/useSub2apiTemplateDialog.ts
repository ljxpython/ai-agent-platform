import { computed, ref } from 'vue'
import {
  relatedTemplatesOf,
  type Sub2apiTemplateDetail,
  type Sub2apiTemplateItem
} from '@/modules/examples/ui-assets-catalog'

export type TemplateDetailTab = 'preview' | 'overview' | 'template' | 'script' | 'style' | 'code'

export function useSub2apiTemplateDialog() {
  const selectedTemplate = ref<Sub2apiTemplateItem | null>(null)
  const selectedTemplateDetail = ref<Sub2apiTemplateDetail | null>(null)
  const detailLoading = ref(false)
  const initialTab = ref<TemplateDetailTab>('preview')
  const detailCache = new Map<string, Sub2apiTemplateDetail>()

  const relatedItems = computed(() =>
    selectedTemplate.value ? relatedTemplatesOf(selectedTemplate.value) : []
  )

  async function openTemplate(item: Sub2apiTemplateItem, tab: TemplateDetailTab = 'preview') {
    initialTab.value = tab
    selectedTemplate.value = item
    selectedTemplateDetail.value = detailCache.get(item.id) || null

    if (detailCache.has(item.id)) {
      return
    }

    detailLoading.value = true

    try {
      const { loadSub2apiTemplateDetail } = await import('@/modules/examples/template-detail-loader')
      const detail = await loadSub2apiTemplateDetail(item)
      detailCache.set(item.id, detail)

      if (selectedTemplate.value?.id === item.id) {
        selectedTemplateDetail.value = detail
      }
    } finally {
      if (selectedTemplate.value?.id === item.id) {
        detailLoading.value = false
      }
    }
  }

  function closeTemplate() {
    selectedTemplate.value = null
    selectedTemplateDetail.value = null
    detailLoading.value = false
    initialTab.value = 'preview'
  }

  return {
    selectedTemplate,
    selectedTemplateDetail,
    detailLoading,
    initialTab,
    relatedItems,
    openTemplate,
    closeTemplate
  }
}
