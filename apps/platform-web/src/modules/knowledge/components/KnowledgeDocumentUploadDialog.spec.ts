import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import KnowledgeDocumentUploadDialog from './KnowledgeDocumentUploadDialog.vue'

describe('KnowledgeDocumentUploadDialog', () => {
  function createWrapper() {
    return mount(KnowledgeDocumentUploadDialog, {
      props: {
        show: true,
        submitting: false,
        batchResult: null,
      },
      global: {
        stubs: {
          BaseDialog: {
            template: '<div><slot /><slot name="footer" /></div>',
          },
          BaseButton: {
            template: '<button><slot /></button>',
          },
          BaseSelect: {
            props: ['modelValue', 'disabled'],
            emits: ['update:modelValue'],
            template: '<select :disabled="disabled" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>',
          },
        },
      },
    })
  }

  async function addFiles(wrapper: ReturnType<typeof createWrapper>, names: string[]) {
    const input = wrapper.get('input[type="file"]')
    const files = names.map((name) => new File(['content'], name, { type: 'text/plain' }))
    Object.defineProperty(input.element, 'files', {
      configurable: true,
      value: files,
    })
    await input.trigger('change')
    await flushPromises()
  }

  it('emits resolved single-file rows using inherited defaults', async () => {
    const wrapper = createWrapper()
    await addFiles(wrapper, ['a.txt'])

    const tagsInput = wrapper.get('input[placeholder="architecture, storage"]')
    await tagsInput.setValue('architecture, storage')
    const selects = wrapper.findAll('select')
    await selects[0].setValue('infrastructure')

    const submitButton = wrapper.findAll('button').find((button) => button.text().includes('确认上传'))
    await submitButton?.trigger('click')

    const submitEvents = wrapper.emitted('submit')
    expect(submitEvents).toHaveLength(1)
    expect(submitEvents?.[0][0].rows).toHaveLength(1)
    expect(submitEvents?.[0][0].rows[0].metadata).toEqual({
      tags: ['architecture', 'storage'],
      attributes: { layer: 'infrastructure' },
    })
  })

  it('supports explicit clear by replacing inherited tags/layer with empty values', async () => {
    const wrapper = createWrapper()
    await addFiles(wrapper, ['a.txt'])

    const tagsInput = wrapper.get('input[placeholder="architecture, storage"]')
    await tagsInput.setValue('architecture')
    const selects = wrapper.findAll('select')
    await selects[0].setValue('infrastructure')

    const vm = wrapper.vm as unknown as {
      rows: Array<{
        tagsMode: 'inherit' | 'replace'
        layerMode: 'inherit' | 'replace'
        tags: string[]
        layer: string
      }>
    }
    vm.rows[0].tagsMode = 'replace'
    vm.rows[0].layerMode = 'replace'
    await flushPromises()

    const replaceTagsInput = wrapper.findAll('input[placeholder="architecture, storage"]')[1]
    await replaceTagsInput.setValue('')
    const rowLayerSelect = wrapper.findAll('select')[1]
    await rowLayerSelect.setValue('')

    const submitButton = wrapper.findAll('button').find((button) => button.text().includes('确认上传'))
    await submitButton?.trigger('click')

    const payload = wrapper.emitted('submit')?.[0][0]
    expect(payload.rows[0].metadata).toEqual({
      tags: [],
      attributes: { layer: '' },
    })
  })

  it('patches failed row results and keeps the row visible for retry', async () => {
    const wrapper = createWrapper()
    await addFiles(wrapper, ['a.txt', 'b.txt'])

    const submitButton = wrapper.findAll('button').find((button) => button.text().includes('确认上传'))
    await submitButton?.trigger('click')
    const emittedRows = wrapper.emitted('submit')?.[0][0].rows

    await wrapper.setProps({
      batchResult: {
        results: [
          { rowId: emittedRows[0].rowId, status: 'success', trackId: 'track-1' },
          { rowId: emittedRows[1].rowId, status: 'failed', errorMessage: '上传失败' },
        ],
        latestSuccessfulTrackId: 'track-1',
        summary: { succeeded: 1, failed: 1 },
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('上传失败')
    expect(wrapper.text()).toContain('失败 1 个')
  })

  it('retries only failed rows with the same rowId', async () => {
    const wrapper = createWrapper()
    await addFiles(wrapper, ['a.txt', 'b.txt'])

    const submitButton = wrapper.findAll('button').find((button) => button.text().includes('确认上传'))
    await submitButton?.trigger('click')

    const firstPayload = wrapper.emitted('submit')?.[0][0]
    const [firstRow, secondRow] = firstPayload.rows

    await wrapper.setProps({
      batchResult: {
        results: [
          { rowId: firstRow.rowId, status: 'success', trackId: 'track-1' },
          { rowId: secondRow.rowId, status: 'failed', errorMessage: '失败' },
        ],
        latestSuccessfulTrackId: 'track-1',
        summary: { succeeded: 1, failed: 1 },
      },
    })
    await flushPromises()

    await submitButton?.trigger('click')

    const secondPayload = wrapper.emitted('submit')?.[1][0]
    expect(secondPayload.rows).toHaveLength(1)
    expect(secondPayload.rows[0].rowId).toBe(secondRow.rowId)
  })

  it('uses live defaults again after switching back to inherit', async () => {
    const wrapper = createWrapper()
    await addFiles(wrapper, ['a.txt'])

    const defaultTagsInput = wrapper.get('input[placeholder="architecture, storage"]')
    await defaultTagsInput.setValue('architecture')
    const selects = wrapper.findAll('select')
    await selects[0].setValue('infrastructure')

    const vm = wrapper.vm as unknown as {
      rows: Array<{
        tagsMode: 'inherit' | 'replace'
        layerMode: 'inherit' | 'replace'
        tags: string[]
        layer: string
      }>
    }

    vm.rows[0].tagsMode = 'replace'
    vm.rows[0].layerMode = 'replace'
    vm.rows[0].tags = ['application']
    vm.rows[0].layer = 'application'
    await flushPromises()

    vm.rows[0].tagsMode = 'inherit'
    vm.rows[0].layerMode = 'inherit'
    await defaultTagsInput.setValue('architecture, storage')
    await selects[0].setValue('component')

    const submitButton = wrapper.findAll('button').find((button) => button.text().includes('确认上传'))
    await submitButton?.trigger('click')

    const payload = wrapper.emitted('submit')?.at(-1)?.[0]
    expect(payload.rows[0].metadata).toEqual({
      tags: ['architecture', 'storage'],
      attributes: { layer: 'component' },
    })
  })
})
