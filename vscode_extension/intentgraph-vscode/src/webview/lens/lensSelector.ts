// In-viewer lens selector widget.
// Floating dropdown in the top-right corner of the webview.
// Always visible: shows "No lens" when none active, disabled when no lenses defined.
//
// Bug 3 fix: inline input + confirm replace window.prompt / window.confirm
// (unsupported in webviews). One input request can be active at a time;
// last writer wins.

import type { SerialisedLensConfig } from '../../shared/graphTypes';
import { trace } from '../trace';

/**
 * Type of inline-input request.
 * - `text`: user supplies a string (create / rename — confirm enabled iff value non-empty).
 * - `confirm`: yes/no (delete — no input field, just message + confirm/cancel).
 */
export type LensInputAction = 'create' | 'rename' | 'delete';
export type LensInputMode = 'text' | 'confirm';

export interface LensInputRequest {
  action: LensInputAction;
  mode: LensInputMode;
  prefill?: string;
  message?: string; // shown above the input/buttons (e.g. delete confirmation)
  onSubmit: (value: string) => Promise<{ ok: boolean; error?: string }>;
}

export class LensSelector {
  private readonly selectorEl: HTMLElement;
  private readonly btnEl: HTMLButtonElement;
  private readonly labelEl: HTMLElement;
  private readonly listEl: HTMLElement;
  /** CRUD action buttons (PIG LENS_UI.CTRLPANEL.{2,3,4}). */
  private readonly createBtnEl: HTMLButtonElement | null;
  private readonly renameBtnEl: HTMLButtonElement | null;
  private readonly deleteBtnEl: HTMLButtonElement | null;
  private readonly relayoutBtnEl: HTMLButtonElement | null;
  /** Bug 3 fix: inline input + message elements (replace window.prompt/confirm). */
  private readonly inputRowEl: HTMLElement | null;
  private readonly inputEl: HTMLInputElement | null;
  private readonly inputConfirmEl: HTMLButtonElement | null;
  private readonly inputCancelEl: HTMLButtonElement | null;
  private readonly msgEl: HTMLElement | null;
  private isOpen = false;
  /** Active inline-input request (null when in default state). */
  private inputRequest: LensInputRequest | null = null;

  /** Callback invoked when the user picks a lens. */
  private onPick: ((lensName: string | null) => void) | null = null;
  /** Callback invoked when the user clicks "+" to create a new lens. */
  private onCreate: (() => void) | null = null;
  /** Callback invoked when the user clicks the rename (pencil) icon. */
  private onRename: (() => void) | null = null;
  /** Callback invoked when the user clicks the delete (trash) icon. */
  private onDelete: (() => void) | null = null;
  /** Callback invoked when the user clicks the re-layout icon. */
  private onRelayout: (() => void) | null = null;

