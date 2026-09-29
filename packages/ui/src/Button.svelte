<script lang="ts">
  import type { Snippet } from 'svelte';
  import type { HTMLButtonAttributes } from 'svelte/elements';
  let {
    children,
    variant = 'primary',
    class: className = '',
    ...props
  }: HTMLButtonAttributes & {
    children?: Snippet;
    variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  } = $props();
</script>

<button class={`btn btn-${variant} ${className}`} {...props}
  >{#if children}{@render children()}{/if}</button
>
