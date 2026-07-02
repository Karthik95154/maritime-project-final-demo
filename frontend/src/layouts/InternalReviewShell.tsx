import { Avatar, Box, Button, Chip, Divider, Stack, Typography } from "@mui/material";
import { ShieldCheck, Workflow } from "lucide-react";
import { Outlet, useNavigate } from "react-router-dom";
import { useAppStore } from "../store/appStore";

export function InternalReviewShell() {
  const navigate = useNavigate();
  const { user, logout } = useAppStore();

  return (
    <Box
      sx={{
        height: "100vh",
        display: "flex",
        flexDirection: "column",
        background:
          "radial-gradient(circle at top left, rgba(31, 122, 224, 0.16), transparent 30%), linear-gradient(180deg, #061120 0%, #0B1729 100%)",
      }}
    >
      <Box
        sx={{
          flexShrink: 0,
          zIndex: 20,
          px: { xs: 2, md: 4 },
          py: 0.5,
          borderBottom: "1px solid rgba(148, 163, 184, 0.18)",
          backdropFilter: "blur(16px)",
          backgroundColor: "rgba(6, 17, 32, 0.82)",
        }}
      >
        <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" spacing={2} alignItems={{ xs: "flex-start", md: "center" }}>
          <Stack direction="row" spacing={1.5} alignItems="center">
            <Avatar sx={{ bgcolor: "#123B67", color: "#7DD3FC", width: 32, height: 32 }}>
              <ShieldCheck size={18} />
            </Avatar>
            <Box>
              <Typography variant="subtitle1" sx={{ color: "#F8FAFC", fontWeight: 800 }}>
                HITL Review Console
              </Typography>
            </Box>
          </Stack>

          <Stack direction="row" spacing={1.25} alignItems="center">
            <Box>
              <Typography variant="body2" sx={{ color: "#F8FAFC", fontWeight: 700 }}>
                {user?.name || "Internal reviewer"}
              </Typography>
              <Typography variant="caption" sx={{ color: "#94A3B8" }}>
                {user?.role || "Developer team"}
              </Typography>
            </Box>
            <Button
              variant="outlined"
              onClick={() => {
                logout();
                navigate("/internal/login", { replace: true });
              }}
              sx={{
                borderColor: "rgba(148, 163, 184, 0.35)",
                color: "#E2E8F0",
              }}
            >
              Log out
            </Button>
          </Stack>
        </Stack>
      </Box>

      <Box sx={{ flex: 1, minHeight: 0, p: { xs: 1, md: 2 } }}>
        <Outlet />
      </Box>
    </Box>
  );
}
