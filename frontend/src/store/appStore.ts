import { create } from "zustand";
import { persist } from "zustand/middleware";
import { backendApi } from "../api/backendApi";

export interface SelectedVideo {
  id: string;
  file: File;
  previewUrl: string;
}

export interface InspectionForm {
  visitId?: string;
  vesselName: string;
  imoNumber: string;
  vesselType: string;
  grossTonnage: string;
  inspectorName: string;
  location: string;
  inspectionDate: string;
  comments: string;
}

interface AppState {
  // Auth state
  isAuthenticated: boolean;
  user: { name: string; email: string; role: string; organization: string; isAdmin?: boolean } | null;
  authError: string | null;
  login: (email: string, password: string) => Promise<void>;
  signup: (name: string, email: string, password: string, isAdmin: boolean) => Promise<void>;
  adminCreateUser: (name: string, email: string, password: string, isAdmin: boolean) => Promise<void>;
  logout: () => void;

  sidebarOpen: boolean;
  selectedDefectId: string;
  setSidebarOpen: (open: boolean) => void;
  setSelectedDefectId: (id: string) => void;

  // Global state for New Inspection
  inspectionForm: InspectionForm;
  setInspectionForm: (form: InspectionForm | ((prev: InspectionForm) => InspectionForm)) => void;
  inspectionVideos: SelectedVideo[];
  setInspectionVideos: (videos: SelectedVideo[] | ((prev: SelectedVideo[]) => SelectedVideo[])) => void;
  uploadStatus: "idle" | "uploading" | "queued" | "awaiting_review" | "success" | "error";
  uploadProgress: number;
  uploadError: string | null;
  uploadLogs: string[];
  currentStage: string;
  uploadSessionId: string | null;
  uploadStatusMessage: string | null;
  startInspectionUpload: (onSuccess: (batchId: string) => void) => Promise<void>;
  resetInspection: () => void;
}

