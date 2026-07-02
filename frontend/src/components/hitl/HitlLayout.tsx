import React, { useRef, useEffect } from 'react';
import { Box, Typography, Button, Tooltip, Stack, Chip, IconButton, Divider } from '@mui/material';
import { Check, X, Save, ZoomIn, ZoomOut, Maximize, ChevronLeft, ChevronRight, Undo, Redo } from 'lucide-react';
import { HITL_THEME } from './hitlTheme';
import { HitlLayoutProvider, HitlWorkspaceProvider, useHitlLayout } from './HitlContext';

// --- Top Level Layout Wrapper ---
export function HitlLayout({ children }: { children: React.ReactNode }) {
  return (
    <HitlLayoutProvider>
      <HitlWorkspaceProvider>
        <Box sx={{ 
          height: '100%', 
          display: 'flex', 
          flexDirection: 'column', 
          overflow: 'hidden', 
          boxSizing: 'border-box',
          bgcolor: '#f8fafc',
          borderRadius: 2
        }}>
          {children}
        </Box>
      </HitlWorkspaceProvider>
    </HitlLayoutProvider>
  );
}

// --- Header ---
export function HitlHeader({ 
  title, 
  sessionId, 
  saveStatus, 
  lastSaved, 
  confidenceScore,
  onUndo,
  canUndo,
  onRedo,
  canRedo
}: any) {
  return (
    <Box sx={{ 
      height: HITL_THEME.headerHeight, 
      display: 'flex', 
      alignItems: 'center', 
      justifyContent: 'space-between', 
      px: 2, 
      py: 1, 
      borderBottom: '1px solid #e2e8f0', 
      bgcolor: '#ffffff',
      flexShrink: 0
    }}>
      <Box>
        <Typography variant="h6" sx={{ fontSize: '1.1rem', fontWeight: 800, color: '#1e293b' }}>
          {title}
        </Typography>
        <Typography variant="caption" sx={{ color: '#64748b' }}>
          Session: {sessionId}
        </Typography>
      </Box>

      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        {confidenceScore !== undefined && (
          <Chip 
            label={`AI Confidence: ${(confidenceScore * 100).toFixed(1)}%`}
            size="small"
            color={confidenceScore > 0.9 ? "success" : confidenceScore > 0.7 ? "warning" : "error"}
            variant="outlined"
            sx={{ fontWeight: 'bold' }}
          />
        )}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, borderRight: '1px solid #e2e8f0', pr: 2 }}>
           {onUndo && (
             <Tooltip title="Undo (Ctrl+Z)"><span><IconButton size="small" onClick={onUndo} disabled={!canUndo}><Undo size={18} /></IconButton></span></Tooltip>
           )}
           {onRedo && (
             <Tooltip title="Redo (Ctrl+Y)"><span><IconButton size="small" onClick={onRedo} disabled={!canRedo}><Redo size={18} /></IconButton></span></Tooltip>
           )}
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 120, justifyContent: 'flex-end' }}>
          {saveStatus === 'saving' && <Typography variant="caption" color="text.secondary">Saving...</Typography>}
          {saveStatus === 'saved' && <Typography variant="caption" color="success.main">Saved {lastSaved?.toLocaleTimeString()}</Typography>}
          {saveStatus === 'error' && <Typography variant="caption" color="error.main">Save failed</Typography>}
        </Box>
      </Box>
    </Box>
  );
}

// --- Main Container (Row) ---
export function HitlMainContainer({ children }: { children: React.ReactNode }) {
  return (
    <Box sx={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'row', overflow: 'hidden' }}>
      {children}
    </Box>
  );
}

// --- Workspace (Center Column) ---
export function HitlWorkspace({ children }: { children: React.ReactNode }) {
  return (
    <Box sx={{ flex: 1, minHeight: 0, minWidth: 0, display: 'flex', flexDirection: 'column', bgcolor: '#f1f5f9', position: 'relative' }}>
      {children}
    </Box>
  );
}

