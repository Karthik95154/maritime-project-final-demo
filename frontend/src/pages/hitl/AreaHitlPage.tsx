import React, { useEffect, useState, useRef, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Box, Typography, Button, TextField, Stack, Paper, Chip, IconButton, Divider, Tooltip } from "@mui/material";
import { ChevronLeft as ChevronLeftIcon, ChevronRight as ChevronRightIcon, ZoomIn as ZoomInIcon, ZoomOut as ZoomOutIcon, Maximize as FitIcon } from "lucide-react";
import { Stage, Layer, Image as KonvaImage, Line, Group, Circle } from "react-konva";
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
  useHitlHistory, 
  useHitlAutosave,
  useHitlShortcuts,
  useHitlLayout,
  useHitlWorkspace
} from "../../components/hitl";

function AreaHitlContent({ sessionId }: { sessionId: string }) {
  const navigate = useNavigate();
  
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentDefectId, setCurrentDefectId] = useState<string | null>(null);

  // Homography Annotation State
  const [isDrawingHomography, setIsDrawingHomography] = useState(false);
  const [homographyPoints, setHomographyPoints] = useState<number[]>([]);
  const [isRecalculating, setIsRecalculating] = useState(false);

  const { workspaceDimensions } = useHitlLayout();
  const { transform, setTransform, currentFrame: currentDefectIndex, setCurrentFrame: setCurrentDefectIndex } = useHitlWorkspace();

  const stageRef = useRef<any>(null);

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
        const existingHuman = pipelineData["area_human_json"];
        const aiOutput = pipelineData["unique_json"]; // Area estimation works off unique_json
        
        const initialOutput = existingHuman || aiOutput || {};
        resetHistory(initialOutput);
        
        const keys = Object.keys(initialOutput);
        if (keys.length > 0) setCurrentDefectId(keys[0]);
        
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to load session", err);
        setError("Session not found or error loading data.");
        setLoading(false);
      });
  }, [sessionId, resetHistory]);

  const handleSave = async (dataToSave: any) => {
    await fetch(`http://127.0.0.1:8000/api/v1/internal/reviews/${sessionId}/area`, {
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
      await fetch(`http://127.0.0.1:8000/api/v1/internal/reviews/${sessionId}/area`, {
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

  const defectKeys = humanOutput ? Object.keys(humanOutput) : [];
  
  useEffect(() => {
    if (currentDefectIndex >= 0 && currentDefectIndex < defectKeys.length) {
      setCurrentDefectId(defectKeys[currentDefectIndex]);
    }
  }, [currentDefectIndex, defectKeys]);

  const currentIndex = currentDefectId ? defectKeys.indexOf(currentDefectId) : 0;
  
  useEffect(() => {
    if (currentIndex !== currentDefectIndex) {
        setCurrentDefectIndex(currentIndex >= 0 ? currentIndex : 0);
    }
  }, [currentIndex, currentDefectIndex, setCurrentDefectIndex]);

  // Keyboard Shortcuts
  useHitlShortcuts({
    onApprove: () => handleDecision('assess_continue'),
    onReject: () => handleDecision('reject'),
    onSave: () => forceSave(humanOutput),
    onUndo: undo,
    onRedo: redo,
    onNextFrame: () => {
      if (currentIndex < defectKeys.length - 1) {
          setIsDrawingHomography(false);
          setHomographyPoints([]);
          setCurrentDefectId(defectKeys[currentIndex + 1]);
      }
    },
    onPrevFrame: () => {
      if (currentIndex > 0) {
          setIsDrawingHomography(false);
          setHomographyPoints([]);
          setCurrentDefectId(defectKeys[currentIndex - 1]);
      }
    },
    disabled: loading || !!error || isDrawingHomography
  });

  const currentDefect = currentDefectId && humanOutput ? humanOutput[currentDefectId] : null;

  const handleAreaChange = (val: string) => {
    if (!currentDefectId || !currentDefect) return;
    const num = parseFloat(val);
    const newOutput = { ...humanOutput };
    newOutput[currentDefectId] = {
      ...currentDefect,
      defect_area: isNaN(num) ? null : num
    };
    setHumanOutput(newOutput);
  };

  // Image logic for Konva
  let framePath = "";
  const actualPath = currentDefect?.best_frame_path || currentDefect?.frame_path;
  if (actualPath) {
      const parts = actualPath.split("outputs");
      if (parts.length > 1) framePath = `http://127.0.0.1:8000/outputs${parts[1].replace(/\\/g, '/')}`;
  }
  const imageName = actualPath ? actualPath.split(/\\|\//).pop() : "";
  const [image] = useImage(framePath);

  // Polygon Logic
  let polygonPoints: number[] = [];
  const activeDefect = currentDefect?.segmentation ? currentDefect : (currentDefect?.defect_detections?.[0] || null);
  
  if (activeDefect?.segmentation && Array.isArray(activeDefect.segmentation)) {
      if (Array.isArray(activeDefect.segmentation[0])) {
          polygonPoints = activeDefect.segmentation.flat();
      } else {
          polygonPoints = activeDefect.segmentation;
      }
  } else if (activeDefect?.bbox) {
      const [x1, y1, x2, y2] = activeDefect.bbox;
      polygonPoints = [x1, y1, x2, y1, x2, y2, x1, y2];
  }

  const getMinScale = useCallback(() => {
    if (!image || workspaceDimensions.width === 0 || workspaceDimensions.height === 0) return 0.1;
    return Math.min(
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
    const stage = stageRef.current;
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

  // Drawing Handlers
  const handleStageMouseDown = (e: any) => {
    if (e.target.attrs && e.target.attrs.draggable) return; 
    if (!isDrawingHomography || homographyPoints.length >= 8) return; 
    const stage = e.target.getStage();
    const pointer = stage.getPointerPosition();
    if (!pointer) return;
    
    const x = (pointer.x - stage.x()) / stage.scaleX();
    const y = (pointer.y - stage.y()) / stage.scaleY();
    
    setHomographyPoints([...homographyPoints, x, y]);
  };

  const handleRecalculate = async () => {
      if (homographyPoints.length !== 8) {
          alert("Please select exactly 4 points for the reference plane.");
          return;
      }

      const pointsNested = [];
      for(let i=0; i<8; i+=2) {
          pointsNested.push([homographyPoints[i], homographyPoints[i+1]]);
      }

      setIsRecalculating(true);
      try {
          const response = await fetch(`http://127.0.0.1:8000/api/v1/internal/reviews/${sessionId}/area/recalculate`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                  defect_id: currentDefectId,
                  image_name: imageName,
                  homography_points: pointsNested
              })
          });
          const result = await response.json();
          if (result.status === "success") {
              setHumanOutput(result.data);
              setIsDrawingHomography(false);
              setHomographyPoints([]);
          } else {
              alert("Recalculation failed: " + result.detail);
          }
      } catch (err) {
          console.error(err);
          alert("Error during recalculation.");
      } finally {
          setIsRecalculating(false);
      }
  };


  if (loading) return <Box p={4}><Typography color="text.primary">Loading review data...</Typography></Box>;
  if (error) return <Box p={4}><Typography color="error" fontWeight="bold">{error}</Typography></Box>;

  return (
    <>
      <HitlHeader 
        title="Area Estimation Assessment" 
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
          <HitlToolbar 
            currentFrameIndex={currentIndex}
            totalFrames={defectKeys.length}
            onPrev={() => {
                if (currentIndex > 0) {
                    setIsDrawingHomography(false); setHomographyPoints([]); setCurrentDefectId(defectKeys[currentIndex - 1]);
                }
            }}
            onNext={() => {
                if (currentIndex < defectKeys.length - 1) {
                    setIsDrawingHomography(false); setHomographyPoints([]); setCurrentDefectId(defectKeys[currentIndex + 1]);
                }
            }}
            onZoomIn={() => setTransform(prev => ({ ...prev, scale: prev.scale * 1.2 }))}
            onZoomOut={() => setTransform(prev => ({ ...prev, scale: Math.max(getMinScale(), prev.scale / 1.2) }))}
            onFit={fitToScreen}
          >
            <Typography variant="caption" sx={{ ml: 'auto', alignSelf: 'center', color: '#64748b' }}>Drag to pan.</Typography>
          </HitlToolbar>

          <HitlCanvas style={{ cursor: isDrawingHomography ? 'crosshair' : 'grab' }}>
            {image ? (
                <Stage 
                  width={workspaceDimensions.width} 
                  height={workspaceDimensions.height}
                  scaleX={transform.scale} scaleY={transform.scale}
                  x={transform.x} y={transform.y}
                  draggable={!isDrawingHomography}
                  onDragEnd={(e) => {
                    const stage = e.target.getStage();
                    if (stage && e.target === stage) {
                      setTransform(prev => ({ ...prev, x: stage.x(), y: stage.y() }));
                    }
                  }}
                  onWheel={handleWheel}
                  onMouseDown={handleStageMouseDown}
                  ref={stageRef}
                >
                    <Layer>
                            <KonvaImage image={image} name="backgroundImage" />
                            
                            {/* Defect Polygon */}
                            {polygonPoints.length > 0 && (
                                <Line
                                    points={polygonPoints}
                                    fill="rgba(14, 165, 233, 0.4)"
                                    stroke="#0ea5e9"
                                    strokeWidth={3 / transform.scale}
                                    closed={true}
                                />
                            )}

                            {/* Homography Polygon */}
                            {(isDrawingHomography || homographyPoints.length > 0) && (
                                <Group>
                                    <Line
                                        points={homographyPoints}
                                        fill="rgba(217, 70, 239, 0.3)"
                                        stroke="#d946ef"
                                        strokeWidth={3 / transform.scale}
                                        closed={homographyPoints.length === 8}
                                    />
                                    {homographyPoints.map((val, i) => {
                                        if (i % 2 === 0) {
                                            return (
                                                <Circle
                                                    key={i}
                                                    x={homographyPoints[i]}
                                                    y={homographyPoints[i + 1]}
                                                    radius={5 / transform.scale}
                                                    fill="#ffffff"
                                                    stroke="#d946ef"
                                                    strokeWidth={2 / transform.scale}
                                                />
                                            );
                                        }
                                        return null;
                                    })}
                                </Group>
                            )}
                    </Layer>
                </Stage>
            ) : (
              <Box sx={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center' }}>
                <Typography color="#64748b">No image available</Typography>
              </Box>
            )}
          </HitlCanvas>

          <HitlFilmstrip>
            {defectKeys.map((key, i) => {
              const defect = humanOutput[key];
              let p = "";
              const actualP = defect?.best_frame_path || defect?.frame_path;
              if (actualP) {
                  const parts = actualP.split("outputs");
                  if (parts.length > 1) p = `http://127.0.0.1:8000/outputs${parts[1].replace(/\\/g, '/')}`;
              }
              const isSelected = key === currentDefectId;
              
              return (
                <Box 
                  key={key} 
                  onClick={() => {
                      if (!isDrawingHomography) setCurrentDefectId(key);
                  }}
                  sx={{ 
                    height: '100%', minWidth: 140, position: 'relative', cursor: isDrawingHomography ? 'not-allowed' : 'pointer', borderRadius: 1, overflow: 'hidden', 
                    border: isSelected ? '3px solid #0ea5e9' : '1px solid #cbd5e1', opacity: isSelected ? 1 : 0.6,
                    '&:hover': { opacity: 1 },
                    flexShrink: 0
                  }}
                >
                  <img src={p} alt={`Defect ${i}`} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                  <Box sx={{ position: 'absolute', bottom: 0, left: 0, right: 0, bgcolor: 'rgba(0,0,0,0.7)', p: 0.5, display: 'flex', justifyContent: 'center' }}>
                    <Typography variant="caption" sx={{ color: '#fff', fontWeight: 'bold' }}>
                      {defect?.defect_area != null ? `${defect.defect_area.toFixed(4)} sq.m` : 'N/A'}
                    </Typography>
                  </Box>
                </Box>
              );
            })}
          </HitlFilmstrip>
        </HitlWorkspace>
        
        <HitlSidebar>
          <Box sx={{ p: 2.5, flexGrow: 1, overflowY: 'auto' }}>
            {currentDefect ? (
                <>
                <Box sx={{ mb: 4 }}>
                  <Typography variant="subtitle2" color="#64748b" sx={{ textTransform: 'uppercase', mb: 2, letterSpacing: 0.5, borderBottom: 1, borderColor: '#e2e8f0', pb: 1 }}>Area Estimation</Typography>
                  <TextField 
                    fullWidth 
                    size="small"
                    label="Defect Area (sq.m)" 
                    type="number"
                    variant="outlined" 
                    value={currentDefect.defect_area ?? ''} 
                    onChange={(e) => handleAreaChange(e.target.value)}
                    disabled={isDrawingHomography}
                    InputLabelProps={{ shrink: true }}
                    sx={{ mb: 2 }}
                  />
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography variant="body2" color="text.secondary">Status:</Typography>
                    <Chip 
                        size="small" 
                        label={currentDefect.area_status || "Unknown"} 
                        color={currentDefect.area_status === "area_estimated_with_manual_homography" ? "success" : currentDefect.area_status === "failed" || currentDefect.area_status === "apriltag_not_detected" ? "error" : "primary"} 
                        variant="outlined" 
                    />
                  </Box>
                </Box>

                <Box sx={{ display: 'flex', flexDirection: 'column', mb: 4 }}>
                  <Typography variant="subtitle2" color="#64748b" sx={{ textTransform: 'uppercase', mb: 2, letterSpacing: 0.5, borderBottom: 1, borderColor: '#e2e8f0', pb: 1 }}>Manual Homography Reference</Typography>
                  
                  {isDrawingHomography ? (
                      <Box sx={{ bgcolor: '#fdf4ff', p: 2, borderRadius: 1, border: '1px solid #d946ef', mb: 2 }}>
                        <Typography variant="body2" color="#a21caf" fontWeight="bold" paragraph>
                          Homography Plane Mode Active
                        </Typography>
                        <Typography variant="body2" color="#a21caf" paragraph>
                          Click 4 points on the image to define the reference plane. ({homographyPoints.length / 2}/4 selected)
                        </Typography>
                        <Stack spacing={1} direction="row">
                            <Button 
                                variant="contained" 
                                color="secondary" 
                                size="small" 
                                fullWidth 
                                onClick={handleRecalculate}
                                disabled={homographyPoints.length !== 8 || isRecalculating}
                            >
                                {isRecalculating ? "Recalculating..." : "Recalculate Area"}
                            </Button>
                            <Button 
                                variant="outlined" 
                                color="error" 
                                size="small" 
                                fullWidth 
                                onClick={() => { setIsDrawingHomography(false); setHomographyPoints([]); }}
                                disabled={isRecalculating}
                            >
                                Cancel
                            </Button>
                        </Stack>
                      </Box>
                  ) : (
                      <>
                        <Button 
                            variant="outlined" 
                            color="secondary" 
                            sx={{ mb: 2, borderStyle: 'dashed' }}
                            onClick={() => { setIsDrawingHomography(true); setHomographyPoints([]); }}
                        >
                            Draw Reference Plane
                        </Button>
                        <Box sx={{ bgcolor: '#f8fafc', p: 2, borderRadius: 1, border: '1px solid #e2e8f0' }}>
                            <Typography variant="body2" color="text.secondary" paragraph>
                            If Area Estimation failed (e.g. AprilTag missing), you can manually define a reference plane.
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                            Click <b>Draw Reference Plane</b> and select exactly 4 corner points on the image.
                            </Typography>
                        </Box>
                      </>
                  )}
                </Box>
                </>
            ) : (
                <Typography color="text.secondary">No defect selected</Typography>
            )}
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

export function AreaHitlPage() {
  const { sessionId } = useParams();
  if (!sessionId) return null;
  return (
    <HitlLayout>
      <AreaHitlContent sessionId={sessionId} />
    </HitlLayout>
  );
}
