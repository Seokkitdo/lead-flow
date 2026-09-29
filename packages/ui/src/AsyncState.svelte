<script lang="ts">
  import Button from './Button.svelte';
  let {
    loading = false,
    message,
    retry,
  }: { loading?: boolean; message: string; retry?: () => void } = $props();
</script>

<div class="async-state" role={loading ? 'status' : 'alert'} aria-busy={loading}>
  {#if loading}<span class="loading-spinner" aria-hidden="true"></span>{/if}
  <p>{message}</p>
  {#if retry}<Button variant="secondary" onclick={retry}>다시 시도</Button>{/if}
</div>
