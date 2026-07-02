import React, { useEffect, useState, useRef, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Box, Typography, Button, FormControl, InputLabel, Select, MenuItem, TextField, Chip, Stack, IconButton, Divider, Tooltip, Autocomplete } from "@mui/material";
import { ChevronLeft as ChevronLeftIcon, ChevronRight as ChevronRightIcon, ZoomIn as ZoomInIcon, ZoomOut as ZoomOutIcon, Maximize as FitIcon } from "lucide-react";
import { Stage, Layer, Image as KonvaImage, Line, Group, Text, Circle } from "react-konva";
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

function SegmentationHitlContent({ sessionId }: { sessionId: string }) {
  const navigate = useNavigate();
  
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentDefectId, setCurrentDefectId] = useState<string | null>(null);

  // Drawing state
  const [isDrawing, setIsDrawing] = useState(false);
  const [draftPoints, setDraftPoints] = useState<number[]>([]);

  const { workspaceDimensions } = useHitlLayout();
  const { transform, setTransform, currentFrame: currentDefectIndex, setCurrentFrame: setCurrentDefectIndex } = useHitlWorkspace();

  const stageRef = useRef<any>(null);

  // History & State (Assume humanOutput is an Object or Array of unique defects)
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
        const existingHuman = pipelineData["segmentation_human_json"];
        const aiOutput = pipelineData["segmentation_ai_json"];
        
        const initialOutput = existingHuman || aiOutput || {};
        resetHistory(initialOutput);
        
        // Pick first defect ID
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
    await fetch(`http://127.0.0.1:8000/api/v1/internal/reviews/${sessionId}/segmentation`, {
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
      await forceSave(humanOutput); // ensure latest is saved
      await fetch(`http://127.0.0.1:8000/api/v1/internal/reviews/${sessionId}/segmentation`, {
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

  const defectKeys = React.useMemo(() => humanOutput ? Object.keys(humanOutput) : [], [humanOutput]);
  
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
          setIsDrawing(false);
          setDraftPoints([]);
          setCurrentDefectId(defectKeys[currentIndex + 1]);
      }
    },
    onPrevFrame: () => {
      if (currentIndex > 0) {
          setIsDrawing(false);
          setDraftPoints([]);
          setCurrentDefectId(defectKeys[currentIndex - 1]);
      }
    },
    disabled: loading || !!error || isDrawing
  });

  const currentDefect = currentDefectId && humanOutput ? humanOutput[currentDefectId] : null;

  // Get image path
  let framePath = "";
  const actualPath = currentDefect?.best_frame_path || currentDefect?.frame_path;
  if (actualPath) {
    if (actualPath.startsWith("http://") || actualPath.startsWith("https://")) {
      framePath = actualPath;
    } else {
      const parts = actualPath.split("outputs");
      if (parts.length > 1) framePath = `http://127.0.0.1:8000/outputs${parts[1].replace(/\\/g, '/')}`;
    }
  }
  const [image] = useImage(framePath, "anonymous");

  // Parse Polygon
  let polygonPoints: number[] = [];
  const activeDefect = currentDefect?.segmentation ? currentDefect : (currentDefect?.defect_detections?.[0] || null);
  
  if (activeDefect?.segmentation && Array.isArray(activeDefect.segmentation)) {
      // Flatten [[x,y], [x,y]] into [x,y,x,y]
      if (Array.isArray(activeDefect.segmentation[0])) {
          polygonPoints = activeDefect.segmentation.flat();
      } else {
          polygonPoints = activeDefect.segmentation;
      }
  } else if (activeDefect?.bbox) {
      // Fallback to bbox if no segmentation [x1, y1, x2, y2]
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
    setTransform((prev) => {
      const newX = (workspaceDimensions.width - image.width * scale) / 2;
      const newY = (workspaceDimensions.height - image.height * scale) / 2;
      if (prev.scale === scale && prev.x === newX && prev.y === newY) return prev;
      return {
        scale,
        x: newX,
        y: newY
      };
    });
  }, [image, workspaceDimensions, getMinScale, setTransform]);

  useEffect(() => {
    if (image && workspaceDimensions.width > 0 && workspaceDimensions.height > 0) {
      fitToScreen();
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

  const updateDefectClass = (newClass: string) => {
    if (!currentDefectId || !currentDefect) return;
    const newOutput = { ...humanOutput };
    
    if (currentDefect.defect_detections && currentDefect.defect_detections.length > 0) {
        const dets = [...currentDefect.defect_detections];
        dets[0] = { ...dets[0], class_name: newClass };
        newOutput[currentDefectId] = { ...currentDefect, defect_detections: dets };
    } else {
        newOutput[currentDefectId] = { ...currentDefect, class_name: newClass };
    }
    setHumanOutput(newOutput);
  };

  const handlePointDrag = (index: number, newX: number, newY: number) => {
    if (!currentDefectId || !currentDefect || isDrawing) return;
    const newOutput = { ...humanOutput };
    const defect = { ...currentDefect };
    
    // Copy the current flat array of points
    const newPoints = [...polygonPoints];
    newPoints[index] = newX;
    newPoints[index + 1] = newY;
    
    const activeD = defect.segmentation ? defect : (defect.defect_detections?.[0] || null);
    if (!activeD) return;
    
    // Convert back to original format if it was nested
    if (activeD.segmentation && Array.isArray(activeD.segmentation) && Array.isArray(activeD.segmentation[0])) {
        const nested = [];
        for (let i = 0; i < newPoints.length; i += 2) {
            nested.push([newPoints[i], newPoints[i+1]]);
        }
        activeD.segmentation = nested;
    } else {
        activeD.segmentation = newPoints;
    }
    
    if (defect.defect_detections) {
        defect.defect_detections[0] = activeD;
    }
    
    newOutput[currentDefectId] = defect;
    setHumanOutput(newOutput);
  };

  const handleStageMouseDown = (e: any) => {
    if (e.target.attrs && e.target.attrs.draggable) return; 
    if (!isDrawing) return;
    const stage = e.target.getStage();
    const pointer = stage.getPointerPosition();
    if (!pointer) return;
    
    const x = (pointer.x - stage.x()) / stage.scaleX();
    const y = (pointer.y - stage.y()) / stage.scaleY();
    
    setDraftPoints([...draftPoints, x, y]);
  };

  const handleSaveMask = () => {
    if (draftPoints.length < 6) {
        alert("Please draw at least a triangle (3 points).");
        return;
    }
    
    if (!currentDefectId || !currentDefect) return;
    
    const newOutput = { ...humanOutput };
    const defect = { ...currentDefect };
    
    const activeD = defect.segmentation ? defect : (defect.defect_detections?.[0] || null);
    if (!activeD) {
        // Fallback create activeD if not exists
        defect.defect_detections = defect.defect_detections || [{}];
    }
    const targetD = defect.segmentation ? defect : defect.defect_detections[0];
    
    const nested = [];
    for (let i = 0; i < draftPoints.length; i += 2) {
        nested.push([draftPoints[i], draftPoints[i+1]]);
    }
    targetD.segmentation = nested;
    
    newOutput[currentDefectId] = defect;
    setHumanOutput(newOutput);
    setIsDrawing(false);
    setDraftPoints([]);
  };

  if (loading) return <Box p={4}><Typography color="text.primary">Loading review data...</Typography></Box>;
  if (error) return <Box p={4}><Typography color="error" fontWeight="bold">{error}</Typography></Box>;

  return (
    <>
      <HitlHeader 
        title="Segmentation Assessment" 
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
                    setIsDrawing(false); setDraftPoints([]); setCurrentDefectId(defectKeys[currentIndex - 1]);
                }
            }}
            onNext={() => {
                if (currentIndex < defectKeys.length - 1) {
                    setIsDrawing(false); setDraftPoints([]); setCurrentDefectId(defectKeys[currentIndex + 1]);
                }
            }}
            onZoomIn={() => setTransform(prev => ({ ...prev, scale: prev.scale * 1.2 }))}
            onZoomOut={() => setTransform(prev => ({ ...prev, scale: Math.max(getMinScale(), prev.scale / 1.2) }))}
            onFit={fitToScreen}
          >
            <Typography variant="caption" sx={{ ml: 'auto', alignSelf: 'center', color: '#64748b' }}>Drag to pan. Hover mask borders to drag points.</Typography>
          </HitlToolbar>

          <HitlCanvas style={{ cursor: isDrawing ? 'crosshair' : 'grab' }}>
            {image ? (
                <Stage 
                  width={workspaceDimensions.width} 
                  height={workspaceDimensions.height}
                  scaleX={transform.scale} scaleY={transform.scale}
                  x={transform.x} y={transform.y}
                  draggable={!isDrawing}
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
                            
                            {/* Existing Polygon (hide if drawing) */}
                            {!isDrawing && polygonPoints.length > 0 && (
                                <Group>
                                    <Line
                                        points={polygonPoints}
                                        fill="rgba(14, 165, 233, 0.4)"
                                        stroke="#0ea5e9"
                                        strokeWidth={3 / transform.scale}
                                        closed={true}
                                        tension={0.1}
                                    />
                                    {/* Render interactive vertices */}
                                    {polygonPoints.map((val, i) => {
                                        if (i % 2 === 0) {
                                            const x = polygonPoints[i];
                                            const y = polygonPoints[i + 1];
                                            return (
                                                <Circle
                                                    key={i}
                                                    x={x}
                                                    y={y}
                                                    radius={4 / transform.scale}
                                                    fill="#ffffff"
                                                    stroke="#0ea5e9"
                                                    strokeWidth={2 / transform.scale}
                                                    draggable
                                                    onDragMove={(e) => {
                                                        handlePointDrag(i, e.target.x(), e.target.y());
                                                    }}
                                                    onMouseEnter={(e) => {
                                                        const container = e.target.getStage()?.container();
                                                        if (container) container.style.cursor = 'grab';
                                                    }}
                                                    onMouseLeave={(e) => {
                                                        const container = e.target.getStage()?.container();
                                                        if (container) container.style.cursor = isDrawing ? 'crosshair' : 'default';
                                                    }}
                                                />
                                            );
                                        }
                                        return null;
                                    })}
                                </Group>
                            )}

                            {/* Draft Polygon (when drawing) */}
                            {isDrawing && draftPoints.length > 0 && (
                                <Group>
                                    <Line
                                        points={draftPoints}
                                        fill="rgba(16, 185, 129, 0.4)"
                                        stroke="#10b981"
                                        strokeWidth={3 / transform.scale}
                                        closed={false}
                                        tension={0}
                                    />
                                    {draftPoints.map((val, i) => {
                                        if (i % 2 === 0) {
                                            return (
                                                <Circle
                                                    key={i}
                                                    x={draftPoints[i]}
                                                    y={draftPoints[i + 1]}
                                                    radius={4 / transform.scale}
                                                    fill="#ffffff"
                                                    stroke="#10b981"
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

          {/* Filmstrip Gallery (Unique Defects) */}
          <HitlFilmstrip>
            {defectKeys.map((key, i) => {
              const defect = humanOutput[key];
              let p = "";
              const actualP = defect?.best_frame_path || defect?.frame_path;
              if (actualP) {
                if (actualP.startsWith("http://") || actualP.startsWith("https://")) {
                  p = actualP;
                } else {
                  const parts = actualP.split("outputs");
                  if (parts.length > 1) p = `http://127.0.0.1:8000/outputs${parts[1].replace(/\\/g, '/')}`;
                }
              }
              const isSelected = key === currentDefectId;
              
              return (
                <Box 
                  key={key} 
                  onClick={() => {
                      if (!isDrawing) setCurrentDefectId(key);
                  }}
                  sx={{ 
                    height: '100%', minWidth: 140, position: 'relative', cursor: isDrawing ? 'not-allowed' : 'pointer', borderRadius: 1, overflow: 'hidden', 
                    border: isSelected ? '3px solid #0ea5e9' : '1px solid #cbd5e1', opacity: isSelected ? 1 : 0.6,
                    '&:hover': { opacity: 1 },
                    flexShrink: 0
                  }}
                >
                  <img src={p} alt={`Defect ${i}`} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                  <Box sx={{ position: 'absolute', bottom: 0, left: 0, right: 0, bgcolor: 'rgba(0,0,0,0.7)', p: 0.5, display: 'flex', justifyContent: 'center' }}>
                    <Typography variant="caption" sx={{ color: '#fff', fontWeight: 'bold' }}>
                      {defect?.defect_detections?.[0]?.class_name?.replace(/_/g, ' ') || defect?.class_name?.replace(/_/g, ' ') || 'Unknown'}
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
                {/* Defect Classification */}
                <Box sx={{ mb: 4 }}>
                  <Typography variant="subtitle2" color="#64748b" sx={{ textTransform: 'uppercase', mb: 2, letterSpacing: 0.5, borderBottom: 1, borderColor: '#e2e8f0', pb: 1 }}>Defect Classification</Typography>
                  <FormControl fullWidth size="small" sx={{ mb: 2 }}>
                    <Autocomplete
                      value={currentDefect?.defect_detections?.[0]?.class_name || currentDefect?.class_name || ""}
                      options={["Corrosion", "Peeling Paint", "Crack", "Structural Damage"]}
                      freeSolo
                      onChange={(event, newValue) => {
                        updateDefectClass(newValue || "");
                      }}
                      onInputChange={(event, newInputValue) => {
                        // Only update on real user input, not when Autocomplete syncs state during render
                        if (event) {
                          updateDefectClass(newInputValue || "");
                        }
                      }}
                      disabled={isDrawing}
                      renderInput={(params) => (
                        <TextField 
                          {...params} 
                          label="Defect Type" 
                          InputLabelProps={{ sx: {color:'#64748b'} }}
                          sx={{ '.MuiOutlinedInput-root': { color: '#0f172a', fieldset: { borderColor: '#64748b' } } }}
                        />
                      )}
                    />
                  </FormControl>
                </Box>

                {/* Interactive Editor Instructions */}
                <Box sx={{ display: 'flex', flexDirection: 'column', mb: 4 }}>
                  <Typography variant="subtitle2" color="#64748b" sx={{ textTransform: 'uppercase', mb: 2, letterSpacing: 0.5, borderBottom: 1, borderColor: '#e2e8f0', pb: 1 }}>Interactive Mask Editor</Typography>
                  
                  {isDrawing ? (
                      <Box sx={{ bgcolor: '#ecfdf5', p: 2, borderRadius: 1, border: '1px solid #10b981', mb: 2 }}>
                        <Typography variant="body2" color="#047857" fontWeight="bold" paragraph>
                          Draw Mode Active
                        </Typography>
                        <Typography variant="body2" color="#047857" paragraph>
                          Click on the image to drop points for the new mask.
                        </Typography>
                        <Stack spacing={1} direction="row">
                            <Button variant="contained" color="success" size="small" fullWidth onClick={handleSaveMask}>
                                Save Mask
                            </Button>
                            <Button variant="outlined" color="error" size="small" fullWidth onClick={() => { setIsDrawing(false); setDraftPoints([]); }}>
                                Cancel
                            </Button>
                        </Stack>
                      </Box>
                  ) : (
                      <>
                        <Button 
                            variant="outlined" 
                            color="primary" 
                            sx={{ mb: 2, borderStyle: 'dashed' }}
                            onClick={() => { setIsDrawing(true); setDraftPoints([]); }}
                        >
                            Redraw Mask
                        </Button>
                        <Box sx={{ bgcolor: '#f8fafc', p: 2, borderRadius: 1, border: '1px solid #e2e8f0' }}>
                            <Typography variant="body2" color="text.secondary" paragraph>
                            1. Hover over the mask boundaries to reveal control points.
                            </Typography>
                            <Typography variant="body2" color="text.secondary" paragraph>
                            2. <b>Click and drag</b> the points to reshape the mask.
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                            3. Or click "Redraw Mask" to draw a completely new one.
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

export function SegmentationHitlPage() {
  const { sessionId } = useParams();
  if (!sessionId) return null;
  return (
    <HitlLayout>
      <SegmentationHitlContent sessionId={sessionId} />
    </HitlLayout>
  );
}
