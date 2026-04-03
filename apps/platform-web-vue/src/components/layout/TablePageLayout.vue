<template>
  <div class="pw-table-page">
    <div
      v-if="$slots.actions"
      class="flex-shrink-0"
    >
      <slot name="actions" />
    </div>

    <div
      v-if="$slots.filters"
      class="flex-shrink-0"
    >
      <slot name="filters" />
    </div>

    <div class="min-h-0 flex-1">
      <div class="pw-table-frame h-full">
        <slot name="table" />
      </div>
    </div>

    <div
      v-if="$slots.footer"
      class="flex-shrink-0"
    >
      <slot name="footer" />
    </div>
  </div>
</template>
