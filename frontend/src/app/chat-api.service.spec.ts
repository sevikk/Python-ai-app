import { TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { ChatApiService, FETCHER } from './chat-api.service';
import { ChatMessage } from './chat-api.service';

function responseFromChunks(chunks: string[], status = 200): Response {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
  return new Response(body, {
    status,
    headers: { 'Content-Type': 'text/event-stream' },
  });
}

describe('ChatApiService', () => {
  let service: ChatApiService;
  let fetcher: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetcher = vi.fn();
    TestBed.configureTestingModule({
      providers: [
        ChatApiService,
        { provide: FETCHER, useValue: fetcher },
      ],
    });
    service = TestBed.inject(ChatApiService);
  });

  it('should parse streamed server events even when chunks split events', async () => {
    fetcher.mockResolvedValue(
      responseFromChunks([
        'data: {"token":"Hello"}\r',
        '\n\r\ndata: {"token":" world"}\n\n',
        'data: {"done":true}\n\n',
      ]),
    );
    const messages: ChatMessage[] = [{ role: 'user', content: 'Hi' }];
    const received: string[] = [];

    for await (const token of service.streamReply(messages)) {
      received.push(token);
    }

    expect(received).toEqual(['Hello', ' world']);
    expect(fetcher).toHaveBeenCalledWith(
      'http://localhost:8000/chat/stream',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ messages }),
      }),
    );
  });

  it('should surface provider errors sent in the stream', async () => {
    fetcher.mockResolvedValue(
      responseFromChunks([
        'data: {"error":"Gemini is temporarily unavailable."}\n\n',
      ]),
    );

    await expect(async () => {
      for await (const _token of service.streamReply([])) {
        // The error event should stop iteration.
      }
    }).rejects.toThrow('Gemini is temporarily unavailable.');
  });

  it('should include backend details for non-success responses', async () => {
    fetcher.mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Gemini key is invalid.' }), {
        status: 503,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    await expect(async () => {
      for await (const _token of service.streamReply([])) {
        // A non-success response must fail before streaming begins.
      }
    }).rejects.toThrow('Gemini key is invalid.');
  });
});
