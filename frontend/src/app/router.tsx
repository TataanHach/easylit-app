import { createBrowserRouter, Navigate } from "react-router-dom";
import LoginPage from "@/features/auth/LoginPage";
import CrearContrasenaPage from "@/features/auth/CrearContrasenaPage";
import RutaProtegida from "@/features/auth/RutaProtegida";
import Layout from "@/components/layout/Layout";
import HistorialPage from "@/features/historial/HistorialPage";
import TransformarPage from "@/features/transformaciones/TransformarPage";
import MapeoPage from "@/features/transformaciones/MapeoPage";
import PlantillasPage from "@/features/plantillas/PlantillasPage";

/**
 * Rutas de la aplicación.
 *  - /login y /crear-contrasena son públicas.
 *  - Todo lo demás va dentro del Layout y exige sesión (RutaProtegida).
 */
export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/crear-contrasena", element: <CrearContrasenaPage /> },
  {
    path: "/",
    element: (
      <RutaProtegida>
        <Layout />
      </RutaProtegida>
    ),
    children: [
      { index: true, element: <Navigate to="/historial" replace /> },
      { path: "transformar", element: <TransformarPage /> },
      { path: "transformar/:id/mapeo", element: <MapeoPage /> },
      { path: "historial", element: <HistorialPage /> },
      { path: "plantillas", element: <PlantillasPage /> },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
]);
