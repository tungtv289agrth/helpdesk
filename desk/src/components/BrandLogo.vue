<template>
  <img
    v-if="config.brandLogo"
    :src="config.brandLogo"
    alt="Brand Logo"
    class="h-8 w-8 shrink-0 object-cover"
  />
  <img
    v-else
    :src="defaultLogo"
    alt="Brand Logo"
    class="h-8 w-8 shrink-0 rounded object-cover"
  />
</template>

<script setup lang="ts">
import { useConfigStore } from "@/stores/config";
const config = useConfigStore();

const defaultLogo = "/assets/helpdesk/desk/favicon.ico";
</script>

<style scoped></style>
