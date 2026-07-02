import { useState, useEffect, useRef, useCallback } from 'react';

export type SaveStatus = 'idle' | 'saving' | 'saved' | 'error';

export interface UseHitlAutosaveProps<T> {
  data: T;
  onSave: (data: T) => Promise<void>;
  debounceMs?: number;
  enabled?: boolean;
}

export function useHitlAutosave<T>({ 
  data, 
  onSave, 
  debounceMs = 1500,
  enabled = true
}: UseHitlAutosaveProps<T>) {
  const [status, setStatus] = useState<SaveStatus>('idle');
  const [lastSaved, setLastSaved] = useState<Date | null>(null);
  
  const isFirstRender = useRef(true);
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const latestDataRef = useRef<T>(data);
  const onSaveRef = useRef(onSave);
  
  // Keep refs up to date to avoid stale closures in timeouts
  useEffect(() => {
    latestDataRef.current = data;
    onSaveRef.current = onSave;
  }, [data, onSave]);

  const forceSave = useCallback(async (dataToSave: T = latestDataRef.current) => {
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }
    
    try {
      setStatus('saving');
      await onSaveRef.current(dataToSave);
      setStatus('saved');
      setLastSaved(new Date());
      
      // Reset back to idle after a few seconds showing "saved"
      setTimeout(() => {
        setStatus((current) => current === 'saved' ? 'idle' : current);
      }, 3000);
    } catch (err) {
      console.error('Autosave failed:', err);
      setStatus('error');
    }
  }, []);

  useEffect(() => {
    // Skip autosave on initial mount
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }

    if (!enabled) return;

    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }

    // Set status to pending save if we're not already saving
    if (status !== 'saving') {
      setStatus('idle');
    }

    saveTimeoutRef.current = setTimeout(() => {
      forceSave(latestDataRef.current);
    }, debounceMs);

    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
    };
  }, [data, debounceMs, enabled, forceSave, status]);

  return {
    status,
    lastSaved,
    forceSave
  };
}
