<script lang="ts">
  import { onMount, tick } from 'svelte';
  import { createQuery, useQueryClient, keepPreviousData } from '@tanstack/svelte-query';
  import {
    api,
    body,
    ApiError,
    statuses,
    sources,
    date,
    type User,
    type Lead,
    type LeadPage,
    type Dashboard,
  } from '@leadflow/api-client';
  import { modalFocus, Badge, Button, Field, EmptyState, Icon, AsyncState } from '@leadflow/ui';
  import LeadPanel from './LeadPanel.svelte';
  import LeadEditor from './LeadEditor.svelte';
  import Team from './Team.svelte';
  import WorkList from './WorkList.svelte';
  import Account from './Account.svelte';
  import RecordDetail from './RecordDetail.svelte';
  import DesignSystem from './DesignSystem.svelte';
  import { createNavigation, parseRoute, paths, safeReturn } from './navigation.svelte';
  const client = useQueryClient();
  const navigation = createNavigation();
  const route = $derived(parseRoute(navigation.url.pathname));
  const view = $derived(route.view);
  const selectedId = $derived(route.leadId || null);
  const detailPage = $derived(!!route.leadId || route.create);
  const listReturn = $derived(safeReturn(navigation.url.searchParams.get('from'), '/leads'));
  let refreshing = $state(false),
    loggingOut = $state(false),
    sessionError = $state('');
  let registeredUser = $state<User | null>(null);
  let copiedGuide = $state('');
  async function copyGuide() {
    if (!registeredUser) return;
    try {
      await navigator.clipboard.writeText(
        `${registeredUser.name}님, LeadFlow에 접속해 주세요.\n접속 주소: ${location.origin}/login\n로그인 아이디: ${registeredUser.login_id}\n초기 비밀번호는 관리자에게 별도로 전달받아 주세요. 로그인 후 내 계정 설정에서 변경할 수 있습니다.`,
      );
      copiedGuide = '접속 안내를 복사했습니다. 초기 비밀번호는 직원에게 별도로 전달해 주세요.';
    } catch {
      copiedGuide = '복사하지 못했습니다. 아래 접속 주소와 로그인 아이디를 직접 복사해 주세요.';
    }
  }
  function leadHref(id: string) {
    return `/leads/${id}?from=${encodeURIComponent(navigation.url.pathname + navigation.url.search)}`;
  }
  function newLead() {
    navigation.go(
      `/leads/new?from=${encodeURIComponent(navigation.url.pathname + navigation.url.search)}`,
    );
  }
  function detailHref(id: string, tab = '') {
    return `/leads/${id}${tab ? '/' + tab : ''}?from=${encodeURIComponent(listReturn)}`;
  }
  $effect(() => {
    const query = navigation.url.searchParams;
    search = query.get('search') || '';
    status = query.get('status') || '';
    source = query.get('source') || '';
    assignee = query.get('assignee_id') || '';
    assignment = query.get('assignment') || '';
    workPending = query.get('work_pending') || '';
    acquiredFrom = query.get('acquired_from') || '';
    acquiredTo = query.get('acquired_to') || '';
    const requestedPage = Number(query.get('page'));
    page = Number.isSafeInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1;
  });
  const pathname = $derived(navigation.url.pathname);
  const selectionScope = $derived.by(() => {
    const query = new URLSearchParams(navigation.url.search);
    query.delete('page');
    query.sort();
    return `${pathname}?${query}`;
  });
  $effect(() => {
    selectionScope;
    selected = [];
  });
  $effect(() => {
    pathname;
    selected = [];
    error = '';
    notice = '';
    assigning = false;
    assignUsers = [];
    reason = '';
  });
  $effect(() => {
    document.title = `${detailPage ? (route.create ? '고객 등록' : route.tab === 'edit' ? '고객 정보 수정' : '고객 상세') : titles[view] || '페이지를 찾을 수 없습니다'} · LeadFlow`;
  });
  async function checkSession() {
    checking = true;
    sessionError = '';
    try {
      session = await api<User>('/auth/me');
      if (view === 'login')
        navigation.go(loginDestination(), {
          replace: true,
          force: true,
        });
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) showLogin();
      else sessionError = (e as Error).message;
    } finally {
      checking = false;
    }
  }
  function loginDestination() {
    const fallback = session?.role === 'ADMIN' ? '/' : '/leads';
    const next = safeReturn(navigation.url.searchParams.get('next'), fallback);
    const target = parseRoute(new URL(next, location.origin).pathname);
    if (
      session?.role !== 'ADMIN' &&
      (next === '/' ||
        target.view === 'assign' ||
        target.view === 'team' ||
        target.view === 'staff' ||
        target.create ||
        target.tab === 'edit' ||
        target.tab === 'assignment')
    )
      return fallback;
    return next;
  }
  function showLogin() {
    const next = navigation.url.pathname + navigation.url.search;
    session = null;
    client.clear();
    if (view !== 'login' && view !== 'design')
      navigation.go(`/login?next=${encodeURIComponent(next)}`, { replace: true, force: true });
  }

  let session = $state<User | null>(null),
    checking = $state(true),
    loginId = $state(''),
    password = $state(''),
    error = $state(''),
    pending = $state(false);
  let search = $state(''),
    status = $state(''),
    source = $state(''),
    assignee = $state(''),
    assignment = $state(''),
    workPending = $state(''),
    acquiredFrom = $state(''),
    acquiredTo = $state(''),
    page = $state(1);
  let selected = $state<string[]>([]),
    assignUsers = $state<string[]>([]),
    reason = $state(''),
    assigning = $state(false),
    notice = $state('');
  const isAdmin = $derived(session?.role === 'ADMIN');
  const forbidden = $derived(
    !isAdmin &&
      (view === 'assign' ||
        view === 'team' ||
        view === 'staff' ||
        route.create ||
        route.tab === 'edit' ||
        route.tab === 'assignment'),
  );
  const titles: Record<string, string> = $derived({
    overview: '오늘의 업무 현황',
    leads: isAdmin ? '고객 목록' : '내 담당 고객',
    assign: '고객 배정',
    team: route.memberId === 'new' ? '직원 등록' : route.memberId ? '직원 계정 관리' : '직원 관리',
    staff: '직원 업무 상세',
    callbacks: '재통화 일정',
    account: '내 계정 설정',
    design: '디자인 시스템',
    login: '로그인',
    missing: '페이지를 찾을 수 없습니다',
  });
  $effect(() => {
    if (checking || sessionError || view === 'design') return;
    if (!session && view !== 'login') showLogin();
    else if (session && view === 'login')
      navigation.go(loginDestination(), {
        replace: true,
        force: true,
      });
  });
  onMount(() => {
    const stop = navigation.start();
    if (import.meta.env.DEV && new URLSearchParams(location.search).get('view') === 'design-system')
      navigation.go('/design-system', { replace: true, force: true });
    void checkSession();
    const expired = () => {
      showLogin();
      void tick().then(() => {
        error = '로그인이 만료되었습니다. 다시 로그인해 주세요.';
      });
    };
    window.addEventListener('leadflow:unauthorized', expired);
    const unguard = navigation.register(() =>
      pending || loggingOut ? 'pending' : assigning ? 'dirty' : null,
    );
    return () => {
      stop();
      unguard();
      window.removeEventListener('leadflow:unauthorized', expired);
    };
  });
  const params = $derived(
    new URLSearchParams(
      Object.entries({
        search,
        status,
        source,
        assignee_id: assignee,
        assignment: view === 'assign' ? 'unassigned' : assignment,
        work_pending: workPending,
        acquired_from: acquiredFrom,
        acquired_to: acquiredTo,
        page: String(page),
        page_size: '15',
      }).filter(([, v]) => v),
    ).toString(),
  );
  const leads = createQuery(() => ({
    queryKey: ['leads', params],
    queryFn: ({ signal }) => api<LeadPage>(`/leads?${params}`, { signal }),
    placeholderData: keepPreviousData,
    enabled:
      !!session && !forbidden && !detailPage && ['overview', 'leads', 'assign'].includes(view),
  }));
  const dashboard = createQuery(() => ({
    queryKey: ['dashboard'],
    queryFn: ({ signal }) => api<Dashboard>('/dashboard', { signal }),
    enabled: !!session && !forbidden && (isAdmin || view === 'overview'),
  }));
  const users = createQuery(() => ({
    queryKey: ['users'],
    queryFn: ({ signal }) => api<User[]>('/users', { signal }),
    enabled: isAdmin && view !== 'login',
  }));
  const editLead = createQuery(() => ({
    queryKey: ['lead', route.leadId],
    queryFn: () => api<Lead>(`/leads/${route.leadId}`),
    enabled: isAdmin && route.tab === 'edit',
    refetchOnWindowFocus: false,
  }));
  async function login(event: SubmitEvent) {
    event.preventDefault();
    if (pending) return;
    pending = true;
    error = '';
    try {
      client.clear();
      session = await api<User>('/auth/login', body('POST', { login_id: loginId, password }));
      password = '';
      navigation.go(loginDestination(), {
        replace: true,
        force: true,
      });
      await tick();
      document.querySelector<HTMLElement>('[data-page-heading]')?.focus();
    } catch (e) {
      error = (e as Error).message;
    } finally {
      pending = false;
    }
  }
  async function logout() {
    if (!navigation.allowed()) return;
    loggingOut = true;
    try {
      await api('/auth/logout', body('POST'));
      session = null;
      selected = [];
      client.clear();
      navigation.go('/login', { replace: true, force: true });
    } catch (e) {
      error = (e as Error).message;
    } finally {
      loggingOut = false;
    }
  }
  function navigate(next: string) {
    navigation.go(paths[next] || '/');
  }
  function syncFilters(replace = true) {
    const query = new URLSearchParams(
      Object.entries({
        search,
        status,
        source,
        assignee_id: assignee,
        assignment,
        work_pending: workPending,
        acquired_from: acquiredFrom,
        acquired_to: acquiredTo,
        page: page > 1 ? String(page) : '',
      }).filter(([, value]) => value),
    );
    navigation.go(`${navigation.url.pathname}${query.size ? '?' + query : ''}`, {
      replace,
      force: true,
    });
  }
  function resetPage() {
    page = 1;
    selected = [];
    queueMicrotask(() => syncFilters());
  }
  function pageTo(next: number) {
    page = next;
    syncFilters(false);
  }
  function metricHref(key: string) {
    if (key === 'callback') return '/callbacks?window=all';
    const query = new URLSearchParams();
    const filter = { callback: 'CALLBACK', completed: 'COMPLETED', in_progress: 'IN_PROGRESS' }[
      key as 'callback'
    ];
    if (filter) query.set('status', filter);
    if (key === 'today_new') {
      const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Seoul' }).format(new Date());
      query.set('acquired_from', today);
      query.set('acquired_to', today);
    }
    return `${key === 'unassigned' ? '/assignments' : '/leads'}${query.size ? '?' + query : ''}`;
  }
  async function refresh() {
    if (refreshing) return;
    refreshing = true;
    try {
      await client.invalidateQueries();
    } finally {
      refreshing = false;
    }
  }
  async function assign() {
    if (pending) return;
    pending = true;
    error = '';
    try {
      await api(
        '/leads/bulk-assign',
        body('POST', { lead_ids: selected, user_ids: assignUsers, reason }),
      );
      notice = `${selected.length}명의 고객을 배정했습니다.`;
      selected = [];
      assignUsers = [];
      assigning = false;
      reason = '';
      await refresh();
    } catch (e) {
      error = (e as Error).message;
    } finally {
      pending = false;
    }
  }
