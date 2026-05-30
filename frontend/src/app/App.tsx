import { useState } from "react";
import { DashboardLayout, type RouteKey } from "../layouts/DashboardLayout";
import { useMarketData } from "../hooks/useMarketData";
import { Toast } from "../components/ui/Toast";
import { LandingPage } from "../pages/landing/LandingPage";
import { DashboardPage } from "../pages/dashboard/DashboardPage";
import { AIChoicePage } from "../pages/ai-choice/AIChoicePage";
import { TradeTerminalPage } from "../pages/trade/TradeTerminalPage";

export function App() {
  const data = useMarketData();
  const [route, setRoute] = useState<RouteKey>("landing");
  const [toast, setToast] = useState("");

  const notify = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(""), 3600);
  };

  if (route === "landing") {
    return (
      <>
        <LandingPage data={data} onRoute={setRoute} />
        <Toast message={toast} />
      </>
    );
  }

  return (
    <DashboardLayout route={route} onRoute={setRoute} data={data}>
      {route === "dashboard" && <DashboardPage data={data} />}
      {route === "ai-choice" && (
        <AIChoicePage
          data={data}
          onToast={notify}
          onOpenTrade={() => setRoute("trade")}
        />
      )}
      {route === "trade" && <TradeTerminalPage data={data} onToast={notify} />}
      <Toast message={toast} />
    </DashboardLayout>
  );
}
