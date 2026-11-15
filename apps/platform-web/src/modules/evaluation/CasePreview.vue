<script setup lang="ts">
import {
  evaluationCheckLabels as names,
  type EvaluationCase,
} from "@/services/evaluation/workbench";
defineProps<{ test: EvaluationCase }>();
function readable(value: unknown): string {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map(readable).join("；");
  if (value && typeof value === "object")
    return Object.entries(value)
      .filter(([, part]) => part != null)
      .map(([key, part]) => `${names[key] || key}：${readable(part)}`)
      .join("；");
  return String(value);
}
</script>
<template>
  <div class="space-y-3 text-sm">
    <p v-if="test.business_rules?.length">
      业务口径：{{ test.business_rules.join("；") }}
    </p>
    <ol class="list-decimal space-y-3 pl-5">
      <li v-for="(turn, index) in test.turns" :key="index">
        <p class="whitespace-pre-wrap">提问：{{ turn.content }}</p>
        <p v-if="test.turn_expectations?.[index]" class="mt-1">
          预期：{{
            test.turn_expectations[index]?.answer_equals != null
              ? `只输出 ${test.turn_expectations[index]?.answer_equals}（忽略首尾空白）`
              : test.turn_expectations[index]?.answer_contains.join("；")
          }}
          <span v-if="test.turn_expectations[index]?.answer_excludes.length"
            >；不得出现：{{
              test.turn_expectations[index]?.answer_excludes.join("；")
            }}</span
          >
        </p>
        <p
          v-if="turn.approval || turn.approval_mode === 'live'"
          class="text-amber-700"
        >
          {{
            turn.approval_mode === "live"
              ? "运行时等待指定评审人决定"
              : turn.approval === "approve"
                ? "预设批准允许的测试操作"
                : "预设拒绝测试操作"
          }}
        </p>
      </li>
    </ol>
    <p v-if="test.expectations.answer_contains?.length">
      答案必须包含：{{ test.expectations.answer_contains.join("；") }}
    </p>
    <p v-if="test.expectations.rubric" class="whitespace-pre-wrap">
      评分标准：{{ test.expectations.rubric }}
    </p>
    <p v-if="test.expectations.max_tool_calls != null">
      工具调用上限：{{ test.expectations.max_tool_calls }}
    </p>
    <ul class="space-y-2">
      <li
        v-for="(check, path) in (test.expectations.artifacts as Record<
          string,
          unknown
        >) || {}"
        :key="path"
      >
        文件 {{ path }}：{{ readable(check) }}
      </li>
    </ul>
    <p>
      检查：{{
        test.metrics
          .map(
            (m) =>
              `${names[m.name] || m.name}${m.hard_gate ? "（必须通过）" : ""}`,
          )
          .join("、")
      }}
    </p>
    <details v-if="Object.keys(test.fixture).length">
      <summary class="cursor-pointer">
        查看本题使用的合成文件（{{ Object.keys(test.fixture).length }}个）
      </summary>
      <div v-for="(content, path) in test.fixture" :key="path" class="mt-3">
        <strong>{{ path }}</strong>
        <pre class="overflow-auto whitespace-pre-wrap break-words">{{
          content
        }}</pre>
      </div>
    </details>
  </div>
</template>
