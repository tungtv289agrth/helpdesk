<template>
  <div v-if="!status || status.state !== 'connected'" class="border-t px-4 py-4">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <span class="lucide-bell size-4 text-ink-gray-7" aria-hidden="true" />
        <span class="text-sm font-medium text-ink-gray-8">{{ __("Đăng ký nhận thông báo Zalo") }}</span>
      </div>
      <span
        v-if="status?.state === 'pending'"
        class="rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700"
        >{{ __("Đang chờ xác thực") }}</span
      >
      <span v-else class="rounded bg-gray-100 px-2 py-0.5 text-xs font-medium text-ink-gray-6"
        >{{ __("Chưa đăng ký") }}</span
      >
    </div>

    <!-- QR — hiện cho cả not_connected và pending (chỉ popup mới hiện mã) -->
    <div v-if="status?.state === 'not_connected' || status?.state === 'pending'" class="mt-3">
      <div class="mt-3 flex gap-3">
        <div class="shrink-0 rounded border border-outline-gray-2 bg-surface-white p-1">
          <img :src="status.qr_url" alt="QR" class="h-24 w-24 object-contain" />
        </div>
        <div class="flex flex-col justify-center gap-1 text-p-xs text-ink-gray-7">
          <p>① {{ __("Quét QR để mở ô chat với Bot") }}</p>
          <p>② {{ __("Nhấn Lấy mã xác thực") }}</p>
          <p>③ {{ __("Gửi mã xác thực cho Bot") }}</p>
        </div>
      </div>
      <Button
        class="mt-3 w-full"
        variant="solid"
        theme="blue"
        size="sm"
        :label="__('Lấy mã xác thực')"
        :loading="generate.loading"
        @click="generate.submit()"
      />
    </div>

    <div v-if="loading" class="mt-3 flex justify-center">
      <span class="text-xs text-ink-gray-5">{{ __("Đang tải...") }}</span>
    </div>

    <!-- Popup lớn cho mã 90s -->
    <Dialog v-model:open="showDialog" :options="{ title: __('Mã xác thực với Bot') }">
      <template #body-content>
        <div class="py-2">
          <!-- Hướng dẫn 3 bước rõ ràng -->
          <div class="rounded-lg border border-outline-gray-2 bg-surface-gray-1 p-3">
            <p class="text-p-sm text-ink-gray-7">{{ __("Nhập mã 6 số bên dưới gửi vào Zalo cho Bot để xác thực") }}</p>
          </div>

          <!-- Mã lớn -->
          <div class="mt-4 rounded-xl border border-outline-gray-2 bg-surface-white p-4 text-center">
            <p class="text-xs font-medium uppercase tracking-widest text-ink-gray-5">{{ __("Mã của bạn") }}</p>
            <p class="mt-2 select-all font-mono text-5xl font-extrabold tracking-[0.25em] text-ink-gray-9">{{ status?.code || "------" }}</p>
            <div class="mt-3 flex items-center justify-center gap-2">
              <span
                class="rounded-full px-2.5 py-1 text-xs font-medium"
                :class="countdown > 0 ? 'bg-amber-100 text-amber-800 border border-amber-200' : 'bg-red-100 text-red-700 border border-red-200'"
              >
                <span v-if="countdown > 0">{{ __("Còn lại") }} {{ countdown }}s / 90s</span>
                <span v-else>{{ __("Đã hết hạn") }}</span>
              </span>
              <span v-if="status?.expires_at" class="text-xs text-ink-gray-5">{{ dayjs(status.expires_at).format("HH:mm:ss") }}</span>
            </div>
            <!-- progress -->
            <div class="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-surface-gray-2">
              <div class="h-full bg-ink-gray-9 transition-all" :style="{ width: `${Math.max(0, Math.min(100, (countdown / 90) * 100))}%` }"></div>
            </div>
            <p class="mt-2 flex items-center justify-center gap-1 text-p-xs text-ink-gray-5">
              <span class="lucide-shield size-3.5" aria-hidden="true" /> {{ __("Không chia sẻ mã này với bất cứ ai.") }}
            </p>
          </div>

          <div class="mt-4 flex flex-wrap justify-center gap-2">
            <Button variant="ghost" :label="__('Đóng')" @click="showDialog = false" />
            <Button variant="subtle" :label="__('Huỷ liên kết')" :loading="cancel.loading" @click="cancel.submit()" />
            <Button
              v-if="countdown <= 0"
              variant="solid"
              theme="blue"
              :label="__('Lấy mã mới')"
              :loading="generate.loading"
              @click="generate.submit()"
            />
          </div>
        </div>
      </template>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { __ } from "@/translation";
