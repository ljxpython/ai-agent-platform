import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { createUserMock, listProjectsMock, accessMock, bindMock } = vi.hoisted(() => ({
  createUserMock: vi.fn(),
  listProjectsMock: vi.fn(),
  accessMock: vi.fn(),
  bindMock: vi.fn()
}))
vi.mock('@/services/projects/projects.service', () => ({
  listProjects: listProjectsMock,
  getProjectAccess: accessMock
}))
vi.mock('@/services/members/members.service', () => ({
  upsertProjectMember: bindMock
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() })
}))

vi.mock('@/composables/useAuthorization', () => ({
  useAuthorization: () => ({ can: () => true })
}))

vi.mock('@/services/users/users.service', () => ({
  createUser: createUserMock
}))

import UserCreatePage from './UserCreatePage.vue'

describe('UserCreatePage', () => {
  beforeEach(() => {
    createUserMock.mockReset()
    listProjectsMock.mockResolvedValue([
      { id: 'p1', name: 'Project 1' },
      { id: 'p2', name: 'Project 2' }
    ])
    accessMock.mockResolvedValue({ project_id: 'p1', permissions: ['project.member.write'] })
    bindMock.mockReset()
  })

  it('creates user and assigns multiple projects in a single form flow', async () => {
    createUserMock.mockResolvedValue({ id: 'u1', username: 'new-user' })
    bindMock.mockResolvedValue({ user_id: 'u1', role: 'project_executor' })

    const wrapper = mount(UserCreatePage, {
      global: {
        stubs: {
          BaseButton: {
            props: ['disabled'],
            template: '<button :disabled="disabled"><slot /></button>'
          },
          BaseSelect: {
            props: ['modelValue', 'options', 'disabled'],
            emits: ['update:modelValue'],
            template:
              '<select :value="modelValue" :disabled="disabled" @change="$emit(\'update:modelValue\', $event.target.value)"><option v-for="option in options" :value="option.value">{{ option.label }}</option></select>'
          },
          BaseIcon: true,
          MetricCard: true,
          PageHeader: { template: '<header><slot name="actions" /></header>' },
          SurfaceCard: { template: '<section><slot /></section>' },
          StateBanner: { props: ['title', 'description'], template: '<p>{{ title }} {{ description }}</p>' }
        }
      }
    })

    await flushPromises()

    await wrapper.get('input[placeholder="请输入用户名"]').setValue('new-user')
    await wrapper.get('input[placeholder="请输入至少 8 位密码"]').setValue('password123')
    await wrapper.get('input[placeholder="请再次输入密码"]').setValue('password123')

    // Click "添加项目" to add a project assignment row
    const addProjectBtn = wrapper.findAll('button').find((b) => b.text().includes('添加项目') || b.text().includes('关联项目'))!
    await addProjectBtn.trigger('click')
    await flushPromises()

    // Select project p1 in the dynamically added select
    const selects = wrapper.findAll('select')
    const projectSelect = selects[1] // 0 is platformRole, 1 is project, 2 is projectRole
    await projectSelect.setValue('p1')
    await flushPromises()

    // Submit form
    const submitBtn = wrapper.findAll('button').find((b) => b.text().includes('创建用户'))!
    await submitBtn.trigger('click')
    await flushPromises()

    expect(createUserMock).toHaveBeenCalledTimes(1)
    expect(createUserMock).toHaveBeenCalledWith({
      username: 'new-user',
      password: 'password123',
      platform_roles: [],
      is_super_admin: false
    })

    expect(bindMock).toHaveBeenCalledTimes(1)
    expect(bindMock).toHaveBeenCalledWith({
      projectId: 'p1',
      userId: 'u1',
      role: 'project_executor'
    })
    expect(wrapper.text()).toContain('已创建用户：new-user，并成功加入 1 个项目')
  })

  it('keeps the created account and shows error if project binding fails', async () => {
    createUserMock.mockResolvedValue({ id: 'u2', username: 'fail-bind-user' })
    bindMock.mockRejectedValue(new Error('project locked'))

    const wrapper = mount(UserCreatePage, {
      global: {
        stubs: {
          BaseButton: { props: ['disabled'], template: '<button :disabled="disabled"><slot /></button>' },
          BaseSelect: {
            props: ['modelValue', 'options', 'disabled'],
            emits: ['update:modelValue'],
            template:
              '<select :value="modelValue" :disabled="disabled" @change="$emit(\'update:modelValue\', $event.target.value)"><option v-for="option in options" :value="option.value">{{ option.label }}</option></select>'
          },
          BaseIcon: true,
          MetricCard: true,
          PageHeader: { template: '<header><slot name="actions" /></header>' },
          SurfaceCard: { template: '<section><slot /></section>' },
          StateBanner: { props: ['title', 'description'], template: '<p>{{ title }} {{ description }}</p>' }
        }
      }
    })

    await flushPromises()

    await wrapper.get('input[placeholder="请输入用户名"]').setValue('fail-bind-user')
    await wrapper.get('input[placeholder="请输入至少 8 位密码"]').setValue('password123')
    await wrapper.get('input[placeholder="请再次输入密码"]').setValue('password123')

    const addProjectBtn = wrapper.findAll('button').find((b) => b.text().includes('添加项目') || b.text().includes('关联项目'))!
    await addProjectBtn.trigger('click')
    await flushPromises()

    const projectSelect = wrapper.findAll('select')[1]
    await projectSelect.setValue('p1')
    await flushPromises()

    const submitBtn = wrapper.findAll('button').find((b) => b.text().includes('创建用户'))!
    await submitBtn.trigger('click')
    await flushPromises()

    expect(createUserMock).toHaveBeenCalledTimes(1)
    expect(bindMock).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('用户 fail-bind-user 已创建成功，但有 1 个项目绑定失败')
  })

  it('allows removing an added project assignment row', async () => {
    const wrapper = mount(UserCreatePage, {
      global: {
        stubs: {
          BaseButton: { props: ['disabled'], template: '<button :disabled="disabled"><slot /></button>' },
          BaseSelect: true,
          BaseIcon: true,
          MetricCard: true,
          PageHeader: true,
          SurfaceCard: { template: '<section><slot /></section>' }
        }
      }
    })

    await flushPromises()

    const addBtn = wrapper.findAll('button').find((b) => b.text().includes('添加项目') || b.text().includes('关联项目'))!
    await addBtn.trigger('click')
    await flushPromises()
    expect(wrapper.findAll('button[title="移除此项目"]').length).toBe(1)

    // Remove row
    await wrapper.find('button[title="移除此项目"]').trigger('click')
    await flushPromises()
    expect(wrapper.findAll('button[title="移除此项目"]').length).toBe(0)
  })

  it('rejects passwords shorter than the API minimum before submitting', async () => {
    const wrapper = mount(UserCreatePage, {
      global: {
        stubs: {
          BaseButton: {
            props: ['disabled'],
            template: '<button :disabled="disabled"><slot /></button>'
          },
          BaseIcon: true,
          BaseSelect: true,
          MetricCard: true,
          PageHeader: { template: '<header><slot name="actions" /></header>' },
          StateBanner: {
            props: ['title', 'description'],
            template: '<div>{{ title }}：{{ description }}</div>'
          },
          SurfaceCard: { template: '<section><slot /></section>' }
        }
      }
    })

    await wrapper.get('input[placeholder="请输入用户名"]').setValue('test1')
    const passwordInput = wrapper.get('input[placeholder="请输入至少 8 位密码"]')
    await passwordInput.setValue('test')
    await wrapper.get('input[placeholder="请再次输入密码"]').setValue('test')
    const buttons = wrapper.findAll('button')
    await buttons[buttons.length - 1].trigger('click')

    expect(passwordInput.attributes('minlength')).toBe('8')
    expect(wrapper.text()).toContain('密码至少需要 8 个字符')
    expect(createUserMock).not.toHaveBeenCalled()
  })

  it('rejects submission when password confirmation does not match', async () => {
    const wrapper = mount(UserCreatePage, {
      global: {
        stubs: {
          BaseButton: {
            props: ['disabled'],
            template: '<button :disabled="disabled"><slot /></button>'
          },
          BaseIcon: true,
          BaseSelect: true,
          MetricCard: true,
          PageHeader: { template: '<header><slot name="actions" /></header>' },
          StateBanner: {
            props: ['title', 'description'],
            template: '<div>{{ title }}：{{ description }}</div>'
          },
          SurfaceCard: { template: '<section><slot /></section>' }
        }
      }
    })

    await wrapper.get('input[placeholder="请输入用户名"]').setValue('testuser')
    await wrapper.get('input[placeholder="请输入至少 8 位密码"]').setValue('password123')
    await wrapper.get('input[placeholder="请再次输入密码"]').setValue('password456')
    const buttons = wrapper.findAll('button')
    await buttons[buttons.length - 1].trigger('click')

    expect(wrapper.text()).toContain('两次输入的密码不一致')
    expect(createUserMock).not.toHaveBeenCalled()
  })

  it('configures autocomplete and name attributes to prevent browser autofill on new user creation', () => {
    const wrapper = mount(UserCreatePage, {
      global: {
        stubs: {
          BaseButton: true,
          BaseIcon: true,
          BaseSelect: true,
          MetricCard: true,
          PageHeader: true,
          StateBanner: true,
          SurfaceCard: { template: '<section><slot /></section>' }
        }
      }
    })

    const usernameInput = wrapper.get('input[placeholder="请输入用户名"]')
    const passwordInput = wrapper.get('input[placeholder="请输入至少 8 位密码"]')
    const confirmPasswordInput = wrapper.get('input[placeholder="请再次输入密码"]')

    expect(usernameInput.attributes('autocomplete')).toBe('off')
    expect(usernameInput.attributes('name')).toBe('new_username')
    expect(passwordInput.attributes('autocomplete')).toBe('new-password')
    expect(passwordInput.attributes('name')).toBe('new_password')
    expect(confirmPasswordInput.attributes('autocomplete')).toBe('new-password')
    expect(confirmPasswordInput.attributes('name')).toBe('confirm_password')
  })
})
