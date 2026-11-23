import { useEffect, useState } from "react";
import { ArrowRight } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useCart } from "../context/CartContext";
import { apiRequest } from "../services/api";

export default function WelcomePage() {
  const navigate = useNavigate();
  const { machine, chooseMachine } = useCart();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    try {
      const activeOrder = JSON.parse(sessionStorage.getItem("smartvend-active-order") || "null");
      if (activeOrder?.orderId) {
        navigate(activeOrder.checkoutUrl
          ? `/payment?orderId=${encodeURIComponent(activeOrder.orderId)}`
          : "/checkout", { replace: true });
        return undefined;
      }
    } catch {
      sessionStorage.removeItem("smartvend-active-order");
    }
    let active = true;
    apiRequest("/api/machines/")
      .then(machines => {
        if (!active) return;
        const selected = machines.find(item => item.id === machine?.id)
          || machines.find(item => item.status === "online" && item.is_active)
          || machines[0]
          || null;
        chooseMachine(selected);
      })
      .catch(() => {})
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [navigate]);

  const isOnline = machine?.status === "online" && machine?.is_active;

  return <section className="welcome-screen kiosk-welcome-minimal">
    <span className="welcome-spark welcome-spark-one"/>
    <span className="welcome-spark welcome-spark-two"/>
    <div className="welcome-minimal-content">
      <span className="welcome-mini-machine">{machine?.name || "SMARTVEND"}</span>
      <h1>Pick a treat.</h1>
      <button className="start-shopping" disabled={!isOnline || loading} onClick={() => navigate("/shop")}>
        <span>{loading ? "READY IN A MOMENT" : isOnline ? "START" : "UNAVAILABLE"}</span><ArrowRight size={24}/>
      </button>
    </div>
  </section>;
}
