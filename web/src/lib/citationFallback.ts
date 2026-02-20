/**
 * Citation fallback handler for EFTA/jmail.world links.
 *
 * Some DOJ document IDs (especially from later releases like Vol. 11)
 * are not indexed by jmail.world, which returns a "Thread Not Found"
 * page. This script shows a dismissible notification with a fallback
 * link to the DOJ archive when an EFTA citation is clicked.
 */

let toastShown = false;

function showFallbackToast(fallbackUrl: string): void {
  if (toastShown) return;
  toastShown = true;

  const existing = document.querySelector('.citation-fallback-toast');
  if (existing) existing.remove();

  const toast = document.createElement('div');
  toast.className = 'citation-fallback-toast';
  toast.setAttribute('role', 'status');
  toast.innerHTML = [
    '<span>Document not loading?</span>',
    `<a href="${fallbackUrl}" target="_blank" rel="noopener noreferrer">Open DOJ Archive \u2192</a>`,
    '<button aria-label="Dismiss">\u00d7</button>',
  ].join(' ');

  document.body.appendChild(toast);
  requestAnimationFrame(() => toast.classList.add('citation-fallback-toast--visible'));

  const dismiss = () => {
    toast.classList.remove('citation-fallback-toast--visible');
    toast.addEventListener('transitionend', () => toast.remove(), { once: true });
    setTimeout(() => toast.remove(), 300);
  };

  toast.querySelector('button')?.addEventListener('click', dismiss);
  setTimeout(dismiss, 12000);
}

export function initCitationFallback(): void {
  document.addEventListener('click', (e) => {
    const link = (e.target as HTMLElement).closest<HTMLAnchorElement>('a[data-fallback-url]');
    if (!link) return;

    const fallbackUrl = link.getAttribute('data-fallback-url');
    if (!fallbackUrl) return;

    // Let the default click action proceed (opens jmail.world in new tab).
    // Show the toast so the user has a fallback if the page shows "Thread Not Found".
    showFallbackToast(fallbackUrl);
  });
}
