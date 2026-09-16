<script setup lang="ts">
import { reactive, ref } from "vue";
import type { PendingClarification } from "../human-input";
import {
  normalizeClarificationValues,
  validateClarificationValues,
} from "../human-input";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";

const props = defineProps<{
  clarification: PendingClarification;
  submitting?: boolean;
}>();

const emit = defineEmits<{
  (e: "submit", values: Record<string, unknown>): void;
}>();

// Initialize form values with type-aware defaults
const formValues = reactive<Record<string, any>>({});
for (const field of props.clarification.request.fields) {
  if (field.default !== undefined) {
    formValues[field.name] = field.default;
  } else if (field.type === "checkbox") {
    formValues[field.name] = false;
  } else if (field.type === "multi_select") {
    formValues[field.name] = [];
  } else if (field.type === "select" && field.options?.[0]) {
    formValues[field.name] = field.options[0].value;
  } else {
    formValues[field.name] = "";
  }
}

const formErrors = ref<Record<string, string>>({});

function handleSubmit() {
  const errors = validateClarificationValues(
    props.clarification.request.fields,
    formValues,
  );
  formErrors.value = errors;
  if (Object.keys(errors).length > 0) {
    return;
  }
  const normalized = normalizeClarificationValues(
    props.clarification.request.fields,
    formValues,
  );
  emit("submit", normalized);
}
</script>

