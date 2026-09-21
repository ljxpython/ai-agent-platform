import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { nextTick } from 'vue';
import type { WorkspacePreviewResult } from '@/services/threads/workspace.service';

const { workspaceServiceMock } = vi.hoisted(() => ({
  workspaceServiceMock: {
    getWorkspacePreview: vi.fn(),
  },
}));

vi.mock('@/services/threads/workspace.service', () => workspaceServiceMock);

import WorkspacePreview from './WorkspacePreview.vue';

describe('WorkspacePreview', () => {
  const createObjectURLMock = vi.fn((blob: Blob) => `blob:mock-${blob.size}`);
  const revokeObjectURLMock = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    window.URL.createObjectURL = createObjectURLMock;
    window.URL.revokeObjectURL = revokeObjectURLMock;
  });

  it('renders markdown and toggles between preview and source mode', async () => {
    const previewResult: WorkspacePreviewResult = {
      kind: 'markdown',
      textPreview: {
        path: '/workspace/outputs/test.md',
        file_name: 'test.md',
        mime_type: 'text/markdown',
        size_bytes: 20,
        sha256: 'abc',
        preview_kind: 'markdown',
        text: '# Title Hello',
        truncated: false,
      },
    };

    const wrapper = mount(WorkspacePreview, {
      props: {
        projectId: 'proj-1',
        threadId: 'thread-1',
        path: '/workspace/outputs/test.md',
        previewResult,
        loading: false,
        error: null,
      },
      global: {
        stubs: {
          BaseIcon: true,
          SandboxedHtmlFrame: true,
        },
      },
    });

    await flushPromises();

    // 默认展示渲染态
    expect(wrapper.text()).toContain('test.md');
    expect(wrapper.html()).toContain('Title Hello');

    // 切换为源码态
    const buttons = wrapper.findAll('button');
    const sourceBtn = buttons.find((b) => b.text() === '源码');
    expect(sourceBtn).toBeDefined();
    await sourceBtn?.trigger('click');
    await nextTick();

    expect(wrapper.find('pre code').text()).toContain('# Title Hello');
  });

  it('renders download-only fallback card when kind is download and emits download event', async () => {
    const previewResult: WorkspacePreviewResult = {
      kind: 'download',
      downloadOnly: true,
    };

    const wrapper = mount(WorkspacePreview, {
      props: {
        projectId: 'proj-1',
        threadId: 'thread-1',
        path: '/workspace/outputs/archive.zip',
        previewResult,
        loading: false,
        error: null,
      },
      global: {
        stubs: {
          BaseIcon: true,
          SandboxedHtmlFrame: true,
        },
      },
    });

    await flushPromises();

    expect(wrapper.text()).toContain('此文件类型不支持在线预览');
    expect(wrapper.text()).toContain('archive.zip');

    // 点击下载原文件按钮
    const downloadBtns = wrapper.findAll('button');
    const downloadBtn = downloadBtns.find((b) => b.text().includes('下载原文件'));
    expect(downloadBtn).toBeDefined();
    await downloadBtn?.trigger('click');

    expect(wrapper.emitted('download')).toBeTruthy();
    expect(wrapper.emitted('download')?.[0]).toEqual(['/workspace/outputs/archive.zip']);
  });

  it('concurrently fetches images inside markdown and revokes Object URLs on unmount', async () => {
    const imageBlob1 = new Blob(['img-bytes-1'], { type: 'image/png' });
    const imageBlob2 = new Blob(['img-bytes-2'], { type: 'image/png' });

    workspaceServiceMock.getWorkspacePreview
      .mockResolvedValueOnce({ kind: 'image', imageBlob: imageBlob1 })
      .mockResolvedValueOnce({ kind: 'image', imageBlob: imageBlob2 });

    const previewResult: WorkspacePreviewResult = {
      kind: 'markdown',
      textPreview: {
        path: '/workspace/outputs/report.md',
        file_name: 'report.md',
        mime_type: 'text/markdown',
        size_bytes: 100,
        sha256: 'abc',
        preview_kind: 'markdown',
        text: '图表 1: ![](/workspace/charts/c1.png)\n图表 2: ![](/workspace/charts/c2.png)',
        truncated: false,
      },
    };

    const wrapper = mount(WorkspacePreview, {
      props: {
        projectId: 'proj-1',
        threadId: 'thread-1',
        path: '/workspace/outputs/report.md',
        previewResult,
        loading: false,
        error: null,
      },
      global: {
        stubs: {
          BaseIcon: true,
          SandboxedHtmlFrame: true,
        },
      },
    });

    await flushPromises();

    // 验证发起了两次图片拉取
    expect(workspaceServiceMock.getWorkspacePreview).toHaveBeenCalledTimes(2);
    expect(createObjectURLMock).toHaveBeenCalledTimes(2);

    // 卸载组件，验证 Object URLs 全部被安全释放
    wrapper.unmount();
    expect(revokeObjectURLMock).toHaveBeenCalledTimes(2);
  });
});
