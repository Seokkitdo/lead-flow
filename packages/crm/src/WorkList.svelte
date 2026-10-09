<script lang="ts">
  import { createQuery } from '@tanstack/svelte-query';
  import { api, date, statuses, type User, type LeadPage } from '@leadflow/api-client';
  import { AsyncState, EmptyState, Badge, Button, Field } from '@leadflow/ui';
  import { useNavigation } from './navigation.svelte';
  let { member }: { member?: User } = $props();
  const navigation = useNavigation();
  const windowFilter = $derived(
    ['today', 'overdue', 'upcoming', 'all'].includes(
      navigation.url.searchParams.get('window') || '',
    )
      ? navigation.url.searchParams.get('window')!
      : 'today',
  );
  const status = $derived(navigation.url.searchParams.get('status') || '');
  const pendingOnly = $derived(navigation.url.searchParams.get('work_pending') === 'true');
  const page = $derived(
    Math.max(1, Number.parseInt(navigation.url.searchParams.get('page') || '1') || 1),
  );
  const params = $derived(
    new URLSearchParams({
      page: String(page),
      page_size: '15',
      ...(member
        ? {
            assignee_id: member.id,
            ...(status ? { status } : {}),
            ...(pendingOnly ? { work_pending: 'true' } : {}),
          }
        : { callback_window: windowFilter }),
    }).toString(),
  );
  const leads = createQuery(() => ({
    queryKey: ['leads', params],
    queryFn: ({ signal }) => api<LeadPage>(`/leads?${params}`, { signal }),
  }));
  function change(key: string, value: string) {
    const query = new URLSearchParams(navigation.url.search);
    if (value) query.set(key, value);
    else query.delete(key);
    if (key !== 'page') query.delete('page');
    navigation.go(`${navigation.url.pathname}?${query}`);
  }
  function href(id: string) {
    return `/leads/${id}?from=${encodeURIComponent(navigation.url.pathname + navigation.url.search)}`;
  }
</script>

{#if member}
  <a class="back-link" href="/team">직원 목록으로</a>
  <section class="panel">
    <div class="section-heading">
      <div>
        <h2>{member.name}님의 업무</h2>
        <p>
          {member.login_id} · {member.status === 'ACTIVE'
            ? '재직'
            : member.status === 'INACTIVE'
              ? '비활성'
              : '퇴사'}
        </p>
      </div>
      <a class="btn btn-secondary" href={`/team/${member.id}`}>계정 관리</a>
    </div>
    <p>
      현재 담당 고객과 최근 상담 메모를 확인하세요. 고객을 선택하면 누적 상담·배분 이력을 볼 수
      있습니다.
    </p>
    <div class="form-grid">
      <Field label="업무 상태"
        ><select value={status} onchange={(e) => change('status', e.currentTarget.value)}
          ><option value="">전체 상태</option
          >{#each Object.entries(statuses) as [key, label]}<option value={key}>{label}</option
            >{/each}</select
        ></Field
      >
      <Field label="처리 여부"
        ><select
          value={pendingOnly ? 'true' : ''}
          onchange={(e) => change('work_pending', e.currentTarget.value)}
          ><option value="">전체 고객</option><option value="true">배분 후 미처리</option></select
        ></Field
      >
    </div>
  </section>
{:else}
  <p>한국 시간 기준입니다. 기한 초과에는 오늘 중 예정 시각이 지난 고객도 포함됩니다.</p>
  <nav class="tabs" aria-label="재통화 기간">
    {#each [{ key: 'today', label: '오늘' }, { key: 'overdue', label: '기한 초과' }, { key: 'upcoming', label: '내일 이후' }, { key: 'all', label: '전체' }] as item}<a
        href={`/callbacks?window=${item.key}`}
        class:active={windowFilter === item.key}
        aria-current={windowFilter === item.key ? 'page' : undefined}>{item.label}</a
      >{/each}
  </nav>
{/if}
<section class="panel" aria-busy={leads.isFetching}>
  <div class="section-heading">
    <h2>
      {member ? '담당 고객' : '재통화 고객'}
      <span class="count-chip">{leads.data?.total ?? '—'}</span>
    </h2>
    <Button variant="secondary" disabled={leads.isFetching} onclick={() => leads.refetch()}
      >새로고침</Button
    >
  </div>
  {#if leads.isPending}<AsyncState loading message="고객을 불러오고 있어요…" />
  {:else if leads.isError}<AsyncState message={leads.error.message} retry={() => leads.refetch()} />
  {:else if !leads.data.items.length}<EmptyState
      title="해당하는 고객이 없습니다"
      description="다른 조건을 선택하거나 새로고침해 주세요."
    />
  {:else}<div class="table-scroll">
      <table>
        <thead
          ><tr
            ><th>고객</th><th>상태</th><th>담당자</th><th>재통화 일시</th><th>최근 상담 메모</th><th
              >최근 활동</th
            ></tr
          ></thead
        ><tbody
          >{#each leads.data.items as lead (lead.id)}<tr
              ><td
                ><a id={`work-lead-${lead.id}`} href={href(lead.id)}>{lead.name}</a>
                <div>{lead.phone}</div></td
              ><td
                ><Badge tone={lead.current_status}>{statuses[lead.current_status]}</Badge
                >{#if lead.assignment_pending}<div>배분 후 미처리</div>{/if}</td
              ><td>{lead.assignee_name || '미배분'}</td><td>{date(lead.callback_at, true)}</td><td
                >{lead.latest_memo || '—'}</td
              ><td>{date(lead.last_activity_at, true)}</td></tr
            >{/each}</tbody
        >
      </table>
    </div>{/if}
  {#if leads.data && (page > 1 || leads.data.total > 15)}<div class="pagination">
      <Button
        variant="ghost"
        disabled={page <= 1 || leads.isFetching}
        onclick={() => change('page', String(page - 1))}>이전</Button
      ><span>{page}페이지</span><Button
        variant="ghost"
        disabled={page * 15 >= leads.data.total || leads.isFetching}
        onclick={() => change('page', String(page + 1))}>다음</Button
      >
    </div>{/if}
</section>
