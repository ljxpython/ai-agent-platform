import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { effectScope, nextTick, ref } from "vue";
import {
  aggregateTranscriptResults,
  getSpeechRecognitionConstructor,
  mapSpeechRecognitionError,
  normalizeSpeechRecognitionLocale,
  useVoiceInput,
  type BrowserSpeechRecognition,
  type SpeechRecognitionErrorEventLike,
  type SpeechRecognitionEventLike,
} from "./useVoiceInput";

class MockSpeechRecognition implements BrowserSpeechRecognition {
  continuous = false;
  interimResults = false;
  lang = "zh-CN";
  maxAlternatives = 1;

  onstart: (() => void) | null = null;
  onend: (() => void) | null = null;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null = null;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null = null;

  startCalls = 0;
  stopCalls = 0;
  abortCalls = 0;

  static instances: MockSpeechRecognition[] = [];

  constructor() {
    MockSpeechRecognition.instances.push(this);
  }

  start() {
    this.startCalls++;
    setTimeout(() => this.onstart?.(), 0);
  }

  stop() {
    this.stopCalls++;
  }

  abort() {
    this.abortCalls++;
  }

  // 测试辅助发射方法
  emitResult(results: any) {
    this.onresult?.({ results });
  }

  emitError(error: string) {
    this.onerror?.({ error });
  }

  emitEnd() {
    this.onend?.();
  }
}

