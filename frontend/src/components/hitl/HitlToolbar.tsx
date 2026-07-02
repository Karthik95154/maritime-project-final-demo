import React from 'react';
import { Box, Typography, Chip, IconButton, Tooltip, Stack } from '@mui/material';
import { Save, CheckCircle, AlertCircle, RefreshCw } from 'lucide-react';
import { SaveStatus } from './useHitlAutosave';

export interface HitlToolbarProps {
  title: string;
  sessionId: string;
  saveStatus?: SaveStatus;
  lastSaved?: Date | null;
  confidenceScore?: number; // 0 to 1
  onUndo?: () => void;
  canUndo?: boolean;
  onRedo?: () => void;
  canRedo?: boolean;
  extraControls?: React.ReactNode;
}

export function HitlToolbar({
  title,
  sessionId,
  saveStatus = 'idle',
  lastSaved,
  confidenceScore,
  onUndo,
  canUndo = false,
  onRedo,
  canRedo = false,
  extraControls
}: HitlToolbarProps) {
  
  const getConfidenceColor = (score?: number) => {
    if (score === undefined) return 'default';
    if (score >= 0.95) return 'success';
    if (score >= 0.80) return 'warning';
    return 'error';
  };

  return (
    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', p: 1.5, bgcolor: '#ffffff', borderRadius: 1, border: '1px solid', borderColor: '#e2e8f0' }}>
      
      {/* Left side: Title & Info */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <Typography variant="h6" color="#0f172a" fontWeight="bold">
          {title}
        </Typography>
        <Typography variant="caption" sx={{ p: 0.5, px: 1, bgcolor: '#f1f5f9', borderRadius: 1, border: '1px solid', borderColor: '#cbd5e1', color: '#64748b' }}>
          ID: {sessionId.substring(0, 8)}...
        </Typography>
        
        {confidenceScore !== undefined && (
          <Chip 
            label={`AI Confidence: ${(confidenceScore * 100).toFixed(1)}%`} 
            color={getConfidenceColor(confidenceScore)} 
            size="small" 
            variant="outlined"
          />
        )}
      </Box>

      {/* Right side: Controls & Status */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        
        {/* Autosave Status */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, color: '#64748b' }}>
          {saveStatus === 'saving' && (
            <><RefreshCw size={16} className="animate-spin" /> <Typography variant="caption">Saving...</Typography></>
          )}
          {saveStatus === 'saved' && (
            <><CheckCircle size={16} color="#10b981" /> <Typography variant="caption" color="#10b981">Saved</Typography></>
          )}
          {saveStatus === 'error' && (
            <><AlertCircle size={16} color="#ef4444" /> <Typography variant="caption" color="#ef4444">Save Failed</Typography></>
          )}
          {saveStatus === 'idle' && lastSaved && (
            <><Save size={16} /> <Typography variant="caption">Last saved: {lastSaved.toLocaleTimeString()}</Typography></>
          )}
        </Box>

        <Stack direction="row" spacing={1}>
          {extraControls}
        </Stack>
      </Box>
    </Box>
  );
}
