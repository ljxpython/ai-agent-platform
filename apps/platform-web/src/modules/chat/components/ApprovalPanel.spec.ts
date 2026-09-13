import { mount } from "@vue/test-utils";
import { expect, it } from "vitest";
import ApprovalPanel from "./ApprovalPanel.vue";
import { parseReviews } from "../approvals";

it("keeps unchanged decisions, resets changed requests and removes departed requests", async () => {
  const review = (id: string, path: string) =>
    parseReviews([
      {
        id,
        value: {
          action_requests: [{ name: "write_file", args: { path } }],
          review_configs: [
            {
              action_name: "write_file",
              allowed_decisions: ["approve", "reject"],
            },
          ],
        },
      },
    ])[0];
  const first = review("a", "/a");
  const second = review("b", "/b");
  const wrapper = mount(ApprovalPanel, {
    props: { reviews: [first], disabled: false },
  });

  // 点击第一个 review 的批准药丸
  await wrapper.get('[data-action="approve"]').trigger("click");
  await wrapper.setProps({ reviews: [first, second] });

  // 第一个保持批准（高亮），第二个尚未批准
  const approvePills = wrapper.findAll('[data-action="approve"]');
  expect(approvePills[0].classes()).toContain("border-emerald-500");

  // 点击第二个 review 的批准药丸
  await approvePills[1].trigger("click");
  expect(wrapper.findAll('[data-action="approve"]')[1].classes()).toContain("border-emerald-500");

  // 修改第一个 review 的参数触发重置
  await wrapper.setProps({ reviews: [review("a", "/changed"), second] });
  const updatedApprovePills = wrapper.findAll('[data-action="approve"]');
  expect(updatedApprovePills[0].classes()).not.toContain("border-emerald-500");
  expect(updatedApprovePills[1].classes()).toContain("border-emerald-500");

  // 只保留 second 提交
  await wrapper.setProps({ reviews: [second] });
  await wrapper.get("button").trigger("click");
  expect(Object.keys(wrapper.emitted("submit")![0][0] as object)).toEqual([
    "b",
  ]);
});

it("renders code diff view for edit_file with old and new string", async () => {
  const review = parseReviews([
    {
      id: "review-edit-1",
      value: {
        action_requests: [
          {
            name: "edit_file",
            args: {
              file_path: "/workspace/report.py",
              old_string: "price",
              new_string: "price * qty",
            },
          },
        ],
        review_configs: [
          {
            action_name: "edit_file",
            allowed_decisions: ["approve", "edit", "reject"],
          },
        ],
      },
    },
  ])[0];

  const wrapper = mount(ApprovalPanel, {
    props: { reviews: [review], disabled: false },
    global: {
      stubs: {
        BaseIcon: true,
      },
    },
  });

  expect(wrapper.text()).toContain("修改代码文件");
  expect(wrapper.text()).toContain("/workspace/report.py");
  expect(wrapper.text()).toContain("- 原代码片段");
  expect(wrapper.text()).toContain("+ 新代码片段");
  expect(wrapper.text()).toContain("price");
  expect(wrapper.text()).toContain("price * qty");

  // 点击快捷批准药丸
  const approvePill = wrapper.find('[data-action="approve"]');
  expect(approvePill.exists()).toBe(true);
  expect(approvePill.text()).toContain("批准 (Approve)");
  await approvePill.trigger("click");

  expect(approvePill.classes()).toContain("border-emerald-500");
  expect(wrapper.text()).toContain("确认批准所选操作");
});

it("renders write_file preview with content and path", async () => {
  const review = parseReviews([
    {
      id: "review-write-1",
      value: {
        action_requests: [
          {
            name: "write_file",
            args: {
              file_path: "/workspace/report.py",
              content: "import csv\nprint('hello')",
            },
          },
        ],
        review_configs: [
          {
            action_name: "write_file",
            allowed_decisions: ["approve", "reject"],
          },
        ],
      },
    },
  ])[0];

  const wrapper = mount(ApprovalPanel, {
    props: { reviews: [review], disabled: false },
    global: {
      stubs: {
        BaseIcon: true,
      },
    },
  });

  expect(wrapper.text()).toContain("写入文件");
  expect(wrapper.text()).toContain("/workspace/report.py");
  expect(wrapper.text()).toContain("文件内容预览");
  expect(wrapper.text()).toContain("import csv\nprint('hello')");
});

