import { useEffect } from 'react';

export interface HitlShortcuts {
  onAccept?: () => void;
  onReject?: () => void;
  onEdit?: () => void;
  onDelete?: () => void;
  onNext?: () => void;
  onPrevious?: () => void;
  onSave?: () => void;
  onUndo?: () => void;
  onRedo?: () => void;
  disabled?: boolean;
}

export function useHitlKeyboardShortcuts(shortcuts: HitlShortcuts) {
  useEffect(() => {
    if (shortcuts.disabled) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't trigger if user is typing in an input or textarea
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        e.target instanceof HTMLSelectElement
      ) {
        return;
      }

      const key = e.key.toLowerCase();
      
      // Ctrl+S or Cmd+S for Save
      if ((e.ctrlKey || e.metaKey) && key === 's') {
        e.preventDefault();
        shortcuts.onSave?.();
        return;
      }
      
      // Ctrl+Z for Undo, Ctrl+Y or Ctrl+Shift+Z for Redo
      if ((e.ctrlKey || e.metaKey) && key === 'z') {
        e.preventDefault();
        if (e.shiftKey) {
          shortcuts.onRedo?.();
        } else {
          shortcuts.onUndo?.();
        }
        return;
      }
      
      if ((e.ctrlKey || e.metaKey) && key === 'y') {
        e.preventDefault();
        shortcuts.onRedo?.();
        return;
      }

      // Single key shortcuts
      if (!e.ctrlKey && !e.metaKey && !e.altKey) {
        switch (key) {
          case 'a':
            shortcuts.onAccept?.();
            break;
          case 'r':
            shortcuts.onReject?.();
            break;
          case 'e':
            shortcuts.onEdit?.();
            break;
          case 'd':
          case 'delete':
            shortcuts.onDelete?.();
            break;
          case 'n':
            shortcuts.onNext?.();
            break;
          case 'p':
            shortcuts.onPrevious?.();
            break;
          default:
            break;
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [shortcuts]);
}
