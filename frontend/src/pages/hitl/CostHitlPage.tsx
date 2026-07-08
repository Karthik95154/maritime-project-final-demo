import { backendApi, getAssetUrl } from "../../api/backendApi";
import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Autocomplete,
  Box,
  Button,
  Chip,
  Divider,
  IconButton,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
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

const COMMON_REPAIR_ITEMS = [
  "Marine Primer",
  "Epoxy Paint",
  "Rust Converter",
  "Sandblasting Media",
  "Welding Electrodes",
  "Steel Plate",
  "Scaffolding",
  "Labor (General)",
  "Labor (Specialized)",
  "Antifouling Coating",
  "Grinding Discs"
];

const LABOR_KEYWORDS = ["labor", "welding", "blasting", "grinding", "inspection"];
const EQUIPMENT_KEYWORDS = ["scaffolding", "machine", "equipment", "rental", "crane", "compressor"];

function toNumber(value: unknown) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : 0;
}

function normalizeItem(item: any, defaultCurrency: string) {
  const quantityPerSqm = toNumber(item?.quantity_per_sqm ?? 0);
  const requiredQuantity = toNumber(item?.required_quantity ?? item?.quantity ?? quantityPerSqm ?? 0);
  const unitCost = toNumber(item?.unit_cost ?? item?.cost ?? 0);
  const explicitTotalCost = item?.total_cost;
  const totalCost =
    explicitTotalCost === undefined || explicitTotalCost === null || explicitTotalCost === ""
      ? requiredQuantity * unitCost
      : requiredQuantity * unitCost;

  return {
    item_name: item?.item_name || item?.name || "New Item",
    metrics: item?.metrics || item?.unit || "pcs",
    quantity_per_sqm: quantityPerSqm,
    required_quantity: requiredQuantity,
    unit_cost: unitCost,
    currency: item?.currency || defaultCurrency,
    total_cost: totalCost,
  };
}

const inputCellSx = {
  minWidth: 96,
  "& .MuiOutlinedInput-root": {
    bgcolor: "#ffffff",
  },
};

const itemNameInputSx = {
  minWidth: 220,
  "& .MuiOutlinedInput-root": {
    bgcolor: "#ffffff",
  },
};

function categorizeItem(itemName: string) {
  const normalized = String(itemName || "").toLowerCase();
  if (LABOR_KEYWORDS.some((keyword) => normalized.includes(keyword))) {
    return "labor";
  }
  if (EQUIPMENT_KEYWORDS.some((keyword) => normalized.includes(keyword))) {
    return "equipment";
  }
  return "material";
}

function normalizeCostState(raw: any) {
  const source = raw && typeof raw === "object" ? raw : {};
  const repairSummary = source.repair_summary && typeof source.repair_summary === "object" ? source.repair_summary : {};
  const defectRepairs = source.defect_repairs && typeof source.defect_repairs === "object" ? source.defect_repairs : {};
  const defaultCurrency = repairSummary.currency || "IDR";

  let totalEstimatedCost = 0;
  let totalMaterialCost = 0;
  let totalLaborCost = 0;
  let totalEquipmentCost = 0;
  const severityDistribution: Record<string, number> = {};

  const normalizedRepairs = Object.fromEntries(
    Object.entries(defectRepairs).map(([defectId, defectData]: [string, any]) => {
      const defectCurrency = defectData?.repair_estimation?.currency || defaultCurrency;
      const requiredItems = Array.isArray(defectData?.repair_estimation?.required_items)
        ? defectData.repair_estimation.required_items.map((item: any) => normalizeItem(item, defectCurrency))
        : [];

      const defectTotal = requiredItems.reduce((sum: number, item: any) => sum + toNumber(item.total_cost), 0);
      const severity = defectData?.severity || "unknown";
      severityDistribution[severity] = (severityDistribution[severity] || 0) + 1;

      requiredItems.forEach((item: any) => {
        const category = categorizeItem(item.item_name);
        if (category === "labor") totalLaborCost += item.total_cost;
        else if (category === "equipment") totalEquipmentCost += item.total_cost;
        else totalMaterialCost += item.total_cost;
      });

      totalEstimatedCost += defectTotal;

      return [
        defectId,
        {
          ...defectData,
          repair_estimation: {
            ...defectData?.repair_estimation,
            currency: defectCurrency,
            estimated_total_cost: defectTotal,
            required_items: requiredItems,
          },
        },
      ];
    })
  );

  return {
    ...source,
    repair_summary: {
      ...repairSummary,
      total_defects: Object.keys(normalizedRepairs).length,
      total_estimated_cost: totalEstimatedCost,
      total_material_cost: totalMaterialCost,
      total_labor_cost: totalLaborCost,
      total_equipment_cost: totalEquipmentCost,
      currency: defaultCurrency,
      severity_distribution: severityDistribution,
    },
    defect_repairs: normalizedRepairs,
  };
}

