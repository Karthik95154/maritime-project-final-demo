import { useRouteError, useNavigate } from "react-router-dom";
import { Box, Button, Typography, Stack, Container, ThemeProvider, createTheme } from "@mui/material";
import { AlertCircle, RefreshCcw, Home } from "lucide-react";

const darkTheme = createTheme({
  palette: {
    mode: "dark",
    primary: { main: "#60A5FA" },
    background: { default: "#020617", paper: "#0F172A" },
  },
  typography: {
    fontFamily: '"Inter", sans-serif',
    button: { textTransform: "none", fontWeight: 600 },
  },
});

export function GlobalErrorElement() {
  const error: any = useRouteError();
  const navigate = useNavigate();

  return (
    <ThemeProvider theme={darkTheme}>
      <Box
        sx={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          bgcolor: "background.default",
          p: 3,
        }}
      >
        <Container maxWidth="sm">
          <Box
            sx={{
              p: 5,
              borderRadius: 4,
              bgcolor: "background.paper",
              border: "1px solid rgba(255,255,255,0.1)",
              boxShadow: "0 20px 40px rgba(0,0,0,0.5)",
              textAlign: "center",
            }}
          >
            <Box
              sx={{
                width: 64,
                height: 64,
                borderRadius: "50%",
                bgcolor: "rgba(239, 68, 68, 0.1)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                mx: "auto",
                mb: 3,
              }}
            >
              <AlertCircle size={32} color="#EF4444" />
            </Box>
            <Typography variant="h4" sx={{ fontWeight: 800, color: "#F8FAFC", mb: 2 }}>
              Unexpected Error
            </Typography>
            <Typography sx={{ color: "#94A3B8", mb: 4 }}>
              {error?.message || "An unexpected application error occurred. Our team has been notified."}
            </Typography>

            <Stack direction="row" spacing={2} justifyContent="center">
              <Button
                variant="outlined"
                startIcon={<RefreshCcw size={18} />}
                onClick={() => window.location.reload()}
                sx={{ borderColor: "rgba(255,255,255,0.2)", color: "#E2E8F0" }}
              >
                Reload Page
              </Button>
              <Button
                variant="contained"
                startIcon={<Home size={18} />}
                onClick={() => navigate("/")}
              >
                Go Home
              </Button>
            </Stack>
          </Box>
        </Container>
      </Box>
    </ThemeProvider>
  );
}
