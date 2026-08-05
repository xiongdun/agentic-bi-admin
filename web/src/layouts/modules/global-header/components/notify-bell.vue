<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { NBadge, NButton, NEmpty, NPopover, NSpin } from 'naive-ui';
import { fetchBiNotifyList, fetchBiNotifyUnreadCount, fetchMarkBiNotifyRead } from '@/service/api/bi-notify';
import { $t } from '@/locales';

defineOptions({ name: 'BiNotifyBell' });

const router = useRouter();

const unreadCount = ref(0);
const recentRecords = ref<Api.Bi.BiNotifyRecord[]>([]);
const loading = ref(false);
const showPopover = ref(false);
let timer: number | null = null;

async function loadUnreadCount() {
  const { data } = await fetchBiNotifyUnreadCount();
  if (data) {
    unreadCount.value = data.count;
  }
}

async function loadRecentRecords() {
  loading.value = true;
  try {
    const { data } = await fetchBiNotifyList({ current: 1, size: 10 });
    if (data?.records) {
      recentRecords.value = data.records;
    }
  } finally {
    loading.value = false;
  }
}

function handleViewAll() {
  showPopover.value = false;
  router.push({ name: 'bi_notify-records' });
}

async function handleClickRecord(record: Api.Bi.BiNotifyRecord) {
  if (!record.isRead) {
    await fetchMarkBiNotifyRead(record.id);
    await loadUnreadCount();
  }
  showPopover.value = false;
  router.push({ name: 'bi_notify-records' });
}

function startPolling() {
  stopPolling();
  timer = window.setInterval(loadUnreadCount, 30000);
}

function stopPolling() {
  if (timer !== null) {
    window.clearInterval(timer);
    timer = null;
  }
}

function handlePopoverUpdate(val: boolean) {
  showPopover.value = val;
  if (val) {
    loadRecentRecords();
  }
}

onMounted(() => {
  loadUnreadCount();
  startPolling();
});

onUnmounted(() => {
  stopPolling();
});
</script>

<template>
  <NPopover :show="showPopover" trigger="click" placement="bottom-end" :width="360" @update:show="handlePopoverUpdate">
    <template #trigger>
      <NBadge :value="String(unreadCount)" :max="99">
        <NButton quaternary circle class="mx-6px">
          <template #icon>
            <icon-ic-round-notifications class="text-icon" />
          </template>
        </NButton>
      </NBadge>
    </template>
    <div class="flex flex-col gap-8px">
      <div class="flex items-center justify-between border-b border-gray-200 pb-8px">
        <span class="text-14px font-500">{{ $t('page.bi.notify.title') }}</span>
        <NButton text type="primary" size="small" @click="handleViewAll">{{ $t('page.bi.notify.viewAll') }}</NButton>
      </div>
      <NSpin :show="loading">
        <NEmpty v-if="!recentRecords.length" :description="$t('page.bi.notify.empty')" class="py-24px" />
        <div v-else class="max-h-320px overflow-y-auto">
          <div
            v-for="record in recentRecords"
            :key="record.id"
            class="cursor-pointer border-b border-gray-100 py-8px last:border-b-0 hover:bg-gray-50"
            @click="handleClickRecord(record)"
          >
            <div class="flex items-center gap-8px">
              <span class="flex-1 truncate text-13px font-500" :class="{ 'font-700': !record.isRead }">
                {{ record.title }}
              </span>
              <span v-if="!record.isRead" class="inline-block h-6px w-6px flex-shrink-0 rounded-full bg-red-500" />
            </div>
            <div class="mt-2px text-11px text-gray-500">{{ record.fmtCreatedAt || '' }}</div>
          </div>
        </div>
      </NSpin>
    </div>
  </NPopover>
</template>
