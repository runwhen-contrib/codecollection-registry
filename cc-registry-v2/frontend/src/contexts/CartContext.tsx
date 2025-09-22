import React, { createContext, useContext, useState, ReactNode } from 'react';
import { Task } from '../services/api';

interface CartItem {
  task: Task;
  selected: boolean;
  addedAt: Date;
}

interface CartContextType {
  cartItems: CartItem[];
  addToCart: (task: Task) => void;
  removeFromCart: (taskId: string) => void;
  isInCart: (taskId: string) => boolean;
  clearCart: () => void;
  getCartCount: () => number;
  getSelectedTasks: () => Task[];
}

const CartContext = createContext<CartContextType | undefined>(undefined);

export const useCart = () => {
  const context = useContext(CartContext);
  if (!context) {
    throw new Error('useCart must be used within a CartProvider');
  }
  return context;
};

interface CartProviderProps {
  children: ReactNode;
}

export const CartProvider: React.FC<CartProviderProps> = ({ children }) => {
  const [cartItems, setCartItems] = useState<CartItem[]>([]);

  const addToCart = (task: Task) => {
    setCartItems(prev => {
      // Check if task is already in cart
      const existingIndex = prev.findIndex(item => item.task.id === task.id);
      if (existingIndex >= 0) {
        // Update existing item
        const updated = [...prev];
        updated[existingIndex] = {
          ...updated[existingIndex],
          selected: true,
          addedAt: new Date()
        };
        return updated;
      } else {
        // Add new item
        return [...prev, {
          task,
          selected: true,
          addedAt: new Date()
        }];
      }
    });
  };

  const removeFromCart = (taskId: string) => {
    setCartItems(prev => prev.filter(item => item.task.id !== taskId));
  };

  const isInCart = (taskId: string) => {
    return cartItems.some(item => item.task.id === taskId && item.selected);
  };

  const clearCart = () => {
    setCartItems([]);
  };

  const getCartCount = () => {
    return cartItems.filter(item => item.selected).length;
  };

  const getSelectedTasks = () => {
    return cartItems.filter(item => item.selected).map(item => item.task);
  };

  const value: CartContextType = {
    cartItems,
    addToCart,
    removeFromCart,
    isInCart,
    clearCart,
    getCartCount,
    getSelectedTasks
  };

  return (
    <CartContext.Provider value={value}>
      {children}
    </CartContext.Provider>
  );
};
