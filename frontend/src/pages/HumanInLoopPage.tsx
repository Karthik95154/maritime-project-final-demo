import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Box, Chip, LinearProgress, Stack, Typography, Grid, Button, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, Tabs, Tab } from "@mui/material";
import { useNavigate } from "react-router-dom";
import { backendApi } from "../api/backendApi";
import { ChevronRight, ClipboardList } from "lucide-react";

export function HumanInLoopPage() {
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState(0);

  const queueQuery = useQuery({
    queryKey: ["internal-review-queue"],
    queryFn: backendApi.getInternalReviewQueue,
    refetchInterval: 1000,
  });

  const queue = queueQuery.data ?? [];
  const pendingReviews = queue.filter(item => 
    (item.reviewStatus === "pending" || item.status === "assessment_in_progress" || item.status === "awaiting_review")
    && item.status !== "Failed" 
    && item.status !== "error"
    && item.status !== "Completed"
  );
  const historyReviews = queue.filter(item => !pendingReviews.includes(item));
  const displayList = activeTab === 0 ? pendingReviews : historyReviews;

  const handleSelect = (item: any) => {
    const cp = item.reviewCheckpoint;
    let route = "";
    if (cp === "classification_review") route = "classification";
    else if (cp === "part_detection_review") route = "part-detection";
    else if (cp === "defect_detection_review") route = "defect-detection";
    else if (cp === "segmentation_review") route = "segmentation";
    else if (cp === "area_review") route = "area";
    else if (cp === "cost_review") route = "cost";

    if (route) {
      navigate(`/internal/${route}/${item.sessionId}`);
    } else {
      console.warn("Unknown checkpoint:", cp);
    }
  };

  const getConfidenceColor = (score: number) => {
    if (score >= 0.95) return 'success';
    if (score >= 0.80) return 'warning';
    return 'error';
  };

  return (
    <Stack spacing={3} sx={{ height: 'calc(100vh - 100px)' }}>
      {/* Header Area */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', mb: 1, borderBottom: 1, borderColor: '#334155' }}>
        <Box>
          <Typography variant="h4" fontWeight={800} color="#F8FAFC" gutterBottom>
            Assessment Center Queue
          </Typography>
          <Tabs 
            value={activeTab} 
            onChange={(e, v) => setActiveTab(v)}
            sx={{ 
              '& .MuiTab-root': { color: '#94A3B8', fontWeight: 'bold' },
              '& .Mui-selected': { color: '#fff !important' },
              '& .MuiTabs-indicator': { backgroundColor: '#3b82f6' }
            }}
          >
            <Tab label={`Pending Reviews (${pendingReviews.length})`} />
            <Tab label={`Review History (${historyReviews.length})`} />
          </Tabs>
        </Box>
        <Box sx={{ pb: 1 }}>
          {activeTab === 0 && (
            <Chip 
              icon={<ClipboardList size={18} />} 
              label={`${pendingReviews.length} Action Needed`} 
              sx={{ bgcolor: 'rgba(255,255,255,0.1)', color: '#fff', fontWeight: 'bold', px: 1, py: 2, fontSize: '1rem' }} 
            />
          )}
        </Box>
      </Box>

      {/* Queue Table */}
      <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', bgcolor: '#f8fafc', borderRadius: 3, overflow: 'hidden', border: '1px solid #e2e8f0', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}>
        {queueQuery.isLoading && <LinearProgress />}
        
        <TableContainer sx={{ flexGrow: 1, overflowY: 'auto' }}>
          <Table stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell sx={{ bgcolor: '#f1f5f9', color: '#64748b', fontWeight: 'bold', textTransform: 'uppercase', letterSpacing: 1 }}>Session ID</TableCell>
                <TableCell sx={{ bgcolor: '#f1f5f9', color: '#64748b', fontWeight: 'bold', textTransform: 'uppercase', letterSpacing: 1 }}>Vessel Name</TableCell>
                <TableCell sx={{ bgcolor: '#f1f5f9', color: '#64748b', fontWeight: 'bold', textTransform: 'uppercase', letterSpacing: 1 }}>Pending Stage</TableCell>
                <TableCell sx={{ bgcolor: '#f1f5f9', color: '#64748b', fontWeight: 'bold', textTransform: 'uppercase', letterSpacing: 1 }}>AI Confidence</TableCell>
                <TableCell sx={{ bgcolor: '#f1f5f9', color: '#64748b', fontWeight: 'bold', textTransform: 'uppercase', letterSpacing: 1 }} align="right">Action</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {displayList.length === 0 && !queueQuery.isLoading && (
                <TableRow>
                  <TableCell colSpan={5} align="center" sx={{ py: 8 }}>
                    <Typography color="#64748b" variant="h6">
                      {activeTab === 0 ? "No pending reviews in the queue." : "No review history available."}
                    </Typography>
                    <Typography color="#94a3b8">
                      {activeTab === 0 ? "All pipelines are caught up!" : ""}
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
              
              {displayList.map((item) => (
                <TableRow 
                  key={item.sessionId}
                  hover
                  onClick={() => {
                    if (activeTab === 0) handleSelect(item);
                  }}
                  sx={{ 
                    cursor: activeTab === 0 ? 'pointer' : 'default',
                    '&:hover': { bgcolor: '#f1f5f9' },
                    transition: 'background-color 0.2s ease',
                    opacity: activeTab === 1 ? 0.7 : 1
                  }}
                >
                  <TableCell>
                    <Typography variant="body2" sx={{ color: "#64748b", fontFamily: 'monospace' }}>
                      {item.sessionId.substring(0, 12)}...
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography fontWeight="bold" color="#0f172a">
                      {item.vesselName}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip 
                      label={item.reviewCheckpoint ? item.reviewCheckpoint.replace('_review', '').toUpperCase() : "COMPLETED"} 
                      size="small" 
                      sx={{ bgcolor: "#0f172a", color: "#f8fafc", fontWeight: 'bold', letterSpacing: 0.5 }} 
                    />
                  </TableCell>
                  <TableCell>
                    {(item as any).aiConfidence !== undefined && (item as any).aiConfidence !== null ? (
                      <Chip 
                        label={`${((item as any).aiConfidence * 100).toFixed(1)}%`} 
                        color={getConfidenceColor((item as any).aiConfidence)}
                        size="small" 
                        variant="outlined"
                        sx={{ fontWeight: 'bold' }} 
                      />
                    ) : (
                      <Typography variant="body2" color="text.secondary">N/A</Typography>
                    )}
                  </TableCell>
                  <TableCell align="right">
                    {activeTab === 0 ? (
                      <Button 
                        variant="contained" 
                        color="primary" 
                        size="small" 
                        endIcon={<ChevronRight size={16} />}
                        sx={{ fontWeight: 'bold', textTransform: 'none', borderRadius: 2 }}
                      >
                        Review
                      </Button>
                    ) : (
                      <Chip 
                        label={item.status === "Failed" ? "Failed" : item.status === "error" ? "Error" : item.reviewStatus === "rejected" ? "Rejected" : "Completed"} 
                        size="small" 
                        color={item.status === "Failed" || item.status === "error" ? "error" : item.reviewStatus === "rejected" ? "warning" : "success"}
                        variant="outlined"
                      />
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Box>
    </Stack>
  );
}
