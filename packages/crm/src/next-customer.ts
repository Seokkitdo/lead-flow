import { api, type LeadPage } from '@leadflow/api-client';
import { parseRoute, safeReturn } from './navigation.svelte';

export async function nextCustomer(id: string, from: string): Promise<string | null> {
  const url = new URL(safeReturn(from, '/leads'), location.origin);
  const route = parseRoute(url.pathname);
  const params = new URLSearchParams();
  if (route.view === 'callbacks') {
    params.set('callback_window', url.searchParams.get('window') || 'today');
  } else {
    for (const key of [
      'search',
      'status',
      'source',
      'assignee_id',
      'assignment',
      'work_pending',
      'acquired_from',
      'acquired_to',
    ]) {
      const value = url.searchParams.get(key);
      if (value) params.set(key, value);
    }
    if (route.view === 'staff' && route.memberId) params.set('assignee_id', route.memberId);
    if (route.view === 'assign') params.set('assignment', 'unassigned');
  }
  params.set('after_id', id);
  params.set('page_size', '1');
  const result = await api<LeadPage>(`/leads?${params}`);
  return result.items[0]?.id ?? null;
}
