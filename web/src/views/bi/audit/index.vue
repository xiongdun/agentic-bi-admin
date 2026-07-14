<script setup lang="ts">
import { $t } from '@/locales';
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-12px">
    <NCard :bordered="false" size="small" class="card-wrapper">
      <div class="text-16px font-medium">{{ $t('route.bi_audit') }}</div>
      <div class="text-12px text-gray-500 mt-4px">{{ $t('common.lookForward') }}</div>
    </NCard>
  </div>
</template>

<style scoped></style>
