<script lang="ts">
  import { QueryClient, QueryClientProvider } from '@tanstack/svelte-query';
  import Workspace from './Workspace.svelte';
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 20_000, refetchOnWindowFocus: true } },
  });
</script>

<QueryClientProvider {client}><Workspace /></QueryClientProvider>