function formatMoney(value: unknown, currency: string) {
  return `${currency} ${toNumber(value).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function CostHitlContent({ sessionId }: { sessionId: string }) {
  const navigate = useNavigate();
  
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [defectImages, setDefectImages] = useState<Record<string, string>>({});

  // humanOutput stores the full JSON structure
  const { currentState: humanOutput, pushState: setHumanOutput, undo, redo, canUndo, canRedo, resetHistory } = useHitlHistory<any>(null);

  useEffect(() => {
    backendApi.getInternalReviewDetail(sessionId!)
      .then(json => {
        setData(json);
        const pipelineData = json.pipeline_data || {};
        const existingHuman = pipelineData["repair_human_json"];
        const aiOutput = pipelineData["repair_ai_json"];

        const areaData = pipelineData["area_human_json"] || pipelineData["unique_json"] || {};
        const images: Record<string, string> = {};
        for (const [key, val] of Object.entries(areaData)) {
            if ((val as any).best_frame_path) {
                images[key] = (val as any).best_frame_path;
            }
        }
        setDefectImages(images);
        
        resetHistory(normalizeCostState(existingHuman || aiOutput || { defect_repairs: {}, repair_summary: {} }));
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to load session", err);
        setError("Session not found or error loading data.");
        setLoading(false);
      });
  }, [sessionId, resetHistory]);

  const handleSave = async (dataToSave: any) => {
    try {
      await backendApi.saveCostReview(sessionId!, {
        decision: "save_assessment",
        corrections: dataToSave,
        reviewer: "System Admin"
      });
    } catch (err) {}
  };

  const { status: saveStatus, lastSaved, forceSave } = useHitlAutosave({
    data: humanOutput,
    onSave: handleSave,
    enabled: !loading && !error && humanOutput
  });

  const handleDecision = async (decision: string) => {
    try {
      await forceSave(humanOutput);
      await backendApi.saveCostReview(sessionId!, {
        decision,
        corrections: humanOutput,
        reviewer: "System Admin"
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
    const items = nextState.defect_repairs?.[defectId]?.repair_estimation?.required_items ?? [];
    items[itemIdx][field] = value;
    setHumanOutput(normalizeCostState(nextState));
  };

  const handleAddItem = (defectId: string) => {
    if (!humanOutput) return;
    const nextState = JSON.parse(JSON.stringify(humanOutput));
    
    if (!nextState.defect_repairs[defectId].repair_estimation) {
        nextState.defect_repairs[defectId].repair_estimation = {
            estimated_total_cost: 0,
            currency: 'USD',
            required_items: []
        };
    }
    if (!nextState.defect_repairs[defectId].repair_estimation.required_items) {
        nextState.defect_repairs[defectId].repair_estimation.required_items = [];
    }

    nextState.defect_repairs[defectId].repair_estimation.required_items.push({
      item_name: "New Item",
      metrics: "pcs",
      quantity_per_sqm: 0,
      required_quantity: 1,
      unit_cost: 0,
      currency: nextState.repair_summary?.currency || "IDR",
      total_cost: 0
    });
    setHumanOutput(normalizeCostState(nextState));
  };

  const handleRemoveItem = (defectId: string, itemIdx: number) => {
    if (!humanOutput) return;
    const nextState = JSON.parse(JSON.stringify(humanOutput));
    const items = nextState.defect_repairs[defectId].repair_estimation.required_items;
    items.splice(itemIdx, 1);

    setHumanOutput(normalizeCostState(nextState));
  };

  const summary = humanOutput?.repair_summary || {};
  const defectEntries = Object.entries(humanOutput?.defect_repairs || {});
  const currency = summary.currency || "IDR";
  const severityChips = Object.entries(summary.severity_distribution || {});

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
          <Box sx={{ flex: 1, p: { xs: 1.5, md: 3 }, overflowY: 'auto' }}>
            <Stack spacing={3}>
              <Paper sx={{ p: { xs: 2, md: 3 }, borderRadius: 3 }}>
                <Stack direction={{ xs: "column", lg: "row" }} spacing={2} justifyContent="space-between">
                  <Box>
                    <Typography variant="h5" fontWeight={800}>Repair Estimation Breakdown</Typography>
                    <Typography variant="body2" color="text.secondary" mt={0.75}>
                      Review itemized repair costs, fix quantities and rates, and confirm the final summary before report generation.
                    </Typography>
                  </Box>
                  <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
                    <Paper variant="outlined" sx={{ p: 1.5, minWidth: 180 }}>
                      <Typography variant="caption" color="text.secondary">Total Estimated Cost</Typography>
                      <Typography variant="h6" fontWeight={800}>{formatMoney(summary.total_estimated_cost, currency)}</Typography>
                    </Paper>
                    <Paper variant="outlined" sx={{ p: 1.5, minWidth: 150 }}>
                      <Typography variant="caption" color="text.secondary">Material</Typography>
                      <Typography variant="subtitle1" fontWeight={700}>{formatMoney(summary.total_material_cost, currency)}</Typography>
                    </Paper>
                    <Paper variant="outlined" sx={{ p: 1.5, minWidth: 150 }}>
                      <Typography variant="caption" color="text.secondary">Labor</Typography>
                      <Typography variant="subtitle1" fontWeight={700}>{formatMoney(summary.total_labor_cost, currency)}</Typography>
                    </Paper>
                    <Paper variant="outlined" sx={{ p: 1.5, minWidth: 150 }}>
                      <Typography variant="caption" color="text.secondary">Equipment</Typography>
                      <Typography variant="subtitle1" fontWeight={700}>{formatMoney(summary.total_equipment_cost, currency)}</Typography>
                    </Paper>
                  </Stack>
                </Stack>
                {severityChips.length > 0 && (
                  <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap mt={2}>
                    {severityChips.map(([severity, count]) => (
                      <Chip key={severity} label={`${severity}: ${count}`} size="small" variant="outlined" />
                    ))}
                  </Stack>
                )}
              </Paper>

              {defectEntries.map(([defectId, defectData]: [string, any]) => (
              <Accordion key={defectId} defaultExpanded sx={{ mb: 0, borderRadius: 2, '&:before': { display: 'none' }, boxShadow: '0 4px 12px rgba(0,0,0,0.05)' }}>
                <AccordionSummary expandIcon={<ChevronDown />} sx={{ bgcolor: 'rgba(0,0,0,0.02)' }}>
                  <Box display="flex" justifyContent="space-between" alignItems={{ xs: "flex-start", sm: "center" }} width="100%" pr={2} gap={2} flexDirection={{ xs: "column", sm: "row" }}>
                    <Box minWidth={0}>
                      <Typography variant="subtitle1" fontWeight={700}>
                        {defectData.defect_name || defectId}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Severity: {defectData.severity || "Unknown"}
                      </Typography>
                    </Box>
                    <Typography variant="subtitle1" fontWeight={800} color="primary" sx={{ whiteSpace: "nowrap" }}>
                      {formatMoney(defectData.repair_estimation?.estimated_total_cost, defectData.repair_estimation?.currency || currency)}
                    </Typography>
                  </Box>
                </AccordionSummary>
                <AccordionDetails>
                  {defectImages[defectId] && (
                    <Box mb={3} textAlign="center" bgcolor="#f8fafc" p={2} borderRadius={2} border="1px solid #e2e8f0">
                      <img 
                        src={getAssetUrl(defectImages[defectId])} 
                        alt={defectData.defect_name || defectId} 
                        style={{ maxHeight: 350, maxWidth: '100%', objectFit: 'contain', borderRadius: 8 }} 
                      />
                    </Box>
                  )}
                  <TableContainer sx={{ overflowX: "auto", border: "1px solid #e2e8f0", borderRadius: 2 }}>
                  <Table size="small" sx={{ minWidth: 900 }}>
                    <TableHead>
                      <TableRow>
                        <TableCell>Required Item / Process</TableCell>
                        <TableCell>Unit</TableCell>
                        <TableCell width={120}>Qty / sqm</TableCell>
                        <TableCell width={100}>Quantity</TableCell>
                        <TableCell width={150}>Unit Cost</TableCell>
                        <TableCell>Currency</TableCell>
                        <TableCell>Total</TableCell>
                        <TableCell width={50}></TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {defectData.repair_estimation?.required_items?.map((item: any, idx: number) => (
                        <TableRow key={idx}>
                          <TableCell>
                            <Autocomplete
                              size="small"
                              freeSolo
                              options={COMMON_REPAIR_ITEMS}
                              value={item.item_name || ""}
                              onChange={(_, newValue) => handleUpdateItem(defectId, idx, 'item_name', newValue || "")}
                              sx={itemNameInputSx}
                              renderInput={(params) => (
                                <TextField
                                  {...params}
                                  value={item.item_name || ""}
                                  onChange={(e) => handleUpdateItem(defectId, idx, "item_name", e.target.value)}
                                  size="small"
                                />
                              )}
                            />
                          </TableCell>
                          <TableCell>
                            <TextField size="small" sx={inputCellSx} value={item.metrics || ""} onChange={(e) => handleUpdateItem(defectId, idx, 'metrics', e.target.value)} />
                          </TableCell>
                          <TableCell>
                            <TextField size="small" sx={inputCellSx} type="number" value={item.quantity_per_sqm ?? 0} onChange={(e) => handleUpdateItem(defectId, idx, 'quantity_per_sqm', e.target.value)} />
                          </TableCell>
                          <TableCell>
                            <TextField size="small" sx={inputCellSx} type="number" value={item.required_quantity} onChange={(e) => handleUpdateItem(defectId, idx, 'required_quantity', e.target.value)} />
                          </TableCell>
                          <TableCell>
                            <TextField size="small" sx={inputCellSx} type="number" value={item.unit_cost} onChange={(e) => handleUpdateItem(defectId, idx, 'unit_cost', e.target.value)} />
                          </TableCell>
                          <TableCell>
                            <TextField size="small" sx={inputCellSx} value={item.currency || ""} onChange={(e) => handleUpdateItem(defectId, idx, 'currency', e.target.value)} />
                          </TableCell>
                          <TableCell sx={{ fontWeight: 700, whiteSpace: "nowrap", color: "primary.main" }}>
                            {formatMoney(item.total_cost, item.currency || currency)}
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
                  </TableContainer>
                  <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" alignItems={{ xs: "stretch", sm: "center" }} spacing={1.5} mt={2}>
                  <Button startIcon={<Plus size={16} />} sx={{ mt: 2 }} onClick={() => handleAddItem(defectId)}>
                    Add Item
                  </Button>
                    <Typography variant="subtitle2" fontWeight={700}>
                      Defect Total: {formatMoney(defectData.repair_estimation?.estimated_total_cost, defectData.repair_estimation?.currency || currency)}
                    </Typography>
                  </Stack>
                </AccordionDetails>
              </Accordion>
            ))}
            </Stack>
          </Box>
        </HitlWorkspace>
        <HitlSidebar>
          <Box p={2.5}>
             <Typography variant="subtitle2" color="text.secondary" textTransform="uppercase" mb={2}>Review Guidelines</Typography>
             <Typography variant="body2" paragraph>Adjust item names, units, quantities, and rates directly in the table. Every change recomputes the defect total and the global cost summary.</Typography>
             <Typography variant="body2" paragraph>Draft saves are allowed even if the pipeline checkpoint has already moved ahead, so you should no longer see repeated 400 errors during autosave.</Typography>
             <Divider sx={{ my: 2 }} />
             <Typography variant="subtitle2" color="text.secondary" textTransform="uppercase" mb={1.5}>Session Summary</Typography>
             <Stack spacing={1.25}>
               <Paper variant="outlined" sx={{ p: 1.5 }}>
                 <Typography variant="caption" color="text.secondary">Defects</Typography>
                 <Typography variant="body1" fontWeight={700}>{summary.total_defects || defectEntries.length}</Typography>
               </Paper>
               <Paper variant="outlined" sx={{ p: 1.5 }}>
                 <Typography variant="caption" color="text.secondary">Grand Total</Typography>
                 <Typography variant="body1" fontWeight={700}>{formatMoney(summary.total_estimated_cost, currency)}</Typography>
               </Paper>
             </Stack>
          </Box>
          <HitlActionBar 
            onApprove={() => handleDecision('assess_continue')}
            onReject={() => handleDecision('reject')}
            onSaveDraft={() => forceSave(humanOutput)}
            isSaving={saveStatus === 'saving'}
            approveText="Approve & Generate Report"
            rejectText="Reject Estimation"
          />
        </HitlSidebar>
      </HitlMainContainer>
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
