import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

export interface User {
  id: string;
  email: string;
  name: string;
  domain?: string;
  roles?: string[];
  created_at?: string;
  last_login?: string;
  is_active?: boolean;
}

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<boolean>;
  logout: () => void;
  // Future OAuth methods
  loginWithGoogle?: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Check for existing session on mount
  useEffect(() => {
    const checkAuthStatus = () => {
      const storedUser = localStorage.getItem('auth_user');
      const storedToken = localStorage.getItem('auth_token');
      
      if (storedUser && storedToken) {
        try {
          const userData = JSON.parse(storedUser);
          setUser(userData);
        } catch (error) {
          console.error('Invalid stored user data:', error);
          localStorage.removeItem('auth_user');
          localStorage.removeItem('auth_token');
        }
      }
      setIsLoading(false);
    };

    checkAuthStatus();
  }, []);

  const login = async (email: string, password: string): Promise<boolean> => {
    setIsLoading(true);
    
    try {
      // For now, implement simple admin login
      // This will be replaced with proper backend authentication
      if (email === 'admin@runwhen.com' && password === 'admin-dev-password') {
        const userData: User = {
          id: 'admin-1',
          email: 'admin@runwhen.com',
          name: 'Administrator',
          domain: 'runwhen.com',
          roles: ['admin']
        };
        
        const token = 'admin-dev-token'; // This matches the backend admin token
        
        setUser(userData);
        localStorage.setItem('auth_user', JSON.stringify(userData));
        localStorage.setItem('auth_token', token);
        
        setIsLoading(false);
        return true;
      }
      
      // Future: Call backend authentication API
      // const response = await fetch('/api/v1/auth/login', {
      //   method: 'POST',
      //   headers: { 'Content-Type': 'application/json' },
      //   body: JSON.stringify({ email, password })
      // });
      
      setIsLoading(false);
      return false;
    } catch (error) {
      console.error('Login error:', error);
      setIsLoading(false);
      return false;
    }
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem('auth_user');
    localStorage.removeItem('auth_token');
  };

  // Future Google OAuth login
  const loginWithGoogle = async () => {
    // TODO: Implement Google OAuth integration
    // 1. Install @google-cloud/oauth2 or similar OAuth library
    // 2. Configure Google OAuth client ID and domain restrictions
    // 3. Handle OAuth flow and token exchange
    // 4. Create/update user in backend with domain validation
    // 5. Store JWT token and user data
    // 6. Redirect to original destination
    console.log('Google OAuth login - to be implemented');
    throw new Error('Google OAuth not yet implemented');
  };

  const value: AuthContextType = {
    user,
    isAuthenticated: !!user,
    isLoading,
    login,
    logout,
    loginWithGoogle
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

// Helper function to get auth token for API calls
export const getAuthToken = (): string | null => {
  return localStorage.getItem('auth_token');
};

// Helper function to check if user has specific role
export const hasRole = (user: User | null, role: string): boolean => {
  return user?.roles?.includes(role) || false;
};

// Helper function to check if user is from allowed domain
export const isAllowedDomain = (user: User | null, allowedDomains: string[]): boolean => {
  if (!user?.domain) return false;
  return allowedDomains.includes(user.domain);
};
