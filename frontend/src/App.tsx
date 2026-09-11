import { lazy, Suspense, useEffect } from "react";
import { Route, Routes, useLocation } from "react-router-dom";
import { DisclaimerBar } from "./components/Disclaimer";
import { Footer } from "./components/layout/Footer";
import { NavBar } from "./components/layout/NavBar";
import { CandidatesPage } from "./pages/CandidatesPage";
import { DiseasePage } from "./pages/DiseasePage";
import { DrugPage } from "./pages/DrugPage";
import { ExplanationPage } from "./pages/ExplanationPage";
import { FusionPage } from "./pages/FusionPage";
import { HomePage } from "./pages/HomePage";
import { HowItWorksPage } from "./pages/HowItWorksPage";
import { PathwaysPage } from "./pages/PathwaysPage";
import { PredictionPage } from "./pages/PredictionPage";
import { TargetsPage } from "./pages/TargetsPage";
import { DiscoveryProvider } from "./state/DiscoveryContext";

/** The graph canvas pulls in the whole flow library, which no other route
 * touches — so it loads when someone actually opens the graph. */
const GraphPage = lazy(() =>
  import("./pages/GraphPage").then((m) => ({ default: m.GraphPage })),
);

export default function App() {
  return (
    <DiscoveryProvider>
      <ScrollToTop />
      <div className="flex min-h-screen flex-col">
        <NavBar />
        <main className="flex-1">
          <Suspense fallback={null}>
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/how-it-works" element={<HowItWorksPage />} />
              <Route path="/disease" element={<DiseasePage />} />
              <Route path="/drug" element={<DrugPage />} />
              <Route path="/targets" element={<TargetsPage />} />
              <Route path="/pathways" element={<PathwaysPage />} />
              <Route path="/prediction" element={<PredictionPage />} />
              <Route path="/fusion" element={<FusionPage />} />
              <Route path="/candidates" element={<CandidatesPage />} />
              <Route path="/graph" element={<GraphPage />} />
              <Route path="/explanation" element={<ExplanationPage />} />
              <Route path="*" element={<HomePage />} />
            </Routes>
          </Suspense>
        </main>
        <Footer />
        <DisclaimerBar />
      </div>
    </DiscoveryProvider>
  );
}

/** Route changes start at the top of the new page rather than inheriting the
 * previous page's scroll position, which otherwise lands mid-section. */
function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "instant" as ScrollBehavior });
  }, [pathname]);
  return null;
}
