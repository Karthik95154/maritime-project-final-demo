import { backendApi, API_BASE_URL } from "../../api/backendApi";
import React, { useEffect, useState, useRef, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Box, Typography, Button, IconButton, Divider, Table, TableBody, TableCell, TableHead, TableRow, Select, MenuItem, FormControl, InputLabel, TextField, Stack, Tooltip, Chip, Autocomplete } from "@mui/material";
import { Stage, Layer, Image as KonvaImage, Line, Circle, Group, Text } from "react-konva";
import useImage from "use-image";
import { ChevronLeft as ChevronLeftIcon, ChevronRight as ChevronRightIcon, Trash2 as DeleteIcon, Undo2 as UndoIcon, Redo2 as RedoIcon, ZoomIn as ZoomInIcon, ZoomOut as ZoomOutIcon, Maximize as FitIcon } from "lucide-react";
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

function PartDetectionHitlContent({ sessionId }: { sessionId: string }) {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<any>(null);
  
  // Array of all frames and their detections
  const [fullOutput, setFullOutput] = useState<any[]>([]);
  const { workspaceDimensions } = useHitlLayout();
  const { transform, setTransform, currentFrame: currentFrameIndex, setCurrentFrame: setCurrentFrameIndex } = useHitlWorkspace();

  const [isDrawing, setIsDrawing] = useState(false);
  const [draftPoints, setDraftPoints] = useState<number[]>([]);

  // missing variables
  const [detections, setDetections] = useState<any[]>([]);
  const [history, setHistory] = useState<any[][]>([]);
  const [historyStep, setHistoryStep] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [frameUrl, setFrameUrl] = useState("");
  const [image] = useImage(frameUrl);

  const stageRef = useRef<any>(null);
  const trRef = useRef<any>(null);

  useEffect(() => {
    backendApi.getInternalReviewDetail(sessionId!)
      .then(json => {
        setData(json);
        const pipelineData = json.pipeline_data || {};
        const existingHuman = pipelineData["part_detection_human_json"];
        const aiOutput = pipelineData["part_detection_ai_json"];
        
        let outputArray: any[] = [];
        const rawOutput = existingHuman || aiOutput;
        
        if (Array.isArray(rawOutput) && rawOutput.length > 0) {
          outputArray = rawOutput;
        } else if (rawOutput && rawOutput.part_detections) {
          outputArray = [rawOutput];
        } else {
            // fallback if it's just frames from extraction
            const frames = pipelineData["frame_json"] || pipelineData["frame_extraction_ai_json"] || [];
            if (Array.isArray(frames)) {
                outputArray = frames.map(f => ({
                    frame_id: f.frame_id || f,
                    frame_path: f.frame_path || f,
                    part_detections: []
                }));
            }
        }
        
        // ensure unique IDs for detections
        outputArray = outputArray.map(frame => ({
            ...frame,
            part_detections: (frame.part_detections || []).map((d: any, i: number) => ({
                ...d,
                id: d.id || `det-${i}-${Date.now()}`
            }))
        }));

        setFullOutput(outputArray);
        
        if (outputArray.length > 0) {
            loadFrameData(outputArray, 0);
        }
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setError("Failed to load session");
        setLoading(false);
      });
  }, [sessionId]);

  const loadFrameData = (frames: any[], index: number) => {
    if (!frames[index]) return;
    const frame = frames[index];
    
    // Setup Detections
    const initialDetections = frame.part_detections || [];
    setDetections(initialDetections);
    setHistory([initialDetections]);
    setHistoryStep(0);
    setSelectedId(null);
    setCurrentFrameIndex(index);
    
    // Setup Image
    const rawPath = frame.frame_path || frame.frame_id;
    if (typeof rawPath === 'string') {
        if (rawPath.startsWith("http://") || rawPath.startsWith("https://")) {
            setFrameUrl(rawPath);
        } else {
            const parts = rawPath.split("outputs");
            if (parts.length > 1) {
                setFrameUrl(`/outputs${parts[1].replace(/\\/g, '/')}`);
            }
        }
    }
  };

  // Switch frame
  const handleSelectFrame = (index: number) => {
      // 1. Save current frame's detections back into fullOutput
      const updatedOutput = [...fullOutput];
      updatedOutput[currentFrameIndex] = {
          ...updatedOutput[currentFrameIndex],
          part_detections: detections
      };
      setFullOutput(updatedOutput);
      
      // 2. Load new frame
      loadFrameData(updatedOutput, index);
  };

  const pushToHistory = (newDetections: any[]) => {
    const newHistory = history.slice(0, historyStep + 1);
    newHistory.push(newDetections);
    setHistory(newHistory);
    setHistoryStep(newHistory.length - 1);
    setDetections(newDetections);
    
    // Also instantly update fullOutput
    setFullOutput(prev => {
        const arr = [...prev];
        arr[currentFrameIndex] = { ...arr[currentFrameIndex], part_detections: newDetections };
        return arr;
    });
  };

  const undo = () => {
    if (historyStep > 0) {
      setHistoryStep(historyStep - 1);
      const oldDets = history[historyStep - 1];
      setDetections(oldDets);
      setFullOutput(prev => {
          const arr = [...prev];
          arr[currentFrameIndex] = { ...arr[currentFrameIndex], part_detections: oldDets };
          return arr;
      });
    }
  };

  const redo = () => {
    if (historyStep < history.length - 1) {
      setHistoryStep(historyStep + 1);
      const newDets = history[historyStep + 1];
      setDetections(newDets);
      setFullOutput(prev => {
          const arr = [...prev];
          arr[currentFrameIndex] = { ...arr[currentFrameIndex], part_detections: newDets };
          return arr;
      });
    }
  };

  const handleSave = async (dataToSave: any) => {
    try {
      await backendApi.savePartDetectionReview(sessionId!, {
        decision: "save_assessment",
        corrections: dataToSave,
        reviewer: "System Admin"
      });
      console.log("Saved part detection:", dataToSave);
    } catch (err) {}
  };

  const { status: saveStatus, lastSaved, forceSave } = useHitlAutosave({
    data: fullOutput,
    onSave: handleSave,
    enabled: !loading && !error && fullOutput.length > 0
  });

  const handleDecision = async (decision: string) => {
    try {
      await forceSave(fullOutput);
      await backendApi.savePartDetectionReview(sessionId!, {
        decision, 
        corrections: fullOutput, 
        reviewer: "System Admin"
      });
      if (decision === "assess_continue") navigate("/internal/review");
    } catch (err) {
      console.error(err);
    }
  };

  useHitlShortcuts({
    onApprove: () => handleDecision('assess_continue'),
    onReject: () => handleDecision('reject'),
    onSave: () => forceSave(fullOutput),
    onUndo: undo,
    onRedo: redo,
    onNextFrame: () => {
      if (currentFrameIndex < fullOutput.length - 1) handleSelectFrame(currentFrameIndex + 1);
    },
    onPrevFrame: () => {
      if (currentFrameIndex > 0) handleSelectFrame(currentFrameIndex - 1);
    },
    disabled: loading || !!error
  });

  const getMinScale = useCallback(() => {
    if (!image || workspaceDimensions.width === 0 || workspaceDimensions.height === 0) return 0.1;
    let contentWidth = image.width;
    let contentHeight = image.height;
    if (detections && detections.length > 0) {
        detections.forEach((det: any) => {
            const [xmin, ymin, xmax, ymax] = det.bbox || [0,0,0,0];
            if (xmax > contentWidth) contentWidth = xmax;
            if (ymax > contentHeight) contentHeight = ymax;
        });
    }
    return Math.min(
      workspaceDimensions.width / contentWidth,
      workspaceDimensions.height / contentHeight
    ) * 0.95;
  }, [image, workspaceDimensions, detections]);

  const fitToScreen = useCallback(() => {
    if (!image || workspaceDimensions.width === 0 || workspaceDimensions.height === 0) return;
    let contentWidth = image.width;
    let contentHeight = image.height;
    if (detections && detections.length > 0) {
        detections.forEach((det: any) => {
            const [xmin, ymin, xmax, ymax] = det.bbox || [0,0,0,0];
            if (xmax > contentWidth) contentWidth = xmax;
            if (ymax > contentHeight) contentHeight = ymax;
        });
    }
    const scale = getMinScale();
    setTransform({
      scale,
      x: (workspaceDimensions.width - contentWidth * scale) / 2,
      y: 20
    });
  }, [image, workspaceDimensions, getMinScale, detections, setTransform]);

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

  const handleMouseDown = (e: any) => {
    if (e.target.attrs && e.target.attrs.draggable) return; 
    if (e.target !== stageRef.current && e.target.name() !== "backgroundImage") {
        if (!isDrawing) return;
    }
    
    if (isDrawing) {
      const stage = stageRef.current;
      const pos = stage.getPointerPosition();
      const ix = (pos.x - stage.x()) / stage.scaleX();
      const iy = (pos.y - stage.y()) / stage.scaleY();
      setDraftPoints([...draftPoints, ix, iy]);
    } else {
        setSelectedId(null);
    }
  };

  const handleMouseMove = (e: any) => {};
  const handleMouseUp = () => {};


  const updateDetection = (id: string, updates: any) => {
    const newDets = detections.map(d => d.id === id ? { ...d, ...updates } : d);
    pushToHistory(newDets);
  };

  const deleteDetection = (id: string) => {
    pushToHistory(detections.filter(d => d.id !== id));
    if (selectedId === id) setSelectedId(null);
  };

  const duplicateDetection = (id: string) => {
    const d = detections.find(x => x.id === id);
    if (d) {
      const newDet = { ...d, id: `det-dup-${Date.now()}`, bbox: [d.bbox[0]+20, d.bbox[1]+20, d.bbox[2]+20, d.bbox[3]+20] };
      pushToHistory([...detections, newDet]);
      setSelectedId(newDet.id);
    }
  };

  useEffect(() => {
    if (selectedId && trRef.current && stageRef.current) {
      const node = stageRef.current.findOne(`#${selectedId}`);
      if (node) {
        trRef.current.nodes([node]);
        trRef.current.getLayer().batchDraw();
      }
    } else if (trRef.current) {
      trRef.current.nodes([]);
    }
  }, [selectedId, detections]);

  if (loading) return <Box p={4} color="#f1f5f9">Loading Editor...</Box>;
  if (error) return <Box p={4} color="error.main">{error}</Box>;

  const selectedDet = detections.find(d => d.id === selectedId);

  const handleFinishDrawing = () => {
      if (draftPoints.length >= 6) {
          const seg = [];
          let xs = [];
          let ys = [];
          for(let j=0; j<draftPoints.length; j+=2) {
              seg.push([draftPoints[j], draftPoints[j+1]]);
              xs.push(draftPoints[j]);
              ys.push(draftPoints[j+1]);
          }
          const det = {
              id: `det-${Date.now()}`,
              class_name: "UNKNOWN",
              conf: 1.0,
              bbox: [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)],
              segmentation: seg
          };
          pushToHistory([...detections, det]);
          setSelectedId(det.id);
      }
      setIsDrawing(false);
      setDraftPoints([]);
  };

  return (
    <>
      <HitlHeader 
        title="Part Detection Annotation" 
        sessionId={sessionId} 
        saveStatus={saveStatus}
        lastSaved={lastSaved}
        onUndo={undo}
        canUndo={historyStep > 0}
        onRedo={redo}
        canRedo={historyStep < history.length - 1}
      />
      <HitlMainContainer>
        <HitlWorkspace>
          <HitlToolbar 
            currentFrameIndex={currentFrameIndex}
            totalFrames={fullOutput.length}
            onPrev={() => { if (currentFrameIndex > 0) handleSelectFrame(currentFrameIndex - 1); }}
            onNext={() => { if (currentFrameIndex < fullOutput.length - 1) handleSelectFrame(currentFrameIndex + 1); }}
            onZoomIn={() => setTransform(prev => ({ ...prev, scale: prev.scale * 1.2 }))}
            onZoomOut={() => setTransform(prev => ({ ...prev, scale: Math.max(getMinScale(), prev.scale / 1.2) }))}
            onFit={fitToScreen}
          >
            <Button size="small" color={isDrawing && draftPoints.length >= 6 ? "success" : "primary"} variant={isDrawing ? "contained" : "outlined"} onClick={() => {
                if (isDrawing && draftPoints.length >= 6) {
                    handleFinishDrawing();
                } else {
                    setIsDrawing(!isDrawing);
                    setDraftPoints([]);
                    setSelectedId(null);
                }
            }}>
                {isDrawing ? (draftPoints.length >= 6 ? "Finish Drawing" : "Cancel Drawing") : "Draw Polygon"}
            </Button>
            <Typography variant="caption" sx={{ ml: 'auto', alignSelf: 'center', color: '#64748b' }}>Drag to pan. Click to add polygon points.</Typography>
          </HitlToolbar>

          <HitlCanvas style={{ cursor: isDrawing ? 'crosshair' : 'grab' }}>
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
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
              ref={stageRef}
            >
              <Layer>
                {image && <KonvaImage image={image} name="backgroundImage" />}
                
                {detections.map((det) => {
                  let points: number[] = [];
                  if (det.segmentation && Array.isArray(det.segmentation)) {
                      points = Array.isArray(det.segmentation[0]) ? det.segmentation.flat() : det.segmentation;
                  } else if (det.bbox) {
                      const [x1, y1, x2, y2] = det.bbox;
                      points = [x1, y1, x2, y1, x2, y2, x1, y2];
                  }
                  
                  return (
                    <Group key={det.id}>
                      <Line
                        points={points}
                        stroke={selectedId === det.id ? "#38bdf8" : "#22c55e"}
                        strokeWidth={2 / transform.scale}
                        fill={selectedId === det.id ? "rgba(56, 189, 248, 0.2)" : "rgba(34, 197, 94, 0.2)"}
                        closed={true}
                        tension={0}
                        onClick={() => { if (!isDrawing) setSelectedId(det.id); }}
                      />
                      {/* Text Label */}
                      {points.length >= 2 && (
                        <Text
                          x={points[0]} y={points[1] - 14 / transform.scale}
                          text={det.class_name || det.type || "UNKNOWN"}
                          fill="#000"
                          fontSize={12 / transform.scale}
                          fontFamily="Inter"
                          padding={2 / transform.scale}
                          align="left"
                          opacity={0.8}
                        />
                      )}
                      {/* Interactive vertices when selected */}
                      {selectedId === det.id && !isDrawing && points.map((val, i) => {
                          if (i % 2 === 0) {
                              return (
                                  <Circle
                                      key={i}
                                      x={points[i]}
                                      y={points[i + 1]}
                                      radius={4 / transform.scale}
                                      fill="#ffffff"
                                      stroke="#0ea5e9"
                                      strokeWidth={2 / transform.scale}
                                      draggable
                                      onDragEnd={(e) => {
                                          const newPoints = [...points];
                                          newPoints[i] = e.target.x();
                                          newPoints[i + 1] = e.target.y();
                                          
                                          let seg = [];
                                          let xs = [];
                                          let ys = [];
                                          for(let j=0; j<newPoints.length; j+=2) {
                                              seg.push([newPoints[j], newPoints[j+1]]);
                                              xs.push(newPoints[j]);
                                              ys.push(newPoints[j+1]);
                                          }
                                          const bbox = [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
                                          
                                          updateDetection(det.id, { segmentation: seg, bbox });
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
                  );
                })}

                {isDrawing && draftPoints.length > 0 && (
                    <Group>
                        <Line
                            points={draftPoints}
                            fill="rgba(16, 185, 129, 0.4)"
                            stroke="#10b981"
                            strokeWidth={3 / transform.scale}
                            closed={draftPoints.length >= 6}
                            tension={0}
                        />
                        {draftPoints.map((val, i) => {
                            if (i % 2 === 0) {
                                const isFirst = i === 0;
                                const canClose = isFirst && draftPoints.length >= 6;
                                return (
                                    <Circle
                                        key={i}
                                        x={draftPoints[i]}
                                        y={draftPoints[i + 1]}
                                        radius={(canClose ? 8 : 4) / transform.scale}
                                        fill={canClose ? "#10b981" : "#ffffff"}
                                        stroke="#10b981"
                                        strokeWidth={2 / transform.scale}
                                        onClick={(e) => {
                                            e.cancelBubble = true;
                                            if (canClose) handleFinishDrawing();
                                        }}
                                        onMouseEnter={(e) => {
                                            if (canClose) {
                                                const container = e.target.getStage()?.container();
                                                if (container) container.style.cursor = 'crosshair';
                                            }
                                        }}
                                    />
                                );
                            }
                            return null;
                        })}
                    </Group>
                )}
              </Layer>
            </Stage>
          </HitlCanvas>
          
          <HitlFilmstrip>
            {fullOutput.map((frame, i) => {
              let p = "";
              const rawPath = frame.frame_path || frame.frame_id;
              if (rawPath) {
                  if (rawPath.startsWith("http://") || rawPath.startsWith("https://")) {
                      p = rawPath;
                  } else {
                      const parts = rawPath.split("outputs");
                      if (parts.length > 1) p = `/outputs${parts[1].replace(/\\/g, '/')}`;
                  }
              }
              const isSelected = i === currentFrameIndex;
              const detsCount = frame.part_detections?.length || 0;
              
              return (
                <Box 
                  key={i} 
                  onClick={() => handleSelectFrame(i)}
                  sx={{ 
                    height: '100%', minWidth: 140, position: 'relative', cursor: 'pointer', borderRadius: 1, overflow: 'hidden', 
                    border: isSelected ? '3px solid #0ea5e9' : '1px solid #cbd5e1', opacity: isSelected ? 1 : 0.6,
                    '&:hover': { opacity: 1 },
                    flexShrink: 0
                  }}
                >
                  <img src={p} alt={`Frame ${i}`} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                  <Box sx={{ position: 'absolute', bottom: 0, left: 0, right: 0, bgcolor: 'rgba(0,0,0,0.7)', p: 0.5, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Typography variant="caption" sx={{ color: '#fff', fontWeight: 'bold' }}>Fr {i}</Typography>
                    <Chip size="small" label={detsCount} sx={{ height: 16, fontSize: '0.65rem', bgcolor: detsCount > 0 ? '#ef4444' : '#64748b', color: '#fff' }} />
                  </Box>
                </Box>
              );
            })}
          </HitlFilmstrip>
        </HitlWorkspace>
        
        <HitlSidebar>
          <Box sx={{ p: 2.5, flexGrow: 1, overflowY: 'auto' }}>
            <Typography variant="subtitle1" fontWeight="bold" mb={2}>Defect Properties</Typography>
            {selectedDet ? (
              <Stack spacing={2.5}>
                <FormControl fullWidth size="small">
                  <Autocomplete
                    freeSolo
                    options={["KEEL_AREA", "RUDDER", "HULL", "BULBOUS_BOW", "UNKNOWN"]}
                    value={selectedDet.class_name || ""}
                    onChange={(event, newValue) => {
                      updateDetection(selectedDet.id, { class_name: newValue || "" });
                    }}
                    onInputChange={(event, newInputValue) => {
                      updateDetection(selectedDet.id, { class_name: newInputValue || "" });
                    }}
                    renderInput={(params) => (
                      <TextField 
                        {...params} 
                        label="Part Type" 
                        InputLabelProps={{ sx: {color:'#64748b'} }}
                        sx={{ '.MuiOutlinedInput-root': { color: '#0f172a', fieldset: { borderColor: '#64748b' } } }}
                      />
                    )}
                  />
                </FormControl>

                <TextField 
                  fullWidth size="small" label="Reviewer Notes" 
                  value={selectedDet.notes || ""}
                  onChange={(e) => updateDetection(selectedDet.id, { notes: e.target.value })}
                  InputLabelProps={{ sx: {color:'#64748b'} }}
                  InputProps={{ sx: { color: '#0f172a', '.MuiOutlinedInput-notchedOutline': { borderColor: '#64748b' } } }}
                />

                <Box display="flex" gap={1} mt={1}>
                  <Button size="small" color="error" variant="outlined" onClick={() => deleteDetection(selectedDet.id)} startIcon={<DeleteIcon/>}>Delete</Button>
                  <Button size="small" color="primary" variant="outlined" onClick={() => duplicateDetection(selectedDet.id)}>Duplicate</Button>
                </Box>
              </Stack>
            ) : (
              <Typography variant="body2" color="#64748b">Select a bounding box on the canvas to edit its properties.</Typography>
            )}

            <Box mt={4}>
              <Box pb={1} borderBottom="1px solid #e2e8f0" mb={1}><Typography variant="subtitle2" color="#64748b" fontWeight="bold" sx={{textTransform:'uppercase'}}>Detections on Frame {currentFrameIndex} ({detections.length})</Typography></Box>
              <Table size="small" sx={{ '& td, & th': { borderColor: '#e2e8f0', color: '#0f172a' } }}>
                <TableHead>
                  <TableRow sx={{ bgcolor: '#f1f5f9' }}>
                    <TableCell>Type</TableCell>
                    <TableCell>Conf</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {detections.map(d => (
                    <TableRow 
                      key={d.id} 
                      hover 
                      selected={selectedId === d.id}
                      onClick={() => setSelectedId(d.id)}
                      sx={{ 
                        cursor: 'pointer',
                        '&.Mui-selected': { bgcolor: 'rgba(56, 189, 248, 0.15) !important' } 
                      }}
                    >
                      <TableCell>{d.class_name}</TableCell>
                      <TableCell>{d.confidence ? (d.confidence*100).toFixed(0)+'%' : 'User'}</TableCell>
                    </TableRow>
                  ))}
                  {detections.length === 0 && (
                    <TableRow><TableCell colSpan={2} align="center" sx={{color:'#64748b'}}>No detections found.</TableCell></TableRow>
                  )}
                </TableBody>
              </Table>
            </Box>
          </Box>

          <HitlActionBar 
            onApprove={() => handleDecision('assess_continue')}
            onReject={() => handleDecision('reject')}
            onSaveDraft={() => forceSave(fullOutput)}
            isSaving={saveStatus === 'saving'}
          />
        </HitlSidebar>
      </HitlMainContainer>
    </>
  );
}

export function PartDetectionHitlPage() {
  const { sessionId } = useParams();
  if (!sessionId) return null;
  return (
    <HitlLayout>
      <PartDetectionHitlContent sessionId={sessionId} />
    </HitlLayout>
  );
}