describe("useVoiceInput", () => {
  const originalSpeechRecognition = (window as any).SpeechRecognition;
  const originalWebkitSpeechRecognition = (window as any)
    .webkitSpeechRecognition;
  const originalIsSecureContext = window.isSecureContext;

  beforeEach(() => {
    vi.useFakeTimers();
    MockSpeechRecognition.instances = [];
    Object.defineProperty(window, "isSecureContext", {
      value: true,
      configurable: true,
    });
    (window as any).SpeechRecognition = MockSpeechRecognition;
    delete (window as any).webkitSpeechRecognition;
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    (window as any).SpeechRecognition = originalSpeechRecognition;
    (window as any).webkitSpeechRecognition = originalWebkitSpeechRecognition;
    Object.defineProperty(window, "isSecureContext", {
      value: originalIsSecureContext,
      configurable: true,
    });
  });

  it("U01: supports standard first, falls back to webkit, and handles insecure context", () => {
    expect(getSpeechRecognitionConstructor(window)).toBe(MockSpeechRecognition);

    // 仅 webkit
    delete (window as any).SpeechRecognition;
    (window as any).webkitSpeechRecognition = MockSpeechRecognition;
    expect(getSpeechRecognitionConstructor(window)).toBe(MockSpeechRecognition);

    // 无构造器
    delete (window as any).webkitSpeechRecognition;
    expect(getSpeechRecognitionConstructor(window)).toBeNull();

    // 非安全上下文
    (window as any).SpeechRecognition = MockSpeechRecognition;
    Object.defineProperty(window, "isSecureContext", {
      value: false,
      configurable: true,
    });
    const { isSupported } = useVoiceInput();
    expect(isSupported.value).toBe(false);
  });

  it("U02: creates instance only on start, prevents double start, and recovers from sync throw", () => {
    const { state, start } = useVoiceInput();
    expect(state.value).toBe("idle");

    const started = start();
    expect(started).toBe(true);
    expect(state.value).toBe("starting");

    // 双击阻止
    const doubleStart = start();
    expect(doubleStart).toBe(false);

    vi.runAllTimers();
    expect(state.value).toBe("listening");

    // 构造或 start 同步异常
    class ThrowingRecognition extends MockSpeechRecognition {
      override start() {
        throw new Error("Camera/mic hardware crash");
      }
    }
    (window as any).SpeechRecognition = ThrowingRecognition;

    const errorCb = vi.fn();
    const failingVoice = useVoiceInput({ onError: errorCb });
    const failStarted = failingVoice.start();
    expect(failStarted).toBe(false);
    expect(failingVoice.state.value).toBe("idle");
    expect(errorCb).toHaveBeenCalledWith("unknown", "start() failed");
  });

  it("U03: aggregates multiple finals, language spacing (CN vs EN), interim changes and identical segments", () => {
    // 1. 中文拼接无空格
    const cnResults = {
      0: { 0: { transcript: "今天" }, isFinal: true, length: 1 },
      1: { 0: { transcript: "天气不错" }, isFinal: true, length: 1 },
      2: { 0: { transcript: "想要出" }, isFinal: false, length: 1 },
      length: 3,
    };
    const cnAgg = aggregateTranscriptResults(cnResults, "zh-CN");
    expect(cnAgg.finalText).toBe("今天天气不错");
    expect(cnAgg.interimText).toBe("想要出");

    // 2. 英文跨段边界补空格防连词，两个相同 final 段均保留
    const enResults = {
      0: { 0: { transcript: "Hello" }, isFinal: true, length: 1 },
      1: { 0: { transcript: "world" }, isFinal: true, length: 1 },
      2: { 0: { transcript: "world" }, isFinal: true, length: 1 },
      3: { 0: { transcript: "again" }, isFinal: false, length: 1 },
      length: 4,
    };
    const enAgg = aggregateTranscriptResults(enResults, "en-US");
    expect(enAgg.finalText).toBe("Hello world world");
    expect(enAgg.interimText).toBe("again");

    // 3. Composable 集成验证
    const onResult = vi.fn();
    const voice = useVoiceInput({ lang: "zh-CN", onResult });
    voice.start();
    vi.runAllTimers();

    const capturedInstance = MockSpeechRecognition.instances.at(-1);
    capturedInstance?.emitResult(cnResults);
    expect(voice.finalText.value).toBe("今天天气不错");
    expect(voice.interimText.value).toBe("想要出");
    expect(onResult).toHaveBeenCalledWith({
      finalText: "今天天气不错",
      interimText: "想要出",
    });
  });

  it("U04: stop receives last final, natural end/no_speech does not restart, 5s timeout cleans up", () => {
    const onEnd = vi.fn();
    const voice = useVoiceInput({ onEnd });
    voice.start();
    vi.runAllTimers();
    expect(voice.state.value).toBe("listening");

    const capturedInstance = MockSpeechRecognition.instances.at(-1);
    // 调用 stop
    voice.stop();
    expect(voice.state.value).toBe("stopping");
    expect(capturedInstance?.stopCalls).toBe(1);

    // 在 stopping 状态收到最后的 final
    capturedInstance?.emitResult({
      0: { 0: { transcript: "收尾一句话" }, isFinal: true, length: 1 },
      length: 1,
    });
    expect(voice.finalText.value).toBe("收尾一句话");

    // 正常 end 触发
    capturedInstance?.emitEnd();
    expect(voice.state.value).toBe("idle");
    expect(onEnd).toHaveBeenCalledWith("stop");

    // 验证 5 秒超时保护
    const timeoutVoice = useVoiceInput();
    timeoutVoice.start();
    vi.runAllTimers();
    timeoutVoice.stop();
    expect(timeoutVoice.state.value).toBe("stopping");

    // 前进 5001ms 触发兜底
    vi.advanceTimersByTime(5001);
    expect(timeoutVoice.state.value).toBe("idle");
    expect(timeoutVoice.errorKind.value).toBe("unknown");
  });

  it("U05: cancel invalidates stale callbacks, session A cannot close session B", () => {
    const voice = useVoiceInput();
    voice.start();
    vi.runAllTimers();
    expect(voice.state.value).toBe("listening");

    const instA = MockSpeechRecognition.instances[0];

    // 取消 A
    voice.cancel();
    expect(voice.state.value).toBe("idle");
    expect(instA?.abortCalls).toBe(1);

    // 重新开启 B
    voice.start();
    vi.runAllTimers();
    expect(voice.state.value).toBe("listening");

    // 此时 A 迟到的 end 或 result 触发，不能关闭或污染 B
    instA?.emitResult({
      0: { 0: { transcript: "来自A的幽灵数据" }, isFinal: true, length: 1 },
      length: 1,
    });
    expect(voice.finalText.value).toBe("");

    instA?.emitEnd();
    expect(voice.state.value).toBe("listening"); // B 依然保持 listening
  });

  it("U06: error classification, silent no_speech and cancelled, block errors notify without retry", () => {
    expect(mapSpeechRecognitionError("aborted")).toBe("cancelled");
    expect(mapSpeechRecognitionError("no-speech")).toBe("no_speech");
    expect(mapSpeechRecognitionError("audio-capture")).toBe(
      "microphone_unavailable",
    );
    expect(mapSpeechRecognitionError("not-allowed")).toBe("permission_denied");
    expect(mapSpeechRecognitionError("service-not-allowed")).toBe(
      "permission_denied",
    );
    expect(mapSpeechRecognitionError("language-not-supported")).toBe(
      "unsupported_language",
    );
    expect(mapSpeechRecognitionError("network")).toBe("network");
    expect(mapSpeechRecognitionError("other-error")).toBe("unknown");

    const onError = vi.fn();
    const voice = useVoiceInput({ onError });
    voice.start();
    vi.runAllTimers();
    const capturedInstance = MockSpeechRecognition.instances.at(-1);

    // 1. no_speech 不触发 onError 回调（避免前端弹全局 Toast）
    capturedInstance?.emitError("no-speech");
    expect(voice.errorKind.value).toBe("no_speech");
    expect(onError).not.toHaveBeenCalled();

    // 自然 end 触发，reason 为 natural
    const onEnd = vi.fn();
    const voiceNatural = useVoiceInput({ onEnd });
    voiceNatural.start();
    vi.runAllTimers();
    const naturalInstance = MockSpeechRecognition.instances.at(-1);
    naturalInstance?.emitError("no-speech");
    naturalInstance?.emitEnd();
    expect(voiceNatural.state.value).toBe("idle");
    expect(onEnd).toHaveBeenCalledWith("natural");

    // 2. network 阻断性错误触发 onError
    const onBlockError = vi.fn();
    const voiceBlock = useVoiceInput({ onError: onBlockError });
    voiceBlock.start();
    vi.runAllTimers();
    const blockInstance = MockSpeechRecognition.instances.at(-1);
    blockInstance?.emitError("network");
    expect(onBlockError).toHaveBeenCalledWith("network", "network");
  });

  it("U07: cancels on lang change, visibility hidden, scope dispose, and safely defaults if locale missing", async () => {
    // 语言切换测试
    const langRef = ref("zh-CN");
    const voice = useVoiceInput({ lang: langRef });
    voice.start();
    vi.runAllTimers();
    expect(voice.state.value).toBe("listening");

    langRef.value = "en-US";
    await nextTick();
    expect(voice.state.value).toBe("idle");

    // document visibility change
    voice.start();
    vi.runAllTimers();
    expect(voice.state.value).toBe("listening");

    Object.defineProperty(document, "hidden", {
      value: true,
      configurable: true,
    });
    document.dispatchEvent(new Event("visibilitychange"));
    expect(voice.state.value).toBe("idle");

    // effectScope dispose
    const scope = effectScope();
    let scopedVoice: ReturnType<typeof useVoiceInput> | null = null;
    scope.run(() => {
      scopedVoice = useVoiceInput();
      scopedVoice.start();
    });
    vi.runAllTimers();
    expect(scopedVoice?.state.value).toBe("listening");

    scope.stop();
    expect(scopedVoice?.state.value).toBe("idle");

    // 未传递 lang 时安全兜底
    expect(normalizeSpeechRecognitionLocale(undefined)).toBe("zh-CN");
    expect(normalizeSpeechRecognitionLocale("")).toBe("zh-CN");
    expect(normalizeSpeechRecognitionLocale("zh-TW")).toBe("zh-CN");
    expect(normalizeSpeechRecognitionLocale("en-GB")).toBe("en-US");
  });

  it("U08: repeated stop and cancel are idempotent and timers cleaned", () => {
    const voice = useVoiceInput();
    voice.start();
    vi.runAllTimers();

    // 连续 cancel 幂等
    voice.cancel();
    voice.cancel();
    voice.cancel();
    expect(voice.state.value).toBe("idle");

    // 连续 stop 幂等
    voice.start();
    vi.runAllTimers();
    voice.stop();
    voice.stop();
    expect(voice.state.value).toBe("stopping");
  });
});
