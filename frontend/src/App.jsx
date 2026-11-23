import { useEffect } from "react";
import { Link, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { ArrowLeft, ShoppingBag, Store } from "lucide-react";
import { useCart } from "./context/CartContext";
import WelcomePage from "./pages/WelcomePage";
import StorePage from "./pages/StorePage";
import CheckoutPage from "./pages/CheckoutPage";
import PaymentPage from "./pages/PaymentPage";
import PaymentResultPage from "./pages/PaymentResultPage";
import OrderProgressPage from "./pages/OrderProgressPage";
import NotFoundPage from "./pages/NotFoundPage";

export default function App() {
  const { itemCount, machine } = useCart();
  const location = useLocation();
  const navigate = useNavigate();
  const isCustomerFlow = ["/shop", "/checkout"].includes(location.pathname);

  useEffect(() => {
    if (!isCustomerFlow) return undefined;
    let timeoutId;
    const reset = () => {
      window.clearTimeout(timeoutId);
      timeoutId = window.setTimeout(() => {
        if (sessionStorage.getItem("smartvend-checkout-busy") === "true") {
          reset();
          return;
        }
        navigate("/");
      }, 90000);
    };
    ["pointerdown", "touchstart", "keydown"].forEach(eventName =>
      window.addEventListener(eventName, reset, { passive: true })
    );
    reset();
    return () => {
      window.clearTimeout(timeoutId);
      ["pointerdown", "touchstart", "keydown"].forEach(eventName =>
        window.removeEventListener(eventName, reset)
      );
    };
  }, [isCustomerFlow, navigate]);

  return <div className="app-shell kiosk-shell">
    <header className="kiosk-topbar">
      <Link className="brand" to="/"><span className="brand-mark"><Store size={22}/></span><span>SMART<span className="brand-accent">VEND</span></span></Link>
      <div className="kiosk-header-right">
        {machine && <span className={`machine-status ${machine.status === "online" ? "online" : "offline"}`}><i/>{machine.status === "online" ? "Machine online" : "Machine unavailable"}</span>}
        {location.pathname === "/shop" && <button className="header-cart" onClick={() => navigate("/checkout")}><ShoppingBag size={19}/><span>Cart</span><b>{itemCount}</b></button>}
        {["/shop", "/checkout"].includes(location.pathname) && <button className="header-home" onClick={() => navigate("/")} aria-label="Back to welcome"><ArrowLeft size={20}/></button>}
      </div>
    </header>
    <main className="kiosk-main"><Routes>
      <Route path="/" element={<WelcomePage/>}/>
      <Route path="/shop" element={<StorePage/>}/>
      <Route path="/checkout" element={<CheckoutPage/>}/>
      <Route path="/payment" element={<PaymentPage/>}/>
      <Route path="/payment/result" element={<PaymentResultPage/>}/>
      <Route path="/order/:orderId" element={<OrderProgressPage/>}/>
      <Route path="*" element={<NotFoundPage/>}/>
    </Routes></main>
    <footer className="kiosk-footer"><span>SMARTVEND · CASHLESS PICKUP</span><span>{machine?.machine_code || "Vending machine"} · Secure Chapa checkout</span></footer>
  </div>;
}
