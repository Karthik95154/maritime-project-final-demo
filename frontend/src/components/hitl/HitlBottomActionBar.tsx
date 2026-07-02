import React from 'react';
import { Box, Button, Tooltip, Stack } from '@mui/material';
import { Check, X, Save } from 'lucide-react';

export interface HitlBottomActionBarProps {
  onApprove: () => void;
  onReject: () => void;
  onSaveDraft?: () => void;
  approveText?: string;
  rejectText?: string;
  isSaving?: boolean;
}

export function HitlBottomActionBar({
  onApprove,
  onReject,
  onSaveDraft,
  approveText = "Approve & Continue (A)",
  rejectText = "Reject (R)",
  isSaving = false
}: HitlBottomActionBarProps) {
  return (
    <Box sx={{ 
      p: 2, 
      bgcolor: '#ffffff', 
      border: '1px solid', 
      borderColor: '#e2e8f0', 
      borderRadius: 2, 
      display: 'flex', 
      flexDirection: 'column', 
      gap: 2, 
      mt: 'auto',
      flexShrink: 0
    }}>
      <Tooltip title="Shortcut: A" placement="top">
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
      </Tooltip>
      
      <Stack direction="row" spacing={2}>
        {onSaveDraft && (
          <Tooltip title="Shortcut: Ctrl+S" placement="top">
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
          </Tooltip>
        )}
        
        <Tooltip title="Shortcut: R" placement="top">
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
        </Tooltip>
      </Stack>
    </Box>
  );
}
