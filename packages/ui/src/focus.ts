const dialogs: HTMLElement[] = [];
/** Keep keyboard focus in the topmost dialog and restore it on close. */
export function modalFocus(node: HTMLElement, close: () => void) {
  const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  dialogs.push(node);
  const focusable = () =>
    Array.from(
      node.querySelectorAll<HTMLElement>(
        'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex="0"]',
      ),
    ).filter((el) => el.offsetParent !== null);
  const timer = setTimeout(() => (focusable()[0] || node).focus(), 0);
  const keydown = (event: KeyboardEvent) => {
    if (dialogs.at(-1) !== node) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      event.stopImmediatePropagation();
      close();
    }
    if (event.key === 'Tab') {
      const elements = focusable();
      const first = elements[0];
      const last = elements.at(-1);
      if (!first) {
        event.preventDefault();
        node.focus();
        return;
      }
      if (
        event.shiftKey &&
        (document.activeElement === first || !node.contains(document.activeElement))
      ) {
        event.preventDefault();
        last?.focus();
      } else if (
        !event.shiftKey &&
        (document.activeElement === last || !node.contains(document.activeElement))
      ) {
        event.preventDefault();
        first.focus();
      }
    }
  };
  document.addEventListener('keydown', keydown, true);
  const originalOverflow = document.body.style.overflow;
  document.body.style.overflow = 'hidden';
  return {
    update(next: () => void) {
      close = next;
    },
    destroy() {
      clearTimeout(timer);
      dialogs.splice(dialogs.indexOf(node), 1);
      document.removeEventListener('keydown', keydown, true);
      document.body.style.overflow = originalOverflow;
      if (previous?.isConnected) previous.focus();
    },
  };
}
