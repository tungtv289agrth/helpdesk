<template>
  <div class="flex w-[382px] flex-col border-s gap-4">
    <!-- Ticket ID -->
    <div class="flex items-center justify-between border-b px-5 py-3">
<span class="cursor-copy text-lg-semibold">{{ __("Ticket details") }}</span>
    </div>
    <!-- ticket id + sla info -->
    <div class="flex flex-col gap-4 pt-0 px-5 py-3 border-b">
      <!-- ticket id -->
      <div
        class="flex items-center justify-between rounded-lg bg-surface-gray-1 px-4 py-3 cursor-pointer transition-colors hover:bg-surface-gray-2 group"
        @click="copyToClipboard(ticket.data.name, __('Ticket #{0} copied', [ticket.data.name]))"
      >
        <div class="flex items-center gap-3">
          <div class="flex size-8 items-center justify-center rounded-md bg-surface-gray-2 text-ink-gray-6 group-hover:bg-surface-gray-3">
            <LucideHash class="size-4" />
          </div>
          <div class="flex flex-col">
            <span class="text-xs text-ink-gray-5">{{ __("Ticket ID") }}</span>
            <span class="text-lg font-semibold text-ink-gray-9">{{ ticket.data.name }}</span>
          </div>
        </div>
        <div class="flex items-center gap-1.5 text-xs text-ink-gray-5 opacity-0 group-hover:opacity-100 transition-opacity">
          <LucideCopy class="size-3.5" />
          <span>{{ __("Copy") }}</span>
        </div>
      </div>

      <!-- Status -->
      <div class="flex items-center text-base leading-5">
        <span class="w-[126px] text-sm text-ink-gray-5">{{ __('Status') }}</span>
        <span class="text-base text-ink-gray-8 flex-1">
          {{ __(ticket.data.status) }}
        </span>
      </div>

      <!-- sla info -->
      <div
        v-for="data in slaData"
        :key="data.label"
        class="flex items-center text-base"
      >
        <div class="w-[126px] text-ink-gray-5 text-sm">{{ data.title }}</div>
        <div
          class="break-words text-base text-ink-gray-8 flex items-center gap-2"
        >
          <Tooltip :text="dateFormat(data.value, dateTooltipFormat)">
            <Badge :label="data.label" :theme="data.theme" variant="subtle" />
          </Tooltip>
          <!-- SLA explanation icon -->
          <Tooltip
            v-if="
              dayjs(data.value).diff(dayjs(), 'day', true) > 4 &&
              data.title === 'Resolution'
            "
            :text="
              __(
                'This date is calculated based on configured SLAs, working hours, and holidays.'
              )
            "
          >
            <lucide-circle-question-mark
              class="h-4 w-4 text-ink-gray-6 cursor-pointer"
            />
          </Tooltip>
        </div>
      </div>
    </div>
    <!-- feedback component -->
    <TicketFeedback
      v-if="ticket.data.feedback_rating"
      class="border-b text-base text-ink-gray-5"
      :ticket="ticket.data"
    />
    <div class="flex flex-col gap-4 pt-0 px-5 py-3 overflow-y-scroll">
      <div
        class="flex items-center text-base leading-5"
        v-for="field in ticketAdditionalInfo"
        :key="field.fieldname"
      >
        <span class="w-[126px] text-sm text-ink-gray-5">{{ field.label }}</span>
        <span
          class="text-base text-ink-gray-8 flex-1 truncate"
          :class="!field.value && 'text-ink-gray-4'"
        >
          <template
            v-if="
              field.value &&
              (field.fieldtype === 'Date' || field.fieldtype === 'Datetime') &&
              dayjs(field.value).isValid()
            "
          >
            {{ dateFormat(field.value, dateTooltipFormat) }}
          </template>
          <template v-else>
            {{ field.value || "—" }}
          </template>
        </span>
      </div>

      <!-- Assignee -->
      <div class="flex items-center text-base leading-5">
        <span class="w-[126px] text-sm text-ink-gray-5">{{ __('Assignee') }}</span>
        <div class="flex-1 min-w-0">
          <MultipleAvatar
            v-if="assigneesList.length"
            :avatars="ticket.data._assign"
            size="xs"
            :max="2"
            hideName
          />
          <span v-else class="text-ink-gray-4">—</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { __ } from "@/translation";