const defaultForm = {
  visitId: "",
  vesselName: "",
  imoNumber: "",
  vesselType: "",
  grossTonnage: "",
  inspectorName: "",
  location: "",
  inspectionDate: new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16),
  comments: "",
};

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      isAuthenticated: false,
      user: null,
      authError: null,
      login: async (email, password) => {
        set({ authError: null });
        try {
          const result = await backendApi.login({ email, password });
          localStorage.setItem("auth_token", result.access_token);
          set({ isAuthenticated: true, user: result.user });
        } catch (err: any) {
          set({ authError: err.message || "Failed to login" });
          throw err;
        }
      },
      signup: async (name, email, password, isAdmin) => {
        set({ authError: null });
        try {
          const result = await backendApi.signup({ name, email, password, isAdmin });
          localStorage.setItem("auth_token", result.access_token);
          set({ isAuthenticated: true, user: result.user });
        } catch (err: any) {
          set({ authError: err.message || "Failed to sign up" });
          throw err;
        }
      },
      adminCreateUser: async (name, email, password, isAdmin) => {
        try {
          await backendApi.signup({ name, email, password, isAdmin });
        } catch (err: any) {
          throw err;
        }
      },
      logout: () => {
        localStorage.removeItem("auth_token");
        set({ isAuthenticated: false, user: null, authError: null });
      },

      sidebarOpen: true,
      selectedDefectId: "DEF-1001",
      setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
      setSelectedDefectId: (selectedDefectId) => set({ selectedDefectId }),

      inspectionForm: defaultForm,
      setInspectionForm: (updater) => 
        set((state) => ({
          inspectionForm: typeof updater === "function" ? updater(state.inspectionForm) : updater,
        })),
      inspectionVideos: [],
      setInspectionVideos: (updater) =>
        set((state) => ({
          inspectionVideos: typeof updater === "function" ? updater(state.inspectionVideos) : updater,
        })),
      uploadStatus: "idle",
      uploadProgress: 0,
      uploadError: null,
      uploadLogs: [],
      currentStage: "",
      uploadSessionId: null,
      uploadStatusMessage: null,

      startInspectionUpload: async (onSuccess) => {
        const { inspectionForm, inspectionVideos } = get();
        if (!inspectionVideos.length) {
          set({ uploadError: "Please select at least one video before creating an inspection.", uploadStatus: "error" });
          return;
        }

        set({
          uploadStatus: "uploading",
          uploadProgress: 0,
          uploadError: null,
          uploadLogs: [],
          currentStage: "Uploading files...",
          uploadSessionId: null,
          uploadStatusMessage: "Uploading videos to the backend.",
        });

        try {
          const payload = {
            videos: inspectionVideos.map((v) => v.file),
            ...inspectionForm,
          };
          
          // Step 1: Upload the files (tracks XHR progress)
          const result = await backendApi.uploadInspectionBatch(payload, (progress) => {
            // Keep progress between 0 and 10% for file upload
            set({ uploadProgress: Math.round(progress * 0.1) });
          });
          
          const batchId = result.batch_id;
          const sessionId = result.session_ids[0];
          set({
            uploadStatus: "queued",
            uploadSessionId: sessionId,
            currentStage: "Queued",
            uploadStatusMessage: "Upload complete. Your inspection is queued and waiting for the pipeline worker.",
            uploadLogs: [
              "Files uploaded successfully.",
              "Inspection queued for AI processing.",
            ],
          });
          
          // Step 2: Poll backend progress (robust HTTP polling instead of SSE)
          const pollInterval = setInterval(async () => {
            try {
              const data = await backendApi.getInspectionProgress(sessionId);
              
              set((state) => {
                const newLogs = [...state.uploadLogs];
                const status = data.status?.toLowerCase();
                const stage = data.currentStage || "Processing";
                const reviewCheckpoint = data.reviewCheckpoint?.replace(/_/g, " ");
                const statusMessage =
                  status === "awaiting_review"
                    ? `AI is paused for ${reviewCheckpoint || "human review"}. Continue it from the HITL console.`
                    : status === "processing" && stage === "Queued"
                      ? "Upload complete. Waiting in queue for the pipeline worker."
                      : status === "processing"
                        ? `AI pipeline is running: ${stage}.`
                        : status === "completed"
                          ? "Inspection analysis completed successfully."
                          : stage;
                const logLine =
                  status === "awaiting_review"
                    ? `Awaiting review: ${reviewCheckpoint || stage}`
                    : `Current status: ${stage}`;
                if (newLogs[newLogs.length - 1] !== logLine) {
                  newLogs.push(logLine);
                }
                
                return {
                  // Pipeline progress represents 10% to 100%
                  uploadProgress: Math.max(state.uploadProgress, 10 + Math.round(data.progress * 0.9)),
                  currentStage: data.currentStage,
                  uploadStatus:
                    status === "awaiting_review"
                      ? "awaiting_review"
                      : status === "processing" && stage === "Queued"
                        ? "queued"
                        : state.uploadStatus === "success"
                          ? "success"
                          : "uploading",
                  uploadStatusMessage: statusMessage,
                  uploadLogs: newLogs,
                };
              });
              
              const status = data.status?.toLowerCase();
              if (status === "completed") {
                set({
                  uploadStatus: "success",
                  uploadProgress: 100,
                  uploadStatusMessage: "Inspection analysis completed successfully.",
                });
                clearInterval(pollInterval);
                onSuccess(batchId);
              } else if (status === "error" || status === "failed") {
                set({
                  uploadStatus: "error",
                  uploadError: "Pipeline execution failed. Check logs.",
                  uploadStatusMessage: "The AI pipeline failed after upload. Review the latest logs and backend output.",
                });
                clearInterval(pollInterval);
              }
            } catch (err) {
              console.error("Polling error:", err);
              set((state) => ({
                uploadStatusMessage:
                  state.uploadStatus === "awaiting_review"
                    ? state.uploadStatusMessage
                    : "Upload succeeded, but live status polling is temporarily unavailable. You can still check progress from the inspections list.",
              }));
            }
          }, 2000);
          
        } catch (err) {
          set({ 
            uploadStatus: "error", 
            uploadError: err instanceof Error ? err.message : "An unexpected error occurred",
            uploadStatusMessage: "The upload request failed before the AI pipeline could start.",
          });
        }
      },

      resetInspection: () => {
        const { inspectionVideos } = get();
        inspectionVideos.forEach((video) => URL.revokeObjectURL(video.previewUrl));
        set({
          inspectionForm: {
            ...defaultForm,
            inspectionDate: new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16),
          },
          inspectionVideos: [],
          uploadStatus: "idle",
          uploadProgress: 0,
          uploadError: null,
          uploadLogs: [],
          currentStage: "",
          uploadSessionId: null,
          uploadStatusMessage: null,
        });
      },
    }),
    {
      name: "maritime-app-storage",
      partialize: (state) => ({
        isAuthenticated: state.isAuthenticated,
        user: state.user,
        sidebarOpen: state.sidebarOpen,
        selectedDefectId: state.selectedDefectId,
      }),
    }
  )
);
