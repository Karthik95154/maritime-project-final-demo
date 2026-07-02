import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Box, Typography, TextField } from "@mui/material";
import { 
  HitlLayout,
  HitlHeader,
  HitlMainContainer,
  HitlWorkspace,
  HitlSidebar,
  HitlActionBar,
  useHitlHistory, 
  useHitlAutosave 
} from "../../components/hitl";

function ReportHitlContent({ sessionId }: { sessionId: string }) {
  const navigate = useNavigate();
  
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Use the standard history hook for undo/redo on text
  const { currentState: humanOutput, pushState: setHumanOutput, undo, redo, canUndo, canRedo, resetHistory } = useHitlHistory<any>(null);

  useEffect(() => {
    fetch(`http://127.0.0.1:8000/api/v1/internal/reviews/${sessionId}`)
      .then(async (res) => {
        if (!res.ok) throw new Error(await res.text());
        return res.json();
      })
      .then(json => {
        setData(json);
        const pipelineData = json.pipeline_data || {};
        const existingHuman = pipelineData["report_human_json"];
        const aiOutput = pipelineData["report_ai_json"];
        
        resetHistory(existingHuman || aiOutput || []);
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to load session", err);
        setError("Session not found or error loading data.");
        setLoading(false);
      });
  }, [sessionId, resetHistory]);

  const handleSave = async (dataToSave: any) => {
    await fetch(`http://127.0.0.1:8000/api/v1/internal/reviews/${sessionId}/report`, {
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
      await fetch(`http://127.0.0.1:8000/api/v1/internal/reviews/${sessionId}/report`, {
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

  if (loading) return <Box p={4}><Typography color="text.primary">Loading review data...</Typography></Box>;
  if (error) return <Box p={4}><Typography color="error" fontWeight="bold">{error}</Typography></Box>;

  return (
    <>
      <HitlHeader 
        title="Report Review Assessment" 
        sessionId={sessionId} 
        saveStatus={saveStatus}
        lastSaved={lastSaved}
        onUndo={undo}
        canUndo={canUndo}
        onRedo={redo}
        canRedo={canRedo}
      />
      <HitlMainContainer>
        <HitlWorkspace>
          <Box sx={{ display: 'flex', flex: 1, gap: 2, p: 2, height: '100%', minHeight: 0 }}>
            <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', bgcolor: '#ffffff', borderRadius: 1, border: '1px solid #e2e8f0', overflow: 'hidden', minHeight: 0 }}>
              <Box sx={{ p: 2, borderBottom: '1px solid #e2e8f0', bgcolor: '#f8fafc' }}>
                <Typography variant="subtitle2" fontWeight="bold" color="#334155">Original AI Output</Typography>
              </Box>
              <Box sx={{ p: 2, flex: 1, overflowY: 'auto' }}>
                <pre style={{ margin: 0, fontSize: '0.85rem', color: '#475569', whiteSpace: 'pre-wrap' }}>
                  {JSON.stringify(data?.pipeline_data?.["report_ai_json"], null, 2)}
                </pre>
              </Box>
            </Box>

            <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', bgcolor: '#ffffff', borderRadius: 1, border: '1px solid #e2e8f0', overflow: 'hidden', minHeight: 0 }}>
              <Box sx={{ p: 2, borderBottom: '1px solid #e2e8f0', bgcolor: '#f8fafc' }}>
                <Typography variant="subtitle2" fontWeight="bold" color="#0ea5e9">Editable Human Output</Typography>
              </Box>
              <Box sx={{ p: 2, flex: 1, display: 'flex', flexDirection: 'column' }}>
                <TextField 
                  multiline
                  fullWidth
                  variant="outlined"
                  sx={{ 
                    flex: 1,
                    '& .MuiInputBase-root': { height: '100%', alignItems: 'flex-start', fontFamily: 'monospace', fontSize: '0.85rem', overflow: 'hidden' },
                    '& .MuiInputBase-input': { height: '100% !important', overflowY: 'auto !important' }
                  }}
                  value={typeof humanOutput === 'string' ? humanOutput : JSON.stringify(humanOutput, null, 2)}
                  onChange={(e) => {
                    try {
                      setHumanOutput(JSON.parse(e.target.value));
                    } catch {
                      setHumanOutput(e.target.value);
                    }
                  }}
                />
              </Box>
            </Box>
          </Box>
        </HitlWorkspace>
        
        <HitlSidebar>
          <Box sx={{ p: 2.5, flexGrow: 1, overflowY: 'auto' }}>
            <Typography variant="subtitle2" color="#64748b" sx={{ textTransform: 'uppercase', mb: 2, letterSpacing: 0.5, borderBottom: 1, borderColor: '#e2e8f0', pb: 1 }}>Instructions</Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              Review the final generated JSON report parameters.
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              Make any required corrections directly in the Editable Human Output text box. The JSON must be valid.
            </Typography>
          </Box>

          <HitlActionBar 
            onApprove={() => handleDecision('assess_continue')}
            onReject={() => handleDecision('reject')}
            onSaveDraft={() => forceSave(humanOutput)}
            isSaving={saveStatus === 'saving'}
          />
        </HitlSidebar>
      </HitlMainContainer>
    </>
  );
}

export function ReportHitlPage() {
  const { sessionId } = useParams();
  if (!sessionId) return null;
  return (
    <HitlLayout>
      <ReportHitlContent sessionId={sessionId} />
    </HitlLayout>
  );
}
