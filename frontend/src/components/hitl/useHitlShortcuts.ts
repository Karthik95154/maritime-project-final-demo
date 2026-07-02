import { useEffect, useRef } from 'react';

export interface HitlShortcutsOptions {
  onApprove?: () => void;
  onReject?: () => void;
  onSave?: () => void;
  onUndo?: () => void;
  onRedo?: () => void;
  onNextFrame?: () => void;
  onPrevFrame?: () => void;
  disabled?: boolean;
}

export function useHitlShortcuts(options: HitlShortcutsOptions) {
  const optionsRef = useRef(options);
  
  useEffect(() => {
    optionsRef.current = options;
  }, [options]);

  useEffect(() => {
    if (options.disabled) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't trigger shortcuts if user is typing in an input field
      const target = e.target as HTMLElement;
      if (
        target.tagName === 'INPUT' || 
        target.tagName === 'TEXTAREA' || 
        target.isContentEditable
      ) {
        return;
      }

      const { onApprove, onReject, onSave, onUndo, onRedo, onNextFrame, onPrevFrame } = optionsRef.current;

      if (e.ctrlKey || e.metaKey) {
        if (e.key === 's' && onSave) {
          e.preventDefault();
          onSave();
        } else if (e.key === 'z' && !e.shiftKey && onUndo) {
          e.preventDefault();
          onUndo();
        } else if ((e.key === 'y' || (e.key === 'z' && e.shiftKey)) && onRedo) {
          e.preventDefault();
          onRedo();
        }
        return;
      }

      switch (e.key.toLowerCase()) {
        case 'a':
          if (onApprove) {
            e.preventDefault();
            onApprove();
          }
          break;
        case 'r':
          if (onReject) {
            e.preventDefault();
            onReject();
          }
          break;
        case 'arrowright':
          if (onNextFrame) {
            e.preventDefault();
            onNextFrame();
          }
          break;
        case 'arrowleft':
          if (onPrevFrame) {
            e.preventDefault();
            onPrevFrame();
          }
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [options.disabled]);
}
