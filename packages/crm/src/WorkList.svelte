<script lang="ts">
  import { createQuery } from '@tanstack/svelte-query';
  import {
    api,
    date,
    statuses,
    type User,
    type LeadPage,
    type Dashboard,
  } from '@leadflow/api-client';
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
  const search = $derived(navigation.url.searchParams.get('search') || '');
  let searchInput = $state('');
  $effect(() => {
    searchInput = search;
  });
  const summary = createQuery(() => ({
    queryKey: ['dashboard'],
    queryFn: ({ signal }) => api<Dashboard>('/dashboard', { signal }),
    enabled: !!member,
  }));
  const memberStats = $derived(summary.data?.staff.find((item) => item.id === member?.id));
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
            ...(search ? { search } : {}),
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

<div class="content-stack">
  {#if member}
    <a class="back-link" href="/team">직원 목록으로</a>
    <section class="panel panel-content" aria-label="직원 기본 정보">
      <div class="section-heading">
        <div>
          <h2>{member.name}님의 업무</h2>
          <p>
            {member.login_id} · {member.status === 'ACTIVE'
              ? '재직'
              : member.status === 'INACTIVE'
                ? '이용 중지'
                : '퇴사'}
          </p>
        </div>
        <a class="btn btn-secondary" href={`/team/${member.id}`}>계정 관리</a>
      </div>
      <p class="field-hint">
        계정 관리에서 직원 정보·직원 상태를 수정하고 비밀번호를 재설정할 수 있습니다.
      </p>
      <dl class="detail-grid">
        <div>
          <dt>권한</dt>
          <dd>{member.role === 'ADMIN' ? '관리자' : '직원'}</dd>
        </div>
        <div>
          <dt>연락처</dt>
          <dd>{member.phone || '등록된 연락처 없음'}</dd>
        </div>
        <div>
          <dt>계정 등록일</dt>
          <dd>{date(member.created_at, true)}</dd>
        </div>
        <div>
          <dt>직원 상태</dt>
          <dd>
            <Badge tone={member.status === 'ACTIVE' ? 'COMPLETED' : 'HOLD'}
              >{member.status === 'ACTIVE'
                ? '재직'
                : member.status === 'INACTIVE'
                  ? '이용 중지'
                  : '퇴사'}</Badge
            >
          </dd>
        </div>
      </dl>
      {#if member.status !== 'ACTIVE'}
        <p class="alert">
          현재 로그인하거나 새 고객을 배정받을 수 없는 계정입니다. 기존 담당 고객과 업무 기록은 남아
          있습니다.
        </p>
      {/if}
    </section>
    <section class="panel panel-content" aria-label="직원 업무 요약">
      <div class="section-heading"><h2>업무 요약</h2></div>
      {#if summary.isPending}<AsyncState loading message="업무 요약을 불러오는 중…" />
      {:else if summary.isError}<AsyncState
          message="업무 요약을 불러오지 못했습니다."
          retry={() => summary.refetch()}
        />
      {:else}
        <dl class="summary-grid" aria-label="전체 담당 고객 업무 요약">
          <div>
            <dt>전체 담당 고객</dt>
            <dd>{memberStats?.total ?? 0}명</dd>
          </div>
          <div>
            <dt>재통화 예정</dt>
            <dd>{memberStats?.callback ?? 0}명</dd>
          </div>
          <div>
            <dt>상담 완료</dt>
            <dd>{memberStats?.completed ?? 0}명</dd>
          </div>
        </dl>
        <p class="field-hint">
          아래에서 검색 조건을 바꿔도 이 요약은 현재 담당 고객 전체를 보여줍니다.
        </p>
      {/if}
    </section>
  {:else}
    <p>‘예정 시간 지남’에는 오늘을 포함해 연락하기로 한 시간이 지난 고객이 표시됩니다.</p>
    <nav class="tabs" aria-label="재통화 기간">
      {#each [{ key: 'today', label: '오늘' }, { key: 'overdue', label: '예정 시간 지남' }, { key: 'upcoming', label: '내일 이후' }, { key: 'all', label: '전체' }] as item}<a
          href={`/callbacks?window=${item.key}`}
          class:active={windowFilter === item.key}
          aria-current={windowFilter === item.key ? 'page' : undefined}>{item.label}</a
        >{/each}
    </nav>
  {/if}
  <section class="panel" aria-busy={leads.isFetching}>
    <div class="panel-content">
      <div class="section-heading">
        <h2>
          {member ? '담당 고객' : '재통화 고객'}
          <span class="count-chip">{leads.data?.total ?? '—'}</span>
        </h2>
        <Button
          variant="secondary"
          disabled={leads.isFetching}
          onclick={() => {
            leads.refetch();
            if (member) summary.refetch();
          }}>새로고침</Button
        >
      </div>
      {#if member}
        <form
          class="filter-form"
          onsubmit={(event) => {
            event.preventDefault();
            change('search', searchInput.trim());
          }}
        >
          <div class="filter-fields">
            <Field label="담당 고객 검색"
              ><input
                type="search"
                bind:value={searchInput}
                placeholder="고객 이름 또는 연락처"
              /></Field
            >
            <Field label="상담 상태"
              ><select value={status} onchange={(e) => change('status', e.currentTarget.value)}
                ><option value="">전체 상태</option
                >{#each Object.entries(statuses) as [key, label]}<option value={key}>{label}</option
                  >{/each}</select
              ></Field
            >
            <Field label="배정 후 기록 여부"
              ><select
                value={pendingOnly ? 'true' : ''}
                onchange={(e) => change('work_pending', e.currentTarget.value)}
                ><option value="">전체 고객</option><option value="true">배정 후 기록 없음</option
                ></select
              ></Field
            >
          </div>
          <div class="filter-actions">
            <a class="btn btn-secondary" href={navigation.url.pathname}>검색 조건 초기화</a>
            <Button type="submit">검색</Button>
          </div>
        </form>{/if}
    </div>
    {#if leads.isPending}<AsyncState loading message="고객을 불러오는 중…" />
    {:else if leads.isError}<AsyncState
        message={leads.error.message}
        retry={() => leads.refetch()}
      />
    {:else if !leads.data.items.length}<EmptyState
        title="해당하는 고객이 없습니다"
        description={member
          ? '검색 조건을 바꾸거나 고객 배정 여부를 확인해 주세요.'
          : '선택한 기간에 다시 연락할 고객이 없습니다. 다른 기간을 선택해 보세요.'}
      />
    {:else}<div class="table-scroll">
        <table>
          <thead
            ><tr
              ><th>고객</th><th>상태</th><th>{member ? '배정일' : '담당자'}</th><th>재통화 일시</th
              ><th>최근 상담 메모</th><th>최근 기록</th></tr
            ></thead
          ><tbody
            >{#each leads.data.items as lead (lead.id)}<tr
                ><td
                  ><a id={`work-lead-${lead.id}`} href={href(lead.id)}>{lead.name}</a>
                  <div>{lead.phone}</div></td
                ><td
                  ><Badge tone={lead.current_status}>{statuses[lead.current_status]}</Badge
                  >{#if lead.assignment_pending}<div>배정 후 기록 없음</div>{/if}</td
                ><td
                  >{member
                    ? date(lead.assigned_at, true)
                    : lead.assignee_name || '담당자 미지정'}</td
                ><td>{date(lead.callback_at, true)}</td><td>{lead.latest_memo || '—'}</td><td
                  >{date(lead.last_activity_at, true)}</td
                ></tr
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
</div>
