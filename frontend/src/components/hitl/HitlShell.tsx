import React from 'react';
import { Box } from '@mui/material';

export interface HitlShellProps {
  toolbar?: React.ReactNode;
  sidebar?: React.ReactNode;
  canvas: React.ReactNode;
  inspector: React.ReactNode;
}

export function HitlShell({
  toolbar,
  sidebar,
  canvas,
  inspector
}: HitlShellProps) {
  return (
    <Box 
      sx={{ 
        height: '100%',
        display: 'flex', 
        flexDirection: 'column', 
        overflow: 'hidden', 
        boxSizing: 'border-box', 
        bgcolor: '#f8fafc', 
        p: 1, 
        borderRadius: 2 
      }}
    >
      {/* Top Toolbar */}
      {toolbar && (
        <Box sx={{ mb: 1, flexShrink: 0 }}>
          {toolbar}
        </Box>
      )}

      {/* Main Content Area */}
      <Box sx={{ flexGrow: 1, minHeight: 0, display: 'flex', flexDirection: 'row', gap: 2, overflow: 'hidden' }}>
        
        {/* Left Sidebar (Optional) */}
        {sidebar && (
          <Box sx={{ width: 250, flexShrink: 0, display: 'flex', flexDirection: 'column', overflowY: 'auto' }}>
            {sidebar}
          </Box>
        )}

        {/* Center Canvas */}
        <Box sx={{ flex: 1, minHeight: 0, minWidth: 0, display: 'flex', flexDirection: 'column', bgcolor: '#ffffff', border: '1px solid', borderColor: '#e2e8f0', borderRadius: 2, overflow: 'hidden' }}>
          {canvas}
        </Box>

        {/* Right Inspector Panel */}
        <Box sx={{ width: { xs: 350, lg: 400 }, flexShrink: 0, display: 'flex', flexDirection: 'column', overflowY: 'auto' }}>
          {inspector}
        </Box>

      </Box>
    </Box>
  );
}
