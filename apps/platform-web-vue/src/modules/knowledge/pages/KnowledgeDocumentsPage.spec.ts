import { computed, ref } from 'vue'
import { defineComponent } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const {
  listProjectKnowledgeDocumentsMock,
  getProjectKnowledgePipelineStatusMock,
  getProjectKnowledgeScanProgressMock,
  getProjectKnowledgeTrackStatusMock,
  uploadProjectKnowledgeDocumentMock,
  startProjectKnowledgeScanMock,
  reprocessFailedProjectKnowledgeDocumentsMock,
  clearProjectKnowledgeDocumentsMock,
  cancelProjectKnowledgePipelineMock,
  deleteProjectKnowledgeDocumentMock,
  getProjectKnowledgeDocumentDetailMock,
} = vi.hoisted(() => ({
  listProjectKnowledgeDocumentsMock: vi.fn(),
  getProjectKnowledgePipelineStatusMock: vi.fn(),
  getProjectKnowledgeScanProgressMock: vi.fn(),
  getProjectKnowledgeTrackStatusMock: vi.fn(),
  uploadProjectKnowledgeDocumentMock: vi.fn(),
  startProjectKnowledgeScanMock: vi.fn(),
  reprocessFailedProjectKnowledgeDocumentsMock: vi.fn(),
  clearProjectKnowledgeDocumentsMock: vi.fn(),
  cancelProjectKnowledgePipelineMock: vi.fn(),
  deleteProjectKnowledgeDocumentMock: vi.fn(),
  getProjectKnowledgeDocumentDetailMock: vi.fn(),
}))

vi.mock('@/composables/useAuthorization', () => ({
  useAuthorization: () => ({
    can: () => true,
  }),
}))

vi.mock('@/modules/knowledge/composables/useKnowledgeProjectRoute', () => ({
  useKnowledgeProjectRoute: () => ({
    projectId: ref('project-42'),
    project: computed(() => ({
      id: 'project-42',
      name: 'Project 42',
    })),
  }),
}))

vi.mock('@/stores/ui', () => ({
  useUiStore: () => ({
    pushToast: vi.fn(),
  }),
}))

vi.mock('@/services/knowledge/knowledge.service', () => ({
  listProjectKnowledgeDocuments: listProjectKnowledgeDocumentsMock,
  getProjectKnowledgePipelineStatus: getProjectKnowledgePipelineStatusMock,
  getProjectKnowledgeScanProgress: getProjectKnowledgeScanProgressMock,
  getProjectKnowledgeTrackStatus: getProjectKnowledgeTrackStatusMock,
  uploadProjectKnowledgeDocument: uploadProjectKnowledgeDocumentMock,
  startProjectKnowledgeScan: startProjectKnowledgeScanMock,
  reprocessFailedProjectKnowledgeDocuments: reprocessFailedProjectKnowledgeDocumentsMock,
  clearProjectKnowledgeDocuments: clearProjectKnowledgeDocumentsMock,
  cancelProjectKnowledgePipeline: cancelProjectKnowledgePipelineMock,
  deleteProjectKnowledgeDocument: deleteProjectKnowledgeDocumentMock,
  getProjectKnowledgeDocumentDetail: getProjectKnowledgeDocumentDetailMock,
}))

vi.mock('@/services/operations/operations.service', () => ({
  waitForOperationTerminalState: vi.fn(),
}))

vi.mock('@/utils/format', () => ({
  formatDateTime: (value: string | null | undefined) => value || '--',
  shortId: (value: string | null | undefined) => String(value || '').slice(0, 8),
}))

vi.mock('@/utils/http-error', () => ({
  resolvePlatformHttpErrorMessage: () => '知识文档加载失败',
}))

import KnowledgeDocumentsPage from './KnowledgeDocumentsPage.vue'

function createDocumentsPayload(page: number, total = 45) {
  return {
    documents: [
      {
        id: `doc-${page}`,
        file_path: `/docs/page-${page}.md`,
        content_summary: `summary-${page}`,
        content_length: 128 + page,
        status: 'PROCESSED',
        updated_at: `2026-04-1${page}T00:00:00Z`,
        track_id: `track-${page}`,
        chunks_count: page,
        metadata: {},
      },
    ],
    pagination: {
      page,
      page_size: 20,
      total_count: total,
      total_pages: Math.ceil(total / 20),
      has_next: page * 20 < total,
      has_prev: page > 1,
    },
    status_counts: {
      PROCESSED: total,
    },
  }
}