</script>

{#if import.meta.env.DEV && view === 'design'}
  <DesignSystem onclose={() => navigate('overview')} />
{:else if checking}
  <div class="loading-screen"><AsyncState loading message="업무 공간를 불러오는 중…" /></div>
{:else if sessionError}
  <main class="loading-screen"><AsyncState message={sessionError} retry={checkSession} /></main>
{:else if !session}
  <main class="login-layout">
    <section class="login-story">
      <a class="brand" href="/"
        ><span class="brand-mark">L</span>LeadFlow<span class="brand-period">.</span></a
      >
      <div>
        <span class="eyebrow light">고객 관리부터 상담 기록까지</span>
        <h1>고객과 다음 할 일을<br />한곳에서 확인하세요.</h1>
        <p>고객을 등록하고 담당자를 정한 뒤,<br />연락 결과와 다음 상담 일정을 기록하세요.</p>
        <div class="journey">
          <span>고객 등록</span><Icon name="arrow" /><span>담당자 배정</span><Icon
            name="arrow"
          /><span>상담 완료</span>
        </div>
      </div>
      <small>이전 상담 내용을 확인하고 다음 연락을 준비하세요.</small>
    </section>
    <section class="login-form">
      <div class="login-box">
        <span class="eyebrow">LeadFlow 로그인</span>
        <h2 data-page-heading tabindex="-1">로그인</h2>
        <p class="muted">발급받은 아이디와 비밀번호를 입력해 주세요.</p>
        <form onsubmit={login}>
          <Field label="로그인 아이디"
            ><input
              bind:value={loginId}
              autocomplete="username"
              required
              placeholder="아이디를 입력하세요"
            /></Field
          ><Field label="비밀번호"
            ><input
              type="password"
              bind:value={password}
              autocomplete="current-password"
              required
              placeholder="비밀번호를 입력하세요"
            /></Field
          >{#if error}<p role="alert" class="alert error">{error}</p>{/if}<Button
            type="submit"
            disabled={pending}
            >{pending ? '로그인 중…' : '로그인'}<Icon name="arrow" size={17} /></Button
          >
        </form>
        <p class="login-help">아이디가 없거나 비밀번호를 잊었다면 관리자에게 문의해 주세요.</p>
        {#if import.meta.env.DEV}
          <button class="text-button" onclick={() => navigate('design')}
            >LeadFlow 디자인 시스템 ↗</button
          >
        {/if}
      </div>
      <small class="login-footer">LeadFlow CRM · 고객과 업무를 연결합니다</small>
    </section>
  </main>
{:else if isAdmin && session.role !== 'ADMIN'}
  <main class="loading-screen">
    <h1>관리자 전용 업무 공간입니다</h1>
    <p>내 담당 고객 목록에서 업무를 진행해 주세요.</p>
    <Button onclick={logout}>로그아웃</Button>
  </main>
{:else}
  <div class="app-shell">
    <aside class="sidebar">
      <a href="/" class="brand"
        ><span class="brand-mark">L</span>LeadFlow<span class="brand-period">.</span></a
      >
      <div class="workspace-tag">
        <span class="workspace-symbol">LF</span>
        <div>
          <strong>LeadFlow 업무 공간</strong><small
            >{isAdmin ? '관리자 화면' : '직원 업무 공간'}</small
          >
        </div>
        <span class="online-dot"></span>
      </div>
      <span class="nav-label">메뉴</span>
      <nav aria-label="주 메뉴" class:admin-navigation={isAdmin}>
        {#each [{ key: 'overview', icon: 'dashboard', label: '업무 현황' }, { key: 'leads', icon: 'users', label: isAdmin ? '고객 목록' : '내 담당 고객' }, { key: 'callbacks', icon: 'clock', label: '재통화 일정' }, { key: 'account', icon: 'users', label: '내 계정 설정' }, ...(isAdmin ? [{ key: 'assign', icon: 'assign', label: '고객 배정' }, { key: 'team', icon: 'grid', label: '직원 관리' }] : [])] as item}<a
            href={paths[item.key]}
            aria-current={view === item.key ? 'page' : undefined}
            aria-label={item.label}
            class:active={view === item.key}
            ><Icon name={item.icon} /><span>{item.label}</span
            >{#if item.key === 'assign' && dashboard.data?.unassigned}<span class="nav-count"
                >{dashboard.data.unassigned}</span
              >{/if}</a
          >{/each}
      </nav>
      <div class="sidebar-bottom">
        {#if import.meta.env.DEV}
          <button class="design-link" onclick={() => navigate('design')}
            ><Icon name="grid" size={16} />디자인 시스템 <span>↗</span></button
          >
        {/if}
        <div class="profile">
          <span class="avatar">{session.name.slice(0, 1)}</span>
          <div>
            <strong>{session.name}</strong><small>{isAdmin ? '관리자' : '상담 담당자'}</small>
          </div>
          <button class="icon-button" aria-label="로그아웃" disabled={loggingOut} onclick={logout}
            ><Icon name="logout" size={17} /></button
          >
        </div>
      </div>
    </aside>
    <main class="main">
      <header class="topbar">
        <div>
          <span class="muted">업무 공간</span><span class="crumb-divider">/</span><strong
            >{detailPage ? '고객 상세' : titles[view]}</strong
          >
        </div>
        <div class="topbar-meta">
          <span class="live-dot"></span>업무 공간<span class="topbar-date"
            >{new Intl.DateTimeFormat('ko-KR', {
              timeZone: 'Asia/Seoul',
              month: 'long',
              day: 'numeric',
              weekday: 'short',
            }).format(new Date())}</span
          >
        </div>
        <button
          class="icon-button mobile-logout"
          aria-label="로그아웃"
          disabled={loggingOut}
          onclick={logout}><Icon name="logout" size={17} /></button
        >
      </header>
      {#key navigation.url.pathname}
        <div class="content page-enter">
          {#if error}<div class="alert error" role="alert">{error}</div>{/if}
          {#if forbidden}
            <h1 data-page-heading tabindex="-1">접근할 수 없는 페이지입니다</h1>
            <EmptyState
              title="관리자 권한이 필요합니다"
              description="내 담당 고객에서 업무를 계속해 주세요."
            />
            <a class="btn btn-primary" href="/leads">내 담당 고객으로</a>
          {:else if view === 'missing'}
            <h1 data-page-heading tabindex="-1">페이지를 찾을 수 없습니다</h1>
            <EmptyState
              title="주소를 확인해 주세요"
              description="페이지 주소가 잘못되었거나 더 이상 사용하지 않는 주소입니다."
            />
            <a class="btn btn-primary" href="/">업무 현황로</a>
          {:else if view === 'callbacks' || view === 'staff'}
            <h1 data-page-heading tabindex="-1">{titles[view]}</h1>
            {#if view === 'staff' && users.isPending}<AsyncState
                loading
                message="직원 정보를 불러오는 중…"
              />
            {:else if view === 'staff' && users.isError}<AsyncState
                message={users.error.message}
                retry={() => users.refetch()}
              />
            {:else if view === 'staff' && !users.data?.some((user) => user.id === route.memberId)}
              <EmptyState
                title="직원을 찾을 수 없습니다"
                description="직원 목록에서 다시 선택해 주세요."
              /><a href="/team" class="btn btn-secondary">직원 목록으로</a>
            {:else}<WorkList
                member={view === 'staff'
                  ? users.data?.find((user) => user.id === route.memberId)
                  : undefined}
              />{/if}
          {:else if view === 'account'}
            <h1 data-page-heading tabindex="-1">내 계정 설정</h1>
            <Account
              onsaved={(user) => {
                session = user;
              }}
              onpasswordchanged={() => {
                showLogin();
              }}
            />
          {:else if detailPage}
            <a
              class="back-link"
              href={route.tab === 'edit' ? detailHref(route.leadId!) : listReturn}
              ><Icon name="arrow" size={16} />{route.tab === 'edit' ? '고객 상세로' : '목록으로'}</a
            >
            <h1 class="detail-page-heading" data-page-heading tabindex="-1">
              {route.create ? '고객 등록' : route.tab === 'edit' ? '고객 정보 수정' : '고객 상세'}
            </h1>
            {#if route.create || route.tab === 'edit'}
              {#if route.tab === 'edit' && editLead.isPending}<AsyncState
                  loading
                  message="고객 정보를 불러오는 중…"
                />
              {:else if route.tab === 'edit' && editLead.isError}<AsyncState
                  message={editLead.error.message}
                  retry={() => editLead.refetch()}
                />
              {:else}<LeadEditor
                  users={users.data || []}
                  usersLoading={users.isPending}
                  usersError={users.error?.message}
                  retryUsers={() => users.refetch()}
                  lead={route.create ? null : editLead.data!}
                  onclose={() =>
                    navigation.go(route.create ? listReturn : detailHref(route.leadId!))}
                  onsaved={async (lead, continueAdding) => {
                    await refresh();
                    if (continueAdding) return;
                    navigation.go(detailHref(lead.id), { replace: true, force: true });
                    await tick();
                    notice = lead.assignee_name
                      ? `고객 정보를 저장했습니다. ${lead.assignee_name}님이 담당합니다.`
                      : '고객 정보를 저장했습니다. 담당자를 지정하면 직원이 업무를 시작할 수 있습니다.';
                  }}
                  onreload={async () => {
                    const result = await editLead.refetch();
                    if (result.error) throw result.error;
                  }}
                  onexisting={(id) => navigation.go(detailHref(id))}
                />{/if}
            {:else if selectedId && route.recordId}<RecordDetail
                id={selectedId}
                recordId={route.recordId}
                backHref={detailHref(selectedId, 'timeline')}
                onrefresh={refresh}
              />
            {:else if selectedId}<LeadPanel
                {listReturn}
                id={selectedId}
                tab={route.tab || 'activity'}
                {isAdmin}
                users={users.data || []}
                usersLoading={users.isPending}
                usersError={users.error?.message}
                retryUsers={() => users.refetch()}
                href={(tab) => detailHref(selectedId, tab)}
                onclose={() => navigation.go(listReturn, { replace: true, force: true })}
                onedit={() => navigation.go(detailHref(selectedId, 'edit'))}
                onrefresh={refresh}
              />{/if}
            {#if notice}<p class="alert success" role="status">{notice}</p>{/if}
          {:else}
            <div class="page-heading">
              <div>
                <h1 data-page-heading tabindex="-1">
                  {titles[view]}<span class="heading-dot">.</span>
                </h1>
                <p>
                  {view === 'overview'
                    ? `${session.name}님, 담당자 지정과 연락이 필요한 고객을 확인하세요.`
                    : view === 'assign'
                      ? '고객을 선택한 뒤 담당할 직원을 지정하세요.'
                      : view === 'team'
                        ? '직원을 등록하고 담당 고객과 업무 기록을 확인하세요.'
                        : '고객별 상담 상태와 다음 연락 일정을 확인하세요.'}
                </p>
              </div>
              {#if isAdmin && view !== 'team'}<Button onclick={newLead}
                  ><Icon name="plus" size={18} />고객 등록</Button
                >{/if}
            </div>
            {#if notice}<div class="alert success" role="status">
                {notice}<button class="text-button" onclick={() => (notice = '')}>닫기</button>
              </div>{/if}
            {#if view === 'overview'}
              {#if dashboard.isError}<p class="alert error" role="alert">
                  현황을 불러오지 못했습니다. <button
                    class="text-button"
                    onclick={() => dashboard.refetch()}>다시 시도</button
                  >
                </p>{/if}
              <div class="metrics">
                {#each [{ label: '오늘 문의', key: 'today_new', icon: 'users', hint: '문의일이 오늘인 고객' }, { label: isAdmin ? '담당자 없는 고객' : '전체 담당 고객', key: isAdmin ? 'unassigned' : 'total', icon: 'assign', hint: isAdmin ? '담당자를 지정해 주세요' : '현재 내가 담당하는 고객' }, { label: '연락·상담 진행 중', key: 'in_progress', icon: 'phone', hint: '연락 또는 상담 중인 고객' }, { label: '재통화 예정', key: 'callback', icon: 'clock', hint: '다시 연락하기로 한 고객' }, { label: '상담 완료', key: 'completed', icon: 'check', hint: '상담 완료로 기록한 고객' }] as metric, i}<a
                    class="metric"
                    class:metric-accent={i === 0}
                    href={metricHref(metric.key)}
                    ><span class="metric-label"
                      >{metric.label}<Icon name={metric.icon} size={18} /></span
                    ><strong
                      >{dashboard.data
                        ? metric.key === 'in_progress'
                          ? dashboard.data.status_counts.IN_PROGRESS || 0
                          : dashboard.data[
                              metric.key as keyof Pick<
                                Dashboard,
                                | 'total'
                                | 'today_new'
                                | 'unassigned'
                                | 'in_progress'
                                | 'callback'
                                | 'completed'
                              >
                            ]
                        : '—'}<small>명</small></strong
                    ><span class="metric-hint">{metric.hint}</span></a
                  >{/each}
              </div>
            {/if}
            {#if view === 'team'}
              {#if registeredUser && !route.memberId}
                <section class="panel panel-content" aria-label="직원 등록 완료">
                  <h2>{registeredUser.name}님을 등록했습니다</h2>
                  <p>접속 주소: {typeof location !== 'undefined' ? location.origin : ''}/login</p>
                  <p>로그인 아이디: <strong>{registeredUser.login_id}</strong></p>
                  <p>등록할 때 설정한 초기 비밀번호를 직원에게 별도로 전달해 주세요.</p>
                  <div class="inline-actions">
                    <Button variant="secondary" onclick={copyGuide}>접속 안내 복사</Button>
                    {#if registeredUser.role === 'USER' && registeredUser.status === 'ACTIVE'}<a
                        class="btn btn-primary"
                        href="/assignments">고객 배정하기</a
                      >{/if}
                  </div>
                  {#if copiedGuide}<p role="status">{copiedGuide}</p>{/if}
                </section>
              {/if}
              <Team
                onsaved={async (saved, created) => {
                  registeredUser = created ? saved : null;
                  copiedGuide = '';
                  navigation.go('/team', { replace: true, force: true });
                  await tick();
                  notice = '직원 정보를 저장했습니다.';
                }}
                memberId={route.memberId}
                loading={users.isPending}
                loadError={users.error?.message}
                retry={() => users.refetch()}
                statsLoading={dashboard.isPending}
                statsError={dashboard.error?.message}
                retryStats={() => dashboard.refetch()}
                users={users.data || []}
                stats={dashboard.data?.staff || []}
                onrefresh={refresh}
              />{:else}
              <section class="panel customer-panel" aria-busy={leads.isFetching}>
                <div class="section-heading">
                  <div>
                    <h2>
                      {view === 'overview'
                        ? '고객 현황'
                        : view === 'assign'
                          ? '배정 대기 고객'
                          : '고객 목록'} <span class="count-chip">{leads.data?.total ?? '—'}</span>
                    </h2>
                    <p>
                      {view === 'overview'
                        ? '최근 문의한 고객부터 표시합니다.'
                        : '고객 이름을 누르면 상세 정보와 업무 기록을 볼 수 있습니다.'}
                    </p>
                  </div>
                  <button
                    class="text-button"
                    disabled={refreshing || leads.isFetching}
                    onclick={refresh}
                    >{refreshing || leads.isFetching ? '새로고침 중…' : '↻ 새로고침'}</button
                  >
                </div>
                {#if !isAdmin}<div class="panel-content">
                    <nav class="inline-actions" aria-label="바로 시작할 업무">
                      <a class="btn btn-secondary" href="/callbacks?window=today"
                        >오늘 다시 연락할 고객</a
                      >
                      <a class="btn btn-secondary" href="/callbacks?window=overdue"
                        >연락 시간이 지난 고객</a
                      >
                      <a class="btn btn-secondary" href="/leads?work_pending=true"
                        >배정 후 기록 없는 고객</a
                      >
                    </nav>
                  </div>{/if}
                <div class="filters">
                  <select
                    aria-label="배정 후 기록 여부"
                    bind:value={workPending}
                    onchange={resetPage}
                  >
                    <option value="">전체 고객</option>
                    <option value="true">배정 후 기록 없음</option>
                  </select>
                  <div class="search-box">
                    <Icon name="search" size={18} /><input
                      aria-label="고객 검색"
                      placeholder="이름 또는 연락처 검색"
                      bind:value={search}
                      oninput={resetPage}
                    />{#if search}<button
                        aria-label="검색 초기화"
                        class="icon-button"
                        onclick={() => {
                          search = '';
                          resetPage();
                        }}><Icon name="close" size={14} /></button
                      >{/if}
                  </div>
                  <select aria-label="상담 상태 필터" bind:value={status} onchange={resetPage}
                    ><option value="">전체 상태</option
                    >{#each Object.entries(statuses) as [key, label]}<option value={key}
                        >{label}</option
                      >{/each}</select
                  ><select aria-label="문의 경로 필터" bind:value={source} onchange={resetPage}
                    ><option value="">전체 문의 경로</option
                    >{#each Object.entries(sources) as [key, label]}<option value={key}
                        >{label}</option
                      >{/each}</select
                  >{#if isAdmin}<select
                      aria-label="담당자 필터"
                      bind:value={assignee}
                      onchange={resetPage}
                      ><option value="">전체 담당자</option>{#each users.data || [] as user}<option
                          value={user.id}>{user.name}</option
                        >{/each}</select
                    >{/if}
                  <details class="more-filters">
                    <summary>검색 조건 더 보기</summary>
                    <div class="filter-popover">
                      <Field label="문의 시작일"
                        ><input type="date" bind:value={acquiredFrom} onchange={resetPage} /></Field
                      ><Field label="문의 종료일"
                        ><input type="date" bind:value={acquiredTo} onchange={resetPage} /></Field
                      >{#if isAdmin && view !== 'assign'}<Field label="배정 상태"
                          ><select bind:value={assignment} onchange={resetPage}
                            ><option value="">전체</option><option value="unassigned"
                              >담당자 미지정</option
                            ><option value="assigned">배정 완료</option></select
                          ></Field
                        >{/if}<Button
                        variant="secondary"
                        onclick={() => {
                          search = '';
                          status = '';
                          source = '';
                          assignee = '';
                          assignment = '';
                          workPending = '';
                          acquiredFrom = '';
                          acquiredTo = '';
                          resetPage();
                        }}>검색 조건 초기화</Button
                      >
                    </div>
                  </details>
                </div>
                {#if selected.length && isAdmin}<div class="selection-bar">
                    <strong>{selected.length}명 선택</strong><span
                      >최대 500명까지 선택할 수 있습니다. 페이지를 넘겨도 유지되며, 검색 조건을
                      바꾸면 선택이 해제됩니다.</span
                    ><Button onclick={() => (assigning = true)}>담당자 배정</Button><button
                      class="text-button"
                      onclick={() => (selected = [])}>선택 해제</button
                    >
                  </div>{/if}
                {#if leads.isPending}<AsyncState
                    loading
                    message="고객 목록을 불러오는 중…"
                  />{:else if leads.isError}<div class="empty-state" role="alert">
                    <p>{leads.error.message}</p>
                    <Button variant="secondary" onclick={() => leads.refetch()}>다시 시도</Button>
                  </div>{:else if !leads.data?.items.length}<EmptyState
                    title={search ||
                    status ||
                    source ||
                    assignee ||
                    assignment ||
                    workPending ||
                    acquiredFrom ||
                    acquiredTo
                      ? '검색 결과가 없습니다'
                      : view === 'assign'
                        ? '배정할 고객이 없습니다'
                        : '아직 고객이 없습니다'}
                    description={isAdmin
                      ? view === 'assign'
                        ? '담당자가 없는 고객만 표시됩니다. 검색 조건을 바꾸거나 새 고객을 등록해 주세요.'
                        : '검색 조건을 바꾸거나 새 고객을 등록해 주세요.'
                      : search || status || source || workPending || acquiredFrom || acquiredTo
                        ? '검색 조건에 맞는 고객이 없습니다. 조건을 바꿔 다시 확인해 주세요.'
                        : '관리자가 고객을 배정하면 이곳에 표시됩니다.'}
                  />{:else}<div class="table-scroll">
                    <table>
                      <thead
                        ><tr
                          >{#if isAdmin}<th class="checkbox-cell"
                              ><input
                                type="checkbox"
                                aria-label="현재 페이지 고객 전체 선택"
                                disabled={leads.isFetching}
                                checked={leads.data.items.every((l) => selected.includes(l.id))}
                                onchange={(e) =>
                                  (selected = e.currentTarget.checked
                                    ? [
                                        ...new Set([
                                          ...selected,
                                          ...leads.data!.items.map((l) => l.id),
                                        ]),
                                      ].slice(0, 500)
                                    : selected.filter(
                                        (id) => !leads.data!.items.some((lead) => lead.id === id),
                                      ))}
                              /></th
                            >{/if}<th>고객 정보</th><th>상담 상태</th><th>문의 경로</th
                          >{#if isAdmin}<th>담당자</th><th>문의일</th>{:else}<th>최근 메모</th><th
                              >배정일</th
                            >{/if}<th>최근 기록</th><th></th></tr
                        ></thead
                      ><tbody
                        >{#each leads.data.items as lead (lead.id)}<tr
                            class:row-selected={selectedId === lead.id}
                            >{#if isAdmin}<td class="checkbox-cell"
                                ><input
                                  type="checkbox"
                                  aria-label={`${lead.name} 선택`}
                                  disabled={leads.isFetching ||
                                    (selected.length >= 500 && !selected.includes(lead.id))}
                                  checked={selected.includes(lead.id)}
                                  onchange={(e) =>
                                    (selected = e.currentTarget.checked
                                      ? [...selected, lead.id]
                                      : selected.filter((id) => id !== lead.id))}
                                /></td
                              >{/if}<td
                              ><a
                                class="customer-name"
                                id={`lead-${lead.id}`}
                                href={leadHref(lead.id)}
                                ><span class="customer-avatar">{lead.name.slice(0, 1)}</span><span
                                  ><strong>{lead.name}</strong><small>{lead.phone}</small></span
                                ></a
                              ></td
                            ><td
                              ><Badge tone={lead.current_status}
                                >{statuses[lead.current_status]}</Badge
                              >
                              {#if lead.assignment_pending}<small class="assignment-note"
                                  >배정 후 기록 없음</small
                                >{/if}</td
                            ><td
                              ><span class="source-label"
                                >{lead.source ? sources[lead.source] : '—'}</span
                              ></td
                            >{#if isAdmin}<td
                                >{#if lead.assignee_name}<span class="assignee-avatar"
                                    >{lead.assignee_name.slice(0, 1)}</span
                                  >{lead.assignee_name}{:else}<span class="muted"
                                    >담당자 미지정</span
                                  >{/if}</td
                              ><td class="muted numeric">{date(lead.acquired_at)}</td>
                            {:else}<td class="memo-cell"
                                >{lead.latest_memo || '아직 상담 메모가 없습니다.'}</td
                              ><td class="muted numeric">{date(lead.assigned_at, true)}</td>{/if}<td
                              class="muted numeric">{date(lead.last_activity_at, true)}</td
                            ><td
                              ><a
                                class="btn btn-ghost"
                                aria-label={`${lead.name} ${isAdmin ? '상세 보기' : '업무 처리'}`}
                                href={leadHref(lead.id)}
                                >{isAdmin ? '상세 보기' : '업무 처리'}<Icon
                                  name="arrow"
                                  size={17}
                                /></a
                              ></td
                            ></tr
                          >{/each}</tbody
                      >
                    </table>
                  </div>{/if}
                <div class="pagination">
                  <span>전체 <strong>{leads.data?.total || 0}</strong>명 · 페이지당 15명</span>
                  <div>
                    <Button
                      variant="ghost"
                      disabled={page <= 1 || leads.isFetching}
                      onclick={() => pageTo(page - 1)}>이전</Button
                    ><span class="page-number">{page}</span><Button
                      variant="ghost"
                      disabled={leads.isFetching || page * 15 >= (leads.data?.total || 0)}
                      onclick={() => pageTo(page + 1)}>다음</Button
                    >
                  </div>
                </div>
              </section>
              {#if view === 'overview' && isAdmin && dashboard.data?.staff.length}<section
                  class="panel team-overview"
                >
                  <div class="section-heading">
                    <div>
                      <h2>팀 업무 현황</h2>
                      <p>담당자별 고객 관리 현황을 확인하세요.</p>
                    </div>
                    <button class="text-button" onclick={() => navigate('team')}>직원 관리 ↗</button
                    >
                  </div>
                  <div class="staff-cards">
                    {#each dashboard.data.staff as member}<div class="staff-card">
                        <a class="text-button" href={`/team/${member.id}/work`}>업무 상세</a>
                        <span class="avatar">{member.name.slice(0, 1)}</span>
                        <div>
                          <strong>{member.name}</strong><small
                            >담당 {member.total}명 · 완료 {member.completed}명 · 재통화 {member.callback}명</small
                          >
                        </div>
                      </div>{/each}
                  </div>
                </section>{/if}
            {/if}
          {/if}
          <footer class="page-footer">
            <span>LeadFlow · 고객 관리와 상담 기록</span><span
              >날짜와 시간은 한국 시간 기준입니다.</span
            >
          </footer>
        </div>
      {/key}
    </main>
  </div>
  {#if assigning}<div class="modal-backdrop">
      <div
        class="modal"
        use:modalFocus={() => {
          if (!pending) assigning = false;
        }}
        role="dialog"
        aria-modal="true"
        aria-label="담당자 배정"
        tabindex="-1"
      >
        <div class="modal-heading">
          <div>
            <h2>담당자 배정</h2>
          </div>
          <button
            class="icon-button"
            aria-label="닫기"
            disabled={pending}
            onclick={() => (assigning = false)}><Icon name="close" /></button
          >
        </div>
        <p class="muted">
          직원 한 명을 선택하면 모두 그 직원에게 배정합니다. 여러 명을 선택하면 이번에 선택한 고객을
          최대한 같은 수로 나눕니다. 현재 담당 고객 수는 배정 수에 반영하지 않습니다.
        </p>
        <fieldset disabled={pending}>
          {#if dashboard.isPending}<AsyncState loading message="직원별 업무량을 불러오는 중…" />
          {:else if dashboard.isError}<AsyncState
              message="직원별 담당 고객 수를 불러오지 못했습니다. 다시 불러오거나 직원을 선택해 배정을 진행할 수 있습니다."
              retry={() => dashboard.refetch()}
            />{/if}
          <div class="employee-choices">
            {#if users.isPending}<AsyncState
                loading
                message="직원 목록을 불러오는 중…"
              />{:else if users.isError}<AsyncState
                message={users.error.message}
                retry={() => users.refetch()}
              />{:else if !(users.data || []).some((u) => u.status === 'ACTIVE' && u.role === 'USER')}<p
              >
                배정 가능한 직원이 없습니다. 직원 관리에서 재직 중인 직원을 등록해 주세요.
                <a href="/team/new">직원 등록하기</a>
              </p>{/if}
            {#each (users.data || []).filter((u) => u.status === 'ACTIVE' && u.role === 'USER') as user}{@const stat =
                dashboard.data?.staff.find((item) => item.id === user.id)}<label
                ><input type="checkbox" value={user.id} bind:group={assignUsers} /><span
                  class="avatar">{user.name.slice(0, 1)}</span
                ><strong>{user.name}</strong>
                <span
                  >담당 {dashboard.isPending || dashboard.isError ? '—' : (stat?.total ?? 0)}명 ·
                  배정 후 기록 없음 {dashboard.isPending || dashboard.isError
                    ? '—'
                    : (stat?.pending ?? 0)}명</span
                >
              </label>{/each}
          </div>
          {#if assignUsers.length}
            <div class="alert" aria-label="배정 예정" aria-live="polite">
              <strong>이번에 배정할 고객</strong>
              {#each assignUsers as userId, index}
                <p>
                  {users.data?.find((user) => user.id === userId)?.name}: {Math.floor(
                    selected.length / assignUsers.length,
                  ) + (index < selected.length % assignUsers.length ? 1 : 0)}명
                </p>
              {/each}
            </div>
          {/if}
          <Field label="배정 사유"
            ><input bind:value={reason} placeholder="예: 신규 고객 정기 배정" /></Field
          >{#if error}<p class="alert error" role="alert">{error}</p>{/if}
        </fieldset>
        <div class="modal-actions">
          <Button variant="secondary" disabled={pending} onclick={() => (assigning = false)}
            >취소</Button
          ><Button
            disabled={!assignUsers.length || pending || users.isError || users.isPending}
            onclick={assign}>{pending ? '배정 중…' : `${selected.length}명 배정하기`}</Button
          >
        </div>
      </div>
    </div>{/if}
{/if}