<template>
  <div
    class="my-3 overflow-hidden rounded-xl border border-amber-200/80 bg-amber-50/40 p-4 shadow-sm transition-all dark:border-amber-900/60 dark:bg-amber-950/20"
    data-testid="clarification-card"
  >
    <!-- Header -->
    <div class="flex items-start gap-3">
      <div
        class="mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg bg-amber-500/10 text-amber-600 dark:bg-amber-500/20 dark:text-amber-400"
      >
        <BaseIcon name="info" class="h-4 w-4" />
      </div>
      <div class="min-w-0 flex-1">
        <h4
          class="text-sm font-semibold text-zinc-900 dark:text-zinc-100"
          data-testid="clarification-question"
        >
          {{ clarification.request.question }}
        </h4>
        <p
          v-if="clarification.request.context"
          class="mt-1 text-xs leading-relaxed text-zinc-600 dark:text-zinc-400"
        >
          {{ clarification.request.context }}
        </p>
      </div>
    </div>

    <!-- Unsupported Tip -->
    <div
      v-if="!clarification.supported"
      class="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-400"
    >
      当前包含暂不支持的输入字段类型，请刷新或重试。
    </div>

    <!-- Fields Form -->
    <form
      v-else
      class="mt-4 space-y-3.5"
      @submit.prevent="handleSubmit"
    >
      <div
        v-for="field in clarification.request.fields"
        :key="field.name"
        class="space-y-1"
      >
        <label
          v-if="field.type !== 'checkbox'"
          :for="'field-' + field.name"
          class="flex items-center text-xs font-medium text-zinc-700 dark:text-zinc-300"
        >
          <span>{{ field.label || field.name }}</span>
          <span v-if="field.required" class="ml-1 text-red-500">*</span>
        </label>

        <!-- Description -->
        <p
          v-if="field.description && field.type !== 'checkbox'"
          class="text-[11px] text-zinc-500 dark:text-zinc-400"
        >
          {{ field.description }}
        </p>

        <!-- 1. Select Field -->
        <div v-if="field.type === 'select'">
          <select
            :id="'field-' + field.name"
            v-model="formValues[field.name]"
            :disabled="submitting"
            class="block w-full rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-800 shadow-sm transition-colors focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500 disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200"
            :class="{
              'border-red-400 dark:border-red-600': formErrors[field.name],
            }"
          >
            <option
              v-for="opt in field.options || []"
              :key="opt.value"
              :value="opt.value"
            >
              {{ opt.label }}
            </option>
          </select>
        </div>

        <!-- 2. Textarea Field -->
        <div v-else-if="field.type === 'textarea'">
          <textarea
            :id="'field-' + field.name"
            v-model="formValues[field.name]"
            :rows="3"
            :placeholder="field.placeholder || ''"
            :disabled="submitting"
            class="block w-full rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-800 shadow-sm transition-colors focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500 disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200"
            :class="{
              'border-red-400 dark:border-red-600': formErrors[field.name],
            }"
          />
        </div>

        <!-- 3. Number Field -->
        <div v-else-if="field.type === 'number'">
          <input
            :id="'field-' + field.name"
            v-model="formValues[field.name]"
            type="number"
            :placeholder="field.placeholder || ''"
            :disabled="submitting"
            class="block w-full rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-800 shadow-sm transition-colors focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500 disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200"
            :class="{
              'border-red-400 dark:border-red-600': formErrors[field.name],
            }"
          />
        </div>

        <!-- 4. Date Field -->
        <div v-else-if="field.type === 'date'">
          <input
            :id="'field-' + field.name"
            v-model="formValues[field.name]"
            type="date"
            :disabled="submitting"
            class="block w-full rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-800 shadow-sm transition-colors focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500 disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200"
            :class="{
              'border-red-400 dark:border-red-600': formErrors[field.name],
            }"
          />
        </div>

        <!-- 5. Checkbox Field (false is valid) -->
        <div v-else-if="field.type === 'checkbox'" class="pt-1 pb-1">
          <label class="inline-flex items-center gap-2 cursor-pointer select-none">
            <input
              :id="'field-' + field.name"
              v-model="formValues[field.name]"
              type="checkbox"
              :disabled="submitting"
              class="h-4 w-4 rounded border-zinc-300 text-amber-600 focus:ring-amber-500 dark:border-zinc-700 dark:bg-zinc-800"
            />
            <span class="text-xs font-medium text-zinc-800 dark:text-zinc-200">
              {{ field.label || field.name }}
              <span v-if="field.required" class="ml-0.5 text-red-500">*</span>
            </span>
          </label>
          <p
            v-if="field.description"
            class="mt-0.5 pl-6 text-[11px] text-zinc-500 dark:text-zinc-400"
          >
            {{ field.description }}
          </p>
        </div>

        <!-- 6. Multi-select Field -->
        <div v-else-if="field.type === 'multi_select'" class="space-y-1.5">
          <div class="flex flex-wrap gap-2 pt-0.5">
            <label
              v-for="opt in field.options || []"
              :key="opt.value"
              class="inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs cursor-pointer select-none transition-colors"
              :class="[
                Array.isArray(formValues[field.name]) && (formValues[field.name] as string[]).includes(opt.value)
                  ? 'border-amber-500 bg-amber-50 font-medium text-amber-900 dark:border-amber-600 dark:bg-amber-950/40 dark:text-amber-200'
                  : 'border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300',
                submitting ? 'opacity-50 cursor-not-allowed' : ''
              ]"
            >
              <input
                v-model="formValues[field.name]"
                type="checkbox"
                :value="opt.value"
                :disabled="submitting"
                class="rounded border-zinc-300 text-amber-600 focus:ring-amber-500 dark:border-zinc-600 dark:bg-zinc-700"
              />
              <span>{{ opt.label }}</span>
            </label>
          </div>
        </div>

        <!-- 7. Plain Text Field (default) -->
        <div v-else>
          <input
            :id="'field-' + field.name"
            v-model="formValues[field.name]"
            type="text"
            :placeholder="field.placeholder || ''"
            :disabled="submitting"
            class="block w-full rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-800 shadow-sm transition-colors focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500 disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200"
            :class="{
              'border-red-400 dark:border-red-600': formErrors[field.name],
            }"
          />
        </div>

        <!-- Field Error -->
        <p
          v-if="formErrors[field.name]"
          class="text-[11px] text-red-600 dark:text-red-400"
          data-testid="field-error"
        >
          {{ formErrors[field.name] }}
        </p>
      </div>

      <!-- Action Buttons -->
      <div class="mt-4 flex items-center justify-end gap-2 pt-1">
        <BaseButton
          type="submit"
          size="sm"
          variant="primary"
          :loading="submitting"
          data-testid="clarification-submit-button"
        >
          提交答复
        </BaseButton>
      </div>
    </form>
  </div>
</template>