describe('KnowledgeDocumentsPage', () => {
  beforeEach(() => {
    listProjectKnowledgeDocumentsMock.mockReset()
    getProjectKnowledgePipelineStatusMock.mockReset()
    getProjectKnowledgeScanProgressMock.mockReset()
    getProjectKnowledgeTrackStatusMock.mockReset()
    uploadProjectKnowledgeDocumentMock.mockReset()
    startProjectKnowledgeScanMock.mockReset()
    reprocessFailedProjectKnowledgeDocumentsMock.mockReset()
    clearProjectKnowledgeDocumentsMock.mockReset()
    cancelProjectKnowledgePipelineMock.mockReset()
    deleteProjectKnowledgeDocumentMock.mockReset()
    getProjectKnowledgeDocumentDetailMock.mockReset()

    getProjectKnowledgePipelineStatusMock.mockResolvedValue({
      busy: false,
      job_name: 'idle',
      latest_message: 'idle',
    })
    getProjectKnowledgeScanProgressMock.mockResolvedValue({
      is_scanning: false,
      current_file: '',
      indexed_count: 0,
      total_files: 0,
      progress: 0,
    })
    getProjectKnowledgeTrackStatusMock.mockResolvedValue({
      track_id: 'track-1',
      documents: [],
      total_count: 0,
      status_summary: {},
    })
    uploadProjectKnowledgeDocumentMock.mockResolvedValue({})
    startProjectKnowledgeScanMock.mockResolvedValue({ id: 'op-1' })
    reprocessFailedProjectKnowledgeDocumentsMock.mockResolvedValue({})
    clearProjectKnowledgeDocumentsMock.mockResolvedValue({ id: 'op-2' })
    cancelProjectKnowledgePipelineMock.mockResolvedValue({})
    deleteProjectKnowledgeDocumentMock.mockResolvedValue({})
    getProjectKnowledgeDocumentDetailMock.mockResolvedValue({})
  })

  const UploadDialogStub = defineComponent({
    name: 'KnowledgeDocumentUploadDialog',
    props: {
      show: {
        type: Boolean,
        default: false,
      },
      submitting: {
        type: Boolean,
        default: false,
      },
      batchResult: {
        type: Object,
        default: null,
      },
    },
    emits: ['close', 'submit'],
    methods: {
      buildRows() {
        return [
          { rowId: 'row-1', file: { name: 'a.txt' }, metadata: { tags: ['architecture'], attributes: { layer: 'infrastructure' } } },
          { rowId: 'row-2', file: { name: 'b.txt' }, metadata: { tags: ['application'], attributes: { layer: 'application' } } },
        ]
      },
    },
    template: `
      <div data-test="upload-dialog" :data-open="show ? 'yes' : 'no'">
        <button
          data-test="submit-upload"
          @click="$emit('submit', { rows: buildRows() })"
        >
          submit
        </button>
      </div>
    `,
  })

  it('reloads the backend page when pagination state changes', async () => {
    listProjectKnowledgeDocumentsMock
      .mockResolvedValueOnce(createDocumentsPayload(1))
      .mockResolvedValueOnce(createDocumentsPayload(2))
      .mockResolvedValueOnce(createDocumentsPayload(1))

    const wrapper = mount(KnowledgeDocumentsPage, {
      global: {
        stubs: {
          BaseButton: { template: '<button><slot /></button>' },
          BaseDialog: { template: '<div><slot /></div>' },
          BaseIcon: { template: '<i />' },
          ConfirmDialog: { template: '<div />' },
          BaseSelect: {
            props: ['modelValue'],
            emits: ['update:modelValue'],
            template: '<select @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>',
          },
          SurfaceCard: { template: '<section><slot /></section>' },
          PageHeader: {
            props: ['title', 'description'],
            template: '<header><h1>{{ title }}</h1><p>{{ description }}</p><slot name="actions" /></header>',
          },
          TablePageLayout: {
            template: '<div data-test="table-page-layout"><slot name="filters" /><slot name="table" /><slot name="footer" /></div>',
          },
          FilterToolbar: { template: '<div><slot /></div>' },
          DataTable: { template: '<div data-test="data-table"><slot /></div>' },
          PaginationBar: {
            template: `
              <div>
                <button data-test="goto-page-2" @click="$emit('update:page', 2)">page-2</button>
                <button data-test="page-size-50" @click="$emit('update:page-size', 50)">size-50</button>
              </div>
            `,
          },
          StateBanner: {
            props: ['title', 'description'],
            template: '<div><strong>{{ title }}</strong><span>{{ description }}</span></div>',
          },
          StatusPill: { template: '<span><slot /></span>' },
          KnowledgeWorkspaceNav: { template: '<nav>knowledge nav</nav>' },
          KnowledgePipelineStatusDialog: { template: '<div />' },
          KnowledgeDocumentUploadDialog: UploadDialogStub,
        },
      },
    })

    await flushPromises()

    expect(wrapper.find('section').classes()).toEqual(
      expect.arrayContaining(['pw-page-shell', 'h-full', 'min-h-0', 'overflow-y-auto']),
    )
    expect(wrapper.get('[data-test="table-page-layout"]').exists()).toBe(true)

    expect(listProjectKnowledgeDocumentsMock).toHaveBeenNthCalledWith(
      1,
      'project-42',
      expect.objectContaining({
        page: 1,
        page_size: 20,
        status_filter: undefined,
      }),
    )

    await wrapper.get('[data-test="goto-page-2"]').trigger('click')
    await flushPromises()

    expect(listProjectKnowledgeDocumentsMock).toHaveBeenNthCalledWith(
      2,
      'project-42',
      expect.objectContaining({
        page: 2,
        page_size: 20,
        status_filter: undefined,
      }),
    )

    await wrapper.get('[data-test="page-size-50"]').trigger('click')
    await flushPromises()

    expect(listProjectKnowledgeDocumentsMock).toHaveBeenNthCalledWith(
      3,
      'project-42',
      expect.objectContaining({
        page: 1,
        page_size: 50,
        status_filter: undefined,
      }),
    )
  })

  it('opens upload dialog and submits rows sequentially while keeping latest successful track', async () => {
    listProjectKnowledgeDocumentsMock.mockResolvedValue(createDocumentsPayload(1))
    uploadProjectKnowledgeDocumentMock
      .mockResolvedValueOnce({ track_id: 'track-success' })
      .mockRejectedValueOnce(new Error('upload failed'))

    const wrapper = mount(KnowledgeDocumentsPage, {
      global: {
        stubs: {
          BaseButton: { template: '<button><slot /></button>' },
          BaseDialog: { template: '<div><slot /><slot name="footer" /></div>' },
          BaseIcon: { template: '<i />' },
          ConfirmDialog: { template: '<div />' },
          BaseSelect: {
            props: ['modelValue'],
            emits: ['update:modelValue'],
            template: '<select @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>',
          },
          SurfaceCard: { template: '<section><slot /></section>' },
          PageHeader: {
            props: ['title', 'description'],
            template: '<header><h1>{{ title }}</h1><p>{{ description }}</p><slot name="actions" /></header>',
          },
          TablePageLayout: {
            template: '<div><slot name="filters" /><slot name="table" /><slot name="footer" /></div>',
          },
          FilterToolbar: { template: '<div><slot /></div>' },
          DataTable: { template: '<div><slot /></div>' },
          PaginationBar: { template: '<div />' },
          StateBanner: {
            props: ['title', 'description'],
            template: '<div><strong>{{ title }}</strong><span>{{ description }}</span></div>',
          },
          StatusPill: { template: '<span><slot /></span>' },
          KnowledgeWorkspaceNav: { template: '<nav />' },
          KnowledgePipelineStatusDialog: { template: '<div />' },
          KnowledgeDocumentUploadDialog: UploadDialogStub,
        },
      },
    })

    await flushPromises()

    const uploadButtons = wrapper.findAll('button').filter((button) => button.text() === '上传文档')
    await uploadButtons[0].trigger('click')
    await flushPromises()

    const uploadDialog = wrapper.getComponent(UploadDialogStub)
    expect(uploadDialog.props('show')).toBe(true)

    await wrapper.get('[data-test="submit-upload"]').trigger('click')
    await flushPromises()

    expect(uploadProjectKnowledgeDocumentMock).toHaveBeenNthCalledWith(
      1,
      'project-42',
      expect.objectContaining({ name: 'a.txt' }),
      { tags: ['architecture'], attributes: { layer: 'infrastructure' } },
    )
    expect(uploadProjectKnowledgeDocumentMock).toHaveBeenNthCalledWith(
      2,
      'project-42',
      expect.objectContaining({ name: 'b.txt' }),
      { tags: ['application'], attributes: { layer: 'application' } },
    )
    expect(getProjectKnowledgeTrackStatusMock).toHaveBeenCalledWith('project-42', 'track-success')
    expect(wrapper.text()).toContain('已成功提交 1 份文档，1 份失败。')
    expect(uploadDialog.props('show')).toBe(true)
  })

  it('removes the page-level metadata upload card and keeps dialog as the default upload path', async () => {
    listProjectKnowledgeDocumentsMock.mockResolvedValue(createDocumentsPayload(1))

    const wrapper = mount(KnowledgeDocumentsPage, {
      global: {
        stubs: {
          BaseButton: { template: '<button><slot /></button>' },
          BaseDialog: { template: '<div><slot /><slot name="footer" /></div>' },
          BaseIcon: { template: '<i />' },
          ConfirmDialog: { template: '<div />' },
          BaseSelect: {
            props: ['modelValue'],
            emits: ['update:modelValue'],
            template: '<select @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>',
          },
          SurfaceCard: { template: '<section><slot /></section>' },
          PageHeader: {
            props: ['title', 'description'],
            template: '<header><h1>{{ title }}</h1><p>{{ description }}</p><slot name="actions" /></header>',
          },
          TablePageLayout: { template: '<div><slot name="filters" /><slot name="table" /><slot name="footer" /></div>' },
          FilterToolbar: { template: '<div><slot /></div>' },
          DataTable: { template: '<div><slot /></div>' },
          PaginationBar: { template: '<div />' },
          StateBanner: { props: ['title', 'description'], template: '<div><strong>{{ title }}</strong><span>{{ description }}</span></div>' },
          StatusPill: { template: '<span><slot /></span>' },
          KnowledgeWorkspaceNav: { template: '<nav />' },
          KnowledgePipelineStatusDialog: { template: '<div />' },
          KnowledgeDocumentUploadDialog: UploadDialogStub,
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).not.toContain('上传时附带 tags')
    expect(wrapper.text()).not.toContain('上传时附带 layer')

    const uploadButtons = wrapper.findAll('button').filter((button) => button.text() === '上传文档')
    await uploadButtons[0].trigger('click')
    await flushPromises()

    const uploadDialog = wrapper.getComponent(UploadDialogStub)
    expect(uploadDialog.props('show')).toBe(true)
  })

  it('closes the dialog when all uploaded rows succeed', async () => {
    listProjectKnowledgeDocumentsMock.mockResolvedValue(createDocumentsPayload(1))
    uploadProjectKnowledgeDocumentMock
      .mockResolvedValueOnce({ track_id: 'track-1' })
      .mockResolvedValueOnce({ track_id: 'track-2' })

    const wrapper = mount(KnowledgeDocumentsPage, {
      global: {
        stubs: {
          BaseButton: { template: '<button><slot /></button>' },
          BaseDialog: { template: '<div><slot /><slot name="footer" /></div>' },
          BaseIcon: { template: '<i />' },
          ConfirmDialog: { template: '<div />' },
          BaseSelect: {
            props: ['modelValue'],
            emits: ['update:modelValue'],
            template: '<select @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>',
          },
          SurfaceCard: { template: '<section><slot /></section>' },
          PageHeader: {
            props: ['title', 'description'],
            template: '<header><h1>{{ title }}</h1><p>{{ description }}</p><slot name="actions" /></header>',
          },
          TablePageLayout: { template: '<div><slot name="filters" /><slot name="table" /><slot name="footer" /></div>' },
          FilterToolbar: { template: '<div><slot /></div>' },
          DataTable: { template: '<div><slot /></div>' },
          PaginationBar: { template: '<div />' },
          StateBanner: { props: ['title', 'description'], template: '<div><strong>{{ title }}</strong><span>{{ description }}</span></div>' },
          StatusPill: { template: '<span><slot /></span>' },
          KnowledgeWorkspaceNav: { template: '<nav />' },
          KnowledgePipelineStatusDialog: { template: '<div />' },
          KnowledgeDocumentUploadDialog: UploadDialogStub,
        },
      },
    })

    await flushPromises()

    const uploadButtons = wrapper.findAll('button').filter((button) => button.text() === '上传文档')
    await uploadButtons[0].trigger('click')
    await flushPromises()
    await wrapper.get('[data-test="submit-upload"]').trigger('click')
    await flushPromises()

    const uploadDialog = wrapper.getComponent(UploadDialogStub)
    expect(uploadDialog.props('show')).toBe(false)
    expect(getProjectKnowledgeTrackStatusMock).toHaveBeenCalledWith('project-42', 'track-2')
  })

  it('chooses the last successful non-empty track id when earlier success is empty', async () => {
    listProjectKnowledgeDocumentsMock.mockResolvedValue(createDocumentsPayload(1))
    uploadProjectKnowledgeDocumentMock
      .mockResolvedValueOnce({ track_id: '' })
      .mockResolvedValueOnce({ track_id: 'track-2' })

    const wrapper = mount(KnowledgeDocumentsPage, {
      global: {
        stubs: {
          BaseButton: { template: '<button><slot /></button>' },
          BaseDialog: { template: '<div><slot /><slot name="footer" /></div>' },
          BaseIcon: { template: '<i />' },
          ConfirmDialog: { template: '<div />' },
          BaseSelect: {
            props: ['modelValue'],
            emits: ['update:modelValue'],
            template: '<select @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>',
          },
          SurfaceCard: { template: '<section><slot /></section>' },
          PageHeader: {
            props: ['title', 'description'],
            template: '<header><h1>{{ title }}</h1><p>{{ description }}</p><slot name="actions" /></header>',
          },
          TablePageLayout: { template: '<div><slot name="filters" /><slot name="table" /><slot name="footer" /></div>' },
          FilterToolbar: { template: '<div><slot /></div>' },
          DataTable: { template: '<div><slot /></div>' },
          PaginationBar: { template: '<div />' },
          StateBanner: { props: ['title', 'description'], template: '<div><strong>{{ title }}</strong><span>{{ description }}</span></div>' },
          StatusPill: { template: '<span><slot /></span>' },
          KnowledgeWorkspaceNav: { template: '<nav />' },
          KnowledgePipelineStatusDialog: { template: '<div />' },
          KnowledgeDocumentUploadDialog: UploadDialogStub,
        },
      },
    })

    await flushPromises()

    const uploadButtons = wrapper.findAll('button').filter((button) => button.text() === '上传文档')
    await uploadButtons[0].trigger('click')
    await flushPromises()
    await wrapper.get('[data-test="submit-upload"]').trigger('click')
    await flushPromises()

    expect(getProjectKnowledgeTrackStatusMock).toHaveBeenCalledWith('project-42', 'track-2')
  })

  it('keeps quick upload as a metadata-free secondary path and summarizes partial success', async () => {
    listProjectKnowledgeDocumentsMock.mockResolvedValue(createDocumentsPayload(1))
    uploadProjectKnowledgeDocumentMock
      .mockRejectedValueOnce(new Error('upload failed'))
      .mockResolvedValueOnce({ track_id: 'track-quick' })

    const wrapper = mount(KnowledgeDocumentsPage, {
      global: {
        stubs: {
          BaseButton: { template: '<button><slot /></button>' },
          BaseDialog: { template: '<div><slot /><slot name="footer" /></div>' },
          BaseIcon: { template: '<i />' },
          ConfirmDialog: { template: '<div />' },
          BaseSelect: {
            props: ['modelValue'],
            emits: ['update:modelValue'],
            template: '<select @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>',
          },
          SurfaceCard: { template: '<section><slot /></section>' },
          PageHeader: {
            props: ['title', 'description'],
            template: '<header><h1>{{ title }}</h1><p>{{ description }}</p><slot name="actions" /></header>',
          },
          TablePageLayout: { template: '<div><slot name="filters" /><slot name="table" /><slot name="footer" /></div>' },
          FilterToolbar: { template: '<div><slot /></div>' },
          DataTable: { template: '<div><slot /></div>' },
          PaginationBar: { template: '<div />' },
          StateBanner: { props: ['title', 'description'], template: '<div><strong>{{ title }}</strong><span>{{ description }}</span></div>' },
          StatusPill: { template: '<span><slot /></span>' },
          KnowledgeWorkspaceNav: { template: '<nav />' },
          KnowledgePipelineStatusDialog: { template: '<div />' },
          KnowledgeDocumentUploadDialog: UploadDialogStub,
        },
      },
    })

    await flushPromises()

    const quickUploadInput = wrapper.get('input[type="file"]')
    Object.defineProperty(quickUploadInput.element, 'files', {
      configurable: true,
      value: [
        new File(['a'], 'quick-a.txt', { type: 'text/plain' }),
        new File(['b'], 'quick-b.txt', { type: 'text/plain' }),
      ],
    })

    await quickUploadInput.trigger('change')
    await flushPromises()

    expect(uploadProjectKnowledgeDocumentMock).toHaveBeenNthCalledWith(
      1,
      'project-42',
      expect.objectContaining({ name: 'quick-a.txt' }),
    )
    expect(uploadProjectKnowledgeDocumentMock).toHaveBeenNthCalledWith(
      2,
      'project-42',
      expect.objectContaining({ name: 'quick-b.txt' }),
    )
    expect(getProjectKnowledgeTrackStatusMock).toHaveBeenCalledWith('project-42', 'track-quick')
    expect(wrapper.text()).toContain('快速上传完成：1 份成功，1 份失败。')
  })
})
