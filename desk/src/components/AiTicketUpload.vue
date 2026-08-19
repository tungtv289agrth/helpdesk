<template>
  <div class="fixed bottom-6 right-6 z-40 flex flex-col items-end gap-2">
    <Transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="opacity-0 translate-y-1"
      leave-active-class="transition duration-150 ease-in"
      leave-to-class="opacity-0"
      mode="out-in"
    >
      <div
        v-if="status === 'idle'"
        class="pointer-events-none relative flex max-w-[300px] select-none items-start gap-1.5 rounded-lg bg-surface-gray-7 px-3.5 py-2.5 text-p-xs leading-relaxed text-ink-white shadow-xl"
      >
        <LucideSparkles class="mt-0.5 size-3.5 shrink-0" />
        <span>
          {{
            __(
              'Bấm nút "Tải file lên" để upload — AI tóm tắt nội dung rồi tự điền tiêu đề & mô tả.'
            )
          }}
        </span>
        <span
          class="absolute -bottom-1 right-8 h-2 w-2 rotate-45 select-none bg-surface-gray-7"
        />
      </div>
      <div
        v-else-if="status === 'working'"
        class="pointer-events-none flex select-none items-center gap-2 rounded-lg border border-outline-gray-2 bg-surface-white px-3.5 py-2 text-p-sm text-ink-gray-7 shadow-xl"
      >
        <Spinner class="shrink-0 text-ink-gray-5" />
        {{ workingText }}
      </div>
      <div
        v-else-if="status === 'error'"
        class="pointer-events-none flex select-none items-start gap-1.5 max-w-[340px] rounded-lg border border-outline-red-2 bg-surface-red-1 px-3.5 py-2 text-p-sm text-ink-red-3 shadow-xl"
      >
        <LucideTriangleAlert class="mt-0.5 size-4 shrink-0" />
        <span>{{ errorMessage }}</span>
      </div>
    </Transition>

    <input
      ref="fileInput"
      type="file"
      multiple
      accept=".pdf,.docx,.xlsx,.csv,.txt,.md,.png,.jpg,.jpeg"
      class="hidden"
      @change="onFileChosen"
    />

    <Button
      theme="gray"
      variant="solid"
      size="xl"
      :loading="status === 'working'"
      :disabled="status === 'working' || props.disabled"
      class="!rounded-full !px-6 shadow-xl ring-1 ring-outline-gray-2 transition-all hover:shadow-2xl hover:ring-outline-gray-3 active:scale-[0.97]"
      @click="openFileSelector"
    >
      <template #prefix>
        <LucideSparkles class="size-5" />
      </template>
      <span class="text-p-sm font-medium">{{ __("Tải file lên") }}</span>
    </Button>
  </div>
</template>

<script setup lang="ts">
import { __ } from "@/translation";
import { uploadFunction } from "@/utils";
import { Button, createResource, Spinner } from "frappe-ui";
import LucideTriangleAlert from "~icons/lucide/triangle-alert";
import LucideSparkles from "~icons/lucide/sparkles";
import { ref } from "vue";

interface UploadedFile {
  name: string;
  file_name: string;
  file_url: string;
  file_type?: string;
}

interface Filled {
  title: string | null;
  summary: string | null;
  files: UploadedFile[];
}

const props = withDefaults(defineProps<{ disabled?: boolean }>(), {
  disabled: false,
});

const emit = defineEmits<{
  filled: [payload: Filled];
}>();

const MAX_FILES = 3;
const MAX_FILE_SIZE_MB = 15;
const REQUEST_TIMEOUT_MS = 30000;
const ERROR_DISMISS_MS = 10000;

const UNREADABLE_MESSAGE = __(
  "Không đọc được nội dung file này, bạn vui lòng tự nhập tiêu đề giúp"
);

const REASON_MESSAGES: Record<string, string> = {
  rate_limited: __(
    "Bạn đã dùng quá nhiều lần tải file lên. Vui lòng thử lại sau khoảng 10 phút."
  ),
  limit_exceeded: __(
    "Tính năng tải file lên tạm thời bị giới hạn. Vui lòng thử lại sau."
  ),
  too_many_files: __("Mỗi lần chỉ tải được tối đa 3 file."),
  file_too_large: __(
    "File này quá lớn (tối đa 15MB). Bạn vui lòng chọn file khác."
  ),
  unsupported_file_type: __(
    "Loại file này chưa được hỗ trợ. Bạn có thể tải PDF, Word, Excel, CSV, TXT hoặc ảnh."
  ),
  not_enough_information: __(
    "File đã đọc được nhưng chưa đủ thông tin để tự điền tiêu đề. Bạn vui lòng nhập thủ công giúp."
  ),
  irrelevant_content: __(
    "Nội dung file không liên quan đến ticket hỗ trợ. Bạn vui lòng nhập thủ công giúp."
  ),
  processing_failed: UNREADABLE_MESSAGE,
};

const fileInput = ref<HTMLInputElement>();
const status = ref<"idle" | "working" | "error">("idle");
const workingText = ref("");
const errorMessage = ref("");
let errorTimer: ReturnType<typeof setTimeout> | undefined;

const aiSummarize = createResource({
  url: "helpdesk.api.ai_summary.ai_summary.ai_summarize_files",
  auto: false,
});

function openFileSelector() {
  fileInput.value?.click();
}

async function onFileChosen(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = Array.from(input.files ?? []);
  input.value = "";

  if (!files.length) return;

  // Client-side quick checks — the server re-checks everything too.
  if (files.length > MAX_FILES) {
    showError(__("Mỗi lần chỉ tải được tối đa 3 file."));
    return;
  }
  const oversized = files.find(
    (f) => f.size > MAX_FILE_SIZE_MB * 1024 * 1024
  );
  if (oversized) {
    showError(
      __("File này quá lớn (tối đa 15MB). Bạn vui lòng chọn file khác.")
    );
    return;
  }

  status.value = "working";
  workingText.value = __("Đang đọc nội dung file {0}...", [
    files.map((f) => f.name).join(", "),
  ]);

  let uploaded: UploadedFile[] = [];
  try {
    for (const file of files) {
      uploaded.push(await uploadFunction(file));
    }
  } catch {
    status.value = "idle";
    return;
  }

  const fileNames = uploaded.map((f) => f.name);

  // Give the request a hard 20s budget; beyond that cancel it and let the
  // user fall back to typing a title themselves.
  const timeoutId = setTimeout(() => aiSummarize.abort(), REQUEST_TIMEOUT_MS);
  try {
    const data = await aiSummarize.submit({ file_names: fileNames });
    clearTimeout(timeoutId);
    if (!data) {
      // Request was aborted by the timeout above.
      showError(UNREADABLE_MESSAGE);
      return;
    }
    handleResponse(data, uploaded);
  } catch {
    clearTimeout(timeoutId);
    showError(UNREADABLE_MESSAGE);
  }
}

function handleResponse(data: any, uploaded: UploadedFile[]) {
  if (data?.success && data.reason === "ok" && (data.title || data.summary)) {
    emit("filled", {
      title: data.title,
      summary: data.summary,
      files: uploaded,
    });
    status.value = "idle";
    return;
  }
  showError(REASON_MESSAGES[data?.reason] ?? UNREADABLE_MESSAGE);
}

function showError(message: string) {
  errorMessage.value = message;
  status.value = "error";
  if (errorTimer) clearTimeout(errorTimer);
  errorTimer = setTimeout(() => {
    status.value = "idle";
    errorTimer = undefined;
  }, ERROR_DISMISS_MS);
}
</script>