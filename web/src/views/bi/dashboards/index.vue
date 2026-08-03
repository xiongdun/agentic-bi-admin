<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import {
  NButton,
  NCard,
  NEmpty,
  NForm,
  NFormItem,
  NInput,
  NModal,
  NPopconfirm,
  NSpace,
  NSpin,
  NPagination
} from 'naive-ui';
import { fetchBiDashboardList, fetchCreateBiDashboard, fetchDeleteBiDashboard } from '@/service/api/bi-dashboard';
import { useAuth } from '@/hooks/business/auth';
import { $t } from '@/locales';

defineOptions({ name: 'BiDashboards' });

const router = useRouter();
const { hasAuth } = useAuth();

const loading = ref<boolean>(false);
const list = ref<Api.Bi.BiDashboardBrief[]>([]);
const total = ref<number>(0);

const searchParams = reactive<Api.Bi.BiDashboardSearchParams>({
  current: 1,
  size: 12,
  name: undefined
});

async function getData() {
  loading.value = true;
  try {
    const { data, error } = await fetchBiDashboardList({
      current: searchParams.current,
      size: searchParams.size,
      name: searchParams.name || undefined
    });
    if (!error && data) {
      list.value = data.records;
      total.value = data.total;
    }
  } finally {
    loading.value = false;
  }
}

function getDataByPage(page: number) {
  searchParams.current = page;
  getData();
}

function resetSearch() {
  searchParams.current = 1;
  searchParams.name = undefined;
  getData();
}

function openDetail(id: string) {
  router.push({ name: 'bi_dashboard-detail', params: { id } });
}

async function handleDelete(id: string) {
  const { error } = await fetchDeleteBiDashboard(id);
  if (!error) {
    window.$message?.success($t('common.deleteSuccess'));
    getData();
  }
}

// 新建模态框
const showCreate = ref<boolean>(false);
const createForm = reactive<{ name: string; description: string }>({ name: '', description: '' });
const creating = ref<boolean>(false);

function openCreate() {
  createForm.name = '';
  createForm.description = '';
  showCreate.value = true;
}