// --- Sidebar (Right Column) ---
export function HitlSidebar({ children }: { children: React.ReactNode }) {
  return (
    <Box sx={{ 
      width: HITL_THEME.sidebarWidth, 
      flexShrink: 0, 
      display: 'flex', 
      flexDirection: 'column', 
      overflow: 'hidden', 
      bgcolor: '#ffffff', 
      borderLeft: '1px solid #e2e8f0' 
    }}>
      <Box sx={{ flex: 1, minHeight: 0, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
        {children}
      </Box>
    </Box>
  );
}

// --- Action Bar (Bottom of Sidebar) ---
export function HitlActionBar({ onApprove, onReject, onSaveDraft, isSaving, approveText = "Approve & Continue (A)", rejectText = "Reject (R)" }: any) {
  return (
    <Box sx={{ 
      p: 2, 
      bgcolor: '#ffffff', 
      borderTop: '1px solid #e2e8f0', 
      display: 'flex', 
      flexDirection: 'column', 
      gap: 2, 
      flexShrink: 0,
      minHeight: HITL_THEME.actionBarHeight
    }}>
      <Tooltip title="Shortcut: A" placement="top">
        <span>
          <Button 
            variant="contained" 
            color="primary" 
            onClick={onApprove} 
            sx={{ py: 1.5, fontWeight: 'bold' }} 
            fullWidth
            disabled={isSaving}
            startIcon={<Check size={18} />}
          >
            {approveText}
          </Button>
        </span>
      </Tooltip>
      
      <Stack direction="row" spacing={2}>
        {onSaveDraft && (
          <Tooltip title="Shortcut: Ctrl+S" placement="top">
            <span>
              <Button 
                variant="outlined" 
                color="secondary" 
                onClick={onSaveDraft} 
                sx={{ flex: 1 }}
                disabled={isSaving}
                startIcon={<Save size={18} />}
              >
                Save Draft
              </Button>
            </span>
          </Tooltip>
        )}
        
        <Tooltip title="Shortcut: R" placement="top">
          <span>
            <Button 
              variant="outlined" 
              color="error" 
              onClick={onReject} 
              sx={{ flex: 1 }}
              disabled={isSaving}
              startIcon={<X size={18} />}
            >
              {rejectText}
            </Button>
          </span>
        </Tooltip>
      </Stack>
    </Box>
  );
}

// --- Canvas Container ---
export function HitlCanvas({ children, style }: { children: React.ReactNode, style?: React.CSSProperties }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const { setWorkspaceDimensions } = useHitlLayout();

  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      if (width > 0 && height > 0) {
        setWorkspaceDimensions((prev) => {
          if (prev.width === width && prev.height === height) return prev;
          return { width, height };
        });
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [setWorkspaceDimensions]);

  return (
    <Box ref={containerRef} sx={{ flex: 1, minHeight: 0, minWidth: 0, overflow: 'hidden', position: 'relative', cursor: 'grab', width: '100%', ...style }}>
      {children}
    </Box>
  );
}

// --- Toolbar ---
export function HitlToolbar({
  onZoomIn,
  onZoomOut,
  onFit,
  currentFrameIndex,
  totalFrames,
  onPrev,
  onNext,
  children
}: any) {
  return (
    <Box sx={{ 
      height: HITL_THEME.toolbarHeight, 
      p: 1, 
      borderBottom: '1px solid #e2e8f0', 
      bgcolor: '#ffffff', 
      display: 'flex', 
      gap: 1, 
      alignItems: 'center', 
      flexShrink: 0,
      width: '100%'
    }}>
      {(totalFrames !== undefined && totalFrames > 0) && (
        <>
          <Tooltip title="Previous Image">
            <span>
              <IconButton size="small" sx={{color: '#475569'}} disabled={currentFrameIndex === 0 || totalFrames === 0} onClick={onPrev}>
                <ChevronLeft size={20} />
              </IconButton>
            </span>
          </Tooltip>
          <Typography variant="body2" sx={{ alignSelf: 'center', fontWeight: 'bold', minWidth: 40, textAlign: 'center' }}>
            {totalFrames > 0 ? currentFrameIndex + 1 : 0} / {totalFrames}
          </Typography>
          <Tooltip title="Next Image">
            <span>
              <IconButton size="small" sx={{color: '#475569'}} disabled={currentFrameIndex >= totalFrames - 1 || totalFrames === 0} onClick={onNext}>
                <ChevronRight size={20} />
              </IconButton>
            </span>
          </Tooltip>
          <Divider orientation="vertical" flexItem sx={{ mx: 1 }} />
        </>
      )}
      
      {onZoomIn && <Tooltip title="Zoom In"><IconButton size="small" sx={{color: '#475569'}} onClick={onZoomIn}><ZoomIn size={20} /></IconButton></Tooltip>}
      {onZoomOut && <Tooltip title="Zoom Out"><IconButton size="small" sx={{color: '#475569'}} onClick={onZoomOut}><ZoomOut size={20} /></IconButton></Tooltip>}
      {onFit && <Tooltip title="Fit to Screen"><IconButton size="small" sx={{color: '#475569'}} onClick={onFit}><Maximize size={20} /></IconButton></Tooltip>}
      
      {children}

      {(onZoomIn || onFit) && (
        <Typography variant="caption" sx={{ ml: 'auto', alignSelf: 'center', color: '#64748b', pr: 1 }}>
          Scroll to zoom. Drag to pan.
        </Typography>
      )}
    </Box>
  );
}

// --- Filmstrip ---
export function HitlFilmstrip({ children }: { children: React.ReactNode }) {
  return (
    <Box sx={{ 
      height: HITL_THEME.filmstripHeight, 
      flexShrink: 0, 
      bgcolor: '#ffffff', 
      borderTop: '1px solid #e2e8f0', 
      p: 1, 
      display: 'flex', 
      gap: 1, 
      overflowX: 'auto', 
      alignItems: 'center',
      width: '100%'
    }}>
      {children}
    </Box>
  );
}
