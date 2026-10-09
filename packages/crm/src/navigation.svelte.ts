import { getContext, onMount, setContext, tick } from 'svelte';

export type View =
  | 'overview'
  | 'leads'
  | 'assign'
  | 'team'
  | 'design'
  | 'login'
  | 'missing'
  | 'callbacks'
  | 'account'
  | 'staff';
export type Route = {
  view: View;
  leadId?: string;
  tab?: string;
  memberId?: string;
  recordId?: string;
  create?: boolean;
};
export function parseRoute(path: string): Route {
  const parts = path.split('/').filter(Boolean);
  if (!parts.length) return { view: 'overview' };
  if (parts.length === 1) {
    const views: Record<string, View> = {
      leads: 'leads',
      assignments: 'assign',
      team: 'team',
      'design-system': 'design',
      login: 'login',
      callbacks: 'callbacks',
      account: 'account',
    };
    return { view: Object.hasOwn(views, parts[0]) ? views[parts[0]] : 'missing' };
  }
  if (
    parts[0] === 'team' &&
    parts.length === 3 &&
    parts[2] === 'work' &&
    /^[\da-f-]{36}$/i.test(parts[1])
  )
    return { view: 'staff', memberId: parts[1] };
  if (
    parts[0] === 'leads' &&
    parts.length === 4 &&
    parts[2] === 'records' &&
    /^[\da-f-]{36}$/i.test(parts[1]) &&
    /^[\da-f-]{36}$/i.test(parts[3])
  )
    return { view: 'leads', leadId: parts[1], tab: 'record', recordId: parts[3] };
  if (parts[0] === 'leads') {
    if (parts[1] === 'new' && parts.length === 2) return { view: 'leads', create: true };
    if (
      /^[\da-f-]{36}$/i.test(parts[1]) &&
      parts.length <= 3 &&
      (!parts[2] || ['activity', 'timeline', 'assignment', 'edit'].includes(parts[2]))
    )
      return { view: 'leads', leadId: parts[1], tab: parts[2] || 'activity' };
  }
  if (
    parts[0] === 'team' &&
    parts.length === 2 &&
    (parts[1] === 'new' || /^[\da-f-]{36}$/i.test(parts[1]))
  )
    return { view: 'team', memberId: parts[1] };
  return { view: 'missing' };
}
export const paths: Record<string, string> = {
  overview: '/',
  leads: '/leads',
  assign: '/assignments',
  team: '/team',
  design: '/design-system',
  callbacks: '/callbacks',
  account: '/account',
};
const context = Symbol('navigation');
type Guard = () => 'pending' | 'dirty' | null;
export function createNavigation() {
  let url = $state(new URL(location.href));
  let revision = $state(0);
  let index = history.state?.leadflowIndex || 0;
  let reverting = false;
  let stopRestoring = () => {};
  const guards = new Set<Guard>();
  function allowed() {
    const states = [...guards].map((guard) => guard());
    if (states.includes('pending')) return false;
    return (
      !states.includes('dirty') ||
      window.confirm('저장하지 않은 내용이 있습니다. 변경 내용을 버리고 이동할까요?')
    );
  }
  function remember() {
    history.replaceState(
      {
        ...history.state,
        leadflowIndex: index,
        scroll: scrollY,
        focus: document.activeElement?.id,
      },
      '',
      url,
    );
  }
  async function render(next: URL, restore = false) {
    const pathChanged = url.pathname !== next.pathname;
    url = next;
    revision++;
    if (!pathChanged && !restore) return;
    const state = history.state;
    await tick();
    stopRestoring();
    const restorePosition = () => {
      const target =
        restore && state?.focus
          ? document.getElementById(state.focus)
          : document.querySelector<HTMLElement>('[data-page-heading]');
      if (!target) return false;
      target.focus({ preventScroll: true });
      window.scrollTo({ top: restore ? state?.scroll || 0 : 0, behavior: 'instant' });
      return true;
    };
    if (restorePosition()) return;
    // Data-backed pages can render their rows after the route itself is mounted.
    const observer = new MutationObserver(() => {
      if (restorePosition()) stopRestoring();
    });
    const timeout = setTimeout(() => {
      stopRestoring();
      document.querySelector<HTMLElement>('[data-page-heading]')?.focus({ preventScroll: true });
    }, 5000);
    const cancel = () => stopRestoring();
    stopRestoring = () => {
      observer.disconnect();
      clearTimeout(timeout);
      document.removeEventListener('pointerdown', cancel);
      document.removeEventListener('keydown', cancel);
    };
    observer.observe(document.body, { subtree: true, childList: true });
    document.addEventListener('pointerdown', cancel, { once: true });
    document.addEventListener('keydown', cancel, { once: true });
  }
  function go(href: string, options: { replace?: boolean; force?: boolean } = {}) {
    const next = new URL(href, location.origin);
    if (next.origin !== location.origin || next.href === url.href) return;
    if (!options.force && !allowed()) return;
    remember();
    if (options.replace) history.replaceState({ leadflowIndex: index }, '', next);
    else history.pushState({ leadflowIndex: ++index }, '', next);
    void render(next);
  }
  function start() {
    history.replaceState({ ...history.state, leadflowIndex: index }, '', url);
    const previousRestoration = history.scrollRestoration;
    history.scrollRestoration = 'manual';
    const pop = () => {
      if (reverting) {
        reverting = false;
        return;
      }
      const nextIndex = history.state?.leadflowIndex ?? 0;
      if (!allowed()) {
        reverting = true;
        history.go(index - nextIndex);
        return;
      }
      index = nextIndex;
      void render(new URL(location.href), true);
    };
    const click = (event: MouseEvent) => {
      if (
        event.defaultPrevented ||
        event.button !== 0 ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey
      )
        return;
      const anchor = (event.target as Element).closest<HTMLAnchorElement>('a[href]');
      if (!anchor || anchor.target || anchor.hasAttribute('download')) return;
      const next = new URL(anchor.href);
      if (next.origin !== location.origin || next.hash) return;
      event.preventDefault();
      go(next.pathname + next.search);
    };
    const unload = (event: BeforeUnloadEvent) => {
      if ([...guards].some((guard) => guard())) event.preventDefault();
    };
    const scroll = () => remember();
    window.addEventListener('popstate', pop);
    window.addEventListener('beforeunload', unload);
    window.addEventListener('scroll', scroll, { passive: true });
    document.addEventListener('click', click);
    return () => {
      stopRestoring();
      window.removeEventListener('popstate', pop);
      window.removeEventListener('beforeunload', unload);
      window.removeEventListener('scroll', scroll);
      document.removeEventListener('click', click);
      history.scrollRestoration = previousRestoration;
    };
  }
  const navigation = {
    get url() {
      return url;
    },
    get revision() {
      return revision;
    },
    go,
    start,
    allowed,
    register(guard: Guard) {
      guards.add(guard);
      return () => {
        guards.delete(guard);
      };
    },
  };
  setContext(context, navigation);
  return navigation;
}
export function useNavigation() {
  return getContext<ReturnType<typeof createNavigation>>(context);
}
export function protectChanges(guard: Guard) {
  const navigation = useNavigation();
  onMount(() => navigation.register(guard));
}
export function safeReturn(value: string | null, fallback = '/') {
  if (!value || !value.startsWith('/') || value.startsWith('//')) return fallback;
  const next = new URL(value, location.origin);
  return next.origin === location.origin && next.pathname !== '/login'
    ? next.pathname + next.search
    : fallback;
}
