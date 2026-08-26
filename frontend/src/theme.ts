/**
 * Theme selection.
 *
 * Dark is the default because this console is watched for long stretches, but light mode is
 * a real, separately chosen set of steps in `styles.css` — not an automatic inversion — so the
 * toggle is safe to expose. The choice is remembered per browser.
 */

export type Theme = "dark" | "light";

const KEY = "ivp.theme";

export function readTheme(): Theme {
  try {
    return window.localStorage.getItem(KEY) === "light" ? "light" : "dark";
  } catch {
    return "dark";
  }
}

export function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  if (theme === "light") root.setAttribute("data-theme", "light");
  else root.removeAttribute("data-theme");
  try {
    window.localStorage.setItem(KEY, theme);
  } catch {
    // A browser with storage disabled still gets a working toggle for this session.
  }
}
