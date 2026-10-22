import { ref } from "vue";

import { LARGE_TEXT_STORAGE_KEY, THEME_STORAGE_KEY } from "./storageKeys";

export type Theme = "light" | "dark";

const theme = ref<Theme>("light");
const largeText = ref(false);
let initialized = false;

export function initializePreferences(): void {
  if (initialized) return;
  initialized = true;

  theme.value = readTheme();
  largeText.value = readLargeText();
  applyTheme(theme.value);
  applyLargeText(largeText.value);
}

export function usePreferences() {
  initializePreferences();

  function setTheme(next: Theme): void {
    theme.value = next;
    applyTheme(next);
    writePreference(THEME_STORAGE_KEY, next);
  }

  function toggleTheme(): void {
    setTheme(theme.value === "dark" ? "light" : "dark");
  }

  function setLargeText(enabled: boolean): void {
    largeText.value = enabled;
    applyLargeText(enabled);
    writePreference(LARGE_TEXT_STORAGE_KEY, enabled ? "1" : "0");
  }

  function toggleLargeText(): void {
    setLargeText(!largeText.value);
  }

  return {
    theme,
    largeText,
    setTheme,
    toggleTheme,
    setLargeText,
    toggleLargeText,
  };
}

function readTheme(): Theme {
  try {
    return localStorage.getItem(THEME_STORAGE_KEY) === "dark" ? "dark" : "light";
  } catch {
    return "light";
  }
}

function readLargeText(): boolean {
  try {
    return localStorage.getItem(LARGE_TEXT_STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

function applyTheme(next: Theme): void {
  document.documentElement.dataset.theme = next;
}

function applyLargeText(enabled: boolean): void {
  if (enabled) {
    document.documentElement.dataset.largeText = "1";
  } else {
    delete document.documentElement.dataset.largeText;
  }
}

function writePreference(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    // The current page keeps the selected preference in memory.
  }
}
