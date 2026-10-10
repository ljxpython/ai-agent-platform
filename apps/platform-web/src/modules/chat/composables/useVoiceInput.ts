import {
  computed,
  getCurrentScope,
  onScopeDispose,
  ref,
  toValue,
  watch,
  type MaybeRefOrGetter,
} from "vue";

export type SpeechRecognitionErrorCode =
  | "aborted"
  | "audio-capture"
  | "bad-grammar"
  | "language-not-supported"
  | "network"
  | "no-speech"
  | "not-allowed"
  | "phrases-not-supported"
  | "service-not-allowed";

export type VoiceInputErrorKind =
  | "cancelled"
  | "microphone_unavailable"
  | "permission_denied"
  | "unsupported_language"
  | "network"
  | "no_speech"
  | "unknown";

export type VoiceInputState = "idle" | "starting" | "listening" | "stopping";

export type SpeechRecognitionConstructor = new () => BrowserSpeechRecognition;

export interface SpeechRecognitionAlternativeLike {
  transcript?: string;
}

export interface SpeechRecognitionResultLike {
  0?: SpeechRecognitionAlternativeLike;
  isFinal: boolean;
  length: number;
}

export interface SpeechRecognitionResultListLike {
  [index: number]: SpeechRecognitionResultLike | undefined;
  length: number;
}

export interface SpeechRecognitionEventLike {
  results: SpeechRecognitionResultListLike;
}

export interface SpeechRecognitionErrorEventLike {
  error?: SpeechRecognitionErrorCode | string;
}

export interface BrowserSpeechRecognition {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  maxAlternatives: number;
  onstart: (() => void) | null;
  onend: (() => void) | null;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
}

type SpeechRecognitionWindow = Window &
  typeof globalThis & {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  };

export interface UseVoiceInputOptions {
  lang?: MaybeRefOrGetter<string>;
  onResult?: (result: { finalText: string; interimText: string }) => void;
  onError?: (error: VoiceInputErrorKind, rawError?: string) => void;
  onEnd?: (reason: "stop" | "cancel" | "natural" | "error") => void;
}

export function getSpeechRecognitionConstructor(
  win: unknown = typeof window !== "undefined" ? window : globalThis,
): SpeechRecognitionConstructor | null {
  const maybeWindow = win as Partial<SpeechRecognitionWindow> | undefined;
  return (
    maybeWindow?.SpeechRecognition ??
    maybeWindow?.webkitSpeechRecognition ??
    null
  );
}

export function normalizeSpeechRecognitionLocale(locale?: string): string {
  if (!locale) return "zh-CN";
  const trimmed = locale.trim().toLowerCase();
  if (trimmed.startsWith("zh")) {
    return "zh-CN";
  }
  return "en-US";
}

export function mapSpeechRecognitionError(
  error?: SpeechRecognitionErrorCode | string,
): VoiceInputErrorKind {
  switch (error) {
    case "aborted":
      return "cancelled";
    case "audio-capture":
      return "microphone_unavailable";
    case "not-allowed":
    case "service-not-allowed":
      return "permission_denied";
    case "language-not-supported":
      return "unsupported_language";
    case "network":
      return "network";
    case "no-speech":
      return "no_speech";
    default:
      return "unknown";
  }
}

export function aggregateTranscriptResults(
  results: SpeechRecognitionResultListLike,
  lang: string,
): { finalText: string; interimText: string } {
  const isEn = lang.startsWith("en");
  let finalAccumulator = "";
  let interimAccumulator = "";

  const count = results.length || 0;
  for (let i = 0; i < count; i++) {
    const item = results[i];
    if (!item) continue;
    const text = item[0]?.transcript ?? "";
    if (!text) continue;

    if (item.isFinal) {
      if (!finalAccumulator) {
        finalAccumulator = text.trim();
      } else {
        if (isEn) {
          const needsSpace =
            !finalAccumulator.endsWith(" ") && !text.startsWith(" ");
          finalAccumulator += needsSpace ? ` ${text.trim()}` : text;
        } else {
          finalAccumulator += text;
        }
      }
    } else {
      if (!interimAccumulator) {
        interimAccumulator = text;
      } else {
        if (isEn) {
          const needsSpace =
            !interimAccumulator.endsWith(" ") && !text.startsWith(" ");
          interimAccumulator += needsSpace ? ` ${text}` : text;
        } else {
          interimAccumulator += text;
        }
      }
    }
  }

  return {
    finalText: finalAccumulator,
    interimText: interimAccumulator,
  };
}

