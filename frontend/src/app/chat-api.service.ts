import { Injectable, InjectionToken, inject } from '@angular/core';
import { environment } from '../environments/environment';

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export const FETCHER = new InjectionToken<typeof fetch>('FETCHER', {
  providedIn: 'root',
  factory: () => globalThis.fetch.bind(globalThis),
});

interface StreamEvent {
  token?: unknown;
  error?: unknown;
  done?: unknown;
}

@Injectable({ providedIn: 'root' })
export class ChatApiService {
  private readonly fetcher = inject(FETCHER);
  private readonly apiUrl = environment.apiUrl;

  async *streamReply(messages: ChatMessage[]): AsyncGenerator<string> {
    const response = await this.fetcher(this.apiUrl, {
      method: 'POST',
      headers: {
        Accept: 'text/event-stream',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ messages }),
    });

    if (!response.ok) {
      const body: unknown = await response.json().catch(() => null);
      const detail =
        typeof body === 'object' &&
        body !== null &&
        'detail' in body &&
        typeof body.detail === 'string'
          ? body.detail
          : `Chat request failed with status ${response.status}.`;
      throw new Error(detail);
    }

    if (!response.body) {
      throw new Error('The server did not provide a response stream.');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let dataLines: string[] = [];

    const processLine = (line: string): string | null => {
      if (line === '') {
        if (dataLines.length === 0) {
          return null;
        }

        const data = dataLines.join('\n');
        dataLines = [];
        let payload: unknown;
        try {
          payload = JSON.parse(data) as unknown;
        } catch {
          throw new Error('Received invalid streaming data from the server.');
        }

        if (typeof payload !== 'object' || payload === null) {
          throw new Error('Received invalid streaming data from the server.');
        }
        const event = payload as StreamEvent;
        if (typeof event.error === 'string') {
          throw new Error(event.error);
        }
        if (typeof event.token === 'string') {
          return event.token;
        }
        if (event.done === true) {
          return null;
        }
        throw new Error('Received an unknown event from the server.');
      }

      if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).replace(/^ /, ''));
      }
      return null;
    };

    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';
        for (const rawLine of lines) {
          const token = processLine(rawLine.replace(/\r$/, ''));
          if (token !== null) {
            yield token;
          }
        }
      }

      buffer += decoder.decode();
      if (buffer.length > 0) {
        const token = processLine(buffer.replace(/\r$/, ''));
        if (token !== null) {
          yield token;
        }
      }
      const finalToken = processLine('');
      if (finalToken !== null) {
        yield finalToken;
      }
    } finally {
      reader.releaseLock();
    }
  }
}
