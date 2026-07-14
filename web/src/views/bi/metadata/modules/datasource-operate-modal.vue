<script setup lang="tsx">
import { computed, reactive, ref, watch } from 'vue';
import { NForm, NFormItemGi, NGrid, NInput, NInputNumber, NSelect, NSwitch, useMessage } from 'naive-ui';
import type { FormRules } from 'naive-ui';
import { fetchCreateBiDatasource, fetchUpdateBiDatasource } from '@/service/api';
import { $t } from '@/locales';
import { useNaiveForm } from '@/hooks/common/form';

defineOptions({ name: 'DatasourceOperateModal' });

const props = defineProps<{
  /** 编辑中的数据源；null 表示新增 */
  editing: Api.Bi.Datasource | null;
}>();

const emit = defineEmits<{
  submitted: [];
}>();

const visible = ref(false);
const message = useMessage();
const { formRef, validate, restoreValidation } = useNaiveForm();

const TYPE_OPTIONS: { label: string; value: Api.Bi.DatasourceType }[] = [
  { label: 'SQLite', value: 'sqlite' },
  { label: 'PostgreSQL', value: 'postgresql' },
  { label: 'MySQL', value: 'mysql' },
  { label: 'ClickHouse', value: 'clickhouse' },
  { label: 'Trino', value: 'trino' }
];

const model = reactive<Api.Bi.DatasourceAddParams & { id?: string }>({
  name: '',
  type: 'sqlite',
  database: '',
  host: null,
  port: null,
  username: null,
  password: null,
  isDefault: false,
  remark: null
});

const isSqlite = computed(() => model.type === 'sqlite');
const isEdit = computed(() => Boolean(props.editing?.id));

const title = computed(() =>
  isEdit.value ? $t('page.bi.metadata.datasource.edit') : $t('page.bi.metadata.datasource.add')
);

const rules = computed<FormRules>(() => {
  const base: FormRules = {
    name: { required: true, message: $t('page.bi.metadata.datasource.form.name'), trigger: ['blur', 'input'] },
    type: { required: true, message: $t('page.bi.metadata.datasource.form.type'), trigger: ['blur', 'change'] },
    database: {
      required: true,
      message: $t('page.bi.metadata.datasource.form.database'),
      trigger: ['blur', 'input']
    }
  };
  if (isSqlite.value) {
    return base;
  }
  return {
    ...base,
    host: { required: true, message: $t('page.bi.metadata.datasource.form.host'), trigger: ['blur', 'input'] },
    port: {
      required: true,
      type: 'number',
      message: $t('page.bi.metadata.datasource.form.port'),
      trigger: ['blur', 'change']
    },
    username: { required: true, message: $t('page.bi.metadata.datasource.form.username'), trigger: ['blur', 'input'] }
  };
});

function resetModel() {
  Object.assign(model, {
    name: '',
    type: 'sqlite',
    database: '',
    host: null,
    port: null,
    username: null,
    password: null,
    isDefault: false,
    remark: null
  });
}

function fillFromEditing(row: Api.Bi.Datasource) {
  Object.assign(model, {
    id: row.id,
    name: row.name,
    type: row.type,
    database: row.database,
    host: row.host,
    port: row.port,
    username: row.username,
    password: null,
    isDefault: row.isDefault,
    remark: row.remark
  });
}

function open(row?: Api.Bi.Datasource) {
  if (row) {
    fillFromEditing(row);
  } else {
    resetModel();
  }
  restoreValidation();
  visible.value = true;
}

function close() {
  visible.value = false;
}

