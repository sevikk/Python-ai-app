import { TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import {
  ChatApiService,
  FETCHER,
  SESSION_STORAGE,
} from './chat-api.service';
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
  let storage: Pick<Storage, 'getItem' | 'setItem'>;

  beforeEach(() => {
    fetcher = vi.fn();
    storage = {
      getItem: vi.fn().mockReturnValue(null),
      setItem: vi.fn(),
    };
    TestBed.configureTestingModule({
      providers: [
        ChatApiService,
        { provide: FETCHER, useValue: fetcher },
        { provide: SESSION_STORAGE, useValue: storage },
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

    const controller = new AbortController();
    for await (const token of service.streamReply(messages, null, controller.signal)) {
      received.push(token);
    }

    expect(received).toEqual(['Hello', ' world']);
    expect(fetcher).toHaveBeenCalledWith(
      'http://localhost:8000/chat/stream',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ messages, conversation_id: null }),
        signal: controller.signal,
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

  it('should reject a stream that ends without a done event', async () => {
    fetcher.mockResolvedValue(
      responseFromChunks(['data: {"token":"Partial response"}\n\n']),
    );
    const received: string[] = [];

    await expect(async () => {
      for await (const token of service.streamReply([])) {
        received.push(token);
      }
    }).rejects.toThrow('The response stream ended before it was complete.');

    expect(received).toEqual(['Partial response']);
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

  it('should work with an in-memory session when storage throws', async () => {
    TestBed.resetTestingModule();
    fetcher = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    TestBed.configureTestingModule({
      providers: [
        ChatApiService,
        { provide: FETCHER, useValue: fetcher },
        {
          provide: SESSION_STORAGE,
          useValue: {
            getItem: () => {
              throw new Error('Storage disabled');
            },
            setItem: () => {
              throw new Error('Storage disabled');
            },
          },
        },
      ],
    });
    service = TestBed.inject(ChatApiService);

    await expect(service.listConversations()).resolves.toEqual([]);
    const request = fetcher.mock.calls[0][1] as RequestInit;
    expect(new Headers(request.headers).get('X-Session-ID')).toBeTruthy();
  });

  it('should send task extraction requests and return structured tasks', async () => {
    const result = {
      tasks: [
        {
          title: 'Send the project brief',
          priority: 'high',
          due_date: '2026-12-01',
        },
      ],
    };
    fetcher.mockResolvedValue(
      new Response(JSON.stringify(result), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    const controller = new AbortController();
    await expect(
      service.extractTasks('Send the project brief', controller.signal),
    ).resolves.toEqual(
      result,
    );
    expect(fetcher).toHaveBeenCalledWith(
      'http://localhost:8000/tasks/extract',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ text: 'Send the project brief' }),
        signal: controller.signal,
      }),
    );
  });

  it('should surface task extraction errors', async () => {
    fetcher.mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Tasks could not be extracted.' }), {
        status: 502,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    await expect(service.extractTasks('Extract tasks')).rejects.toThrow(
      'Tasks could not be extracted.',
    );
  });
});