export function useVoiceInput(options: UseVoiceInputOptions = {}) {
  const state = ref<VoiceInputState>("idle");
  const finalText = ref("");
  const interimText = ref("");
  const errorKind = ref<VoiceInputErrorKind | null>(null);

  const isSupported = computed(() => {
    if (typeof window === "undefined") return false;
    if (!window.isSecureContext) return false;
    return Boolean(getSpeechRecognitionConstructor(window));
  });

  let activeInstance: BrowserSpeechRecognition | null = null;
  let currentSessionId = 0;
  let stopTimeoutTimer: ReturnType<typeof setTimeout> | null = null;
  let stopRequested = false;

  function clearStopTimer() {
    if (stopTimeoutTimer) {
      clearTimeout(stopTimeoutTimer);
      stopTimeoutTimer = null;
    }
  }

  function resolveLanguage(): string {
    try {
      const rawLang = options.lang ? toValue(options.lang) : "zh-CN";
      return normalizeSpeechRecognitionLocale(rawLang);
    } catch {
      return "zh-CN";
    }
  }

  function cleanupActiveInstance(
    reason: "stop" | "cancel" | "natural" | "error",
  ) {
    clearStopTimer();
    const inst = activeInstance;
    activeInstance = null;
    currentSessionId++;
    stopRequested = false;

    if (inst) {
      inst.onstart = null;
      inst.onresult = null;
      inst.onerror = null;
      inst.onend = null;
    }

    state.value = "idle";
    interimText.value = "";
    options.onEnd?.(reason);
  }

  function cancel() {
    if (!activeInstance && state.value === "idle") return;
    const inst = activeInstance;
    clearStopTimer();
    activeInstance = null;
    currentSessionId++;
    stopRequested = false;

    if (inst) {
      inst.onstart = null;
      inst.onresult = null;
      inst.onerror = null;
      inst.onend = null;
      try {
        inst.abort();
      } catch {
        /* ignore abort error on closed recognition */
      }
    }

    state.value = "idle";
    interimText.value = "";
    options.onEnd?.("cancel");
  }

  function stop() {
    if (state.value === "starting") {
      cancel();
      return;
    }
    if (state.value !== "listening" || !activeInstance) {
      return;
    }

    state.value = "stopping";
    stopRequested = true;

    // 5秒收尾兜底超时
    clearStopTimer();
    const sessionId = currentSessionId;
    stopTimeoutTimer = setTimeout(() => {
      if (currentSessionId !== sessionId || state.value !== "stopping") return;
      errorKind.value = "unknown";
      options.onError?.("unknown", "stop timeout");
      cancel();
    }, 5000);

    try {
      activeInstance.stop();
    } catch {
      cleanupActiveInstance("error");
    }
  }

  function start(): boolean {
    if (!isSupported.value) return false;
    if (state.value !== "idle") return false;

    const Ctor = getSpeechRecognitionConstructor();
    if (!Ctor) return false;

    const targetLang = resolveLanguage();
    currentSessionId++;
    const sessionId = currentSessionId;
    stopRequested = false;
    errorKind.value = null;
    finalText.value = "";
    interimText.value = "";
    clearStopTimer();

    let recognition: BrowserSpeechRecognition;
    try {
      recognition = new Ctor();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.maxAlternatives = 1;
      recognition.lang = targetLang;
    } catch {
      state.value = "idle";
      errorKind.value = "unknown";
      options.onError?.("unknown", "Constructor failed");
      return false;
    }

    activeInstance = recognition;
    state.value = "starting";

    recognition.onstart = () => {
      if (currentSessionId !== sessionId || activeInstance !== recognition)
        return;
      state.value = "listening";
    };

    recognition.onresult = (event) => {
      if (currentSessionId !== sessionId || activeInstance !== recognition)
        return;
      const { finalText: aggFinal, interimText: aggInterim } =
        aggregateTranscriptResults(event.results, targetLang);

      finalText.value = aggFinal;
      interimText.value = aggInterim;
      options.onResult?.({ finalText: aggFinal, interimText: aggInterim });
    };

    recognition.onerror = (event) => {
      if (currentSessionId !== sessionId || activeInstance !== recognition)
        return;
      const kind = mapSpeechRecognitionError(event.error);
      errorKind.value = kind;

      if (kind !== "cancelled" && kind !== "no_speech") {
        options.onError?.(
          kind,
          typeof event.error === "string" ? event.error : undefined,
        );
      }
    };

    recognition.onend = () => {
      if (currentSessionId !== sessionId || activeInstance !== recognition)
        return;
      const currentErr = errorKind.value;
      const reason = stopRequested
        ? "stop"
        : currentErr && currentErr !== "cancelled" && currentErr !== "no_speech"
          ? "error"
          : "natural";

      cleanupActiveInstance(reason);
    };

    try {
      recognition.start();
      return true;
    } catch {
      cleanupActiveInstance("error");
      errorKind.value = "unknown";
      options.onError?.("unknown", "start() failed");
      return false;
    }
  }

  // 监听语言变化，进行中则取消
  if (options.lang) {
    watch(
      () => {
        try {
          return toValue(options.lang);
        } catch {
          return "zh-CN";
        }
      },
      (newLang, oldLang) => {
        if (newLang !== oldLang && state.value !== "idle") {
          cancel();
        }
      },
      { flush: "sync" },
    );
  }

  // 页面离开 / hidden 自动安全取消
  function handleVisibilityChange() {
    if (typeof document !== "undefined" && document.hidden) {
      if (state.value !== "idle") {
        cancel();
      }
    }
  }

  if (typeof document !== "undefined") {
    document.addEventListener("visibilitychange", handleVisibilityChange);
  }

  if (getCurrentScope()) {
    onScopeDispose(() => {
      if (typeof document !== "undefined") {
        document.removeEventListener(
          "visibilitychange",
          handleVisibilityChange,
        );
      }
      cancel();
    });
  }

  return {
    isSupported,
    state,
    finalText,
    interimText,
    errorKind,
    start,
    stop,
    cancel,
  };
}