async function handleCreate() {
  if (!createForm.name.trim()) return;
  creating.value = true;
  try {
    const { data, error } = await fetchCreateBiDashboard({
      name: createForm.name.trim(),
      description: createForm.description.trim() || null,
      layout: { items: [] }
    });
    if (!error && data) {
      window.$message?.success($t('page.bi.dashboard.createSuccess'));
      showCreate.value = false;
      router.push({ name: 'bi_dashboard-detail', params: { id: data.createdId }, query: { mode: 'edit' } });
    }
  } finally {
    creating.value = false;
  }
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '-';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

onMounted(() => {
  getData();
});
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <!-- 搜索栏 -->
    <NCard :bordered="false" size="small" class="card-wrapper">
      <NSpace justify="space-between" align="center">
        <NSpace align="center" :size="12">
          <NInput
            v-model:value="searchParams.name"
            clearable
            :placeholder="$t('page.bi.dashboard.searchPlaceholder')"
            style="width: 240px"
            @keydown.enter="getDataByPage(1)"
          />
          <NButton size="small" @click="resetSearch">
            <template #icon><icon-ic-round-refresh class="text-icon" /></template>
            {{ $t('common.reset') }}
          </NButton>
          <NButton size="small" type="primary" ghost @click="getDataByPage(1)">
            <template #icon><icon-ic-round-search class="text-icon" /></template>
            {{ $t('common.search') }}
          </NButton>
        </NSpace>
        <NButton v-if="hasAuth('B_BI_DASHBOARD_CREATE')" type="primary" @click="openCreate">
          <template #icon><icon-ic-round-add class="text-icon" /></template>
          {{ $t('page.bi.dashboard.create') }}
        </NButton>
      </NSpace>
    </NCard>

    <!-- 列表 -->
    <NCard :title="$t('page.bi.dashboard.title')" :bordered="false" size="small" class="card-wrapper sm:flex-1-hidden">
      <template #header-extra>
        <span class="text-12px text-gray-500">{{ $t('page.bi.dashboard.itemCount') }}: {{ total }}</span>
      </template>
      <NSpin :show="loading">
        <NEmpty v-if="!list.length" :description="$t('page.bi.dashboard.empty')" class="py-80px" />
        <div v-else class="grid grid-cols-1 gap-16px sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          <NCard
            v-for="item in list"
            :key="item.id"
            size="small"
            hoverable
            class="cursor-pointer dashboard-card"
            @click="openDetail(item.id)"
          >
            <div class="flex flex-col gap-8px">
              <div class="flex items-center gap-6px">
                <icon-mdi-view-dashboard-outline class="text-20px text-primary" />
                <NTooltip trigger="hover">
                  <template #trigger>
                    <span class="flex-1 truncate text-15px font-500">{{ item.name }}</span>
                  </template>
                  {{ item.name }}
                </NTooltip>
              </div>
              <div v-if="item.description" class="text-12px opacity-70 line-clamp-2">
                {{ item.description }}
              </div>
              <div class="flex items-center gap-8px text-12px text-gray-500">
                <span>{{ $t('page.bi.dashboard.itemCount') }}: {{ item.itemCount }}</span>
                <span>·</span>
                <span>{{ formatDate(item.updatedAt) }}</span>
              </div>
            </div>
            <template #action>
              <NSpace justify="space-between" align="center">
                <NButton size="small" type="primary" ghost @click.stop="openDetail(item.id)">
                  <template #icon><icon-ic-round-open-in-new class="text-icon" /></template>
                  {{ $t('common.view') }}
                </NButton>
                <NPopconfirm v-if="hasAuth('B_BI_DASHBOARD_DELETE')" @positive-click="handleDelete(item.id)">
                  <template #trigger>
                    <NButton size="small" type="error" ghost @click.stop>
                      <template #icon><icon-ic-round-delete class="text-icon" /></template>
                      {{ $t('common.delete') }}
                    </NButton>
                  </template>
                  {{ $t('page.bi.dashboard.confirmDelete') }}
                </NPopconfirm>
              </NSpace>
            </template>
          </NCard>
        </div>
      </NSpin>
      <div v-if="total > 0" class="mt-16px flex justify-end">
        <NPagination
          :page="searchParams.current"
          :page-size="searchParams.size"
          :item-count="total"
          show-size-picker
          :page-sizes="[12, 24, 48]"
          @update:page="getDataByPage"
          @update:page-size="
            (ps: number) => {
              searchParams.size = ps;
              searchParams.current = 1;
              getData();
            }
          "
        />
      </div>
    </NCard>

    <!-- 新建模态框 -->
    <NModal
      v-model:show="showCreate"
      preset="card"
      :title="$t('page.bi.dashboard.create')"
      style="width: 480px"
      :mask-closable="false"
    >
      <NForm label-placement="top">
        <NFormItem :label="$t('page.bi.dashboard.name')" required>
          <NInput
            v-model:value="createForm.name"
            :placeholder="$t('page.bi.dashboard.namePlaceholder')"
            maxlength="100"
            show-count
          />
        </NFormItem>
        <NFormItem :label="$t('page.bi.dashboard.description')">
          <NInput
            v-model:value="createForm.description"
            type="textarea"
            :placeholder="$t('page.bi.dashboard.descPlaceholder')"
            :autosize="{ minRows: 2, maxRows: 4 }"
          />
        </NFormItem>
      </NForm>
      <template #footer>
        <NSpace justify="end">
          <NButton @click="showCreate = false">{{ $t('page.bi.dashboard.cancel') }}</NButton>
          <NButton type="primary" :loading="creating" :disabled="!createForm.name.trim()" @click="handleCreate">
            {{ $t('common.confirm') }}
          </NButton>
        </NSpace>
      </template>
    </NModal>
  </div>
</template>

<style scoped>
.dashboard-card {
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease;
}
.dashboard-card:hover {
  transform: translateY(-2px);
}
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
