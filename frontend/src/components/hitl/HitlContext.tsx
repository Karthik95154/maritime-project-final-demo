import React, { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react';

// --- HitlLayoutContext ---
export interface HitlLayoutContextType {
  workspaceDimensions: { width: number; height: number };
  canvasDimensions: { width: number; height: number };
  setWorkspaceDimensions: React.Dispatch<React.SetStateAction<{ width: number; height: number }>>;
  setCanvasDimensions: React.Dispatch<React.SetStateAction<{ width: number; height: number }>>;
}

export const HitlLayoutContext = createContext<HitlLayoutContextType | null>(null);

export function useHitlLayout() {
  const context = useContext(HitlLayoutContext);
  if (!context) throw new Error("useHitlLayout must be used within HitlLayoutProvider");
  return context;
}

export function HitlLayoutProvider({ children }: { children: React.ReactNode }) {
  const [workspaceDimensions, setWorkspaceDimensions] = useState({ width: 0, height: 0 });
  const [canvasDimensions, setCanvasDimensions] = useState({ width: 0, height: 0 });

  const value = React.useMemo(() => ({
    workspaceDimensions,
    canvasDimensions,
    setWorkspaceDimensions,
    setCanvasDimensions
  }), [workspaceDimensions, canvasDimensions]);

  return (
    <HitlLayoutContext.Provider value={value}>
      {children}
    </HitlLayoutContext.Provider>
  );
}

// --- HitlWorkspaceContext ---
export interface Transform {
  x: number;
  y: number;
  scale: number;
}

export interface HitlWorkspaceContextType {
  transform: Transform;
  setTransform: (transform: Transform | ((prev: Transform) => Transform)) => void;
  selectedAnnotation: string | null;
  setSelectedAnnotation: (id: string | null) => void;
  currentFrame: number;
  setCurrentFrame: (frame: number | ((prev: number) => number)) => void;
}

export const HitlWorkspaceContext = createContext<HitlWorkspaceContextType | null>(null);

export function useHitlWorkspace() {
  const context = useContext(HitlWorkspaceContext);
  if (!context) throw new Error("useHitlWorkspace must be used within HitlWorkspaceProvider");
  return context;
}

export function HitlWorkspaceProvider({ children }: { children: React.ReactNode }) {
  const [transform, setTransform] = useState<Transform>({ x: 0, y: 0, scale: 1 });
  const [selectedAnnotation, setSelectedAnnotation] = useState<string | null>(null);
  const [currentFrame, setCurrentFrame] = useState<number>(0);

  const value = React.useMemo(() => ({
    transform,
    setTransform,
    selectedAnnotation,
    setSelectedAnnotation,
    currentFrame,
    setCurrentFrame
  }), [transform, selectedAnnotation, currentFrame]);

  return (
    <HitlWorkspaceContext.Provider value={value}>
      {children}
    </HitlWorkspaceContext.Provider>
  );
}
