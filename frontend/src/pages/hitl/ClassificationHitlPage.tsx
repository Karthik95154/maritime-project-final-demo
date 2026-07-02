import React, { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Box, Typography, Button, FormControl, InputLabel, Select, MenuItem, TextField, Chip, IconButton, Divider, Tooltip, Autocomplete, Stack } from "@mui/material";
import { ChevronLeft as ChevronLeftIcon, ChevronRight as ChevronRightIcon, ZoomIn as ZoomInIcon, ZoomOut as ZoomOutIcon, Maximize as FitIcon, Copy as CopyAllIcon } from "lucide-react";
import { Stage, Layer, Image as KonvaImage } from "react-konva";
import useImage from "use-image";
import { 
  HitlLayout,
  HitlHeader,
  HitlMainContainer,
  HitlWorkspace,
  HitlSidebar,
  HitlActionBar,
  HitlCanvas,
  HitlToolbar,
  HitlFilmstrip,
  useHitlShortcuts,
  useHitlLayout,
  useHitlWorkspace,
  useHitlHistory, 
  useHitlAutosave 
} from "../../components/hitl";

function ClassificationHitlContent({ sessionId }: { sessionId: string }) {
  const navigate = useNavigate();
  
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const { workspaceDimensions } = useHitlLayout();
  const { transform, setTransform, currentFrame, setCurrentFrame } = useHitlWorkspace();

  // History & State
  const { currentState: humanOutput, pushState: setHumanOutput, undo, redo, canUndo, canRedo, resetHistory } = useHitlHistory<any[]>([]);

  useEffect(() => {
    fetch(`http://127.0.0.1:8000/api/v1/internal/reviews/${sessionId}`)
      .then(async (res) => {
        if (!res.ok) throw new Error(await res.text());
        return res.json();
      })
      .then(json => {
        setData(json);
        const pipelineData = json.pipeline_data || {};
        const existingHuman = pipelineData["classification_human_json"];
        const aiOutput = pipelineData["classification_ai_json"];
        
        let initialOutput = existingHuman || aiOutput || [];
        if (!Array.isArray(initialOutput) && typeof initialOutput === 'object') {
            initialOutput = [initialOutput];
        }
        resetHistory(initialOutput);
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to load session", err);
        setError("Session not found or error loading data.");
        setLoading(false);
      });
  }, [sessionId, resetHistory]);

  const handleSave = async (dataToSave: any[]) => {
    await fetch(`http://127.0.0.1:8000/api/v1/internal/reviews/${sessionId}/classification`, {
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
    enabled: !loading && !error
  });

  const handleDecision = async (decision: string) => {
    try {
      await forceSave(humanOutput); // ensure latest is saved
      await fetch(`http://127.0.0.1:8000/api/v1/internal/reviews/${sessionId}/classification`, {
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

  // Data processing
  const frameJson = data?.pipeline_data?.["frame_json"] || data?.pipeline_data?.["frame_extraction_ai_json"] || [];
  const aiOutputRaw = data?.pipeline_data?.["classification_ai_json"] || [];
  const aiArray = Array.isArray(aiOutputRaw) ? aiOutputRaw : [aiOutputRaw];
  
  const fallbackFrames = (frameJson.length > 0) ? frameJson : aiArray;
  const totalFrames = Array.isArray(fallbackFrames) ? fallbackFrames.length : 0;
  
  const getFramePath = (index: number) => {
    if (Array.isArray(fallbackFrames) && fallbackFrames.length > index) {
      const rawPath = fallbackFrames[index].frame_path || fallbackFrames[index];
      if (typeof rawPath === 'string') {
          if (rawPath.startsWith("http://") || rawPath.startsWith("https://")) {
              return rawPath;
          }
          if (rawPath.startsWith("http://") || rawPath.startsWith("https://")) return rawPath; const parts = rawPath.split("outputs");
          if (parts.length > 1) return `http://127.0.0.1:8000/outputs${parts[1].replace(/\\/g, '/')}`;
      }
    }
    return "";
  };

  const currentFramePath = getFramePath(currentFrame);
  const [image] = useImage(currentFramePath);

  const getMinScale = useCallback(() => {
    if (!image || workspaceDimensions.width === 0 || workspaceDimensions.height === 0) return 0.1;
    return Math.max(
      workspaceDimensions.width / image.width,
      workspaceDimensions.height / image.height
    ) * 0.95;
  }, [image, workspaceDimensions]);

  const fitToScreen = useCallback(() => {
    if (!image || workspaceDimensions.width === 0 || workspaceDimensions.height === 0) return;
    const scale = getMinScale();
    setTransform({
      scale,
      x: (workspaceDimensions.width - image.width * scale) / 2,
      y: (workspaceDimensions.height - image.height * scale) / 2
    });
  }, [image, workspaceDimensions, getMinScale, setTransform]);

  useEffect(() => {
    if (image && workspaceDimensions.width > 0 && workspaceDimensions.height > 0) {
      const timer = setTimeout(() => fitToScreen(), 100);
      return () => clearTimeout(timer);
    }
  }, [image, workspaceDimensions.width, workspaceDimensions.height, fitToScreen]);

  const handleWheel = (e: any) => {
    e.evt.preventDefault();
    const scaleBy = 1.1;
    const stage = e.target.getStage();
    if(!stage) return;
    const oldScale = stage.scaleX();
    const pointer = stage.getPointerPosition();

    const mousePointTo = {
      x: (pointer.x - stage.x()) / oldScale,
      y: (pointer.y - stage.y()) / oldScale,
    };

    const minScale = getMinScale();
    let newScale = e.evt.deltaY < 0 ? oldScale * scaleBy : oldScale / scaleBy;
    if (newScale < minScale) newScale = minScale;
    
    setTransform({
      scale: newScale,
      x: pointer.x - mousePointTo.x * newScale,
      y: pointer.y - mousePointTo.y * newScale
    });
  };

  useHitlShortcuts({
    onApprove: () => handleDecision('assess_continue'),
    onReject: () => handleDecision('reject'),
    onSave: () => forceSave(humanOutput),
    onUndo: canUndo ? undo : undefined,
    onRedo: canRedo ? redo : undefined,
    onNextFrame: () => setCurrentFrame((prev: number) => Math.min(totalFrames - 1, prev + 1)),
    onPrevFrame: () => setCurrentFrame((prev: number) => Math.max(0, prev - 1)),
    disabled: loading || !!error
  });

  if (loading) return <Box p={4}><Typography color="text.primary">Loading review data...</Typography></Box>;
  if (error) return <Box p={4}><Typography color="error" fontWeight="bold">{error}</Typography></Box>;

  const getClassName = (dataSource: any, index: number) => {
    if (!dataSource) return "Unknown";
    let frame = Array.isArray(dataSource) ? dataSource[index] : dataSource;
    if (!frame) return "Unknown";
    if (typeof frame.classification === 'string') return frame.classification;
    if (frame.classification?.class_name) return frame.classification.class_name;
    if (frame.class_name) return frame.class_name;
    return "Unknown";
  };

  const getConfidence = (dataSource: any, index: number) => {
    let frame = Array.isArray(dataSource) ? dataSource[index] : dataSource;
    if (!frame) return 0;
    if (frame.classification?.confidence !== undefined) return frame.classification.confidence;
    if (frame.confidence !== undefined) return frame.confidence;
    return 0;
  };

  const currentClass = getClassName(humanOutput, currentFrame);
  const aiClass = getClassName(aiArray, currentFrame);
  const aiConfidence = getConfidence(aiArray, currentFrame);
  const currentNotes = (Array.isArray(humanOutput) ? humanOutput[currentFrame]?.notes : "") || "";

  const classes = ["Hull", "Keel", "Rudder", "Propeller", "Anchor"];

  const updateClass = (newClass: string) => {
    const newOutput = Array.isArray(humanOutput) ? [...humanOutput] : [];
    if (newOutput[currentFrame]) {
      newOutput[currentFrame] = { ...newOutput[currentFrame], classification: newClass };
    } else {
      newOutput[currentFrame] = { classification: newClass };
    }
    setHumanOutput(newOutput);
  };

  const applyClassToAll = () => {
    if (!Array.isArray(humanOutput)) return;
    const newOutput = humanOutput.map((frame: any) => ({
      ...frame,
      classification: currentClass
    }));
    setHumanOutput(newOutput);
  };

  const updateNotes = (newNotes: string) => {
    const newOutput = Array.isArray(humanOutput) ? [...humanOutput] : [];
    if (newOutput[currentFrame]) {
      newOutput[currentFrame] = { ...newOutput[currentFrame], notes: newNotes };
    } else {
      newOutput[currentFrame] = { notes: newNotes };
    }
    setHumanOutput(newOutput);
  };

  return (
    <>
      <HitlHeader 
        title="Classification Assessment" 
        sessionId={sessionId} 
        saveStatus={saveStatus}
        lastSaved={lastSaved}
        confidenceScore={aiConfidence}
        onUndo={undo}
        canUndo={canUndo}
        onRedo={redo}
        canRedo={canRedo}
      />
      <HitlMainContainer>
        <HitlWorkspace>
          <HitlToolbar 
            currentFrameIndex={currentFrame}
            totalFrames={totalFrames}
            onPrev={() => setCurrentFrame((prev: number) => Math.max(0, prev - 1))}
            onNext={() => setCurrentFrame((prev: number) => Math.min(totalFrames - 1, prev + 1))}
            onZoomIn={() => setTransform((prev: any) => ({ ...prev, scale: prev.scale * 1.2 }))}
            onZoomOut={() => setTransform((prev: any) => ({ ...prev, scale: Math.max(getMinScale(), prev.scale / 1.2) }))}
            onFit={fitToScreen}
          />
          <HitlCanvas>
            {image ? (
                <Stage 
                  width={workspaceDimensions.width} 
                  height={workspaceDimensions.height}
                  scaleX={transform.scale} scaleY={transform.scale}
                  x={transform.x} y={transform.y}
                  draggable
                  onDragEnd={(e: any) => {
                    const stage = e.target.getStage();
                    if (stage) setTransform((prev: any) => ({ ...prev, x: stage.x(), y: stage.y() }));
                  }}
                  onWheel={(e: any) => {
                    e.evt.preventDefault();
                    const scaleBy = 1.1;
                    const stage = e.target.getStage();
                    const oldScale = stage.scaleX();
                    const pointer = stage.getPointerPosition();
                    const mousePointTo = {
                      x: (pointer.x - stage.x()) / oldScale,
                      y: (pointer.y - stage.y()) / oldScale,
                    };
                    const minScale = getMinScale();
                    let newScale = e.evt.deltaY < 0 ? oldScale * scaleBy : oldScale / scaleBy;
                    if (newScale < minScale) newScale = minScale;
                    setTransform((prev: any) => ({
                      scale: newScale,
                      x: pointer.x - mousePointTo.x * newScale,
                      y: pointer.y - mousePointTo.y * newScale
                    }));
                  }}
                >
                  <Layer>
                    <KonvaImage image={image} name="backgroundImage" />
                  </Layer>
                </Stage>
            ) : (
                <Box sx={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center' }}>
                    <Typography color="#64748b">No image available</Typography>
                </Box>
            )}
          </HitlCanvas>
          <HitlFilmstrip>
            {Array.from({ length: totalFrames }).map((_, i) => {
              const p = getFramePath(i);
              const conf = getConfidence(aiArray, i);
              const isSelected = i === currentFrame;
              return (
                <Box 
                  key={i} 
                  onClick={() => setCurrentFrame(i)}
                  sx={{ 
                    height: '100%', minWidth: 120, position: 'relative', cursor: 'pointer', borderRadius: 1, overflow: 'hidden', 
                    border: isSelected ? '3px solid #0ea5e9' : '1px solid #cbd5e1', opacity: isSelected ? 1 : 0.6,
                    '&:hover': { opacity: 1 },
                    flexShrink: 0
                  }}
                >
                  <img src={p} alt={`Thumb ${i}`} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                  {/* Confidence Overlay */}
                  <Box sx={{ position: 'absolute', bottom: 0, left: 0, right: 0, bgcolor: 'rgba(0,0,0,0.7)', p: 0.25, display: 'flex', justifyContent: 'center' }}>
                    <Typography variant="caption" sx={{ color: conf >= 0.9 ? '#4ade80' : conf >= 0.7 ? '#fbbf24' : '#f87171', fontWeight: 'bold', fontSize: '0.65rem' }}>
                      {(conf * 100).toFixed(1)}%
                    </Typography>
                  </Box>
                  <Box sx={{ position: 'absolute', top: 0, left: 0, bgcolor: 'rgba(0,0,0,0.6)', px: 0.5 }}>
                     <Typography variant="caption" sx={{ color: '#fff', fontSize: '0.65rem' }}>{i + 1}</Typography>
                  </Box>
                </Box>
              );
            })}
          </HitlFilmstrip>
        </HitlWorkspace>

        <HitlSidebar>
          <Box sx={{ p: 2.5, flexGrow: 1, overflowY: 'auto' }}>
            {/* AI Prediction */}
            <Box sx={{ mb: 4 }}>
              <Typography variant="subtitle2" color="#64748b" sx={{ textTransform: 'uppercase', mb: 2, letterSpacing: 0.5, borderBottom: 1, borderColor: '#e2e8f0', pb: 1 }}>AI Prediction</Typography>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1.5 }}>
                  <Typography variant="body2" color="#64748b">Ship Part</Typography>
                  <Typography variant="body2" fontWeight="bold" color="#0f172a" sx={{ textTransform: 'capitalize' }}>{(typeof aiClass === 'string' ? aiClass : 'Unknown').replace(/_/g, ' ')}</Typography>
              </Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1.5 }}>
                  <Typography variant="body2" color="#64748b">Confidence</Typography>
                  <Typography variant="body2" fontWeight="bold" color="#0f172a">{(aiConfidence * 100).toFixed(1)}%</Typography>
              </Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography variant="body2" color="#64748b">Status</Typography>
                  <Chip label={aiConfidence > 0.9 ? "High Confidence" : aiConfidence > 0.7 ? "Medium Confidence" : "Low Confidence"} color={aiConfidence > 0.9 ? "success" : aiConfidence > 0.7 ? "warning" : "error"} size="small" sx={{ height: 20, fontSize: '0.7rem' }} />
              </Box>
            </Box>

            {/* Human Classification */}
            <Box sx={{ mb: 4 }}>
              <Typography variant="subtitle2" color="#64748b" sx={{ textTransform: 'uppercase', mb: 2, letterSpacing: 0.5, borderBottom: 1, borderColor: '#e2e8f0', pb: 1 }}>Human Classification</Typography>
              <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
                <Autocomplete
                  freeSolo
                  size="small"
                  options={classes}
                  value={currentClass === "Unknown" ? "" : currentClass}
                  onChange={(e, newValue) => updateClass(newValue || "")}
                  onInputChange={(e, newInputValue) => updateClass(newInputValue || "")}
                  renderInput={(params) => <TextField {...params} label="Ship Part" variant="outlined" />}
                  sx={{ flexGrow: 1 }}
                />
                <Tooltip title="Apply this classification to all images">
                  <IconButton onClick={applyClassToAll} color="primary" sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
                    <CopyAllIcon size={20} />
                  </IconButton>
                </Tooltip>
              </Stack>
              <TextField disabled fullWidth size="small" value="100% (Manual Override)" label="Confidence" variant="filled" sx={{ bgcolor: 'rgba(0,0,0,0.02)', '.MuiFilledInput-root': { py: 0 } }} />
            </Box>

            {/* Notes */}
            <Box>
              <Typography variant="subtitle2" color="#64748b" sx={{ textTransform: 'uppercase', mb: 2, letterSpacing: 0.5, borderBottom: 1, borderColor: '#e2e8f0', pb: 1 }}>Reviewer Notes</Typography>
              <TextField multiline rows={4} fullWidth variant="outlined" size="small" value={currentNotes} onChange={(e) => updateNotes(e.target.value)} placeholder="Add any specific observations..." />
            </Box>
          </Box>

          {/* Bottom Action Bar */}
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

export function ClassificationHitlPage() {
  const { sessionId } = useParams();
  if (!sessionId) return null;
  return (
    <HitlLayout>
      <ClassificationHitlContent sessionId={sessionId} />
    </HitlLayout>
  );
}
