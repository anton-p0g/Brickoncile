import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { DashboardPage } from "./pages/DashboardPage";
import { SetsPage } from "./pages/SetsPage";
import { FindPartPage } from "./pages/FindPartPage";
import { SetDetailPage } from "./pages/SetDetailPage";
import { MissingPartsPage } from "./pages/MissingPartsPage";
import { MinifigsOverviewPage } from "./pages/MinifigsOverviewPage";
import { MinifigDetailPage } from "./pages/MinifigDetailPage";
import { IdentifyMinifigPage } from "./pages/IdentifyMinifigPage";
import { CollectionSelector } from "./components/CollectionSelector";

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `px-3 py-2 text-sm font-medium ${isActive ? "text-gray-900 border-b-2 border-gray-900" : "text-gray-500"}`;

function App() {
  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      {/* Wraps rather than scrolls: on a phone every destination stays reachable without a swipe. */}
      <nav className="flex flex-wrap border-b border-gray-200 bg-white px-4">
        <NavLink to="/sets" className={navLinkClass}>
          Sets
        </NavLink>
        <NavLink to="/find" className={navLinkClass}>
          Find a Brick
        </NavLink>
        <NavLink to="/minifigs" className={navLinkClass}>
          Minifigures
        </NavLink>
        <NavLink to="/identify" className={navLinkClass}>
          Identify
        </NavLink>
        <NavLink to="/missing" className={navLinkClass}>
          Missing Parts
        </NavLink>
        {/* Last in the row: the dashboard is somewhere to check in on rather than a step in the
            sorting flow the other tabs form. */}
        <NavLink to="/dashboard" className={navLinkClass}>
          Dashboard
        </NavLink>
        <CollectionSelector />
      </nav>
      <Routes>
        <Route path="/" element={<Navigate to="/sets" replace />} />
        <Route path="/sets" element={<SetsPage />} />
        <Route path="/sets/:setNum" element={<SetDetailPage />} />
        <Route path="/find" element={<FindPartPage />} />
        <Route path="/missing" element={<MissingPartsPage />} />
        {/* The screen was called "Shopping List" until it became a view of what is missing. */}
        <Route path="/shopping-list" element={<Navigate to="/missing" replace />} />
        <Route path="/minifigs" element={<MinifigsOverviewPage />} />
        <Route path="/minifigs/:instanceId" element={<MinifigDetailPage />} />
        <Route path="/identify" element={<IdentifyMinifigPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
      </Routes>
    </div>
  );
}

export default App;
