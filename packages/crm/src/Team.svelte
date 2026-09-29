<script lang="ts">
  import { api, body, type User, type Dashboard } from '@leadflow/api-client';
  import { Badge, Button, Field, Icon, EmptyState, AsyncState } from '@leadflow/ui';
  import { useNavigation, protectChanges } from './navigation.svelte';
  const navigation = useNavigation();
  let {
    users,
    memberId,
    loading,
    loadError,
    retry,
    statsLoading,
    statsError,
    retryStats,
    stats,
    onrefresh,
    onsaved,
  }: {
    users: User[];
    memberId?: string;
    loading: boolean;
    loadError?: string;
    retry: () => void;
    statsLoading: boolean;
    statsError?: string;
    retryStats: () => void;
    stats: Dashboard['staff'];
    onrefresh: () => Promise<void>;
    onsaved: () => Promise<void>;
  } = $props();
  const editing = $derived(
    memberId === 'new' ? 'new' : users.find((user) => user.id === memberId) || null,
  );
  let dirty = $state(false);
  protectChanges(() => (pending ? 'pending' : dirty ? 'dirty' : null));
  let name = $state(''),
    loginId = $state(''),
    password = $state(''),
    phone = $state(''),
    role = $state('USER'),
    status = $state('ACTIVE'),
    error = $state(''),
    pending = $state(false);
  $effect(() => {
    const user = editing;
    if (!user || dirty) return;
    name = user === 'new' ? '' : user.name;
    loginId = user === 'new' ? '' : user.login_id;
    phone = user === 'new' ? '' : user.phone || '';
    role = user === 'new' ? 'USER' : user.role;
    status = user === 'new' ? 'ACTIVE' : user.status;
    password = '';
    error = '';
  });
  async function save(e: SubmitEvent) {
    e.preventDefault();
    if (pending) return;
    pending = true;
    error = '';
    try {
      await api(
        editing === 'new' ? '/users' : `/users/${(editing as User).id}`,
        body(editing === 'new' ? 'POST' : 'PATCH', {
          name,
          ...(editing === 'new' ? { login_id: loginId } : {}),
          phone,
          role,
          status,
          ...(password ? { password } : {}),
        }),
      );
      dirty = false;
      await onrefresh();
      await onsaved();
    } catch (e) {
      error = (e as Error).message;
    } finally {
      pending = false;
    }
  }
</script>

{#if loading}<AsyncState loading message="직원 목록을 불러오고 있어요…" />
{:else if loadError}<AsyncState message={loadError} {retry} />
{:else if memberId && !editing}<EmptyState
    title="직원을 찾을 수 없습니다"
    description="직원 목록에서 계정을 다시 선택해 주세요."
  /><a class="btn btn-secondary" href="/team">직원 목록으로</a>
{:else if !memberId}
  <section class="panel">
    <div class="section-heading">
      <div>
        <h2>팀 구성원 <span class="count-chip">{users.length}</span></h2>
        <p>계정과 재직 상태를 관리하고 고객 현황을 확인하세요.</p>
      </div>
      <a class="btn btn-primary" href="/team/new"><Icon name="plus" size={17} />직원 등록</a>
    </div>
    {#if statsError}<AsyncState
        message="직원별 업무 현황을 불러오지 못했습니다."
        retry={retryStats}
      />{/if}
    {#if !users.length}<EmptyState
        title="등록된 직원이 없습니다"
        description="함께 고객을 관리할 직원을 등록하세요."
      />{:else}<div class="table-scroll">
        <table>
          <thead
            ><tr
              ><th>이름 / 계정</th><th>권한</th><th>재직 상태</th><th>담당 고객</th><th
                >상담 완료</th
              ><th>재통화 예정</th><th></th></tr
            ></thead
          ><tbody
            >{#each users as user (user.id)}{@const stat = stats.find((s) => s.id === user.id)}<tr
                ><td
                  ><div class="customer-name">
                    <span class="avatar">{user.name.slice(0, 1)}</span><span
                      ><strong>{user.name}</strong><small>{user.login_id}</small></span
                    >
                  </div></td
                ><td>{user.role === 'ADMIN' ? '관리자' : '직원'}</td><td
                  ><Badge tone={user.status === 'ACTIVE' ? 'COMPLETED' : 'HOLD'}
                    >{user.status === 'ACTIVE'
                      ? '재직'
                      : user.status === 'INACTIVE'
                        ? '비활성'
                        : '퇴사'}</Badge
                  ></td
                ><td>{statsLoading || statsError ? '—' : stat?.total || 0}명</td><td
                  >{statsLoading || statsError ? '—' : stat?.completed || 0}명</td
                ><td>{statsLoading || statsError ? '—' : stat?.callback || 0}명</td><td
                  ><a class="btn btn-ghost" id={`member-${user.id}`} href={`/team/${user.id}`}
                    >계정 관리</a
                  ></td
                ></tr
              >{/each}</tbody
          >
        </table>
      </div>{/if}
  </section>
{:else if editing}
  <a class="back-link" href="/team"><Icon name="arrow" size={16} />직원 목록으로</a>
  <section class="panel editor-page" aria-label="직원 계정 관리">
    <div class="modal-heading">
      <div>
        <span class="eyebrow">TEAM MEMBER</span>
        <h2>{editing === 'new' ? '새 직원 등록' : '직원 계정 관리'}</h2>
      </div>
      <button
        class="icon-button"
        aria-label="취소"
        disabled={pending}
        onclick={() => navigation.go('/team')}><Icon name="close" /></button
      >
    </div>
    <form
      onsubmit={save}
      aria-busy={pending}
      oninput={() => (dirty = true)}
      onchange={() => (dirty = true)}
    >
      <fieldset disabled={pending}>
        <div class="form-grid">
          <Field label="이름 *"><input bind:value={name} required maxlength="100" /></Field><Field
            label="로그인 ID *"
            ><input
              bind:value={loginId}
              disabled={editing !== 'new'}
              required
              minlength="3"
              maxlength="100"
              autocomplete="off"
            /></Field
          ><Field
            label={editing === 'new' ? '초기 비밀번호 *' : '새 비밀번호'}
            hint={editing === 'new'
              ? '12자 이상으로 입력하세요.'
              : '비워 두면 기존 비밀번호를 유지합니다.'}
            ><input
              type="password"
              bind:value={password}
              required={editing === 'new'}
              minlength="12"
              autocomplete="new-password"
            /></Field
          ><Field label="연락처"><input type="tel" bind:value={phone} /></Field><Field label="권한"
            ><select bind:value={role}
              ><option value="USER">직원</option><option value="ADMIN">관리자</option></select
            ></Field
          ><Field label="재직 상태"
            ><select bind:value={status}
              ><option value="ACTIVE">재직</option><option value="INACTIVE">비활성</option><option
                value="DEPARTED">퇴사</option
              ></select
            ></Field
          >
        </div>
        <p class="field-hint">
          비활성·퇴사 계정은 로그인과 신규 배분이 제한됩니다. 기존 업무 기록은 유지됩니다.
        </p>
        {#if error}<p class="alert error" role="alert">{error}</p>{/if}
        <div class="modal-actions">
          <Button
            type="button"
            variant="secondary"
            disabled={pending}
            onclick={() => navigation.go('/team')}>취소</Button
          ><Button type="submit" disabled={pending}>{pending ? '저장 중…' : '저장하기'}</Button>
        </div>
      </fieldset>
    </form>
  </section>
{/if}
