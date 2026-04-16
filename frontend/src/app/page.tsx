'use client';
import { useChat } from '@ai-sdk/react';
import { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import { Send, Scale } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

function TypingText({ text, isStreaming, onUpdate }: { text: string; isStreaming: boolean; onUpdate?: () => void }) {
  const [displayed, setDisplayed] = useState('');
  const targetRef = useRef(text);
  const indexRef = useRef(0);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    targetRef.current = text;
  }, [text]);

  useEffect(() => {
    let lastTime = 0;
    const speed = 4; // ms per character

    function tick(now: number) {
      if (!lastTime) lastTime = now;
      const elapsed = now - lastTime;
      const target = targetRef.current;

      if (indexRef.current < target.length) {
        const charsToAdd = Math.max(1, Math.floor(elapsed / speed));
        const nextIndex = Math.min(indexRef.current + charsToAdd, target.length);
        indexRef.current = nextIndex;
        setDisplayed(target.slice(0, nextIndex));
        lastTime = now;
        onUpdate?.();
      }

      rafRef.current = requestAnimationFrame(tick);
    }

    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, []);

  const showCursor = isStreaming || indexRef.current < targetRef.current.length;

  return (
    <span>
      <div className="markdown-body"><ReactMarkdown>{displayed}</ReactMarkdown></div>
      {showCursor && <span className="typing-cursor">|</span>}
    </span>
  );
}

function getMessageText(m: any): string {
  return m.parts?.filter((p: any) => p.type === 'text').map((p: any) => p.text).join('') || '';
}

function formatTimer(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  const minutes = Math.floor(ms / 60000);
  const seconds = Math.floor((ms % 60000) / 1000);
  return `${minutes}m:${seconds.toString().padStart(2, '0')}s`;
}

function ThinkingDots() {
  return (
    <span className="thinking-dots">
      <span>.</span><span>.</span><span>.</span>
    </span>
  );
}

