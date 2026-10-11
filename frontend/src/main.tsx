import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router-dom";
import { AuthProvider } from "@/features/auth/AuthContext";
import { AvisosProvider } from "@/components/ui/Avisos";
import { router } from "./app/router";
import "./styles/tokens.css";
import "./styles/global.css";
import { cargarConfiguracion } from "@/lib/configuracion";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
});

// Reglas de negocio del backend (IVA, contraseña, peso de archivos), una sola vez.
queryClient.prefetchQuery({ queryKey: ["configuracion"], queryFn: cargarConfiguracion, staleTime: Infinity });

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <AvisosProvider>
          <RouterProvider router={router} />
        </AvisosProvider>
      </AuthProvider>
    </QueryClientProvider>
  </React.StrictMode>
);