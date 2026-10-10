<script lang="ts">
  import { tick } from 'svelte';
  import {
    api,
    body,
    ApiError,
    sources,
    localInput,
    fromLocal,
    date,
    type Lead,
    type User,
  } from '@leadflow/api-client';
  import { Button, Field, Icon, AsyncState } from '@leadflow/ui';
  import { protectChanges } from './navigation.svelte';
  import { formatPhone, validPhone } from './phone';
  let form: HTMLFormElement;
  let {
    lead,
    onclose,
    onsaved,
    onexisting,
    onreload,
    users,
    usersLoading,
    usersError,
    retryUsers,
  }: {
    lead: Lead | null;
    onclose: () => void;
    onsaved: (lead: Lead, continueAdding: boolean) => void | Promise<void>;
    onexisting: (id: string) => void;
    onreload: () => Promise<void>;
    users: User[];
    usersLoading: boolean;
    usersError?: string;
    retryUsers: () => void;
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
  let assignee = $state('');
  let continueAdding = $state(false);
  let success = $state('');
  protectChanges(() => (pending ? 'pending' : dirty ? 'dirty' : null));
  $effect(() => {
    name = lead?.name || '';
    phone = formatPhone(lead?.phone || '');
    source = lead?.source || 'ETC';
    sourceDetail = lead?.source_detail || '';
    memo = lead?.initial_memo || '';
    acquired = localInput(lead?.acquired_at || new Date().toISOString());
  });
  async function save(allowDuplicate = false) {
    if (pending || conflict) return;
    const nameInput = form.elements.namedItem('customer-name') as HTMLInputElement;
    const phoneInput = form.elements.namedItem('customer-phone') as HTMLInputElement;
    nameInput.setCustomValidity(name.trim() ? '' : '고객 이름을 입력해 주세요.');
    phoneInput.setCustomValidity(
      validPhone(phone) ? '' : '연락처를 확인해 주세요. 예: 010-1234-5678',
    );
    if (!form.reportValidity()) return;
    pending = true;
    error = '';
    try {
      const saved = await api<Lead>(
        lead ? `/leads/${lead.id}` : '/leads',
        body(lead ? 'PATCH' : 'POST', {
          name: name.trim(),
          phone: phone.trim(),
          source,
          source_detail: sourceDetail,
          initial_memo: memo,
          acquired_at: fromLocal(acquired),
          allow_duplicate: allowDuplicate,
          ...(!lead ? { assignee_id: assignee || null } : {}),
          ...(lead ? { version: lead.version } : {}),
        }),
      );
      dirty = false;
      if (continueAdding && !lead) {
        name = '';
        phone = '';
        memo = '';
        acquired = localInput(new Date().toISOString());
        duplicates = [];
        success = `${saved.name} 고객을 등록했습니다.${saved.assignee_name ? ` 담당자: ${saved.assignee_name}` : ' 담당자는 나중에 지정할 수 있습니다.'}`;
      }
      await onsaved(saved, continueAdding && !lead);
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
      if (continueAdding && !dirty) {
        await tick();
        (form?.elements.namedItem('customer-name') as HTMLInputElement | null)?.focus();
      }
    }
  }
</script>

<section class="panel editor-page" aria-label={lead ? '고객 수정' : '고객 등록'}>
  <div class="modal-heading">
    <div>
      <h2>{lead ? '고객 정보 수정' : '새 고객 등록'}</h2>
    </div>
    <button class="icon-button" aria-label="취소" disabled={pending} onclick={onclose}
      ><Icon name="close" /></button
    >
  </div>
  <p class="muted">
    {lead
      ? '변경할 고객 정보를 입력해 주세요.'
      : '이름과 연락처는 필수입니다. 담당자는 지금 지정하거나 나중에 정할 수 있습니다.'}
  </p>
  {#if success}<p class="alert success" role="status">{success}</p>{/if}
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
    bind:this={form}
    novalidate
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
      continueAdding = (e.submitter as HTMLButtonElement | null)?.value === 'continue';
      save();
    }}
  >
    <fieldset disabled={pending || conflict}>
      <div class="form-grid">
        <Field label="이름 *"
          ><input
            name="customer-name"
            bind:value={name}
            oninput={(e) => e.currentTarget.setCustomValidity('')}
            required
            maxlength="100"
            placeholder="고객 이름"
          /></Field
        ><Field label="연락처 *"
          ><input
            type="tel"
            name="customer-phone"
            autocomplete="tel"
            value={phone}
            oninput={(e) => {
              const input = e.currentTarget;
              const position = input.selectionStart ?? input.value.length;
              const digitsBefore = input.value.slice(0, position).replace(/[^0-9]/g, '').length;
              phone = formatPhone(input.value);
              if (input.value !== phone) {
                input.value = phone;
                let caret = 0;
                let count = 0;
                while (caret < phone.length && count < digitsBefore) {
                  if (/[0-9]/.test(phone[caret])) count++;
                  caret++;
                }
                input.setSelectionRange(caret, caret);
              }
              input.setCustomValidity('');
            }}
            required
            maxlength="30"
            placeholder="010-0000-0000"
          /></Field
        ><Field label="문의 경로"
          ><select bind:value={source}
            >{#each Object.entries(sources) as [key, label]}<option value={key}>{label}</option
              >{/each}</select
          ></Field
        ><Field label="문의 경로 상세"
          ><input
            bind:value={sourceDetail}
            maxlength="255"
            placeholder="예: 9월 상담 신청서"
          /></Field
        >
      </div>
      {#if !lead}
        <Field label="담당자" hint="지금 지정하면 직원의 담당 고객 목록에 바로 표시됩니다.">
          <select aria-label="담당자" bind:value={assignee} disabled={usersLoading || !!usersError}>
            <option value="">나중에 지정</option>
            {#each users.filter((user) => user.role === 'USER' && user.status === 'ACTIVE') as user}
              <option value={user.id}>{user.name}</option>
            {/each}
          </select>
        </Field>
        {#if usersLoading}<AsyncState loading message="담당자를 불러오는 중…" />
        {:else if usersError}<AsyncState
            message="담당자를 불러오지 못했습니다. 나중에 지정으로 등록하거나 다시 불러와 주세요."
            retry={retryUsers}
          />
        {:else if !users.some((user) => user.role === 'USER' && user.status === 'ACTIVE')}
          <p class="field-hint">
            배정할 직원이 없습니다. 고객을 먼저 등록한 뒤 <a href="/team/new">직원을 등록</a>할 수
            있습니다.
          </p>
        {/if}
      {/if}
      <Field label="문의일 (한국 시간)" hint="고객이 처음 문의한 날짜와 시간입니다."
        ><input type="datetime-local" bind:value={acquired} required /></Field
      ><Field label="등록 메모"
        ><textarea
          rows="3"
          maxlength="10000"
          bind:value={memo}
          placeholder="처음 문의한 내용이나 담당자에게 전달할 사항을 적어 주세요."
        ></textarea></Field
      >{#if duplicates.length}<div class="alert warning">
          <strong>같은 연락처로 등록된 고객이 있습니다</strong>
          <p>
            기존 고객을 확인해 주세요. 가족이 같은 번호를 쓰거나 별도로 관리할 문의라면 새 고객으로
            등록할 수 있습니다.
          </p>
          {#each duplicates as match}<p>
              {match.name} · 문의일 {date(match.acquired_at)} · {match.assignee_name ||
                '담당자 미지정'}
              <button type="button" class="text-button" onclick={() => onexisting(match.id)}
                >기존 고객 보기 ↗</button
              >
            </p>{/each}<Button
            type="button"
            variant="secondary"
            disabled={pending}
            onclick={() => save(true)}>같은 번호로 새 고객 등록</Button
          >
        </div>{/if}{#if error}<p class="alert error" role="alert">{error}</p>{/if}
      <div class="modal-actions">
        <Button type="button" variant="secondary" disabled={pending} onclick={onclose}>취소</Button
        >{#if !lead}<Button type="submit" value="continue" variant="secondary" disabled={pending}
            >등록 후 계속 추가</Button
          >{/if}<Button type="submit" disabled={pending}
          >{pending ? '저장 중…' : lead ? '변경 사항 저장' : '고객 등록'}</Button
        >
      </div>
    </fieldset>
  </form>
</section>
