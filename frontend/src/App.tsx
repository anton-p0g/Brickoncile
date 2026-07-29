import { NavLink, Route, Routes } from "react-router-dom";
import { DashboardPage } from "./pages/DashboardPage";
import { FindPartPage } from "./pages/FindPartPage";
import { SetDetailPage } from "./pages/SetDetailPage";
import { ShoppingListPage } from "./pages/ShoppingListPage";
import { MinifigsOverviewPage } from "./pages/MinifigsOverviewPage";
import { MinifigDetailPage } from "./pages/MinifigDetailPage";
import { IdentifyMinifigPage } from "./pages/IdentifyMinifigPage";

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `px-3 py-2 text-sm font-medium ${isActive ? "text-gray-900 border-b-2 border-gray-900" : "text-gray-500"}`;

function App() {
  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <nav className="border-b border-gray-200 bg-white px-4 flex gap-2">
        <NavLink to="/" end className={navLinkClass}>
          Dashboard
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
        <NavLink to="/shopping-list" className={navLinkClass}>
          Shopping List
        </NavLink>
      </nav>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/sets/:setNum" element={<SetDetailPage />} />
        <Route path="/find" element={<FindPartPage />} />
        <Route path="/shopping-list" element={<ShoppingListPage />} />
        <Route path="/minifigs" element={<MinifigsOverviewPage />} />
        <Route path="/minifigs/:instanceId" element={<MinifigDetailPage />} />
        <Route path="/identify" element={<IdentifyMinifigPage />} />
      </Routes>
    </div>
  );
}

export default App;
