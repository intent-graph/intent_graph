// Edit state machine for node overlay cards.
// Manages entry/exit of edit mode, field change detection, and commit flow.

import type { EditableField } from '../../messaging/messageTypes';
import { trace } from '../trace';

export type NodeEditFields = {
  name?: string;
  intent?: string;
  epistemic_state?: string;
  constraints?: string[];
};

export interface EditStateMachine {
  isEditing(uid: string): boolean;
  getCurrentEditingUid(): string | null;
  enterEditMode(card: HTMLElement, uid: string, corr?: string): boolean;
  exitEditModeAndCollect(
    uid: string,
    card: HTMLElement
  ): { name?: string; intent?: string; epistemic_state?: string; constraints?: string[] } | null;
  restorePreEditDOM(card: HTMLElement): void;
  exitEditModeDOM(card: HTMLElement): void;
  cancelEdit(card: HTMLElement): void;
  /** Reset state without touching DOM. Used when the card has been removed
   *  out from under the state machine (overlay torn down, node deleted). */
  forceClear(): void;
}

export function createEditStateMachine(): EditStateMachine {
  let editingUid: string | null = null;

  return {
    isEditing(uid) {
      return editingUid === uid;
    },

    getCurrentEditingUid() {
      return editingUid;
    },

    enterEditMode(card, uid, corr) {
      // Already editing this node.
      if (editingUid === uid) {
        trace({ src: 'overlay', kind: 'editEnter', corr, data: { uid, ok: true } });
        return true;
      }

      // Can't edit a hidden card.
      if (card.style.display === 'none') {
        trace({ src: 'overlay', kind: 'editEnter', corr, data: { uid, ok: false } });
        return false;
      }

      editingUid = uid;
      card.classList.add('ig-card--editing');

      // Enable all editable fields simultaneously.
      const fields = Array.from(card.querySelectorAll<HTMLElement>('[data-ig-editable="1"]'));
      const fieldSnapshot = fields.map((el) => ({
        field: el.dataset['igField'],
        value: el.dataset['igValue'],
        ciStr: el.dataset['igConstraintIndex']
      }));
      trace({
        src: 'overlay',
        kind: 'editEnterContent',
        corr,
        data: { uid, fields: fieldSnapshot }
      });

      for (const textEl of fields) {
        // Strip display prefix before entering edit mode.
        const rawValue = textEl.dataset['igValue'] ?? textEl.textContent ?? '';
        textEl.textContent = rawValue;
        textEl.contentEditable = 'true';
        textEl.classList.add('ig-edit-field', 'ig-editing');
      }

      // Focus the name field (first editable field) by default.
      if (fields.length > 0) {
        fields[0].focus();
        const sel = window.getSelection();
        if (sel) {
          const range = document.createRange();
          range.selectNodeContents(fields[0]);
          sel.removeAllRanges();
          sel.addRange(range);
        }
      }

      trace({ src: 'overlay', kind: 'editEnter', corr, data: { uid, ok: true } });
      return true;
    },

    exitEditModeAndCollect(uid, card) {
      if (editingUid !== uid) return null;

      const fields = Array.from(card.querySelectorAll<HTMLElement>('[data-ig-editable="1"]'));

      const changedName: string | undefined = (() => {
        const el = fields.find((f) => f.dataset['igField'] === 'name');
        if (!el) return undefined;
        const newVal = (el.textContent ?? '').trim();
        const origVal = (el.dataset['igValue'] ?? '').trim();
        return newVal !== origVal && newVal.length > 0 ? newVal : undefined;
      })();

      const changedIntent: string | undefined = (() => {
        const el = fields.find((f) => f.dataset['igField'] === 'intent');
        if (!el) return undefined;
        const newVal = (el.textContent ?? '').trim();
        const origVal = (el.dataset['igValue'] ?? '').trim();
        return newVal !== origVal && newVal.length > 0 ? newVal : undefined;
      })();

      const changedEpistemic: string | undefined = (() => {
        const el = fields.find((f) => f.dataset['igField'] === 'epistemic_state');
        if (!el) return undefined;
        const newVal = (el.textContent ?? '').trim();
        const origVal = (el.dataset['igValue'] ?? '').trim();
        return newVal !== origVal && newVal.length > 0 ? newVal : undefined;
      })();

      const changedConstraints: string[] | undefined = (() => {
        const constraintEls = fields.filter((f) => f.dataset['igField'] === 'constraint');
        if (constraintEls.length === 0) return undefined;
        const arr: string[] = [];
        let anyChanged = false;
        for (const el of constraintEls) {
          const ciStr = el.dataset['igConstraintIndex'];
          const ci = ciStr !== undefined ? parseInt(ciStr, 10) : -1;
          if (ci < 0) continue;
          const newVal = (el.textContent ?? '').trim();
          const origVal = (el.dataset['igValue'] ?? '').trim();
          arr[ci] = newVal || origVal;
          if (newVal !== origVal && newVal.length > 0) anyChanged = true;
        }
        return anyChanged ? arr : undefined;
      })();

      // Nothing changed — no-op.
      if (!changedName && !changedIntent && !changedEpistemic && !changedConstraints) {
        this.exitEditModeDOM(card);
        return null;
      }

      return { name: changedName, intent: changedIntent, epistemic_state: changedEpistemic, constraints: changedConstraints };
    },

    restorePreEditDOM(card) {
      const fields = Array.from(card.querySelectorAll<HTMLElement>('[data-ig-editable="1"]'));
      for (const el of fields) {
        el.textContent = (el.dataset['igPrefix'] ?? '') + (el.dataset['igValue'] ?? '');
      }
    },

    exitEditModeDOM(card) {
      editingUid = null;
      card.classList.remove('ig-card--editing');
      const fields = Array.from(card.querySelectorAll<HTMLElement>('[data-ig-editable="1"]'));
      for (const el of fields) {
        el.contentEditable = 'false';
        el.classList.remove('ig-edit-field', 'ig-editing');
      }
      // Remove any stale inline errors.
      const errEl = card.querySelector('.ig-edit-error');
      if (errEl) errEl.parentNode?.removeChild(errEl);
    },

    cancelEdit(card) {
      if (!editingUid) return;
      trace({ src: 'overlay', kind: 'editCancel', data: { uid: editingUid } });
      const fields = Array.from(card.querySelectorAll<HTMLElement>('[data-ig-editable="1"]'));
      for (const el of fields) {
        el.textContent = (el.dataset['igPrefix'] ?? '') + (el.dataset['igValue'] ?? '');
      }
      this.exitEditModeDOM(card);
    },

    forceClear() {
      editingUid = null;
    }
  };
}
