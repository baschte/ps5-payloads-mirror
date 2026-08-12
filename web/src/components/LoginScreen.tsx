import { useRef, useState } from "react";
import type { FormEvent } from "react";

import { useAuth } from "../auth/useAuth";
import { Logo } from "./icons";

interface LoginScreenProps {
  /** Shown above the form when the session could not be checked at all. */
  notice?: string | null;
}

/**
 * Sign-in screen, rendered in place of the app while there is no session.
 *
 * A real <form> so Enter submits, browsers offer to save the credentials, and
 * password managers can fill them — hence the autoComplete hints below.
 */
export function LoginScreen({ notice }: LoginScreenProps) {
  const { signIn } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const passwordRef = useRef<HTMLInputElement>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;

    setSubmitting(true);
    setError(null);
    try {
      await signIn(username, password);
      // On success this component unmounts — the gate swaps in the app.
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed.");
      // Never leave a rejected password in the field; put the cursor back
      // where the correction has to happen. This works only because the
      // inputs stay enabled while submitting — focus() on a disabled element
      // is silently ignored.
      setPassword("");
      passwordRef.current?.focus();
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-dvh max-w-md flex-col justify-center px-5 py-10">
      <div className="card animate-rise px-7 py-8">
        <div className="flex items-center gap-3.5">
          <Logo />
          <div>
            <h1 className="font-display text-2xl font-bold leading-none tracking-tight text-ink">
              Payloads Mirror
            </h1>
            <p className="mt-1.5 text-[0.95rem] text-muted">
              Sign in to manage the collection
            </p>
          </div>
        </div>

        {notice && (
          <p className="mt-6 rounded-xl border border-line-strong bg-paper/60 px-3.5 py-2.5 text-sm text-muted">
            {notice}
          </p>
        )}

        {/* Inputs stay enabled while submitting (only the button locks) so the
            failure path can put focus straight back into the password field. */}
        <form
          className="mt-7 flex flex-col gap-4"
          onSubmit={handleSubmit}
          aria-busy={submitting}
        >
          <div>
            <label className="label" htmlFor="login-username">
              Username
            </label>
            <input
              id="login-username"
              className="input"
              type="text"
              name="username"
              autoComplete="username"
              autoFocus
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
          </div>

          <div>
            <label className="label" htmlFor="login-password">
              Password
            </label>
            <input
              id="login-password"
              ref={passwordRef}
              className="input"
              type="password"
              name="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          {/* role="alert" is announced by screen readers the moment it appears. */}
          {error && (
            <p
              role="alert"
              className="rounded-xl border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-600
                dark:border-red-500/40 dark:bg-red-500/10 dark:text-red-400"
            >
              {error}
            </p>
          )}

          <button
            type="submit"
            className="btn btn-md btn-primary mt-1 w-full"
            disabled={submitting}
          >
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}
