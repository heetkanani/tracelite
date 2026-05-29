"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import {
  getMe,
  login as apiLogin,
  logout as apiLogout,
  signup as apiSignup,
  UnauthorizedError,
} from "@/lib/api";
import type {
  LoginRequest,
  SignupRequest,
  UserResponse,
} from "@/lib/types";

// ----------------------------------------------------------------------
// Context shape
// ----------------------------------------------------------------------

interface AuthContextValue {
  /**
   * The currently authenticated user, null if logged out,
   * undefined if still bootstrapping (haven't called /me yet).
   *
   * Why three states: distinguishing "loading" from "logged out" prevents
   * us from showing the login screen during the initial /me round-trip.
   */
  user: UserResponse | null | undefined;

  /** True only during the very first bootstrap of /me. */
  isLoading: boolean;

  /** Convenience flag. False during isLoading too. */
  isAuthenticated: boolean;

  /** Log in; on success, user is populated. */
  login: (payload: LoginRequest) => Promise<void>;

  /** Sign up; on success, user is populated. */
  signup: (payload: SignupRequest) => Promise<void>;

  /** Log out; clears cookie + user. */
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

// ----------------------------------------------------------------------
// Provider
// ----------------------------------------------------------------------

export function AuthProvider({ children }: { children: ReactNode }) {
  // undefined = still bootstrapping (haven't checked /me yet)
  // null      = checked, no session
  // object    = logged in
  const [user, setUser] = useState<UserResponse | null | undefined>(undefined);

  // Bootstrap: on mount, try to load the current user via the cookie.
  useEffect(() => {
    let cancelled = false;

    getMe()
      .then((u) => {
        if (!cancelled) setUser(u);
      })
      .catch((e) => {
        if (cancelled) return;
        if (e instanceof UnauthorizedError) {
          setUser(null); // No session — that's fine, user just isn't logged in.
        } else {
          // Real error (network, 500, etc.) — log it but treat as logged out
          // so the user can still try to log in.
          console.error("Auth bootstrap failed:", e);
          setUser(null);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  // ----------------------------------------------------------------------
  // Mutations
  // ----------------------------------------------------------------------

  const login = useCallback(async (payload: LoginRequest) => {
    const result = await apiLogin(payload);
    setUser(result.user);
  }, []);

  const signup = useCallback(async (payload: SignupRequest) => {
    const result = await apiSignup(payload);
    setUser(result.user);
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiLogout();
    } catch (e) {
      // Even if the request fails (network down, etc.), clear local state.
      // The user clicked logout — respect their intent.
      console.error("Logout request failed:", e);
    }
    setUser(null);
  }, []);

  // ----------------------------------------------------------------------
  // Render
  // ----------------------------------------------------------------------

  const value: AuthContextValue = {
    user,
    isLoading: user === undefined,
    isAuthenticated: user !== null && user !== undefined,
    login,
    signup,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ----------------------------------------------------------------------
// Hook
// ----------------------------------------------------------------------

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (ctx === undefined) {
    throw new Error("useAuth() must be used inside <AuthProvider>");
  }
  return ctx;
}