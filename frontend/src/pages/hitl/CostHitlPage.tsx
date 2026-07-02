import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Box, Typography, Button, Stack, Table, TableBody, TableCell, TableHead, TableRow, IconButton, TextField, Paper, Divider, Accordion, AccordionSummary, AccordionDetails } from "@mui/material";
import { ChevronDown, Plus, Trash2 } from "lucide-react";
import { 
  HitlLayout,
  HitlHeader,
  HitlMainContainer,
  HitlWorkspace,
  HitlSidebar,
  HitlActionBar,
  useHitlHistory, 
  useHitlAutosave,
  useHitlShortcuts
} from "../../components/hitl";
import { backendApi, API_BASE_URL } from "../../api/backendApi";

function CostHitlContent({ sessionId }: { sessionId: string }) {
  const navigate = useNavigate();
  
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // humanOutput stores the full JSON structure
  const { currentState: humanOutput, pushState: setHumanOutput, undo, redo, canUndo, canRedo, resetHistory } = useHitlHistory<any>(null);

  useEffect(() => {
    fetch($/api/v1/internal/reviews/{sessionId})
      .then(async (res) => {
        if (!res.ok) throw new Error(await res.text());
        return res.json();
      })
      .then(json => {
        setData(json);
        const pipelineData = json.pipeline_data || {};
        const existingHuman = pipelineData["repair_human_json"];
        const aiOutput = pipelineData["repair_ai_json"];
        
        resetHistory(existingHuman || aiOutput || { defect_repairs: {}, repair_summary: {} });
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to load session", err);
        setError("Session not found or error loading data.");
        setLoading(false);
      });
  }, [sessionId, resetHistory]);

  const handleSave = async (dataToSave: any) => {
    await fetch($/api/v1/internal/reviews/{sessionId}/cost, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        decision: "save_assessment",
        corrections: dataToSave,
        reviewer: "System Admin"
      })
    });
  };

  const { status: saveStatus, lastSaved, forceSave } = useHitlAutosave({
    data: humanOutput,
    onSave: handleSave,
    enabled: !loading && !error && humanOutput
  });

  const handleDecision = async (decision: string) => {
    try {
      await forceSave(humanOutput);
      await fetch($/api/v1/internal/reviews/{sessionId}/cost, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          decision,
          corrections: humanOutput,
          reviewer: "System Admin"
        })
      });
      if (decision === "assess_continue") {
        navigate("/internal/review");
      }
    } catch (err) {
      console.error("Failed to submit decision", err);
    }
  };

  useHitlShortcuts({
    onApprove: () => handleDecision('assess_continue'),
    onReject: () => handleDecision('reject'),
    onSave: () => forceSave(humanOutput),
    onUndo: undo,
    onRedo: redo,
    disabled: loading || !!error
  });

  const handleUpdateItem = (defectId: string, itemIdx: number, field: string, value: any) => {
    if (!humanOutput) return;
    const nextState = JSON.parse(JSON.stringify(humanOutput));
    
    const items = nextState.defect_repairs[defectId].repair_estimation.required_items;
    items[itemIdx][field] = value;
    
    // Recalculate total_cost for item
    if (field === 'quantity' || field === 'unit_cost') {
        const q = Number(items[itemIdx].quantity) || 0;
        const c = Number(items[itemIdx].unit_cost) || 0;
        items[itemIdx].total_cost = q * c;
    }
    
    // Recalculate defect estimated_total_cost
    const total = items.reduce((sum: number, item: any) => sum + (Number(item.total_cost) || 0), 0);
    nextState.defect_repairs[defectId].repair_estimation.estimated_total_cost = total;
    
    setHumanOutput(nextState);
  };

  const handleAddItem = (defectId: string) => {
    if (!humanOutput) return;
    const nextState = JSON.parse(JSON.stringify(humanOutput));
    nextState.defect_repairs[defectId].repair_estimation.required_items.push({
      item_name: "New Item",
      unit: "pcs",
      quantity: 1,
      unit_cost: 0,
      total_cost: 0
    });
    setHumanOutput(nextState);
  };

  const handleRemoveItem = (defectId: string, itemIdx: number) => {
    if (!humanOutput) return;
    const nextState = JSON.parse(JSON.stringify(humanOutput));
    const items = nextState.defect_repairs[defectId].repair_estimation.required_items;
    items.splice(itemIdx, 1);
    
    const total = items.reduce((sum: number, item: any) => sum + (Number(item.total_cost) || 0), 0);
    nextState.defect_repairs[defectId].repair_estimation.estimated_total_cost = total;
    
    setHumanOutput(nextState);
  };

  if (loading) return <Box p={4}><Typography>Loading session...</Typography></Box>;
  if (error) return <Box p={4}><Typography color="error" fontWeight="bold">{error}</Typography></Box>;

  return (
    <>
      <HitlHeader 
        title="Cost Review Assessment" 
        sessionId={sessionId!} 
        saveStatus={saveStatus}
        lastSaved={lastSaved}
        onUndo={undo}
        canUndo={canUndo}
        onRedo={redo}
        canRedo={canRedo}
      />
      <HitlMainContainer>
        <HitlWorkspace>
          <Box sx={{ flex: 1, p: 3, overflowY: 'auto' }}>
            <Typography variant="h5" fontWeight={700} mb={3}>Repair Estimation Breakdown</Typography>
            
            {humanOutput?.defect_repairs && Object.entries(humanOutput.defect_repairs).map(([defectId, defectData]: [string, any]) => (
              <Accordion key={defectId} defaultExpanded sx={{ mb: 2, borderRadius: 2, '&:before': { display: 'none' }, boxShadow: '0 4px 12px rgba(0,0,0,0.05)' }}>
                <AccordionSummary expandIcon={<ChevronDown />} sx={{ bgcolor: 'rgba(0,0,0,0.02)' }}>
                  <Box display="flex" justifyContent="space-between" alignItems="center" width="100%" pr={2}>
                    <Typography variant="subtitle1" fontWeight={600}>
                      {defectData.defect_name || defectId}
                    </Typography>
                    <Typography variant="subtitle1" fontWeight={700} color="primary">
                      {defectData.repair_estimation?.estimated_total_cost?.toLocaleString() || 0}
                    </Typography>
                  </Box>
                </AccordionSummary>
                <AccordionDetails>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Required Item / Process</TableCell>
                        <TableCell>Unit</TableCell>
                        <TableCell width={100}>Quantity</TableCell>
                        <TableCell width={150}>Unit Cost ($)</TableCell>
                        <TableCell>Total ($)</TableCell>
                        <TableCell width={50}></TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {defectData.repair_estimation?.required_items?.map((item: any, idx: number) => (
                        <TableRow key={idx}>
                          <TableCell>
                            <TextField size="small" fullWidth value={item.item_name} onChange={(e) => handleUpdateItem(defectId, idx, 'item_name', e.target.value)} />
                          </TableCell>
                          <TableCell>
                            <TextField size="small" value={item.unit} onChange={(e) => handleUpdateItem(defectId, idx, 'unit', e.target.value)} />
                          </TableCell>
                          <TableCell>
                            <TextField size="small" type="number" value={item.quantity} onChange={(e) => handleUpdateItem(defectId, idx, 'quantity', e.target.value)} />
                          </TableCell>
                          <TableCell>
                            <TextField size="small" type="number" value={item.unit_cost} onChange={(e) => handleUpdateItem(defectId, idx, 'unit_cost', e.target.value)} />
                          </TableCell>
                          <TableCell sx={{ fontWeight: 600 }}>
                            {item.total_cost?.toLocaleString()}
                          </TableCell>
                          <TableCell>
                            <IconButton size="small" color="error" onClick={() => handleRemoveItem(defectId, idx)}>
                              <Trash2 size={16} />
                            </IconButton>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                  <Button startIcon={<Plus size={16} />} sx={{ mt: 2 }} onClick={() => handleAddItem(defectId)}>
                    Add Item
                  </Button>
                </AccordionDetails>
              </Accordion>
            ))}
          </Box>
        </HitlWorkspace>
        <HitlSidebar>
          <Box p={2}>
             <Typography variant="subtitle2" color="text.secondary" textTransform="uppercase" mb={2}>Review Guidelines</Typography>
             <Typography variant="body2" paragraph>Review the required repairing items for each defect. You can add missing tools, adjust labor hours, or fix material costs directly in the tables.</Typography>
             <Typography variant="body2">Totals will recalculate automatically when you change quantities or unit prices.</Typography>
          </Box>
        </HitlSidebar>
      </HitlMainContainer>
      <HitlActionBar 
        onApprove={() => handleDecision('assess_continue')}
        onReject={() => handleDecision('reject')}
        approveLabel="Approve & Generate Report"
        rejectLabel="Reject Estimation"
      />
    </>
  );
}

export function CostHitlPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  if (!sessionId) return null;

  return (
    <HitlLayout>
      <CostHitlContent sessionId={sessionId} />
    </HitlLayout>
  );
}
