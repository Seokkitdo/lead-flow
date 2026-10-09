<script lang="ts">
  import { createQuery } from '@tanstack/svelte-query';
  import {
    api,
    ApiError,
    body,
    statuses,
    sources,
    activities,
    date,
    localInput,
    fromLocal,
    type Lead,
    type User,
  } from '@leadflow/api-client';
  import { Badge, Button, Field, Icon, AsyncState } from '@leadflow/ui';
  import { protectChanges, useNavigation } from './navigation.svelte';
  const navigation = useNavigation();
  let {
    id,
    tab,
    href,
    usersLoading,
    usersError,
    retryUsers,
    isAdmin,
    users,
    onclose,
    onedit,
    onrefresh,
  }: {
    id: string;
    tab: string;
    href: (tab: string) => string;
    usersLoading: boolean;
    usersError?: string;
    retryUsers: () => void;
    isAdmin: boolean;
    users: User[];
    onclose: () => void;
    onedit: (lead: Lead) => void;
    onrefresh: () => Promise<void>;
  } = $props();
  let activity = $state('CALL_CONNECTED'),
    memo = $state(''),
    status = $state(''),
    callback = $state(''),
    assignee = $state(''),
    reason = $state(''),
    error = $state(''),
    pending = $state(false),
    deleting = $state(false),
    success = $state(''),
    dirty = $state(false),
    conflict = $state(false);
  protectChanges(() => (pending ? 'pending' : dirty ? 'dirty' : null));
  const lead = createQuery(() => ({
    queryKey: ['lead', id],
    queryFn: () => api<Lead>(`/leads/${id}`),
    refetchOnWindowFocus: false,
  }));
  $effect(() => {
    if (lead.data && !dirty) {
      status = lead.data.current_status;
      callback = localInput(lead.data.callback_at);
      assignee = lead.data.assignee_id || '';
    }
  });
  $effect(() => {
    id;
    memo = '';
    error = '';
    success = '';
    deleting = false;
  });
  async function save(e: SubmitEvent) {
    e.preventDefault();
    const returnToList = (e.submitter as HTMLButtonElement | null)?.value === 'return';
    if (pending || conflict) return;
    pending = true;
    error = '';
    success = '';
    try {
      await api(
        `/leads/${id}/activities`,
        body('POST', {
          activity_type: activity,
          memo,
          status,
          callback_at: status === 'CALLBACK' ? fromLocal(callback) : null,
          version: lead.data?.version,
        }),
      );
      dirty = false;
      memo = '';
      success = '업무 기록을 저장했습니다.';
      await onrefresh();
      if (returnToList) onclose();
    } catch (e) {
      error = (e as Error).message;
      conflict = e instanceof ApiError && e.status === 409;
    } finally {
      pending = false;
    }
  }
  async function assign(e: SubmitEvent) {
    e.preventDefault();
    if (pending || conflict) return;
    pending = true;
    error = '';
    try {
      await api('/leads/assign', body('POST', { lead_id: id, user_id: assignee, reason }));
      dirty = false;
      reason = '';
      success = '담당자를 변경했습니다.';
      await onrefresh();
    } catch (e) {
      error = (e as Error).message;
    } finally {
      pending = false;
    }
  }
  async function remove() {
    if (pending) return;
    pending = true;
    error = '';
    try {
      await api(`/leads/${id}`, body('DELETE'));
      dirty = false;
      await onrefresh();
      onclose();
    } catch (e) {
      error = (e as Error).message;
    } finally {
      pending = false;
    }
  }
</script>