async function handleSubmit() {
  await validate();
  const payload: Api.Bi.DatasourceAddParams = {
    name: model.name,
    type: model.type,
    database: model.database,
    host: model.host,
    port: model.port,
    username: model.username,
    password: model.password || undefined,
    isDefault: model.isDefault,
    remark: model.remark
  };
  let error: unknown = null;
  if (isEdit.value && model.id) {
    const updatePayload: Api.Bi.DatasourceUpdateParams = { ...payload };
    if (!model.password) {
      // 不修改密码
      delete updatePayload.password;
    }
    const res = await fetchUpdateBiDatasource(model.id, updatePayload);
    error = res.error;
    if (!error) message.success($t('common.modifySuccess'));
  } else {
    const res = await fetchCreateBiDatasource(payload);
    error = res.error;
    if (!error) message.success($t('common.addSuccess'));
  }
  if (!error) {
    close();
    emit('submitted');
  }
}

defineExpose({ open, close });

watch(visible, v => {
  if (!v) resetModel();
});
</script>

<template>
  <NModal
    v-model:show="visible"
    preset="card"
    :title="title"
    style="width: 640px"
    :mask-closable="false"
    @close="close"
  >
    <NForm ref="formRef" :model="model" :rules="rules" label-placement="top">
      <NGrid :cols="12" :x-gap="12">
        <NFormItemGi :span="8" :label="$t('page.bi.metadata.datasource.name')" path="name">
          <NInput v-model:value="model.name" :placeholder="$t('page.bi.metadata.datasource.form.name')" />
        </NFormItemGi>
        <NFormItemGi :span="4" :label="$t('page.bi.metadata.datasource.type')" path="type">
          <NSelect v-model:value="model.type" :options="TYPE_OPTIONS" />
        </NFormItemGi>

        <NFormItemGi :span="12" :label="$t('page.bi.metadata.datasource.database')" path="database">
          <NInput v-model:value="model.database" :placeholder="$t('page.bi.metadata.datasource.form.database')" />
        </NFormItemGi>

        <template v-if="!isSqlite">
          <NFormItemGi :span="7" :label="$t('page.bi.metadata.datasource.host')" path="host">
            <NInput v-model:value="model.host" :placeholder="$t('page.bi.metadata.datasource.form.host')" />
          </NFormItemGi>
          <NFormItemGi :span="5" :label="$t('page.bi.metadata.datasource.port')" path="port">
            <NInputNumber
              v-model:value="model.port"
              :placeholder="$t('page.bi.metadata.datasource.form.port')"
              :min="1"
              :max="65535"
              style="width: 100%"
            />
          </NFormItemGi>
          <NFormItemGi :span="6" :label="$t('page.bi.metadata.datasource.username')" path="username">
            <NInput v-model:value="model.username" :placeholder="$t('page.bi.metadata.datasource.form.username')" />
          </NFormItemGi>
          <NFormItemGi :span="6" :label="$t('page.bi.metadata.datasource.password')" path="password">
            <NInput
              v-model:value="model.password"
              type="password"
              show-password-on="click"
              :placeholder="$t('page.bi.metadata.datasource.passwordPlaceholder')"
            />
          </NFormItemGi>
        </template>
        <template v-else>
          <NFormItemGi :span="6" :label="$t('page.bi.metadata.datasource.password')" path="password">
            <NInput
              v-model:value="model.password"
              type="password"
              show-password-on="click"
              :placeholder="$t('page.bi.metadata.datasource.passwordPlaceholder')"
            />
          </NFormItemGi>
        </template>

        <NFormItemGi :span="12" :label="$t('page.bi.metadata.datasource.remark')" path="remark">
          <NInput v-model:value="model.remark" type="textarea" :rows="2" />
        </NFormItemGi>

        <NFormItemGi :span="6" :label="$t('page.bi.metadata.datasource.isDefault')" path="isDefault">
          <NSwitch v-model:value="model.isDefault" />
        </NFormItemGi>
      </NGrid>
    </NForm>

    <template #footer>
      <NSpace justify="end">
        <NButton @click="close">{{ $t('common.cancel') }}</NButton>
        <NButton type="primary" @click="handleSubmit">{{ $t('common.confirm') }}</NButton>
      </NSpace>
    </template>
  </NModal>
</template>
