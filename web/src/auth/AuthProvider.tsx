import { createContext, useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import {
  getSession,
  login as loginRequest,
  logout as logoutRequest,
  setUnauthorizedHandler,
} from "../api";
import { ApiError } from "../types";

/**
 * - `loading`  — the session has not been determined yet. Render neither the
 *                app nor the login form, or a signed-in user sees the login
 *                screen flash on every reload.
 * - `anon`     — a login is required and we do not have one.
 * - `authed`   — signed in.
 * - `disabled` — this deployment has no credentials configured, so there is
 *                nothing to sign in to and no sign-out control to show.
 */
export type AuthStatus = "loading" | "anon" | "authed" | "disabled";

export interface AuthContextValue {
  status: AuthStatus;
  username: string | null;
  /** Set when the session could not be checked at all (backend unreachable). */
  bootstrapError: string | null;
  signIn: (username: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [username, setUsername] = useState<string | null>(null);
  const [bootstrapError, setBootstrapError] = useState<string | null>(null);

  // Effect: register the global 401 handler with the API client (external
  // system). Runs before any protected call can happen, because the app tree
  // that makes those calls only mounts once `status` has left "loading".
  useEffect(() => {
    setUnauthorizedHandler(() => {
      // Functional update: this closure outlives many renders.
      setStatus((prev) => (prev === "disabled" ? prev : "anon"));
      setUsername(null);
    });
    return () => setUnauthorizedHandler(null);
  }, []);

  // Effect: determine the session once on mount (external system). The
  // `ignore` flag is the documented guard against a late response landing
  // after unmount — and it makes StrictMode's double-invoke a no-op.
  useEffect(() => {
    let ignore = false;

    getSession()
      .then((session) => {
        if (ignore) return;
        setBootstrapError(null);
        if (!session.auth_enabled) {
          setUsername(null);
          setStatus("disabled");
          return;
        }
        setUsername(session.username ?? null);
        setStatus("authed");
      })
      .catch((err: unknown) => {
        if (ignore) return;
        setUsername(null);
        setStatus("anon");
        // A 401 is the normal "not signed in" answer. Anything else means we
        // could not ask at all — say so on the login screen rather than
        // leaving the user on an endless loading state.
        setBootstrapError(
          err instanceof ApiError && err.status === 401
            ? null
            : err instanceof Error
              ? `Could not reach the server: ${err.message}`
              : "Could not reach the server.",
        );
      });

    return () => {
      ignore = true;
    };
  }, []);

  const signIn = useCallback(async (user: string, password: string) => {
    // Errors propagate on purpose — the login form shows them inline.
    const session = await loginRequest(user, password);
    setBootstrapError(null);
    setUsername(session.username ?? null);
    setStatus(session.auth_enabled ? "authed" : "disabled");
  }, []);

  const signOut = useCallback(async () => {
    try {
      await logoutRequest();
    } catch {
      // Clearing the cookie server-side failed, but leaving the user in the
      // app would be worse than signing them out locally: the next protected
      // call would 401 and drop them at the login screen anyway.
    }
    setUsername(null);
    setStatus("anon");
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ status, username, bootstrapError, signIn, signOut }),
    [status, username, bootstrapError, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
