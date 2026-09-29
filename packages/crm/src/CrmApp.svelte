<script lang="ts">
  import { QueryClient, QueryClientProvider } from '@tanstack/svelte-query';
  import Workspace from './Workspace.svelte';
  let { mode }: { mode: 'admin' | 'staff' } = $props();
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 20_000, refetchOnWindowFocus: true } },
  });
</script>

<QueryClientProvider {client}><Workspace {mode} /></QueryClientProvider>