  constructor() {
    const sel = document.getElementById('lens-selector');
    const btn = document.getElementById('lens-selector-btn') as HTMLButtonElement | null;
    const label = document.getElementById('lens-selector-label');
    const list = document.getElementById('lens-selector-list');

    if (!sel || !btn || !label || !list) {
      // DOM not ready — create minimal stubs so runtime never crashes.
      this.selectorEl = sel ?? document.createElement('div');
      this.btnEl = btn ?? document.createElement('button') as HTMLButtonElement;
      this.labelEl = label ?? document.createElement('span');
      this.listEl = list ?? document.createElement('ul');
      this.createBtnEl = null;
      this.renameBtnEl = null;
      this.deleteBtnEl = null;
      this.relayoutBtnEl = null;
      this.inputRowEl = null;
      this.inputEl = null;
      this.inputConfirmEl = null;
      this.inputCancelEl = null;
      this.msgEl = null;
      return;
    }

    this.selectorEl = sel;
    this.btnEl = btn;
    this.labelEl = label;
    this.listEl = list;
    this.createBtnEl = document.getElementById('lens-create-btn') as HTMLButtonElement | null;
    this.renameBtnEl = document.getElementById('lens-rename-btn') as HTMLButtonElement | null;
    this.deleteBtnEl = document.getElementById('lens-delete-btn') as HTMLButtonElement | null;
    this.relayoutBtnEl = document.getElementById('lens-relayout-btn') as HTMLButtonElement | null;
    this.inputRowEl = document.getElementById('lens-input-row');
    this.inputEl = document.getElementById('lens-input') as HTMLInputElement | null;
    this.inputConfirmEl = document.getElementById('lens-input-confirm') as HTMLButtonElement | null;
    this.inputCancelEl = document.getElementById('lens-input-cancel') as HTMLButtonElement | null;
    this.msgEl = document.getElementById('lens-msg');

    // Open/close on button click.
    this.btnEl.addEventListener('click', (e) => {
      e.stopPropagation();
      if (this.btnEl.disabled) return;
      // If an input request is active, ignore dropdown clicks (mode lock).
      if (this.inputRequest !== null) return;
      this.isOpen ? this.close() : this.open();
    });

    // CRUD button clicks.
    this.createBtnEl?.addEventListener('click', (e) => {
      e.stopPropagation();
      this.onCreate?.();
    });
    this.renameBtnEl?.addEventListener('click', (e) => {
      e.stopPropagation();
      if (!this.renameBtnEl?.disabled) this.onRename?.();
    });
    this.deleteBtnEl?.addEventListener('click', (e) => {
      e.stopPropagation();
      if (!this.deleteBtnEl?.disabled) this.onDelete?.();
    });
    this.relayoutBtnEl?.addEventListener('click', (e) => {
      e.stopPropagation();
      if (!this.relayoutBtnEl?.disabled) this.onRelayout?.();
    });

    // Bug 3 fix: inline input controls.
    this.inputConfirmEl?.addEventListener('click', (e) => {
      e.stopPropagation();
      void this.submitInputRequest();
    });
    this.inputCancelEl?.addEventListener('click', (e) => {
      e.stopPropagation();
      this.cancelInputRequest('cancelBtn');
    });
    this.inputEl?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        e.stopPropagation();
        void this.submitInputRequest();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        this.cancelInputRequest('esc');
      }
    });
    this.inputEl?.addEventListener('input', () => {
      // Clearing the error as soon as the user retypes is the standard idiom.
      this.clearMessage();
      if (this.inputEl) this.inputEl.classList.remove('lens-selector__input--error');
    });

    // Close on click-outside.
    // - dropdown open → close dropdown
    // - input request active → cancel it
    document.addEventListener('click', (e) => {
      if (this.selectorEl.contains(e.target as Node)) return;
      if (this.isOpen) this.close();
      if (this.inputRequest !== null) this.cancelInputRequest('clickOutside');
    });

    // Escape: close dropdown OR cancel input request.
    document.addEventListener('keydown', (e) => {
      if (e.key !== 'Escape') return;
      if (this.inputRequest !== null) {
        this.cancelInputRequest('esc');
      } else if (this.isOpen) {
        this.close();
      }
    });

    // PIG OBSERVABILITY constraint #4: lifecycle marker — bug-3 diagnostic.
    // If buttons aren't found, the trace says so explicitly.
    trace({
      src: 'lens',
      kind: 'lensSelectorMounted',
      data: {
        btnFound: btn !== null,
        createBtnFound: document.getElementById('lens-create-btn') !== null,
        renameBtnFound: document.getElementById('lens-rename-btn') !== null,
        deleteBtnFound: document.getElementById('lens-delete-btn') !== null
      }
    });
  }

  /** Register callbacks for CRUD actions. */
  setCrudHandlers(handlers: {
    onCreate?: () => void;
    onRename?: () => void;
    onDelete?: () => void;
  }): void {
    this.onCreate = handlers.onCreate ?? null;
    this.onRename = handlers.onRename ?? null;
    this.onDelete = handlers.onDelete ?? null;
  }

  /** Register the callback invoked when the user clicks the re-layout button. */
  setRelayoutHandler(cb: () => void): void {
    this.onRelayout = cb;
  }

  /**
   * Returns the lens selector's root container — used by the gesture router
   * to exempt clicks on the selector from triggering edit-mode exit.
   */
  getRoot(): HTMLElement {
    return this.selectorEl;
  }

  /**
   * Register the callback invoked when a lens is selected or cleared.
   * null = clear active lens.
   */
  setPickHandler(cb: (lensName: string | null) => void): void {
    this.onPick = cb;
  }

  /**
   * Rebuild the dropdown with the given lens map.
   * Call whenever LoadGraphResponse arrives with a new lens dict.
   */
  update(lenses: Record<string, SerialisedLensConfig>, activeLensName: string | null): void {
    const lensKeys = Object.keys(lenses);
    const hasLenses = lensKeys.length > 0;

    // Update empty-state modifier class.
    if (hasLenses) {
      this.selectorEl.classList.remove('lens-selector--empty');
    } else {
      this.selectorEl.classList.add('lens-selector--empty');
    }

    // Update button state.
    this.btnEl.disabled = !hasLenses;
    this.btnEl.title = hasLenses ? 'Select a lens to apply' : 'No lenses defined in this IG';

    // Rename and delete only meaningful when a lens is active.
    const hasActive = activeLensName !== null;
    if (this.renameBtnEl) this.renameBtnEl.disabled = !hasActive;
    if (this.deleteBtnEl) this.deleteBtnEl.disabled = !hasActive;

    // Update label.
    this.labelEl.textContent = activeLensName ?? 'No lens';

    // Rebuild list.
    while (this.listEl.firstChild) this.listEl.removeChild(this.listEl.firstChild);

    if (hasLenses) {
      // Clear lens item (always first).
      const clearItem = document.createElement('li');
      clearItem.className = 'lens-selector__item lens-selector__item--clear';
      clearItem.textContent = '✕ Clear lens';
      clearItem.setAttribute('role', 'option');
      clearItem.setAttribute('aria-selected', 'false');
      clearItem.addEventListener('click', () => {
        this.close();
        this.onPick?.(null);
      });
      this.listEl.appendChild(clearItem);

      // One item per lens.
      for (const name of lensKeys) {
        const cfg = lenses[name];
        const nodeCount = Object.keys(cfg.nodes).length;
        const item = document.createElement('li');
        item.className = 'lens-selector__item' + (name === activeLensName ? ' lens-selector__item--active' : '');
        item.setAttribute('role', 'option');
        item.setAttribute('aria-selected', name === activeLensName ? 'true' : 'false');
        const descPart = cfg.description ? ` · ${cfg.description}` : '';
        item.textContent = `${name} (${nodeCount} nodes${descPart})`;
        item.title = cfg.description ?? name;
        item.addEventListener('click', () => {
          this.close();
          this.onPick?.(name);
        });
        this.listEl.appendChild(item);
      }
    }
  }

  /** Update only the label + active state — does not rebuild list items. */
  setActiveLens(name: string | null): void {
    this.labelEl.textContent = name ?? 'No lens';
    // Update active-class on list items without full rebuild.
    const items = this.listEl.querySelectorAll<HTMLElement>('.lens-selector__item:not(.lens-selector__item--clear)');
    items.forEach((item) => {
      const isActive = item.textContent?.startsWith(name ?? '\x00') && name !== null;
      item.classList.toggle('lens-selector__item--active', isActive);
      item.setAttribute('aria-selected', isActive ? 'true' : 'false');
    });
  }

  private open(): void {
    this.isOpen = true;
    this.listEl.hidden = false;
  }

  private close(): void {
    this.isOpen = false;
    this.listEl.hidden = true;
  }

  /**
   * Bug 3 fix: open the inline input row for a CRUD action.
   * Replaces window.prompt / window.confirm (unsupported in webviews).
   * Closes the dropdown first; only one input request can be active at a time.
   */
  openInputRequest(req: LensInputRequest): void {
    if (!this.inputRowEl || !this.inputEl) return;
    // If another request is active, cancel it silently — last writer wins.
    if (this.inputRequest !== null) {
      this.cancelInputRequest('clickOutside');
    }
    if (this.isOpen) this.close();
    this.inputRequest = req;

    // Set up the input or confirm view.
    if (req.mode === 'text') {
      this.inputEl.hidden = false;
      this.inputEl.value = req.prefill ?? '';
      this.inputEl.placeholder =
        req.action === 'create' ? 'New lens name' :
        req.action === 'rename' ? 'New name' :
        '';
      this.inputEl.classList.remove('lens-selector__input--error');
      // Show message above (placeholder helper) or hide.
      if (req.message) {
        this.showMessage(req.message, 'confirm');
      } else {
        this.clearMessage();
      }
    } else {
      // Confirm mode: hide input, show only ✓/✕ buttons + message.
      this.inputEl.hidden = true;
      this.inputEl.value = '';
      if (req.message) this.showMessage(req.message, 'confirm');
      else this.clearMessage();
    }

    this.inputRowEl.hidden = false;
    if (req.mode === 'text') {
      // Focus + select-all for easy overwrite.
      requestAnimationFrame(() => {
        this.inputEl?.focus();
        this.inputEl?.select();
      });
    } else {
      // Confirm mode: focus the confirm button so Enter triggers it.
      requestAnimationFrame(() => this.inputConfirmEl?.focus());
    }

    trace({
      src: 'lens',
      kind: 'lensCrudInputOpened',
      data: { action: req.action, mode: req.mode, prefill: req.prefill ?? null }
    });
  }

  private async submitInputRequest(): Promise<void> {
    const req = this.inputRequest;
    if (!req) return;
    const value = req.mode === 'text' ? (this.inputEl?.value ?? '').trim() : '';
    if (req.mode === 'text' && value === '') {
      // Don't submit empty values — flash the input border, no trace.
      this.inputEl?.classList.add('lens-selector__input--error');
      this.inputEl?.focus();
      return;
    }
    trace({
      src: 'lens',
      kind: 'lensCrudInputSubmitted',
      data: { action: req.action, mode: req.mode, value }
    });
    const result = await req.onSubmit(value);
    // The request may have been cancelled while the host was working.
    if (this.inputRequest !== req) return;
    if (result.ok) {
      this.closeInputRow();
    } else {
      // Persistent error message; user can retype and resubmit.
      this.inputEl?.classList.add('lens-selector__input--error');
      this.showMessage(result.error ?? 'Operation failed', 'error');
      this.inputEl?.focus();
      trace({
        src: 'lens',
        kind: 'lensCrudInputError',
        data: { action: req.action, error: result.error ?? 'unknown' }
      });
    }
  }

  private cancelInputRequest(reason: 'esc' | 'cancelBtn' | 'clickOutside'): void {
    const req = this.inputRequest;
    if (!req) return;
    trace({
      src: 'lens',
      kind: 'lensCrudInputCancelled',
      data: { action: req.action, reason }
    });
    this.closeInputRow();
  }

  private closeInputRow(): void {
    this.inputRequest = null;
    if (this.inputRowEl) this.inputRowEl.hidden = true;
    if (this.inputEl) {
      this.inputEl.value = '';
      this.inputEl.classList.remove('lens-selector__input--error');
    }
    this.clearMessage();
  }

  private showMessage(text: string, kind: 'error' | 'confirm'): void {
    if (!this.msgEl) return;
    this.msgEl.textContent = text;
    this.msgEl.classList.toggle('lens-selector__msg--confirm', kind === 'confirm');
    this.msgEl.hidden = false;
  }

  private clearMessage(): void {
    if (!this.msgEl) return;
    this.msgEl.hidden = true;
    this.msgEl.textContent = '';
    this.msgEl.classList.remove('lens-selector__msg--confirm');
  }
}
