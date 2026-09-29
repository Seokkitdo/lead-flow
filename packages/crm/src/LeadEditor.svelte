<script lang="ts">
  import {
    api,
    body,
    ApiError,
    sources,
    localInput,
    fromLocal,
    date,
    type Lead,
  } from '@leadflow/api-client';
  import { Button, Field, Icon } from '@leadflow/ui';
  import { protectChanges } from './navigation.svelte';
  let {
    lead,
    onclose,
    onsaved,
    onexisting,
    onreload,
  }: {
    lead: Lead | null;
    onclose: () => void;
    onsaved: (lead: Lead) => void;
    onexisting: (id: string) => void;
    onreload: () => Promise<void>;
  } = $props();
  let name = $state(''),
    phone = $state(''),
    source = $state('ETC'),
    sourceDetail = $state(''),
    memo = $state(''),
    acquired = $state(''),
    error = $state(''),
    pending = $state(false),
    duplicates = $state<Lead[]>([]),
    dirty = $state(false),
    conflict = $state(false);
  protectChanges(() => (pending ? 'pending' : dirty ? 'dirty' : null));
  $effect(() => {
    name = lead?.name || '';
    phone = lead?.phone || '';
    source = lead?.source || 'ETC';
    sourceDetail = lead?.source_detail || '';
    memo = lead?.initial_memo || '';
    acquired = localInput(lead?.acquired_at || new Date().toISOString());
  });
  async function save(allowDuplicate = false) {
    if (pending || conflict) return;
    pending = true;
    error = '';
    try {
      const saved = await api<Lead>(
        lead ? `/leads/${lead.id}` : '/leads',
        body(lead ? 'PATCH' : 'POST', {
          name,
          phone,
          source,
          source_detail: sourceDetail,
          initial_memo: memo,
          acquired_at: fromLocal(acquired),
          allow_duplicate: allowDuplicate,
          ...(lead ? { version: lead.version } : {}),
        }),
      );
      dirty = false;
      await onsaved(saved);
    } catch (e) {
      if (
        e instanceof ApiError &&
        e.status === 409 &&
        typeof e.detail === 'object' &&
        e.detail &&
        'code' in e.detail &&
        'matches' in e.detail &&
        e.detail.code === 'DUPLICATE_PHONE'
      ) {
        duplicates = (e.detail as { matches: Lead[] }).matches;
      } else {
        error = (e as Error).message;
        conflict = e instanceof ApiError && e.status === 409;
      }
    } finally {
      pending = false;
    }
  }
</script>

<section class="panel editor-page" aria-label={lead ? '고객 수정' : '고객 등록'}>
  <div class="modal-heading">
    <div>
      <span class="eyebrow">CUSTOMER INFORMATION</span>
      <h2>{lead ? '고객 정보 수정' : '새 고객 등록'}</h2>
    </div>
    <button class="icon-button" aria-label="취소" disabled={pending} onclick={onclose}
      ><Icon name="close" /></button
    >
  </div>
  <p class="muted">첫 연결을 기록하고, 새로운 기회를 만들어 보세요.</p>
  {#if conflict}<div class="alert warning" role="alert">
      <p>다른 사용자가 고객 정보를 변경했습니다. 최신 내용을 확인한 뒤 다시 수정해 주세요.</p>
      <Button
        variant="secondary"
        disabled={pending}
        onclick={async () => {
          if (!window.confirm('입력 중인 내용을 버리고 최신 고객 정보를 불러올까요?')) return;
          pending = true;
          try {
            await onreload();
            dirty = false;
            conflict = false;
            error = '';
          } catch (e) {
            error = (e as Error).message;
          } finally {
            pending = false;
          }
        }}>최신 정보 불러오기</Button
      >
    </div>{/if}
  <form
    aria-busy={pending}
    oninput={() => {
      dirty = true;
      duplicates = [];
    }}
    onchange={() => {
      dirty = true;
      duplicates = [];
    }}
    onsubmit={(e) => {
      e.preventDefault();
      save();
    }}
  >
    <fieldset disabled={pending || conflict}>
      <div class="form-grid">
        <Field label="이름 *"
          ><input bind:value={name} required maxlength="100" placeholder="고객 이름" /></Field
        ><Field label="연락처 *"
          ><input
            type="tel"
            bind:value={phone}
            required
            maxlength="30"
            placeholder="010-0000-0000"
          /></Field
        ><Field label="유입 경로"
          ><select bind:value={source}
            >{#each Object.entries(sources) as [key, label]}<option value={key}>{label}</option
              >{/each}</select
          ></Field
        ><Field label="상세 경로"
          ><input bind:value={sourceDetail} placeholder="예: 9월 상담 신청 폼" /></Field
        >
      </div>
      <Field label="유입일 (한국 표준시)"
        ><input type="datetime-local" bind:value={acquired} required /></Field
      ><Field label="최초 메모"
        ><textarea rows="3" bind:value={memo} placeholder="고객의 관심사나 문의 내용을 기록하세요."
        ></textarea></Field
      >{#if duplicates.length}<div class="alert warning">
          <strong>같은 연락처의 고객이 있습니다</strong>{#each duplicates as match}<p>
              {match.name} · 유입 {date(match.acquired_at)} · {match.assignee_name || '미배분'}
              <button type="button" class="text-button" onclick={() => onexisting(match.id)}
                >기존 고객 보기 ↗</button
              >
            </p>{/each}<Button
            type="button"
            variant="secondary"
            disabled={pending}
            onclick={() => save(true)}>확인했어요, 그래도 등록</Button
          >
        </div>{/if}{#if error}<p class="alert error" role="alert">{error}</p>{/if}
      <div class="modal-actions">
        <Button type="button" variant="secondary" disabled={pending} onclick={onclose}>취소</Button
        ><Button type="submit" disabled={pending}
          >{pending ? '저장 중…' : lead ? '변경 사항 저장' : '고객 등록'}</Button
        >
      </div>
    </fieldset>
  </form>
</section>
