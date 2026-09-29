<script lang="ts">
  import type { Snippet } from 'svelte';
  let { label, children, hint }: { label: string; children: Snippet; hint?: string } = $props();
</script>

<label class="field"
  ><span>{label}</span>{@render children()}{#if hint}<small>{hint}</small>{/if}</label
>
