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
  await wrapper.get("select").setValue("approve");
  await wrapper.setProps({ reviews: [first, second] });
  expect(wrapper.findAll("select")[0].element.value).toBe("approve");
  await wrapper.findAll("select")[1].setValue("approve");
  await wrapper.setProps({ reviews: [review("a", "/changed"), second] });
  expect(wrapper.findAll("select")[0].element.value).not.toBe("approve");
  expect(wrapper.findAll("select")[1].element.value).toBe("approve");
  await wrapper.setProps({ reviews: [second] });
  await wrapper.get("button").trigger("click");
  expect(Object.keys(wrapper.emitted("submit")![0][0] as object)).toEqual([
    "b",
  ]);
});
