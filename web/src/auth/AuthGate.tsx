import { App } from "../App";
import { LoginScreen } from "../components/LoginScreen";
import { useAuth } from "./useAuth";

/**
 * Chooses between the login screen and the app.
 *
 * <App> is mounted only once access is permitted, which is what stops it from
 * fetching anything while signed out — and, on the way back out, unmounts the
 * scheduler panel so its polling interval stops with the session.
 */
export function AuthGate() {
  const { status, bootstrapError } = useAuth();

  if (status === "loading") {
    // Neutral placeholder: rendering the login form here would make it flash
    // for every already-signed-in visitor.
    return (
      <div className="grid min-h-dvh place-items-center" aria-busy="true">
        <span className="sr-only">Loading…</span>
      </div>
    );
  }

  if (status === "anon") {
    return <LoginScreen notice={bootstrapError} />;
  }

  return <App />;
}
