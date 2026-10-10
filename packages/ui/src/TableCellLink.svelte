<script lang="ts">
  import type { Snippet } from 'svelte';
  let {
    href,
    label,
    id,
    primary = false,
    children,
  }: {
    href: string;
    label: string;
    id?: string;
    primary?: boolean;
    children: Snippet;
  } = $props();
</script>

<td class="table-link-cell">
  <a class="table-cell-link" {href} {id} aria-label={label} tabindex={primary ? 0 : -1}>
    {@render children()}
  </a>
</td>
