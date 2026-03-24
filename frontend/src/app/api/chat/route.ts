import { NextRequest } from 'next/server';

/**
 * POST /api/chat
 * Proxy giữa AI SDK v6 frontend và Python FastAPI backend.
 * Chuyển đổi raw text stream từ backend sang UIMessageStream SSE format.
 */
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();

    // AI SDK v6 gửi { id, messages } — extract messages
    const messages = body.messages ?? [];

    // Thu gọn chat history gửi cho Python backend (sliding window 5 câu gần nhất)
    const history = messages.slice(-6, -1).map((msg: any) => ({
      role: msg.role === 'user' ? 'user' : 'model',
      content: msg.parts?.filter((p: any) => p.type === 'text').map((p: any) => p.text).join('') ?? msg.content ?? '',
    }));

    // Lấy câu hỏi cuối cùng
    const lastMsg = messages[messages.length - 1];
    const query = lastMsg.parts?.filter((p: any) => p.type === 'text').map((p: any) => p.text).join('') ?? lastMsg.content ?? '';

    // Giao tiếp với FastAPI backend
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
    const response = await fetch(`${backendUrl}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, history }),
    });

    if (!response.ok || !response.body) {
      return new Response(
        JSON.stringify({ error: 'Backend RAG Error' }),
        { status: response.status, headers: { 'Content-Type': 'application/json' } }
      );
    }

    // Chuyển đổi raw text stream → UIMessageStream SSE format
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    const partId = crypto.randomUUID();

    const stream = new ReadableStream({
      async start(controller) {
        const encoder = new TextEncoder();

        // text-start
        controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'text-start', id: partId })}\n\n`));

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const text = decoder.decode(value, { stream: true });
          if (text) {
            // text-delta
            controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'text-delta', id: partId, delta: text })}\n\n`));
          }
        }

        // text-end
        controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'text-end', id: partId })}\n\n`));
        // finish signal
        controller.enqueue(encoder.encode(`data: [DONE]\n\n`));
        controller.close();
      },
    });

    return new Response(stream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
      },
    });
  } catch (e: any) {
    console.error('Chat API error:', e);
    return new Response(
      JSON.stringify({ error: e.message }),
      { status: 500, headers: { 'Content-Type': 'application/json' } }
    );
  }
}