{#snippet history(customer: Lead)}
  <div class="timeline">
    {#each customer.timeline || [] as event (event.id)}<article class="timeline-item">
        <span class="timeline-dot"
          ><Icon name={event.kind === 'ASSIGNMENT' ? 'assign' : 'clock'} size={14} /></span
        >
        <div>
          <div class="timeline-heading">
            <strong
              >{event.kind === 'ASSIGNMENT'
                ? '담당자 배분'
                : event.activity_type
                  ? activities[event.activity_type]
                  : '업무 기록'}</strong
            ><time>{date(event.created_at, true)}</time>
          </div>
          {#if event.kind === 'ACTIVITY'}<a
              class="text-button"
              id={`record-${event.id}`}
              href={`/leads/${id}/records/${event.id}?from=${encodeURIComponent(navigation.url.searchParams.get('from') || '/leads')}`}
              >기록 상세·정정</a
            >{/if}
          <small
            >{event.actor_name}{event.kind === 'ASSIGNMENT'
              ? ` → ${event.assignee_name || '담당자'}`
              : ''}</small
          >{#if event.new_status}<div class="status-transition">
              {event.previous_status ? statuses[event.previous_status] : ''} → <Badge
                tone={event.new_status}>{statuses[event.new_status]}</Badge
              >
            </div>{/if}{#if event.memo || event.reason}<p>
              {event.memo || event.reason}
            </p>{/if}
        </div>
      </article>{:else}<p class="muted">
        아직 기록된 활동이 없습니다. 첫 업무 기록을 남겨 보세요.
      </p>{/each}
  </div>
{/snippet}

<section class="panel detail-page" aria-label="고객 상세">
  {#if lead.isPending}<AsyncState
      loading
      message="고객 정보를 불러오고 있어요…"
    />{:else if lead.isError}<div class="alert error" role="alert">
      {lead.error.message}<Button variant="secondary" onclick={() => lead.refetch()}
        >다시 시도</Button
      >
    </div>{:else if lead.data}{@const customer = lead.data}
    <div class="detail-body">
      <div class="customer-detail-title">
        <span class="customer-avatar large">{customer.name.slice(0, 1)}</span>
        <div>
          <h2>{customer.name}</h2>
          <a class="phone-link" href={`tel:${customer.phone}`}
            ><Icon name="phone" size={14} />{customer.phone}</a
          >
        </div>
        <Badge tone={customer.current_status}>{statuses[customer.current_status]}</Badge>
      </div>
      <dl class="detail-grid">
        <div>
          <dt>유입 경로</dt>
          <dd>
            {customer.source ? sources[customer.source] : '—'}{customer.source_detail
              ? ` · ${customer.source_detail}`
              : ''}
          </dd>
        </div>
        <div>
          <dt>담당자</dt>
          <dd>{customer.assignee_name || '미배분'}</dd>
        </div>
        <div>
          <dt>유입일</dt>
          <dd>{date(customer.acquired_at, true)}</dd>
        </div>
        <div>
          <dt>시스템 등록일</dt>
          <dd>{date(customer.created_at, true)}</dd>
        </div>
        <div>
          <dt>현재 담당자 배분일</dt>
          <dd>{date(customer.assigned_at, true)}</dd>
        </div>
        <div>
          <dt>재통화 일정</dt>
          <dd>{date(customer.callback_at, true)}</dd>
        </div>
      </dl>
      {#if customer.assignment_pending}<p class="field-hint">
          배분 후 미처리 · 현재 담당자가 이번 배분 이후 아직 업무 기록을 남기지 않았습니다.
        </p>{/if}
      {#if customer.initial_memo}<div class="initial-memo">
          <small>최초 메모</small>
          <p>{customer.initial_memo}</p>
        </div>{/if}{#if isAdmin}<div class="detail-admin-actions">
          <Button variant="secondary" disabled={pending} onclick={() => onedit(customer)}
            >정보 수정</Button
          ><button
            class="text-button danger-text"
            disabled={pending}
            onclick={() => (deleting = true)}>고객 삭제</button
          >
        </div>{/if}{#if deleting}<div class="alert warning">
          <p>이 고객을 목록에서 삭제할까요? 업무 이력은 보존됩니다.</p>
          <div class="inline-actions">
            <Button variant="secondary" onclick={() => (deleting = false)}>취소</Button><Button
              variant="danger"
              disabled={pending}
              onclick={remove}>{pending ? '삭제 중…' : '삭제 확인'}</Button
            >
          </div>
        </div>{/if}
      <nav class="tabs" aria-label="고객 상세 메뉴">
        <a
          href={href('activity')}
          aria-current={tab === 'activity' ? 'page' : undefined}
          class:active={tab === 'activity'}>업무 기록</a
        ><a
          href={href('timeline')}
          aria-current={tab === 'timeline' ? 'page' : undefined}
          class:active={tab === 'timeline'}
          >전체 타임라인 <span>{customer.timeline?.length || 0}</span></a
        >{#if isAdmin}<a
            href={href('assignment')}
            aria-current={tab === 'assignment' ? 'page' : undefined}
            class:active={tab === 'assignment'}>담당자 변경</a
          >{/if}
      </nav>
      {#if error}<div class="alert error" role="alert">
          <p>{error}</p>
          {#if conflict}<Button
              variant="secondary"
              onclick={async () => {
                if (
                  !window.confirm(
                    '최신 정보를 불러오면 입력 중인 상태와 메모가 초기화됩니다. 계속할까요?',
                  )
                )
                  return;
                const result = await lead.refetch();
                if (result.isSuccess) {
                  dirty = false;
                  memo = '';
                  conflict = false;
                  error = '';
                }
              }}>최신 정보 불러오기</Button
            >{/if}
        </div>{/if}{#if success}<p class="alert success" role="status">
          {success}
        </p>{/if}{#if tab === 'activity'}<div class="consultation-layout">
          <form
            class="activity-form"
            aria-busy={pending}
            oninput={() => (dirty = true)}
            onchange={() => (dirty = true)}
            onsubmit={save}
          >
            <fieldset disabled={pending || conflict}>
              <h3>어떤 업무를 진행하셨나요?</h3>
              <div class="activity-options">
                {#each Object.entries(activities) as [key, label]}<button
                    type="button"
                    class:chosen={activity === key}
                    aria-pressed={activity === key}
                    onclick={() => {
                      activity = key;
                      dirty = true;
                    }}>{label}</button
                  >{/each}
              </div>
              {#if activity === 'KAKAO_SENT'}<p class="field-hint">
                  외부에서 전달한 카카오톡을 수동 기록합니다.
                </p>{/if}<Field label="현재 상태"
                ><select bind:value={status}
                  >{#each Object.entries(statuses) as [key, label]}<option value={key}
                      >{label}</option
                    >{/each}</select
                ></Field
              >{#if status === 'CALLBACK'}<Field label="재통화 일시 * (한국 표준시)"
                  ><input type="datetime-local" bind:value={callback} required /></Field
                >{/if}<Field label="업무 메모"
                ><textarea
                  bind:value={memo}
                  rows="5"
                  placeholder="연락 결과와 다음에 확인할 내용을 남겨 주세요."
                  maxlength="10000"
                ></textarea></Field
              >
              <div class="consultation-actions">
                <Button type="submit" disabled={pending}
                  ><Icon name="check" size={17} />{pending ? '저장 중…' : '업무 기록 저장'}</Button
                >
                <Button type="submit" value="return" variant="secondary" disabled={pending}
                  >저장 후 목록으로</Button
                >
              </div>
            </fieldset>
          </form>
          <section class="consultation-history" aria-label="이전 상담 및 배분 이력">
            <h3>이전 상담 및 배분 이력</h3>
            {@render history(customer)}
          </section>
        </div>{:else if tab === 'assignment'}<form
          class="activity-form"
          aria-busy={pending}
          oninput={() => (dirty = true)}
          onchange={() => (dirty = true)}
          onsubmit={assign}
        >
          <fieldset disabled={pending || usersLoading || !!usersError}>
            {#if usersLoading}<AsyncState
                loading
                message="직원 목록을 불러오고 있어요…"
              />{:else if usersError}<AsyncState
                message={usersError}
                retry={retryUsers}
              />{:else if !users.some((u) => u.status === 'ACTIVE' && u.role === 'USER')}<p
                class="alert warning"
              >
                변경 가능한 직원이 없습니다.
              </p>{/if}
            <p class="field-hint">
              재배분해도 상담 상태·재통화 일정·기존 기록은 유지됩니다. 이전 담당자는 더 이상 조회할
              수 없습니다.
            </p>
            <Field label="새 담당자"
              ><select bind:value={assignee} required
                ><option value="" disabled>직원을 선택하세요</option
                >{#each users.filter((u) => u.status === 'ACTIVE' && u.role === 'USER') as user}<option
                    value={user.id}>{user.name}</option
                  >{/each}</select
              ></Field
            ><Field label="변경 사유"
              ><textarea bind:value={reason} rows="3" placeholder="담당자 변경 사유를 남겨 주세요."
              ></textarea></Field
            ><Button
              type="submit"
              disabled={pending || !assignee || assignee === customer.assignee_id}
              >{pending ? '변경 중…' : '담당자 변경'}</Button
            >
          </fieldset>
        </form>{:else}{@render history(customer)}{/if}
    </div>{/if}
</section>