import { ITicket } from "@/pages/ticket/symbols";
import { Field } from "@/types";
import { copyToClipboard, dateFormat, dateTooltipFormat, formatTime } from "@/utils";
import { dayjs, Tooltip } from "frappe-ui";
import { computed, inject } from "vue";
import MultipleAvatar from "../MultipleAvatar.vue";
import LucideHash from "~icons/lucide/hash";
import LucideCopy from "~icons/lucide/copy";

const ticket = inject(ITicket);

const assigneesList = computed(() => {
  return JSON.parse(ticket.data._assign || "[]");
});

const slaData = computed(() => {
  const firstResponse = firstResponseData();
  const resolution = resolutionData();
  return [
    {
      title: __("First Response"),
      value: ticket.data.first_responded_on || ticket.data.response_by,
      label: firstResponse.label,
      theme: firstResponse.color,
    },
    {
      title: __("Resolution"),
      value: ticket.data.resolution_date || ticket.data.resolution_by,
      label: resolution.label,
      theme: resolution.color,
    },
  ];
});

function firstResponseData() {
  let firstResponse = null;
  if (
    !ticket.data.first_responded_on &&
    dayjs().isBefore(dayjs(ticket.data.response_by))
  ) {
    firstResponse = {
      label: __("Due in {0}", formatTime(
        dayjs(ticket.data.response_by).diff(dayjs(), "s")
      )),
      color: "orange",
    };
  } else if (
    dayjs(ticket.data.first_responded_on).isBefore(
      dayjs(ticket.data.response_by)
    )
  ) {
    firstResponse = {
      label: __("Fulfilled in {0}", formatTime(
        dayjs(ticket.data.first_responded_on).diff(
          dayjs(ticket.data.creation),
          "s"
        )
      )),
      color: "green",
    };
  } else {
    firstResponse = {
      label: __("Failed"),
      color: "red",
    };
  }
  return firstResponse;
}

function resolutionData() {
  let resolution = null;
  if (
    !ticket.data.resolution_date &&
    dayjs().isBefore(ticket.data.resolution_by)
  ) {
    resolution = {
      label: __("Due in {0}", formatTime(
        dayjs(ticket.data.resolution_by).diff(dayjs(), "s")
      )),
      color: "orange",
    };
  } else if (ticket.data.agreement_status === "Fulfilled") {
    resolution = {
      label: __("Fulfilled in {0}", formatTime(
        dayjs(ticket.data.resolution_time, "s")
      )),
      color: "green",
    };
  } else {
    resolution = {
      label: __("Failed"),
      color: "red",
    };
  }
  return resolution;
}

const ticketAdditionalInfo = computed(() => {
  const fields = [
    {
      fieldname: "subject",
      label: __("Subject"),
      value: ticket.data.subject,
    },
    {
      fieldname: "team",
      label: __("Team"),
      value: ticket.data.agent_group || "-",
    },
    {
      fieldname: "priority",
      label: __("Priority"),
      value: __(ticket.data.priority),
    },
  ];
  const custom_fields = ticket.data.template.fields
    .filter(
      (field: Field) =>
        !field.hide_from_customer &&
        ["subject", "team", "priority"].indexOf(field.fieldname) === -1
    )
    .map((field: Field) => {
      const option = {
        label: field.label,
        value: ticket.data[field.fieldname],
      };
      if (field.fieldtype === "Date") {
        option.value = dayjs(option.value).format(
          window.date_format.toUpperCase()
        );
      }
      if (field.fieldtype === "Datetime") {
        // window.time_format
        option.value = dayjs(option.value).format(
          `${window.date_format.toUpperCase()} ${window.time_format}`
        );
      }
      return option;
    });

  return [...fields, ...custom_fields];
});
</script>

<style scoped></style>
