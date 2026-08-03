<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { statusTypeOptions } from '@/constants/business';
import { fetchAddBiDatasource, fetchBiDatasource, fetchUpdateBiDatasource } from '@/service/api/bi';
import { useFormRules, useNaiveForm } from '@/hooks/common/form';
import { $t } from '@/locales';

defineOptions({ name: 'DatasourceOperateModal' });

interface Props {
  operateType: NaiveUI.TableOperateType;
  rowData?: Api.Bi.BiDatasource | null;
}

const props = defineProps<Props>();

interface Emits {
  (e: 'submitted'): void;
}

const emit = defineEmits<Emits>();
const visible = defineModel<boolean>('visible', { default: false });
const { formRef, validate, restoreValidation } = useNaiveForm();
const { defaultRequiredRule } = useFormRules();

const title = computed(() => {
  const titles: Record<NaiveUI.TableOperateType, string> = {
    add: $t('common.add'),
    edit: $t('common.edit')
  };
  return titles[props.operateType];
});

const isEdit = computed(() => props.operateType === 'edit');

const dbTypeOptions = computed(() => [
  { label: 'PostgreSQL', value: 'postgresql' },
  { label: 'MySQL', value: 'mysql' },
  { label: 'ClickHouse', value: 'clickhouse' },
  { label: 'Trino', value: 'trino' },
  { label: 'SQLite', value: 'sqlite' }
]);

interface DatasourceModel {
  id?: string;
  name: string;
  dbType: Api.Bi.DatasourceType;
  host: string;
  port: number | null;
  username: string;
  password: string;
  database: string;
  extraParams: Record<string, any> | null;
  statusType: Api.Common.EnableStatus;
}

function defaultModel(): DatasourceModel {
  return {
    name: '',
    dbType: 'postgresql',
    host: '127.0.0.1',
    port: 5432,
    username: '',
    password: '',
    database: '',
    extraParams: null,
    statusType: '1'
  };
}

const model = ref<DatasourceModel>(defaultModel());
const extraParamsText = ref('');

type RuleKey = 'name' | 'dbType' | 'host' | 'port' | 'username' | 'database';
const rules: Record<RuleKey, App.Global.FormRule> = {
  name: defaultRequiredRule,
  dbType: defaultRequiredRule,
  host: defaultRequiredRule,
  port: defaultRequiredRule,
  username: defaultRequiredRule,
  database: defaultRequiredRule
};

const passwordRules = computed<App.Global.FormRule[]>(() => {
  return isEdit.value ? [] : [defaultRequiredRule];
});

async function handleInitModel() {
  model.value = defaultModel();
  extraParamsText.value = '';
  if (isEdit.value && props.rowData) {
    const { data } = await fetchBiDatasource(props.rowData.id);
    if (data) {
      const { id, name, dbType, host, port, username, database, extraParams, statusType } = data;
      Object.assign(model.value, {
        id,
        name,
        dbType,
        host,
        port,
        username,
        password: '',
        database,
        extraParams,
        statusType
      });
      extraParamsText.value = extraParams ? JSON.stringify(extraParams, null, 2) : '';
    }
  }
}

function closeModal() {
  visible.value = false;
}

async function handleSubmit() {
  await validate();

  let parsedExtra: Record<string, any> | null = null;
  const text = extraParamsText.value.trim();
  if (text) {
    try {
      parsedExtra = JSON.parse(text);
    } catch {
      window.$message?.error($t('common.pleaseCheckValue'));
      return;
    }
  }

  if (isEdit.value) {
    const payload: Api.Bi.BiDatasourceOperateParams = {
      id: model.value.id,
      name: model.value.name,
      dbType: model.value.dbType,
      host: model.value.host,
      port: model.value.port as number,
      username: model.value.username,
      database: model.value.database,
      extraParams: parsedExtra,
      statusType: model.value.statusType
    };
    if (model.value.password.trim() !== '') {
      payload.password = model.value.password;
    }
    const { error } = await fetchUpdateBiDatasource(payload);
    if (error) return;
    window.$message?.success($t('common.updateSuccess'));
  } else {
    const payload: Api.Bi.BiDatasourceOperateParams = {
      name: model.value.name,
      dbType: model.value.dbType,
      host: model.value.host,
      port: model.value.port as number,
      username: model.value.username,
      password: model.value.password,
      database: model.value.database,
      extraParams: parsedExtra,
      statusType: model.value.statusType
    };
    const { error } = await fetchAddBiDatasource(payload);
    if (error) return;
    window.$message?.success($t('common.addSuccess'));
  }
  closeModal();
  emit('submitted');
}

watch(visible, () => {
  if (visible.value) {
    handleInitModel();
    restoreValidation();
  }
});
</script>

<template>
  <NModal v-model:show="visible" :title="title" preset="card" class="w-720px">
    <NScrollbar class="h-520px pr-20px">
      <NForm ref="formRef" :model="model" :rules="rules" label-placement="left" :label-width="110">
        <NGrid responsive="screen" item-responsive>
          <NFormItemGi span="24 m:12" :label="$t('page.bi.metadata.datasource')" path="name">
            <NInput v-model:value="model.name" :placeholder="$t('page.bi.metadata.datasource')" />
          </NFormItemGi>
          <NFormItemGi span="24 m:12" :label="$t('page.bi.models.providerType')" path="dbType">
            <NSelect
              v-model:value="model.dbType"
              :options="dbTypeOptions"
              :placeholder="$t('page.bi.models.form.providerType')"
            />
          </NFormItemGi>
          <NFormItemGi span="24 m:12" label="Host" path="host">
            <NInput v-model:value="model.host" placeholder="127.0.0.1" />
          </NFormItemGi>
          <NFormItemGi span="24 m:12" label="Port" path="port">
            <NInputNumber v-model:value="model.port" class="w-full" placeholder="5432" />
          </NFormItemGi>
          <NFormItemGi span="24 m:12" :label="$t('page.bi.audit.username')" path="username">
            <NInput v-model:value="model.username" :placeholder="$t('page.bi.audit.username')" />
          </NFormItemGi>
          <NFormItemGi span="24 m:12" label="Password" path="password" :rule="passwordRules">
            <NInput
              v-model:value="model.password"
              type="password"
              show-password-on="click"
              :placeholder="isEdit ? $t('page.bi.models.apiKeyHint') : '******'"
            />
          </NFormItemGi>
          <NFormItemGi span="24 m:12" label="Database" path="database">
            <NInput v-model:value="model.database" placeholder="db_name" />
          </NFormItemGi>
          <NFormItemGi span="24 m:12" :label="$t('page.bi.audit.status')" path="statusType">
            <NRadioGroup v-model:value="model.statusType">
              <NRadio v-for="item in statusTypeOptions" :key="item.value" :value="item.value" :label="$t(item.label)" />
            </NRadioGroup>
          </NFormItemGi>
          <NFormItemGi span="24" label="Extra Params" path="extraParams">
            <NInput v-model:value="extraParamsText" type="textarea" :rows="3" placeholder="{&quot;sslmode&quot;: &quot;prefer&quot;}" />
          </NFormItemGi>
        </NGrid>
      </NForm>
    </NScrollbar>
    <template #footer>
      <NSpace justify="end" :size="16">
        <NButton @click="closeModal">{{ $t('common.cancel') }}</NButton>
        <NButton type="primary" @click="handleSubmit">{{ $t('common.confirm') }}</NButton>
      </NSpace>
    </template>
  </NModal>
</template>
