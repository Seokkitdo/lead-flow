<script lang="ts">
  import type { Snippet } from 'svelte';
  let { children, tone = 'neutral' }: { children: Snippet; tone?: string } = $props();
</script>

<span class={`badge tone-${tone}`}><span class="badge-dot"></span>{@render children()}</span>
