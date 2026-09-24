// Banner UI state management.
// Handles visibility, styling, and content for the status banner element.
// Constraints:
//   - Edit conflict banners are non-dismissable until explicitly reloaded
//   - Each banner type has distinct styling (error, warn, diagnostics, default)
//   - All text set via textContent only (no innerHTML for XSS safety)

import type { LensDiagnostic } from '../../messaging/messageTypes';

function getElement(): HTMLElement | null {
  return document.getElementById('banner');
}

export interface BannerManager {
  show(message: string, options?: { withRetry?: boolean; onRetry?: () => void }): void;
  showEditConflict(message: string, onReload: () => void): void;
  showWarning(message: string): void;
  showDiagnostics(diagnostics: LensDiagnostic[]): void;
  hide(): void;
  clearEditConflict(): void;
}

export function createBannerManager(): BannerManager {
  return {
    show(message, options) {
      const el = getElement();
      if (!el) return;
      el.textContent = '';
      el.classList.remove('banner-warn', 'banner-diagnostics');

      const span = document.createElement('span');
      span.textContent = message;
      el.appendChild(span);

      if (options?.withRetry && options?.onRetry) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.textContent = 'Retry';
        btn.addEventListener('click', () => options.onRetry!());
        el.appendChild(btn);
      }
      el.hidden = false;
    },

    showEditConflict(message, onReload) {
      const el = getElement();
      if (!el) return;
      el.textContent = '';
      el.classList.add('banner-error');
      el.classList.remove('banner-warn', 'banner-diagnostics');

      const span = document.createElement('span');
      span.textContent = message;
      el.appendChild(span);

      const btn = document.createElement('button');
      btn.type = 'button';
      btn.textContent = 'Reload';
      btn.addEventListener('click', () => onReload());
      el.appendChild(btn);

      el.hidden = false;
      el.setAttribute('data-dismissable', 'false');
    },

    showWarning(message) {
      const el = getElement();
      if (!el) return;
      el.textContent = '';
      el.classList.add('banner-warn');
      el.classList.remove('banner-diagnostics');

      const span = document.createElement('span');
      span.textContent = message;
      el.appendChild(span);

      const btn = document.createElement('button');
      btn.type = 'button';
      btn.textContent = 'Dismiss';
      btn.addEventListener('click', () => this.hide());
      el.appendChild(btn);
      el.hidden = false;
    },

    showDiagnostics(diagnostics) {
      if (diagnostics.length === 0) return;
      const el = getElement();
      if (!el) return;

      el.textContent = '';
      el.classList.remove('banner-warn');
      el.classList.add('banner-diagnostics');

      const header = document.createElement('span');
      header.textContent = `IntentGraph: Lens diagnostics — ${diagnostics.length} issue(s)`;
      el.appendChild(header);

      const dismissBtn = document.createElement('button');
      dismissBtn.type = 'button';
      dismissBtn.textContent = 'Dismiss';
      dismissBtn.addEventListener('click', () => this.hide());
      el.appendChild(dismissBtn);

      const list = document.createElement('ul');
      list.style.margin = '4px 0 0 0';
      list.style.paddingLeft = '1.2em';
      list.style.listStyle = 'disc';

      for (const d of diagnostics) {
        const item = document.createElement('li');
        item.style.color = 'var(--vscode-editorWarning-foreground, #d7ba7d)';
        const uidPart = d.uid ? `'${d.uid}' ` : '';
        item.textContent = `${d.level} · ${uidPart}${d.message}`;
        list.appendChild(item);
      }
      el.appendChild(list);
      el.hidden = false;
    },

    hide() {
      const el = getElement();
      if (!el) return;
      // PIG DIAGNOSTICS.EDIT_CONFLICT constraint #1: respect non-dismissable flag.
      if (el.getAttribute('data-dismissable') === 'false') {
        return;
      }
      el.hidden = true;
      el.textContent = '';
      el.classList.remove('banner-warn', 'banner-diagnostics', 'banner-error');
      el.removeAttribute('data-dismissable');
    },

    clearEditConflict() {
      const el = getElement();
      if (!el) return;
      if (el.getAttribute('data-dismissable') === 'false') {
        el.hidden = true;
        el.textContent = '';
        el.classList.remove('banner-error');
        el.removeAttribute('data-dismissable');
      }
    }
  };
}
