import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { CodeBundle } from '../services/api';

export interface CartItem {
  codebundle: CodeBundle;
  addedAt: string;
}

export interface RepositoryConfig {
  collection_name: string;
  collection_slug: string;
  git_url: string;
  git_ref?: string;
  codebundles: CartItem[];
}

interface CartContextType {
  items: CartItem[];
  addToCart: (codebundle: CodeBundle) => void;
  removeFromCart: (codebundleId: number) => void;
  clearCart: () => void;
  isInCart: (codebundleId: number) => boolean;
  getRepositoryConfigs: () => RepositoryConfig[];
  itemCount: number;
}

const CartContext = createContext<CartContextType | undefined>(undefined);

export const useCart = (): CartContextType => {
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
  const [items, setItems] = useState<CartItem[]>([]);

  // Load cart from localStorage on mount
  useEffect(() => {
    const savedCart = localStorage.getItem('runwhen-cart');
    if (savedCart) {
      try {
        const parsedCart = JSON.parse(savedCart);
        setItems(parsedCart);
      } catch (error) {
        console.error('Failed to parse saved cart:', error);
        localStorage.removeItem('runwhen-cart');
      }
    }
  }, []);

  // Save cart to localStorage whenever it changes
  useEffect(() => {
    localStorage.setItem('runwhen-cart', JSON.stringify(items));
  }, [items]);

  const addToCart = (codebundle: CodeBundle) => {
    if (!isInCart(codebundle.id)) {
      const newItem: CartItem = {
        codebundle,
        addedAt: new Date().toISOString()
      };
      setItems(prev => [...prev, newItem]);
    }
  };

  const removeFromCart = (codebundleId: number) => {
    setItems(prev => prev.filter(item => item.codebundle.id !== codebundleId));
  };

  const clearCart = () => {
    setItems([]);
  };

  const isInCart = (codebundleId: number): boolean => {
    return items.some(item => item.codebundle.id === codebundleId);
  };

  const getRepositoryConfigs = (): RepositoryConfig[] => {
    const configMap = new Map<string, RepositoryConfig>();

    items.forEach(item => {
      const collection = item.codebundle.codecollection;
      if (!collection) return;

      const key = `${collection.slug}`;
      
      if (!configMap.has(key)) {
        configMap.set(key, {
          collection_name: collection.name,
          collection_slug: collection.slug,
          git_url: collection.git_url,
          git_ref: collection.git_ref || 'main',
          codebundles: []
        });
      }

      configMap.get(key)!.codebundles.push(item);
    });

    return Array.from(configMap.values()).sort((a, b) => 
      a.collection_name.localeCompare(b.collection_name)
    );
  };

  const value: CartContextType = {
    items,
    addToCart,
    removeFromCart,
    clearCart,
    isInCart,
    getRepositoryConfigs,
    itemCount: items.length
  };

  return (
    <CartContext.Provider value={value}>
      {children}
    </CartContext.Provider>
  );
};