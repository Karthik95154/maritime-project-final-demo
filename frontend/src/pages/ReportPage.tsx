import { useQuery } from "@tanstack/react-query";
import { Box, Button, Divider, Grid, List, ListItemButton, ListItemText, Stack, Table, TableBody, TableCell, TableHead, TableRow, Typography, alpha } from "@mui/material";
import { Download, FileText, Share2, ShieldCheck, MapPin, Calendar, Ship } from "lucide-react";
import { backendApi, getAssetUrl } from "../api/backendApi";
import { useParams } from "react-router-dom";
import { useResolvedSessionId } from "../hooks/useResolvedSessionId";
import type { BatchReportResponse, InspectionReportResponse } from "../types";
import { Logo } from "../components/Logo";
import { useState } from "react";
import { ImagePreviewModal } from "../components/ImagePreviewModal";
import { Sparkles, X } from "lucide-react";
import { Dialog, DialogTitle, DialogContent, DialogActions, CircularProgress, IconButton } from "@mui/material";

export function ReportContent({ batchId, sessionId, hideHeader }: { batchId?: string, sessionId?: string, hideHeader?: boolean }) {
  const [previewImage, setPreviewImage] = useState<string | null>(null);
  const [explainModalOpen, setExplainModalOpen] = useState(false);
  const [explainingItem, setExplainingItem] = useState<string | null>(null);
  const [explanationText, setExplanationText] = useState<string | null>(null);
  const [isExplaining, setIsExplaining] = useState(false);

  const isBatchReport = Boolean(batchId);
  const { data, isLoading } = useQuery<InspectionReportResponse | BatchReportResponse>({
    queryKey: ["report", batchId ?? sessionId],
    queryFn: () =>
      batchId
        ? backendApi.getBatchReport(batchId)
        : backendApi.getInspectionReport(sessionId!),
    enabled: Boolean(batchId || sessionId),
    refetchInterval: isBatchReport ? 10000 : false,
  });

  if (isLoading) return <Box p={4}>Loading...</Box>;
  if (!data) return null;

  const reportData = data as InspectionReportResponse | BatchReportResponse;
  const batchReportData = isBatchReport ? (reportData as BatchReportResponse) : null;
  const singleReportData = !isBatchReport ? (reportData as InspectionReportResponse) : null;

  const handleExplain = async (defectId: string) => {
    if (!sessionId) return;
    setExplainingItem(defectId);
    setExplainModalOpen(true);
    setExplanationText(null);
    setIsExplaining(true);
    try {
      const result = await backendApi.explainDefect(sessionId, defectId);
      setExplanationText(result.explanation);
    } catch (err) {
      setExplanationText("Failed to retrieve explanation for this line item.");
    } finally {
      setIsExplaining(false);
    }
  };

  return (
    <Stack spacing={2}>
      {!hideHeader && (
        <Stack spacing={0.5} mb={1}>
          <Typography variant="caption" color="text.secondary" sx={{ textTransform: "uppercase", letterSpacing: 1 }}>
            {batchId ? `Inspection Batches / ${batchId} / Combined Report` : "Inspections / Final Report"}
          </Typography>
          <Typography variant="h4" fontSize={26}>
            {batchId ? "Combined Inspection Report" : "Inspection Report"}
          </Typography>
        </Stack>
      )}
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, lg: 9 }}>
          <Box
            sx={{
              bgcolor: "background.paper",
              borderRadius: 3,
              p: { xs: 2, md: 3 },
              minHeight: 800,
              boxShadow: "0 4px 20px rgba(0,0,0,0.03)",
            }}
          >
            {/* EMBEDDED PDF DOCUMENT */}
            <Box
              sx={{
                mx: "auto",
                maxWidth: 800,
                height: 840,
                borderRadius: 1,
                bgcolor: "#fff",
                boxShadow: "0 10px 40px rgba(15, 23, 42, 0.08)",
                border: "1px solid",
                borderColor: "divider",
                overflow: "hidden",
              }}
            >
              {reportData.downloadPdfUrl ? (
                <iframe 
                  src={getAssetUrl(reportData.downloadPdfUrl)} 
                  width="100%" 
                  height="100%" 
                  style={{ border: 'none' }}
                  title="Inspection Report PDF"
                />
              ) : (
                <Box sx={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center', p: 4, textAlign: 'center' }}>
                  <Typography color="text.secondary">
                    The PDF document is still being generated or is not available.
                  </Typography>
                </Box>
              )}
            </Box>
          </Box>
        </Grid>

        <Grid size={{ xs: 12, lg: 3 }}>
          <Box sx={{ bgcolor: "background.paper", borderRadius: 3, p: 2.5, position: "sticky", top: 24, mb: 2 }}>
            <Typography variant="h6" fontSize={14} mb={2} textTransform="uppercase" color="text.secondary">
              Report Intelligence
            </Typography>
            <Stack spacing={2}>
              <Box>
                <Typography variant="caption" color="text.secondary">Health Score</Typography>
                <Typography variant="h4" fontWeight={800} color="primary.main">85/100</Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">Risk Level</Typography>
                <Typography variant="h5" fontWeight={700} color="warning.main">Medium</Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">Est. Cost Exposure</Typography>
                <Typography variant="h5" fontWeight={700} color="error.main">₹ 4,50,000</Typography>
              </Box>
            </Stack>
          </Box>
          <Box sx={{ bgcolor: "background.paper", borderRadius: 3, p: 2.5, position: "sticky", top: 280 }}>
            <Typography variant="h6" fontSize={14} mb={2} textTransform="uppercase" color="text.secondary">
              Report Actions
            </Typography>
            <Stack spacing={1.5}>
              <Button fullWidth variant="outlined" startIcon={<FileText size={16} />} component="a" href={reportData.downloadDocxUrl ? (reportData.downloadDocxUrl.includes("supabase.co") ? `${getAssetUrl(reportData.downloadDocxUrl)}?download=` : getAssetUrl(reportData.downloadDocxUrl)) : undefined} download disabled={!reportData.downloadDocxUrl} sx={{ justifyContent: "flex-start", textAlign: "left", lineHeight: 1.2 }}>
                Download DOCX
              </Button>
              <Button fullWidth variant="outlined" startIcon={<Download size={16} />} component="a" href={reportData.downloadPdfUrl ? (reportData.downloadPdfUrl.includes("supabase.co") ? `${getAssetUrl(reportData.downloadPdfUrl)}?download=` : `${getAssetUrl(reportData.downloadPdfUrl)}?attachment=true`) : undefined} download disabled={!reportData.downloadPdfUrl} sx={{ justifyContent: "flex-start", textAlign: "left", lineHeight: 1.2 }}>
                Download PDF
              </Button>
              <Divider sx={{ my: 1 }} />
              <Button fullWidth variant="outlined" startIcon={<Share2 size={16} />} sx={{ justifyContent: "flex-start", textAlign: "left", lineHeight: 1.2 }}>
                Share Link
              </Button>
              <Button fullWidth variant="contained" color="success" startIcon={<ShieldCheck size={16} />} sx={{ justifyContent: "flex-start", textAlign: "left", lineHeight: 1.2 }}>
                Approve & Sign-off
              </Button>
            </Stack>
          </Box>
        </Grid>
      </Grid>
      
      {/* LINE ITEMS SECTION */}
      {reportData && reportData.defects && reportData.defects.length > 0 && (
        <Box sx={{ bgcolor: "background.paper", borderRadius: 3, p: 3, mt: 3, boxShadow: "0 4px 20px rgba(0,0,0,0.03)" }}>
          <Typography variant="h5" mb={3} fontWeight={700}>Line Items Breakdown</Typography>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Type</TableCell>
                <TableCell>Part</TableCell>
                <TableCell>Area</TableCell>
                <TableCell>Severity</TableCell>
                <TableCell>Cost</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {reportData.defects.map(defect => (
                <TableRow key={defect.defectId}>
                  <TableCell sx={{ fontWeight: 500 }}>{defect.defectType}</TableCell>
                  <TableCell>{defect.partName}</TableCell>
                  <TableCell>{defect.area} sq.m</TableCell>
                  <TableCell>
                    <Box sx={{ 
                      px: 1, py: 0.5, borderRadius: 1, display: 'inline-block', fontSize: 12, fontWeight: 700,
                      bgcolor: defect.severity.toLowerCase() === 'high' ? alpha('#ef4444', 0.1) : 
                               defect.severity.toLowerCase() === 'medium' ? alpha('#f59e0b', 0.1) : alpha('#10b981', 0.1),
                      color: defect.severity.toLowerCase() === 'high' ? '#ef4444' : 
                             defect.severity.toLowerCase() === 'medium' ? '#f59e0b' : '#10b981'
                    }}>
                      {defect.severity.toUpperCase()}
                    </Box>
                  </TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>${defect.repairCost.toLocaleString()}</TableCell>
                  <TableCell align="right">
                    <Button 
                      size="small" 
                      variant="outlined" 
                      color="secondary" 
                      startIcon={<Sparkles size={14} />}
                      onClick={() => handleExplain(defect.defectId)}
                    >
                      Explain
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Box>
      )}

      {/* EXPLANATION MODAL */}
      <Dialog open={explainModalOpen} onClose={() => setExplainModalOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Box display="flex" alignItems="center" gap={1}>
            <Sparkles size={20} color="#8b5cf6" />
            <Typography variant="h6" fontWeight={700}>AI Explanation</Typography>
          </Box>
          <IconButton onClick={() => setExplainModalOpen(false)} size="small"><X size={20} /></IconButton>
        </DialogTitle>
        <DialogContent dividers sx={{ minHeight: 120, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          {isExplaining ? (
            <Stack spacing={2} alignItems="center" color="text.secondary">
              <CircularProgress size={24} color="secondary" />
              <Typography variant="body2">Analyzing line item logic...</Typography>
            </Stack>
          ) : (
            <Typography variant="body1" sx={{ lineHeight: 1.6 }}>
              {explanationText}
            </Typography>
          )}
        </DialogContent>
      </Dialog>
      
      <ImagePreviewModal 
        open={!!previewImage} 
        onClose={() => setPreviewImage(null)} 
        imageUrl={previewImage} 
      />
    </Stack>
  );
}

export function ReportPage() {
  const { batchId } = useParams<{ batchId?: string }>();
  const { sessionId } = useResolvedSessionId();
  
  return <ReportContent batchId={batchId} sessionId={sessionId} />;
}