export default function Chat() {
  const { messages, sendMessage, status, error } = useChat();
  const mainRef = useRef<HTMLElement>(null);
  const [input, setInput] = useState('');
  const [delayNotice, setDelayNotice] = useState(false);

  const isStreaming = status === 'streaming';
  const isLoading = status === 'submitted' || isStreaming;

  // Response Timer
  const [elapsedMs, setElapsedMs] = useState(0);
  const [finalTimes, setFinalTimes] = useState<Record<string, number>>({});
  const timerStartRef = useRef<number>(0);
  const timerRafRef = useRef<number>(0);
  const msgCountAtSubmitRef = useRef<number>(0);
  const timerRunningRef = useRef(false);

  const delayMessages = [
    "Đang lật giở hàng ngàn trang luật để tìm câu trả lời chính xác nhất...",
    "Hệ thống đang đối chiếu các điều khoản liên quan, bạn chờ chút nhé...",
    "Đang tra cứu cơ sở dữ liệu pháp luật, sắp có kết quả rồi...",
    "Luật sư ảo đang nghiên cứu hồ sơ của bạn, vui lòng đợi một chút...",
    "Đang rà soát các văn bản pháp quy để đưa ra tư vấn chính xác...",
    "Câu hỏi hay đấy! Đang tìm căn cứ pháp lý phù hợp nhất...",
    "Đang phân tích và đối chiếu các nguồn luật, chỉ một lát thôi...",
    "Hệ thống đang xử lý — mỗi câu trả lời đều cần độ chính xác cao nhất!",
  ];
  const [delayMsg, setDelayMsg] = useState(delayMessages[0]);

  const lastAssistantIdx = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'assistant') return i;
    }
    return -1;
  }, [messages]);

  const scrollToBottom = () => {
    const el = mainRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, delayNotice]);

  const lastAssistantHasContent = lastAssistantIdx >= 0 && !!getMessageText(messages[lastAssistantIdx]);

  // Start rAF timer loop
  const startTimerLoop = useCallback(() => {
    const tick = () => {
      if (timerStartRef.current) {
        setElapsedMs(Date.now() - timerStartRef.current);
      }
      timerRafRef.current = requestAnimationFrame(tick);
    };
    timerRafRef.current = requestAnimationFrame(tick);
  }, []);

  // Stop timer when a NEW assistant message has content
  useEffect(() => {
    if (!timerRunningRef.current) return;
    // Find assistant messages added after submit
    const assistantMessages = messages.filter(m => m.role === 'assistant');
    const newAssistants = assistantMessages.slice(Math.floor(msgCountAtSubmitRef.current / 2));
    const hasNewContent = newAssistants.some(m => !!getMessageText(m));
    if (hasNewContent && timerStartRef.current) {
      const final = Date.now() - timerStartRef.current;
      cancelAnimationFrame(timerRafRef.current);
      setElapsedMs(final);
      // Save final time for all new assistant messages
      const updates: Record<string, number> = {};
      newAssistants.forEach(m => { if (getMessageText(m)) updates[m.id] = final; });
      setFinalTimes(prev => ({ ...prev, ...updates }));
      timerStartRef.current = 0;
      timerRunningRef.current = false;
    }
  }, [messages]);

  useEffect(() => {
    if (isLoading && !lastAssistantHasContent) {
      setDelayMsg(delayMessages[Math.floor(Math.random() * delayMessages.length)]);
      setDelayNotice(true);
    } else if (lastAssistantHasContent || !isLoading) {
      setDelayNotice(false);
    }
  }, [isLoading, lastAssistantHasContent]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isLoading) return;
    // Start response timer
    cancelAnimationFrame(timerRafRef.current);
    timerStartRef.current = Date.now();
    timerRunningRef.current = true;
    msgCountAtSubmitRef.current = messages.length;
    setElapsedMs(0);
    startTimerLoop();
    sendMessage({ text: trimmed });
    setInput('');
  };

  return (
    <div className="flex flex-col h-screen bg-[#f0f4fb] text-gray-800 font-sans relative">
      {/* Header: navy đậm giống HUFLIT ACA */}
      <header className="bg-[#0d1b6e] p-5 flex items-center gap-3 shadow-md fixed w-full top-0 start-0 z-10">
        <Scale className="text-white" size={28} />
        <h1 className="text-white text-xl font-semibold tracking-wide">AI tư vấn pháp chế</h1>
      </header>

      <main ref={mainRef} className="flex-1 overflow-y-auto px-4 sm:px-6 w-full max-w-4xl mx-auto flex flex-col gap-6 pt-24 pb-32">
        {messages.length === 0 && (
          <div className="flex-1 flex flex-col items-center justify-center text-center opacity-80 mt-20">
            <Scale className="w-20 h-20 text-[#c5cfe8] mb-6" />
            <h2 className="text-2xl font-medium text-[#0d1b6e]">Bạn cần hỗ trợ pháp lý?</h2>
            <p className="text-[#6b7280] mt-2">Nhập câu hỏi để chúng tôi tư vấn Luật, nghị định, thông tư...</p>
          </div>
        )}

        {messages.map((m, idx) => {
          if (m.role === 'assistant' && !getMessageText(m)) return null;
          return (
          <div key={m.id} className={`flex flex-col w-full ${m.role === 'user' ? 'items-end' : 'items-start'} msg-appear`}>
            <div
              className={`px-5 py-4 max-w-[85%] rounded-3xl leading-relaxed shadow-sm text-[15.5px] ${
                m.role === 'user'
                ? 'bg-[#0d1b6e] text-white rounded-tr-md whitespace-pre-wrap'
                : 'bg-white border border-[#dde3f0] text-gray-800 rounded-tl-md'
              }`}
            >
              {m.role === 'assistant' && idx === lastAssistantIdx ? (
                <TypingText text={getMessageText(m)} isStreaming={isStreaming} onUpdate={scrollToBottom} />
              ) : m.role === 'assistant' ? (
                <div className="markdown-body"><ReactMarkdown>{getMessageText(m)}</ReactMarkdown></div>
              ) : (
                getMessageText(m)
              )}
            </div>
            {m.role === 'assistant' && finalTimes[m.id] && (
              <span className="text-[11px] text-[#9ca3af] mt-1 ml-2">{formatTimer(finalTimes[m.id])}</span>
            )}
          </div>
          );
        })}

        {delayNotice && (
           <div className="flex flex-col w-full items-start msg-appear">
             <div className="px-5 py-4 bg-white/90 border border-[#dde3f0] text-[#6b7280] rounded-3xl rounded-tl-md max-w-[85%] leading-relaxed shadow-sm text-[15px]">
                <span className="flex items-center gap-3">
                    <Scale size={22} className="text-[#0d1b6e] scale-swing flex-shrink-0" />
                    {delayMsg}
                </span>
             </div>
             <span className="text-[11px] text-[#9ca3af] mt-1 ml-2">Đang phân tích câu hỏi của bạn<ThinkingDots /> {formatTimer(elapsedMs)}</span>
           </div>
        )}
      </main>

      <div className="p-4 bg-[#f0f4fb] flex-none border-t border-[#dde3f0] fixed w-full bottom-0 left-0 flex justify-center md:pb-8 shadow-[0_-4px_10px_-4px_rgba(13,27,110,0.08)]">
        <form onSubmit={handleSubmit} className="relative w-full max-w-4xl flex items-center drop-shadow-sm">
          <input
            className="w-full px-6 py-4 pr-16 bg-white border border-[#c5cfe8] rounded-full focus:outline-none focus:ring-2 focus:ring-[#0d1b6e] focus:border-transparent transition-all text-base text-gray-800 placeholder-[#9ca3af]"
            value={input}
            placeholder="Nhập câu hỏi, thủ tục pháp lý bạn thắc mắc..."
            onChange={(e) => setInput(e.target.value)}
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="absolute right-2 p-2.5 bg-[#0d1b6e] text-white rounded-full hover:bg-[#1a2e9e] disabled:bg-[#c5cfe8] disabled:text-[#9ca3af] disabled:cursor-not-allowed transition-all"
          >
            <Send size={20} className={isLoading ? "opacity-50" : ""} />
          </button>
        </form>
      </div>
    </div>
  );
}
