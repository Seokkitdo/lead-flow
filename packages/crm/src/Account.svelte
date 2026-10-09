<script lang="ts">
  import { createQuery } from '@tanstack/svelte-query';
  import { api, ApiError, body, type User } from '@leadflow/api-client';
  import { AsyncState, Field, Button } from '@leadflow/ui';
  import { protectChanges } from './navigation.svelte';
  let {
    onsaved,
    onpasswordchanged,
  }: { onsaved: (user: User) => void; onpasswordchanged: () => void } = $props();
  const account = createQuery(() => ({
    queryKey: ['account'],
    queryFn: () => api<User>('/auth/me'),
    refetchOnWindowFocus: false,
  }));
  let phone = $state(''),
    currentPassword = $state(''),
    password = $state(''),
    confirmation = $state(''),
    error = $state(''),
    success = $state(''),
    dirty = $state(false),
    pending = $state(false),
    conflict = $state(false);
  protectChanges(() => (pending ? 'pending' : dirty ? 'dirty' : null));
  $effect(() => {
    if (account.data && !dirty) phone = account.data.phone || '';
  });
  async function reload() {
    if (dirty && !window.confirm('입력 내용을 버리고 최신 계정 정보를 불러올까요?')) return;
    const result = await account.refetch();
    if (result.isSuccess) {
      dirty = false;
      conflict = false;
      error = '';
      currentPassword = '';
      password = '';
      confirmation = '';
    }
  }
  async function save(e: SubmitEvent) {
    e.preventDefault();
    if (pending || conflict) return;
    error = '';
    success = '';
    if (password !== confirmation) {
      error = '새 비밀번호 확인이 일치하지 않습니다.';
      return;
    }
    pending = true;
    try {
      const user = await api<User>(
        '/auth/me',
        body('PATCH', {
          version: account.data?.version,
          phone,
          current_password: currentPassword,
          ...(password ? { password } : {}),
        }),
      );
      const changedPassword = !!password;
      dirty = false;
      currentPassword = '';
      password = '';
      confirmation = '';
      onsaved(user);
      if (changedPassword) {
        onpasswordchanged();
        return;
      }
      await account.refetch();
      success = '계정 정보를 저장했습니다.';
    } catch (e) {
      error = (e as Error).message;
      conflict = e instanceof ApiError && e.status === 409;
    } finally {
      pending = false;
    }
  }
</script>

{#if account.isPending}<AsyncState loading message="계정 정보를 불러오고 있어요…" />
{:else if account.isError}<AsyncState
    message={account.error.message}
    retry={() => account.refetch()}
  />
{:else if account.data}<section class="panel editor-page">
    <h2>{account.data.name}</h2>
    <p>{account.data.login_id} · {account.data.role === 'ADMIN' ? '관리자' : '직원'}</p>
    <p>
      비밀번호를 변경하면 모든 기기의 로그인 세션이 종료됩니다. 새 비밀번호로 다시 로그인해 주세요.
    </p>
    {#if error}<p class="alert error" role="alert">{error}</p>{/if}
    {#if conflict}<Button variant="secondary" onclick={reload}>최신 계정 정보 불러오기</Button>{/if}
    {#if success}<p class="alert success" role="status">{success}</p>{/if}
    <form
      onsubmit={save}
      oninput={() => {
        dirty = true;
        success = '';
      }}
      aria-busy={pending}
    >
      <fieldset disabled={pending || conflict}>
        <Field label="연락처"
          ><input type="tel" bind:value={phone} maxlength="30" autocomplete="tel" /></Field
        >
        <Field label="현재 비밀번호 *"
          ><input
            type="password"
            bind:value={currentPassword}
            required
            maxlength="128"
            autocomplete="current-password"
          /></Field
        >
        <Field label="새 비밀번호" hint="변경할 때만 12자 이상 입력하세요."
          ><input
            type="password"
            bind:value={password}
            aria-label="새 비밀번호"
            minlength="12"
            maxlength="128"
            autocomplete="new-password"
          /></Field
        >
        <Field label="새 비밀번호 확인"
          ><input
            type="password"
            bind:value={confirmation}
            required={!!password}
            maxlength="128"
            autocomplete="new-password"
          /></Field
        >
        <Button type="submit" disabled={pending}>{pending ? '저장 중…' : '계정 정보 저장'}</Button>
      </fieldset>
    </form>
  </section>{/if}
