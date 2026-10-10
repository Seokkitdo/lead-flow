<script lang="ts">
  import { createQuery } from '@tanstack/svelte-query';
  import {
    api,
    ApiError,
    body,
    activities,
    statuses,
    date,
    localInput,
    fromLocal,
    type Lead,
  } from '@leadflow/api-client';
  import { AsyncState, EmptyState, Field, Button } from '@leadflow/ui';
  import { protectChanges } from './navigation.svelte';
  let {
    id,
    recordId,
    backHref,
    onrefresh,
  }: { id: string; recordId: string; backHref: string; onrefresh: () => Promise<void> } = $props();
  const lead = createQuery(() => ({
    queryKey: ['lead', id],
    queryFn: () => api<Lead>(`/leads/${id}`),
    refetchOnWindowFocus: false,
  }));
  const original = $derived(
    lead.data?.timeline?.find((event) => event.id === recordId && event.kind === 'ACTIVITY'),
  );
  let kind = $state('CORRECTION'),
    reason = $state(''),
    memo = $state(''),
    status = $state(''),
    callback = $state(''),
    dirty = $state(false),
    pending = $state(false),
    conflict = $state(false),
    error = $state(''),
    success = $state('');
  protectChanges(() => (pending ? 'pending' : dirty ? 'dirty' : null));
  $effect(() => {
    if (lead.data && !dirty) {
      status = lead.data.current_status;
      callback = localInput(lead.data.callback_at);
    }
  });
  async function reload() {
    if (!window.confirm('입력 내용을 버리고 최신 정보를 불러올까요?')) return;
    const result = await lead.refetch();
    if (result.isSuccess) {
      dirty = false;
      conflict = false;
      reason = '';
      memo = '';
      error = '';
    }
  }
  async function save(e: SubmitEvent) {
    e.preventDefault();
    if (pending || conflict) return;
    pending = true;
    error = '';
    success = '';
    try {
      await api(
        `/leads/${id}/activities/${recordId}/corrections`,
        body('POST', {
          version: lead.data?.version,
          kind,
          reason,
          memo,
          status,
          callback_at: status === 'CALLBACK' ? fromLocal(callback) : null,
        }),
      );
      dirty = false;
      reason = '';
      memo = '';
      await onrefresh();
      success = '기존 기록은 그대로 두고 변경 내용을 추가했습니다.';
    } catch (e) {
      error = (e as Error).message;
      conflict = e instanceof ApiError && e.status === 409;
    } finally {
      pending = false;
    }
  }
</script>

<a class="back-link" href={backHref}>전체 기록으로</a>
{#if lead.isPending}<AsyncState loading message="업무 기록을 불러오는 중…" />
{:else if lead.isError}<AsyncState message={lead.error.message} retry={() => lead.refetch()} />
{:else if !original}<EmptyState
    title="업무 기록을 찾을 수 없습니다"
    description="고객의 전체 기록에서 기록을 다시 선택해 주세요."
  />
{:else}<section class="panel editor-page">
    <h2>업무 기록 상세</h2>
    <h3>{original.activity_type ? activities[original.activity_type] : '업무 기록'}</h3>
    <p>{original.actor_name} · {date(original.created_at, true)}</p>
    {#if original.new_status}<p>
        {original.previous_status ? statuses[original.previous_status] : ''} → {statuses[
          original.new_status
        ]}
      </p>{/if}
    <div class="initial-memo"><p>{original.memo || '메모가 없습니다.'}</p></div>
    <h3>기록 바로잡기</h3>
    <p>
      기존 기록은 그대로 남고, 바로잡을 내용이나 취소 사유가 새 기록으로 추가됩니다. 상담 상태와
      재통화 일정은 이전 값으로 돌아가지 않으므로 아래에서 함께 확인해 주세요.
    </p>
    {#if error}<p class="alert error" role="alert">{error}</p>{/if}{#if conflict}<Button
        variant="secondary"
        onclick={reload}>최신 정보 불러오기</Button
      >{/if}{#if success}<p class="alert success" role="status">{success}</p>{/if}
    <form
      onsubmit={save}
      oninput={() => {
        dirty = true;
        success = '';
      }}
      onchange={() => (dirty = true)}
      aria-busy={pending}
    >
      <fieldset disabled={pending || conflict}>
        <Field label="변경할 내용"
          ><select bind:value={kind}
            ><option value="CORRECTION">내용 바로잡기</option><option value="CANCELLATION"
              >취소 사유 기록</option
            ></select
          ></Field
        >
        <Field label="사유 *"
          ><textarea bind:value={reason} required maxlength="1000" rows="3"></textarea></Field
        >
        <Field label={kind === 'CORRECTION' ? '바로잡을 내용 *' : '추가 설명'}
          ><textarea bind:value={memo} required={kind === 'CORRECTION'} maxlength="8000" rows="4"
          ></textarea></Field
        >
        <Field label="저장 후 상담 상태"
          ><select bind:value={status}
            >{#each Object.entries(statuses) as [key, label]}<option value={key}>{label}</option
              >{/each}</select
          ></Field
        >
        {#if status === 'CALLBACK'}<Field label="재통화 일시 * (한국 시간)"
            ><input type="datetime-local" bind:value={callback} required /></Field
          >{/if}
        <Button type="submit" disabled={pending}>{pending ? '저장 중…' : '변경 내용 저장'}</Button>
      </fieldset>
    </form>
  </section>{/if}
