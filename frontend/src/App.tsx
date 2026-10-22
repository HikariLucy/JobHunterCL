import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Empty } from "./components/ui";
import { CvPage } from "./pages/CvPage";
import { Dashboard } from "./pages/Dashboard";
import { Explore } from "./pages/Explore";
import { ProfilePage } from "./pages/ProfilePage";
import { Settings } from "./pages/Settings";
import { Tracking } from "./pages/Tracking";

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="ofertas" element={<Explore />} />
        <Route path="seguimiento" element={<Tracking />} />
        <Route path="cv" element={<CvPage />} />
        <Route path="perfil" element={<ProfilePage />} />
        <Route path="configuracion" element={<Settings />} />
        <Route path="*" element={<Empty title="Página no encontrada" />} />
      </Route>
    </Routes>
  );
}