import { createResource, Dialog, toast } from "frappe-ui";
import { computed, ref, watch, onMounted, onUnmounted } from "vue";
import dayjs from "dayjs";
import { globalStore } from "@/stores/globalStore";

const props = defineProps<{
  ticketId: string;
}>();

const showDialog = ref(false);

const statusRes = createResource({
  url: "helpdesk.api.zalo.get_zalo_link_status",
  params: { ticket: props.ticketId },
  auto: true,
});

const generate = createResource({
  url: "helpdesk.api.zalo.generate_zalo_code",
  makeParams: () => ({ ticket: props.ticketId }),
  onSuccess: () => {
    toast.success(__("Đã tạo mã, vui lòng gửi cho Bot trong 90s"));
    statusRes.reload();
    showDialog.value = true;
  },
  onError: (err) => toast.error(err.messages?.[0] || err.message),
});

const cancel = createResource({
  url: "helpdesk.api.zalo.cancel_zalo_link",
  makeParams: () => ({ ticket: props.ticketId }),
  onSuccess: () => {
    toast.success(__("Đã huỷ"));
    showDialog.value = false;
    statusRes.reload();
  },
  onError: (err) => toast.error(err.messages?.[0] || err.message),
});

const status = computed(() => statusRes.data as any);
const loading = computed(() => statusRes.loading);

const countdown = ref(0);
let timer: ReturnType<typeof setInterval> | null = null;

// dùng remaining server-side (90s) tránh lệch clock client 3520s
watch(
  () => status.value?.remaining,
  (val) => {
    if (val !== undefined && val !== null) countdown.value = val;
  },
  { immediate: true },
);

watch(
  () => status.value?.expires_at,
  () => {
    if (status.value?.remaining === undefined) {
      const exp = status.value?.expires_at;
      if (!exp) {
        countdown.value = 0;
        return;
      }
      const diff = dayjs(exp).diff(dayjs(), "second");
      countdown.value = diff > 0 ? diff : 0;
    }
  },
);

function onZaloLinked(data: any) {
  if (!data) return;
  if (data.ticket === props.ticketId || data.email === status.value?.email) {
    statusRes.reload();
    showDialog.value = false;
    if (data.chat_id) toast.success(__("Đã liên kết Zalo thành công"));
  }
}

onMounted(() => {
  try {
    const { $socket } = globalStore();
    $socket?.on("helpdesk:zalo-linked", onZaloLinked);
  } catch {}
  timer = setInterval(() => {
    if (countdown.value > 0) {
      countdown.value -= 1;
      if (countdown.value <= 0) statusRes.reload();
    } else if (status.value?.remaining === undefined && status.value?.expires_at) {
      const exp = status.value?.expires_at;
      const diff = dayjs(exp).diff(dayjs(), "second");
      countdown.value = diff > 0 ? diff : 0;
    }
  }, 1000);
});

onUnmounted(() => {
  if (timer) clearInterval(timer);
  try {
    const { $socket } = globalStore();
    $socket?.off("helpdesk:zalo-linked", onZaloLinked);
  } catch {}
});

defineExpose({ reload: () => statusRes.reload() });
</script>
