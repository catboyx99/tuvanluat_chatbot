'use client';
import { useChat } from '@ai-sdk/react';
import { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import { Send, Scale, FileDown, RefreshCw } from 'lucide-react';

const GEMINI_OVERLOAD_SENTINEL = '__GEMINI_OVERLOAD__';
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

// Định dạng thời gian kiểu Việt Nam: "Thứ Hai, ngày 21 tháng 4 năm 2026, 14:35:22"
function formatVNTime(d: Date): string {
  const days = ['Chủ nhật', 'Thứ Hai', 'Thứ Ba', 'Thứ Tư', 'Thứ Năm', 'Thứ Sáu', 'Thứ Bảy'];
  const hh = d.getHours().toString().padStart(2, '0');
  const mm = d.getMinutes().toString().padStart(2, '0');
  const ss = d.getSeconds().toString().padStart(2, '0');
  return `${days[d.getDay()]}, ngày ${d.getDate()} tháng ${d.getMonth() + 1} năm ${d.getFullYear()}, ${hh}:${mm}:${ss}`;
}

// Tao ten file PDF dang: tu-van-luat_2026-04-21_14-35.pdf
function pdfFilename(d: Date): string {
  const pad = (n: number) => n.toString().padStart(2, '0');
  return `tu-van-luat_${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}_${pad(d.getHours())}-${pad(d.getMinutes())}.pdf`;
}

// Export noi dung 1 bubble assistant ra PDF.
// Clone node render san (markdown da thanh HTML) -> wrap header/footer -> html2pdf.
async function exportBubbleToPdf(messageId: string, timestamp: string) {
  const sourceNode = document.querySelector<HTMLElement>(`[data-pdf-message-id="${messageId}"]`);
  if (!sourceNode) return;

  const contentClone = sourceNode.cloneNode(true) as HTMLElement;
  // Xoa cursor typing va timestamp noi bo neu co
  contentClone.querySelectorAll('.typing-cursor, .pdf-exclude').forEach(el => el.remove());

  // Xay wrapper PDF: header + body + footer
  const wrapper = document.createElement('div');
  wrapper.className = 'pdf-export';
  // Width 720px de lai bien an toan cho A4 (794px la canh), tranh cat chu
  wrapper.style.cssText = 'padding:32px;font-family:Inter,Segoe UI,sans-serif;color:#1f2937;background:#ffffff;width:720px;box-sizing:border-box;word-wrap:break-word;overflow-wrap:break-word;';
  wrapper.innerHTML = `
    <style>
      /* Tu render bullet bang ::before de chu dong vi tri (html2canvas khong render ::marker tot) */
      .pdf-export ul, .pdf-export ol { padding-left: 0; margin: 8px 0; list-style: none; counter-reset: pdflist; }
      .pdf-export li { margin-bottom: 6px; padding-left: 22px; position: relative; page-break-inside: avoid; break-inside: avoid; }
      .pdf-export ul > li::before {
        content: "•";
        position: absolute;
        left: 6px;
        top: 0;
        line-height: 1.7;
        color: #1f2937;
      }
      .pdf-export ol { counter-reset: pdflist; }
      .pdf-export ol > li { counter-increment: pdflist; }
      .pdf-export ol > li::before {
        content: counter(pdflist) ".";
        position: absolute;
        left: 0;
        top: 0;
        line-height: 1.7;
        color: #1f2937;
      }
      .pdf-export p { margin: 8px 0; page-break-inside: avoid; break-inside: avoid; }
      .pdf-export strong { color: #0d1b6e; font-weight: 700; }
      .pdf-export h1, .pdf-export h2, .pdf-export h3 { color: #0d1b6e; margin: 12px 0 6px 0; page-break-after: avoid; }
      .pdf-export * { box-sizing: border-box; max-width: 100%; }
    </style>
    <div style="border-bottom:2px solid #0d1b6e;padding-bottom:12px;margin-bottom:20px;">
      <h1 style="color:#0d1b6e;font-size:22px;font-weight:700;margin:0;">AI tư vấn pháp luật</h1>
      <p style="color:#6b7280;font-size:13px;margin:6px 0 0 0;">${timestamp}</p>
    </div>
    <div id="pdf-body" style="font-size:14px;line-height:1.7;"></div>
    <div style="border-top:1px solid #dde3f0;margin-top:24px;padding-top:12px;color:#9ca3af;font-size:11px;font-style:italic;">
      Nội dung mang tính tham khảo, không thay thế tư vấn chính thức của luật sư. Hệ thống AI có thể có sai sót.
    </div>
  `;
  wrapper.querySelector('#pdf-body')!.appendChild(contentClone);

  // html2pdf dung window nen phai dynamic import
  const html2pdf = (await import('html2pdf.js')).default;
  const filename = pdfFilename(new Date());
  await html2pdf()
    .from(wrapper)
    .set({
      margin: [10, 10, 10, 10],
      filename,
      image: { type: 'jpeg', quality: 0.98 },
      html2canvas: { scale: 2, useCORS: true, backgroundColor: '#ffffff' },
      jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' },
      pagebreak: { mode: ['css', 'legacy'], avoid: ['li', 'p', 'tr'] },
    })
    .save();
}

export default function Chat() {
  const { messages, sendMessage, status, error } = useChat();
  const mainRef = useRef<HTMLElement>(null);
  const [input, setInput] = useState('');
  const [delayNotice, setDelayNotice] = useState(false);
  const [answerTimestamps, setAnswerTimestamps] = useState<Record<string, string>>({});
  const lastUserQueryRef = useRef<string>('');

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

  // Gan timestamp cho assistant message khi xuat hien lan dau (chua co trong map)
  useEffect(() => {
    const missing: Record<string, string> = {};
    messages.forEach(m => {
      if (m.role === 'assistant' && !answerTimestamps[m.id] && getMessageText(m)) {
        missing[m.id] = formatVNTime(new Date());
      }
    });
    if (Object.keys(missing).length > 0) {
      setAnswerTimestamps(prev => ({ ...prev, ...missing }));
    }
  }, [messages, answerTimestamps]);

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

  // Kiem tra co assistant message moi (sau luc submit) da co content chua
  const newAssistantHasContent = useMemo(() => {
    for (let i = msgCountAtSubmitRef.current; i < messages.length; i++) {
      if (messages[i].role === 'assistant' && getMessageText(messages[i])) return true;
    }
    return false;
  }, [messages]);

  useEffect(() => {
    if (!isLoading) {
      setDelayNotice(false);
    } else if (!newAssistantHasContent) {
      setDelayNotice(true);
    } else {
      setDelayNotice(false);
    }
  }, [isLoading, newAssistantHasContent]);

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
    // Hien loading ngay lap tuc voi random message
    setDelayMsg(delayMessages[Math.floor(Math.random() * delayMessages.length)]);
    setDelayNotice(true);
    startTimerLoop();
    lastUserQueryRef.current = trimmed;
    sendMessage({ text: trimmed });
    setInput('');
  };

  // Retry: gui lai cau hoi cuoi cung khi gap loi Gemini qua tai
  const handleRetry = () => {
    const q = lastUserQueryRef.current;
    if (!q || isLoading) return;
    cancelAnimationFrame(timerRafRef.current);
    timerStartRef.current = Date.now();
    timerRunningRef.current = true;
    msgCountAtSubmitRef.current = messages.length;
    setElapsedMs(0);
    setDelayMsg(delayMessages[Math.floor(Math.random() * delayMessages.length)]);
    setDelayNotice(true);
    startTimerLoop();
    sendMessage({ text: q });
  };

  return (
    <div className="flex flex-col h-screen bg-[#f0f4fb] text-gray-800 font-sans relative">
      {/* Header: navy đậm giống HUFLIT ACA */}
      <header className="bg-[#0d1b6e] p-5 flex items-center gap-3 shadow-md fixed w-full top-0 start-0 z-10">
        <Scale className="text-white" size={28} />
        <h1 className="text-white text-xl font-semibold tracking-wide">AI tư vấn pháp luật</h1>
      </header>

      <main ref={mainRef} className="flex-1 overflow-y-auto px-4 sm:px-6 w-full max-w-4xl mx-auto flex flex-col gap-6 pt-24 pb-32">
        {messages.length === 0 && (
          <div className="flex-1 flex flex-col items-center justify-center text-center opacity-80 mt-20">
            <Scale className="w-20 h-20 text-[#c5cfe8] mb-6" />
            <h2 className="text-2xl font-medium text-[#0d1b6e]">Bạn cần hỗ trợ pháp luật?</h2>
            <p className="text-[#6b7280] mt-2">Nhập câu hỏi để chúng tôi tư vấn Luật, nghị định, thông tư...</p>
          </div>
        )}

        {messages.map((m, idx) => {
          if (m.role === 'assistant' && !getMessageText(m)) return null;
          const isCurrentlyStreaming = m.role === 'assistant' && idx === lastAssistantIdx && isStreaming;
          const rawText = getMessageText(m);
          const hasOverloadError = m.role === 'assistant' && rawText.includes(GEMINI_OVERLOAD_SENTINEL);
          const canExport = m.role === 'assistant' && answerTimestamps[m.id] && !isCurrentlyStreaming && !hasOverloadError;
          return (
            <div key={m.id} className={`flex flex-col w-full ${m.role === 'user' ? 'items-end' : 'items-start'} msg-appear`}>
              <div
                className={`px-5 py-4 max-w-[85%] rounded-3xl leading-relaxed shadow-sm text-[15.5px] ${m.role === 'user'
                  ? 'bg-[#0d1b6e] text-white rounded-tr-md whitespace-pre-wrap'
                  : 'bg-white border border-[#dde3f0] text-gray-800 rounded-tl-md'
                  }`}
              >
                {/* Vung noi dung duoc export PDF — data-pdf-message-id de exporter query */}
                <div data-pdf-message-id={m.id}>
                  {hasOverloadError ? (
                    <div className="flex flex-col gap-3">
                      <div className="text-[#b91c1c] font-medium">
                        ⚠️ Model Gemini hiện đang quá tải, vui lòng bấm nút retry để load câu trả lời.
                      </div>
                      <button
                        onClick={handleRetry}
                        disabled={isLoading}
                        className="inline-flex items-center justify-center gap-2 px-4 py-2 bg-[#0d1b6e] text-white rounded-lg hover:bg-[#1a2a8a] disabled:opacity-50 disabled:cursor-not-allowed self-start text-sm font-medium"
                      >
                        <RefreshCw size={16} /> Retry
                      </button>
                    </div>
                  ) : m.role === 'assistant' && idx === lastAssistantIdx ? (
                    <TypingText text={rawText} isStreaming={isStreaming} onUpdate={scrollToBottom} />
                  ) : m.role === 'assistant' ? (
                    <div className="markdown-body"><ReactMarkdown>{rawText}</ReactMarkdown></div>
                  ) : (
                    rawText
                  )}
                </div>
                {m.role === 'assistant' && answerTimestamps[m.id] && !isCurrentlyStreaming && !hasOverloadError && (
                  <div className="font-medium mt-3 pdf-exclude">{answerTimestamps[m.id]}</div>
                )}
                {canExport && (
                  <div className="flex justify-end mt-2 pdf-exclude">
                    <button
                      onClick={() => exportBubbleToPdf(m.id, answerTimestamps[m.id])}
                      className="inline-flex items-center gap-1 text-[12px] text-[#0d1b6e] hover:underline"
                      title="Tải lời tư vấn này thành file PDF"
                    >
                      <FileDown size={14} /> Tải lời tư vấn
                    </button>
                  </div>
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
