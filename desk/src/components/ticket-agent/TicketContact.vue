<template>
  <div
    class="flex items-center justify-between rounded-lg bg-surface-gray-1 px-4 py-3 cursor-pointer transition-colors hover:bg-surface-gray-2 group"
    @click="copyToClipboard(ticket.doc.name, __('Ticket #{0} copied', [ticket.doc.name]))"
  >
    <div class="flex items-center gap-3">
      <div class="flex size-8 items-center justify-center rounded-md bg-surface-gray-2 text-ink-gray-6 group-hover:bg-surface-gray-3">
        <LucideHash class="size-4" />
      </div>
      <div class="flex flex-col">
        <span class="text-xs text-ink-gray-5">{{ __("Ticket ID") }}</span>
        <span class="text-lg font-semibold text-ink-gray-9">{{ ticket.doc.name }}</span>
      </div>
    </div>
    <div class="flex items-center gap-1.5 text-xs text-ink-gray-5 opacity-0 group-hover:opacity-100 transition-opacity">
      <LucideCopy class="size-3.5" />
      <span>{{ __("Copy") }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { TicketSymbol } from "@/types";
import { __ } from "@/translation";
import { copyToClipboard } from "@/utils";
import LucideHash from "~icons/lucide/hash";
import LucideCopy from "~icons/lucide/copy";
import { inject } from "vue";

const ticket = inject(TicketSymbol)!;
</script>
