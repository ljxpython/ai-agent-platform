import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { listUsersPageMock, deleteUserMock, pushToastMock } = vi.hoisted(() => ({
  listUsersPageMock: vi.fn(),
  deleteUserMock: vi.fn(),
  pushToastMock: vi.fn(),
}));

vi.mock("@/services/users/users.service", () => ({
  listUsersPage: listUsersPageMock,
  deleteUser: deleteUserMock,
}));

vi.mock("@/stores/ui", () => ({
  useUiStore: () => ({ pushToast: pushToastMock }),
}));

vi.mock("@/stores/auth", () => ({
  useAuthStore: () => ({
    user: { id: "admin-1", username: "admin" },
  }),
}));

vi.mock("@/composables/useAuthorization", () => ({
  useAuthorization: () => ({ can: () => true }),
}));

vi.mock("vue-router", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

import UsersPage from "./UsersPage.vue";

describe("UsersPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listUsersPageMock.mockResolvedValue({
      items: [
        {
          id: "admin-1",
          username: "admin",
          email: "admin@example.com",
          status: "active",
          is_super_admin: true,
          platform_roles: ["platform_super_admin"],
          created_at: "2026-10-01T00:00:00Z",
        },
        {
          id: "user-2",
          username: "bob",
          email: "bob@example.com",
          status: "active",
          is_super_admin: false,
          platform_roles: ["platform_viewer"],
          created_at: "2026-10-02T00:00:00Z",
        },
      ],
      total: 2,
    });
    deleteUserMock.mockResolvedValue({ ok: true });
  });

  it("renders user list and provides soft-delete guardrails", async () => {
    const wrapper = mount(UsersPage, {
      global: {
        stubs: {
          BaseButton: {
            props: ["disabled"],
            template: '<button :disabled="disabled"><slot /></button>',
          },
          BaseSelect: {
            props: ["modelValue"],
            template: '<select :value="modelValue"><slot /></select>',
          },
          BaseIcon: true,
          MetricCard: true,
          SearchInput: true,
          StatusPill: {
            props: ["tone"],
            template: '<span class="status-pill"><slot /></span>',
          },
          ActionMenu: {
            props: ["items"],
            template: `
              <div class="action-menu">
                <button
                  v-for="item in items"
                  :key="item.key"
                  :class="['menu-item-' + item.key]"
                  :disabled="item.disabled"
                  @click="item.onSelect && item.onSelect()"
                >
                  {{ item.label }}
                </button>
              </div>
            `,
          },
          ConfirmDialog: {
            props: ["show", "title", "message"],
            emits: ["confirm", "cancel"],
            template: `
              <div v-if="show" class="confirm-dialog">
                <p>{{ message }}</p>
                <button class="confirm-btn" @click="$emit('confirm')">Confirm</button>
                <button class="cancel-btn" @click="$emit('cancel')">Cancel</button>
              </div>
            `,
          },
          DataTable: {
            props: ["rows", "columns"],
            template: `
              <table>
                <tbody>
                  <tr v-for="row in rows" :key="row.id">
                    <td><slot name="cell-username" :row="row" /></td>
                    <td><slot name="cell-actions" :row="row" /></td>
                  </tr>
                </tbody>
              </table>
            `,
          },
          TablePageLayout: {
            template:
              '<div><slot name="filters" /><slot name="actions" /><slot name="table" /><slot /></div>',
          },
          FilterToolbar: {
            template: "<div><slot /></div>",
          },
          BulkActionsBar: true,
          PaginationBar: true,
          PageHeader: true,
        },
      },
    });

    await flushPromises();

    // 验证列表拉取了 2 个用户
    expect(listUsersPageMock).toHaveBeenCalled();

    // 找到所有的删除按钮
    const deleteButtons = wrapper.findAll(".menu-item-delete");
    expect(deleteButtons).toHaveLength(2);

    // 第一个用户是 admin-1（当前操作者自己），删除按钮必须 disabled，且文字为“不能删除当前登录账号”
    expect(deleteButtons[0].attributes("disabled")).toBeDefined();
    expect(deleteButtons[0].text()).toContain("不能删除当前登录账号");

    // 第二个用户是 user-2（bob），删除按钮可用，文字为“删除用户”
    expect(deleteButtons[1].attributes("disabled")).toBeUndefined();
    expect(deleteButtons[1].text()).toContain("删除用户");

    // 点击第二个用户的删除按钮，应弹出 ConfirmDialog
    expect(wrapper.find(".confirm-dialog").exists()).toBe(false);
    await deleteButtons[1].trigger("click");
    expect(wrapper.find(".confirm-dialog").exists()).toBe(true);
    expect(wrapper.find(".confirm-dialog").text()).toContain("bob");

    // 点击确认删除
    await wrapper.find(".confirm-btn").trigger("click");
    await flushPromises();

    // 验证调用了 deleteUser('user-2') 并弹出了 success Toast
    expect(deleteUserMock).toHaveBeenCalledWith("user-2");
    expect(pushToastMock).toHaveBeenCalledWith(
      expect.objectContaining({
        type: "success",
        title: "用户已删除",
      }),
    );
  });
});
