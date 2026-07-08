import { useQuery } from "@tanstack/react-query";
import { Box, Button, Divider, Grid, Stack, Table, TableBody, TableCell, TableHead, TableRow, Typography, alpha } from "@mui/material";
import { Download, FileText, Share2, ShieldCheck } from "lucide-react";
import { backendApi, getAssetUrl } from "../api/backendApi";
import { useParams } from "react-router-dom";
import { useResolvedSessionId } from "../hooks/useResolvedSessionId";
import type { BatchReportResponse, InspectionReportResponse } from "../types";
import { useState } from "react";
import { ImagePreviewModal } from "../components/ImagePreviewModal";
import { Sparkles, X } from "lucide-react";
import { Dialog, DialogTitle, DialogContent, CircularProgress, IconButton } from "@mui/material";

function formatIDR(value: number) {
  return `IDR ${Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function getRiskLevel(criticalDefects: number, defectCount: number) {
  if (criticalDefects >= 3 || defectCount >= 8) return "High";
  if (criticalDefects >= 1 || defectCount >= 3) return "Medium";
  return "Low";
}

export function ReportContent({ batchId, sessionId, hideHeader }: { batchId?: string, sessionId?: string, hideHeader?: boolean }) {
  const [previewImage, setPreviewImage] = useState<string | null>(null);
  const [explainModalOpen, setExplainModalOpen] = useState(false);
  const [explainingItem, setExplainingItem] = useState<string | null>(null);
  const [explanationText, setExplanationText] = useState<string | null>(null);
  const [isExplaining, setIsExplaining] = useState(false);

  // Multilingual State
  const [language, setLanguage] = useState<"en" | "bahasa">("en");
  const [langUrls, setLangUrls] = useState<{ document_docx_url: string; document_pdf_url: string } | null>(null);
  const [isLangLoading, setIsLangLoading] = useState(false);

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
  const healthScore = reportData.healthScore ?? 0;
  const totalEstimatedCost = reportData.totalEstimatedCost ?? 0;
  const riskLevel = getRiskLevel(reportData.criticalDefects ?? 0, reportData.defectCount ?? 0);

  const handleLanguageChange = async (lang: "en" | "bahasa") => {
    setLanguage(lang);
    if (lang === "en") {
      setLangUrls(null);
      return;
    }
    
    setIsLangLoading(true);
    try {
      const res = await backendApi.getReportLanguage(batchId ?? sessionId!, "bahasa");
      if (res && !("error" in res)) {
        setLangUrls(res);
      }
    } catch (err) {
      console.error("Failed to load translated report URLs", err);
    } finally {
      setIsLangLoading(false);
    }
  };

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

  const t = (text: string) => {
    if (language !== "bahasa") return text;
    const dict: Record<string, string> = {
      "Inspection Batches / ": "Batch Inspeksi / ",
      "Combined Report": "Laporan Gabungan",
      "Inspections / Final Report": "Inspeksi / Laporan Akhir",
      "Combined Inspection Report": "Laporan Inspeksi Gabungan",
      "Inspection Report": "Laporan Inspeksi",
      "Report Intelligence": "Kecerdasan Laporan",
      "Health Score": "Skor Kesehatan",
      "Risk Level": "Tingkat Risiko",
      "Est. Cost Exposure": "Estimasi Paparan Biaya",
      "Report Actions": "Tindakan Laporan",
      "Download DOCX": "Unduh DOCX",
      "Download PDF": "Unduh PDF",
      "Share Link": "Bagikan Tautan",
      "Approve & Sign-off": "Setujui & Tandatangani",
      "Line Items Breakdown": "Rincian Item Baris",
      "Type": "Jenis",
      "Part": "Bagian",
      "Area": "Area",
      "Severity": "Keparahan",
      "Cost": "Biaya",
      "Actions": "Tindakan",
      "Explain": "Jelaskan",
      "AI Explanation": "Penjelasan AI",
      "High": "Tinggi",
      "Medium": "Sedang",
      "Low": "Rendah",
      "Corrosion": "Korosi",
      "Crack": "Retak",
      "Deformation": "Deformasi",
      "Pitting": "Lubang Korosi",
      "Wastage": "Penipisan Plat",
      "Dent": "Penyok",
      "Welding Defect": "Cacat Pengelasan",
      "Hull": "Lambung",
      "Side Shell": "Pelat Sisi",
      "Bottom Shell": "Pelat Alas",
      "Deck": "Geladak",
      "Bulkhead": "Sekat",
      "Frame": "Gading",
      "Transverse Frame": "Gading Melintang",
      "Longitudinal Frame": "Gading Membujur",
      "The PDF document is still being generated or is not available.": "Dokumen PDF masih dibuat atau tidak tersedia.",
      "Generating translated report... Please wait.": "Menghasilkan laporan terjemahan... Silakan tunggu."
    };
    return dict[text] || text;
  };

  const activePdfUrl = langUrls ? langUrls.document_pdf_url : reportData.downloadPdfUrl;
  const activeDocxUrl = langUrls ? langUrls.document_docx_url : reportData.downloadDocxUrl;

  return (
    <Stack spacing={2}>
{!hideHeader && (
  <Stack
    direction={{ xs: "column", sm: "row" }}
    justifyContent="space-between"
    alignItems={{ xs: "flex-start", sm: "center" }}
    spacing={2}
    mb={1}
  >
    <Stack spacing={0.5}>
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{ textTransform: "uppercase", letterSpacing: 1 }}
      >
        {batchId
          ? `${t("Inspection Batches / ")} ${batchId} / ${t("Combined Report")}`
          : t("Inspections / Final Report")}
      </Typography>

      <Typography variant="h4" fontSize={26}>
        {batchId
          ? t("Combined Inspection Report")
          : t("Inspection Report")}
      </Typography>
    </Stack>
  </Stack>
)}

<Box
  sx={{
    display: "flex",
    justifyContent: "flex-end",
    mb: 2,
  }}
>
  <Stack
    direction="row"
    spacing={1}
    sx={{
      bgcolor: "background.paper",
      p: 0.5,
      borderRadius: 2,
      border: "1px solid",
      borderColor: "divider",
    }}
  >
    <Button
      size="small"
      variant={language === "en" ? "contained" : "text"}
      color={language === "en" ? "primary" : "inherit"}
      onClick={() => handleLanguageChange("en")}
      sx={{ px: 2, borderRadius: 1.5 }}
    >
      English
    </Button>

    <Button
      size="small"
      variant={language === "bahasa" ? "contained" : "text"}
      color={language === "bahasa" ? "primary" : "inherit"}
      onClick={() => handleLanguageChange("bahasa")}
      sx={{ px: 2, borderRadius: 1.5 }}
    >
      Bahasa
    </Button>
  </Stack>
</Box>
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
              {isLangLoading ? (
                <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', alignItems: 'center', justifyContent: 'center', p: 4, gap: 2 }}>
                  <CircularProgress size={40} />
                  <Typography color="text.secondary">
                    {t("Generating translated report... Please wait.")}
                  </Typography>
                </Box>
              ) : activePdfUrl ? (
                <iframe 
                  src={getAssetUrl(activePdfUrl)} 
                  width="100%" 
                  height="100%" 
                  style={{ border: 'none' }}
                  title="Inspection Report PDF"
                />
              ) : (
                <Box sx={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center', p: 4, textAlign: 'center' }}>
                  <Typography color="text.secondary">
                    {t("The PDF document is still being generated or is not available.")}
                  </Typography>
                </Box>
              )}
            </Box>
          </Box>
        </Grid>

        <Grid size={{ xs: 12, lg: 3 }}>
          <Box sx={{ bgcolor: "background.paper", borderRadius: 3, p: 2.5, position: "sticky", top: 24, mb: 2 }}>
            <Typography variant="h6" fontSize={14} mb={2} textTransform="uppercase" color="text.secondary">
              {t("Report Intelligence")}
            </Typography>
            <Stack spacing={2}>
              <Box>
                <Typography variant="caption" color="text.secondary">{t("Health Score")}</Typography>
                <Typography variant="h4" fontWeight={800} color="primary.main">{healthScore}/100</Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">{t("Risk Level")}</Typography>
                <Typography
                  variant="h5"
                  fontWeight={700}
                  color={riskLevel === "High" ? "error.main" : riskLevel === "Medium" ? "warning.main" : "success.main"}
                >
                  {t(riskLevel)}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">{t("Est. Cost Exposure")}</Typography>
                <Typography variant="h5" fontWeight={700} color="error.main">{formatIDR(totalEstimatedCost)}</Typography>
              </Box>
            </Stack>
          </Box>
          <Box sx={{ bgcolor: "background.paper", borderRadius: 3, p: 2.5, position: "sticky", top: 280 }}>
            <Typography variant="h6" fontSize={14} mb={2} textTransform="uppercase" color="text.secondary">
              {t("Report Actions")}
            </Typography>
            <Stack spacing={1.5}>
              <Button fullWidth variant="outlined" startIcon={<FileText size={16} />} component="a" href={activeDocxUrl ? (activeDocxUrl.includes("supabase.co") ? `${getAssetUrl(activeDocxUrl)}?download=` : getAssetUrl(activeDocxUrl)) : undefined} download disabled={!activeDocxUrl} sx={{ justifyContent: "flex-start", textAlign: "left", lineHeight: 1.2 }}>
                {t("Download DOCX")}
              </Button>
              <Button fullWidth variant="outlined" startIcon={<Download size={16} />} component="a" href={activePdfUrl ? (activePdfUrl.includes("supabase.co") ? `${getAssetUrl(activePdfUrl)}?download=` : `${getAssetUrl(activePdfUrl)}?attachment=true`) : undefined} download disabled={!activePdfUrl} sx={{ justifyContent: "flex-start", textAlign: "left", lineHeight: 1.2 }}>
                {t("Download PDF")}
              </Button>
              <Divider sx={{ my: 1 }} />
              <Button fullWidth variant="outlined" startIcon={<Share2 size={16} />} sx={{ justifyContent: "flex-start", textAlign: "left", lineHeight: 1.2 }}>
                {t("Share Link")}
              </Button>
              <Button fullWidth variant="contained" color="success" startIcon={<ShieldCheck size={16} />} sx={{ justifyContent: "flex-start", textAlign: "left", lineHeight: 1.2 }}>
                {t("Approve & Sign-off")}
              </Button>
            </Stack>
          </Box>
        </Grid>
      </Grid>
      
      {/* LINE ITEMS SECTION */}
      {reportData && reportData.defects && reportData.defects.length > 0 && (
        <Box sx={{ bgcolor: "background.paper", borderRadius: 3, p: 3, mt: 3, boxShadow: "0 4px 20px rgba(0,0,0,0.03)" }}>
          <Typography variant="h5" mb={3} fontWeight={700}>{t("Line Items Breakdown")}</Typography>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>{t("Type")}</TableCell>
                <TableCell>{t("Part")}</TableCell>
                <TableCell>{t("Area")}</TableCell>
                <TableCell>{t("Severity")}</TableCell>
                <TableCell>{t("Cost")}</TableCell>
                <TableCell align="right">{t("Actions")}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {reportData.defects.map(defect => (
                <TableRow key={defect.defectId}>
                  <TableCell sx={{ fontWeight: 500 }}>{t(defect.defectType)}</TableCell>
                  <TableCell>{t(defect.partName)}</TableCell>
                  <TableCell>{defect.area} sq.m</TableCell>
                  <TableCell>
                    <Box sx={{ 
                      px: 1, py: 0.5, borderRadius: 1, display: 'inline-block', fontSize: 12, fontWeight: 700,
                      bgcolor: defect.severity.toLowerCase() === 'high' ? alpha('#ef4444', 0.1) : 
                               defect.severity.toLowerCase() === 'medium' ? alpha('#f59e0b', 0.1) : alpha('#10b981', 0.1),
                      color: defect.severity.toLowerCase() === 'high' ? '#ef4444' : 
                             defect.severity.toLowerCase() === 'medium' ? '#f59e0b' : '#10b981'
                    }}>
                      {t(defect.severity.toUpperCase())}
                    </Box>
                  </TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>{formatIDR(defect.repairCost)}</TableCell>
                  <TableCell align="right">
                    <Button 
                      size="small" 
                      variant="outlined" 
                      color="secondary" 
                      startIcon={<Sparkles size={14} />}
                      onClick={() => handleExplain(defect.defectId)}
                    >
                      {t("Explain")}
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
            <Typography variant="h6" fontWeight={700}>{t("AI Explanation")}</Typography>
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
