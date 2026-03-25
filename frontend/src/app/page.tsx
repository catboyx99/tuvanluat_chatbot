'use client';
import { useChat } from '@ai-sdk/react';
import { useEffect, useRef, useState, useMemo } from 'react';
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

export default function Chat() {
  const { messages, sendMessage, status, error } = useChat();
  const mainRef = useRef<HTMLElement>(null);
  const [input, setInput] = useState('');
  const [delayNotice, setDelayNotice] = useState(false);

  const isStreaming = status === 'streaming';
  const isLoading = status === 'submitted' || isStreaming;

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
    sendMessage({ text: trimmed });
    setInput('');
  };

  return (
    <div className="flex flex-col h-screen bg-[#1e1e1e] text-gray-200 font-sans relative">
      <header className="bg-[#252526] p-5 flex items-center gap-3 shadow-lg fixed w-full top-0 start-0 z-10 border-b border-[#3c3c3c]">
        <Scale className="text-[#569cd6]" size={28} />
        <h1 className="text-[#cccccc] text-xl font-semibold tracking-wide">Trợ lý ảo tư vấn luật</h1>
      </header>

      <main ref={mainRef} className="flex-1 overflow-y-auto px-4 sm:px-6 w-full max-w-4xl mx-auto flex flex-col gap-6 pt-24 pb-32">
        {messages.length === 0 && (
          <div className="flex-1 flex flex-col items-center justify-center text-center opacity-80 mt-20">
            <Scale className="w-20 h-20 text-[#3c3c3c] mb-6" />
            <h2 className="text-2xl font-medium text-[#808080]">Bạn cần hỗ trợ pháp lý?</h2>
            <p className="text-[#6a6a6a] mt-2">Nhập câu hỏi để chúng tôi tư vấn Luật, nghị định, thông tư...</p>
          </div>
        )}

        {messages.map((m, idx) => {
          if (m.role === 'assistant' && !getMessageText(m)) return null;
          return (
          <div key={m.id} className={`flex w-full ${m.role === 'user' ? 'justify-end' : 'justify-start'} msg-appear`}>
            <div
              className={`px-5 py-4 max-w-[85%] rounded-3xl leading-relaxed shadow-sm text-[15.5px] ${
                m.role === 'user'
                ? 'bg-[#264f78] text-[#d4d4d4] rounded-tr-md whitespace-pre-wrap'
                : 'bg-[#2d2d2d] border border-[#3c3c3c] text-[#cccccc] rounded-tl-md'
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
          </div>
          );
        })}

        {delayNotice && (
           <div className="flex w-full justify-start msg-appear">
             <div className="px-5 py-4 bg-[#2d2d2d]/80 border border-[#3c3c3c]/60 text-[#808080] rounded-3xl rounded-tl-md max-w-[85%] leading-relaxed shadow-sm text-[15px]">
                <span className="flex items-center gap-3">
                    <Scale size={22} className="text-[#569cd6] scale-swing flex-shrink-0" />
                    {delayMsg}
                </span>
             </div>
           </div>
        )}
      </main>

      <div className="p-4 bg-gradient-to-t from-[#1e1e1e] md:bg-[#1e1e1e] md:bg-none flex-none border-t border-[#3c3c3c] fixed w-full bottom-0 left-0 flex justify-center md:pb-8 shadow-[0_-4px_10px_-4px_rgba(0,0,0,0.3)]">
        <form onSubmit={handleSubmit} className="relative w-full max-w-4xl flex items-center drop-shadow-lg">
          <input
            className="w-full px-6 py-4 pr-16 bg-[#3c3c3c] border border-[#4a4a4a] rounded-full focus:outline-none focus:ring-2 focus:ring-[#569cd6] focus:border-transparent transition-all text-base text-[#d4d4d4] placeholder-[#6a6a6a]"
            value={input}
            placeholder="Nhập câu hỏi, thủ tục pháp lý bạn thắc mắc..."
            onChange={(e) => setInput(e.target.value)}
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="absolute right-2 p-2.5 bg-[#569cd6] text-[#1e1e1e] rounded-full hover:bg-[#6eb0e6] disabled:bg-[#4a4a4a] disabled:text-[#6a6a6a] disabled:cursor-not-allowed transition-all"
          >
            <Send size={20} className={isLoading ? "opacity-50" : ""} />
          </button>
        </form>
      </div>
    </div>
  );
}
