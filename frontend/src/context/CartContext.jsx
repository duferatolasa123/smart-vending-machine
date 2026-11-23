import { createContext, useCallback, useContext, useMemo, useState } from "react";
const CartContext = createContext(null);
export function CartProvider({ children }) {
  const [items, setItems] = useState([]);
  const [machine, setMachine] = useState(null);
  const chooseMachine = useCallback((nextMachine) => {
    if (machine?.id !== nextMachine?.id) setItems([]);
    setMachine(nextMachine);
  }, [machine?.id]);
  const addItem = useCallback((product) => setItems(current => {
    const found = current.find(item => item.machine_slot_id === product.machine_slot_id);
    return found
      ? current.map(item => item.machine_slot_id === product.machine_slot_id ? { ...item, quantity: Math.min(item.quantity + 1, product.available_quantity) } : item)
      : [...current, { ...product, quantity: 1 }];
  }), []);
  const setQuantity = useCallback((slotId, quantity) => setItems(current => quantity <= 0
    ? current.filter(item => item.machine_slot_id !== slotId)
    : current.map(item => item.machine_slot_id === slotId ? { ...item, quantity: Math.min(quantity, item.available_quantity) } : item)), []);
  const clearCart = useCallback(() => setItems([]), []);
  const total = items.reduce((sum, item) => sum + item.price * item.quantity, 0);
  const itemCount = items.reduce((sum, item) => sum + item.quantity, 0);
  const value = useMemo(() => ({ items, machine, chooseMachine, addItem, setQuantity, clearCart, total, itemCount }), [items, machine, chooseMachine, addItem, setQuantity, clearCart, total, itemCount]);
  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}
export function useCart() {
  const context = useContext(CartContext);
  if (!context) throw new Error("useCart must be used inside CartProvider");
  return context;
}
