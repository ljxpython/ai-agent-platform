<script setup lang="ts">
import { ref, watch } from "vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import {
  describeCron,
  parseCron,
  serializeCron,
  WEEKDAYS,
  ZH_WEEKDAY,
  type CronParts,
  type CronPreset,
  type Weekday,
} from "../utils/cron";

const props = defineProps<{
  modelValue: string;
  disabled?: boolean;
}>();

const emit = defineEmits<{
  (e: "update:modelValue", value: string): void;
}>();

const preset = ref<CronPreset>("daily");
const hour = ref(9);
const minute = ref(0);
const weekdays = ref<Weekday[]>(["mon", "wed", "fri"]);
const dayOfMonth = ref(1);
const rawCron = ref("0 9 * * *");

let internalChange = false;

function syncFromValue(val: string) {
  if (!val) return;
  const parsed = parseCron(val);
  preset.value = parsed.preset;
  if (parsed.preset === "custom") {
    rawCron.value = parsed.parts.raw || val;
  } else {
    hour.value = parsed.parts.hour ?? 9;
    minute.value = parsed.parts.minute ?? 0;
    if (parsed.parts.weekdays) weekdays.value = parsed.parts.weekdays;
    if (parsed.parts.dayOfMonth) dayOfMonth.value = parsed.parts.dayOfMonth;
  }
}

watch(
  () => props.modelValue,
  (val) => {
    if (internalChange) return;
    syncFromValue(val);
  },
  { immediate: true },
);

function emitCron() {
  internalChange = true;
  let expr = "";
  if (preset.value === "custom") {
    expr = rawCron.value.trim() || "0 9 * * *";
  } else {
    const parts: CronParts = {
      hour: hour.value,
      minute: minute.value,
      weekdays: weekdays.value,
      dayOfMonth: dayOfMonth.value,
    };
    expr = serializeCron(preset.value, parts);
  }
  emit("update:modelValue", expr);
  setTimeout(() => {
    internalChange = false;
  }, 0);
}

function selectPreset(p: CronPreset) {
  if (props.disabled) return;
  preset.value = p;
  emitCron();
}

function toggleWeekday(w: Weekday) {
  if (props.disabled) return;
  if (weekdays.value.includes(w)) {
    if (weekdays.value.length > 1) {
      weekdays.value = weekdays.value.filter((d) => d !== w);
    }
  } else {
    weekdays.value = [...weekdays.value, w];
  }
  emitCron();
}
</script>

<template>
  <div class="space-y-3">
    <!-- 预设分段选择器 -->
    <div
      class="flex flex-wrap rounded-xl bg-surface-subtle p-1 border border-border/60 gap-0.5"
    >
      <button
        v-for="(pName, pKey) in {
          hourly: '每小时',
          daily: '每天',
          weekly: '每周',
          monthly: '每月',
          custom: '自定义',
        }"
        :key="pKey"
        type="button"
        class="flex-1 py-1 px-2 text-xs font-medium rounded-lg transition-all text-center select-none"
        :class="
          preset === pKey
            ? 'bg-surface text-foreground shadow-xs font-semibold dark:bg-dark-800'
            : 'text-muted-foreground hover:text-foreground'
        "
        :disabled="disabled"
        @click="selectPreset(pKey as CronPreset)"
      >
        {{ pName }}
      </button>
    </div>

    <!-- 预设详细配置面板 -->
    <div
      class="rounded-xl border border-border/70 bg-surface/90 p-3.5 space-y-3.5 shadow-xs dark:bg-dark-900/80"
    >
      <!-- 每周选择星期 -->
      <div v-if="preset === 'weekly'" class="space-y-2">
        <div class="text-[11px] text-muted-foreground font-medium">
          执行星期
        </div>
        <div class="grid grid-cols-7 gap-1">
          <button
            v-for="w in WEEKDAYS"
            :key="w"
            type="button"
            class="py-1.5 text-xs rounded-lg border transition-all text-center font-medium"
            :class="
              weekdays.includes(w)
                ? 'border-primary bg-primary/10 text-primary shadow-xs'
                : 'border-border/60 bg-surface text-muted-foreground hover:border-border hover:text-foreground dark:bg-dark-800'
            "
            :disabled="disabled"
            @click="toggleWeekday(w)"
          >
            {{ ZH_WEEKDAY[w] }}
          </button>
        </div>
      </div>

      <!-- 每月选择几号 -->
      <div v-if="preset === 'monthly'" class="flex items-center gap-2 text-xs">
        <span class="text-muted-foreground">每月第</span>
        <input
          v-model.number="dayOfMonth"
          type="number"
          min="1"
          max="31"
          class="w-16 h-8 px-2 text-xs text-center border rounded-lg bg-surface border-border/80 focus:border-primary font-mono"
          :disabled="disabled"
          @change="emitCron"
        />
        <span class="text-muted-foreground">日</span>
      </div>

      <!-- 时间选择（时:分） -->
      <div v-if="preset !== 'custom'" class="flex items-center gap-2 text-xs">
        <span class="text-muted-foreground">触发时刻:</span>
        <div v-if="preset !== 'hourly'" class="flex items-center gap-1">
          <input
            v-model.number="hour"
            type="number"
            min="0"
            max="23"
            class="w-14 h-8 px-2 text-xs text-center border rounded-lg bg-surface border-border/80 focus:border-primary font-mono"
            :disabled="disabled"
            @change="emitCron"
          />
          <span class="text-muted-foreground">时</span>
        </div>
        <div class="flex items-center gap-1">
          <input
            v-model.number="minute"
            type="number"
            min="0"
            max="59"
            class="w-14 h-8 px-2 text-xs text-center border rounded-lg bg-surface border-border/80 focus:border-primary font-mono"
            :disabled="disabled"
            @change="emitCron"
          />
          <span class="text-muted-foreground">分</span>
        </div>
      </div>

      <!-- 自定义表达式输入 -->
      <div v-else class="space-y-1.5">
        <div class="text-[11px] text-muted-foreground font-medium">
          5 字段 Cron 表达式（分 时 日 月 周）
        </div>
        <input
          v-model="rawCron"
          type="text"
          placeholder="例如 0 9 * * *"
          class="w-full h-8.5 px-3 text-xs font-mono border rounded-lg bg-surface border-border/80 focus:border-primary"
          :disabled="disabled"
          @input="emitCron"
        />
      </div>

      <!-- 人话描述条目 -->
      <div
        class="flex items-center justify-between text-xs pt-2 border-t border-border/40"
      >
        <span class="text-muted-foreground flex items-center gap-1">
          <BaseIcon name="info" size="xs" />
          <span>解析描述:</span>
        </span>
        <span class="font-semibold text-foreground font-mono">{{
          describeCron(modelValue)
        }}</span>
      </div>
    </div>
  </div>
</template>
