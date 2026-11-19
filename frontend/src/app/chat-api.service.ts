import { Injectable, InjectionToken, inject } from '@angular/core';
import { environment } from '../environments/environment';

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ConversationSummary {
  id: string;
  title: string;
  updated_at: string;
}

export interface ConversationDetail {
  id: string;
  title: string;
  updated_at: string;
  messages: ChatMessage[];
}

export interface AuthUser {
  id: string;
  email: string;
}

export const FETCHER = new InjectionToken<typeof fetch>('FETCHER', {
  providedIn: 'root',
  factory: () => globalThis.fetch.bind(globalThis),
});

interface StreamEvent {
  token?: unknown;
  error?: unknown;
  done?: unknown;
  conversation_id?: unknown;
}

@Injectable({ providedIn: 'root' })
export class ChatApiService {
  private readonly fetcher = inject(FETCHER);
  private readonly apiUrl = environment.apiUrl;
  private readonly conversationsUrl = this.apiUrl.replace('/chat/stream', '/conversations');
  private readonly sessionId = this.getSessionId();
  lastConversationId: string | null = null;

  async register(email: string, password: string): Promise<AuthUser> {
    return this.authRequest('/auth/register', email, password);
  }

  async login(email: string, password: string): Promise<AuthUser> {
    return this.authRequest('/auth/login', email, password);
  }

  async me(): Promise<AuthUser | null> {
    const response = await this.fetcher(
      this.apiUrl.replace('/chat/stream', '/auth/me'),
      {
        credentials: 'include',
      },
    );
    if (response.status === 401) {
      return null;
    }
    if (!response.ok) {
      throw await this.responseError(response, 'Could not load account.');
    }
    return (await response.json()) as AuthUser;
  }

  async logout(): Promise<void> {
    const response = await this.fetcher(
      this.apiUrl.replace('/chat/stream', '/auth/logout'),
      {
        method: 'POST',
        credentials: 'include',
      },
    );
    if (!response.ok) {
      throw await this.responseError(response, 'Could not log out.');
    }
  }

  private async authRequest(
    path: string,
    email: string,
    password: string,
  ): Promise<AuthUser> {
    const response = await this.fetcher(
      this.apiUrl.replace('/chat/stream', path),
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': this.sessionId,
        },
        credentials: 'include',
        body: JSON.stringify({ email, password }),
      },
    );
    if (!response.ok) {
      throw await this.responseError(response, 'Authentication failed.');
    }
    return (await response.json()) as AuthUser;
  }

  private getSessionId(): string {
    const storageKey = 'ai-chat-session-id';
    const existing = localStorage.getItem(storageKey);
    if (existing) {
      return existing;
    }
    const generated =
      typeof crypto.randomUUID === 'function'
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    localStorage.setItem(storageKey, generated);
    return generated;
  }

  private sessionHeaders(): HeadersInit {
    return { 'X-Session-ID': this.sessionId };
  }

  async listConversations(): Promise<ConversationSummary[]> {
    const response = await this.fetcher(this.conversationsUrl, {
      credentials: 'include',
      headers: this.sessionHeaders(),
    });
    if (!response.ok) {
      throw await this.responseError(response, 'Could not load chat history.');
    }
    return (await response.json()) as ConversationSummary[];
  }

  async getConversation(conversationId: string): Promise<ConversationDetail> {
    const response = await this.fetcher(
      `${this.conversationsUrl}/${conversationId}`,
      {
        credentials: 'include',
        headers: this.sessionHeaders(),
      },
    );
    if (!response.ok) {
      throw await this.responseError(response, 'Could not load this chat.');
    }
    return (await response.json()) as ConversationDetail;
  }

  async deleteConversation(conversationId: string): Promise<void> {
    const response = await this.fetcher(
      `${this.conversationsUrl}/${conversationId}`,
      {
        method: 'DELETE',
        credentials: 'include',
        headers: this.sessionHeaders(),
      },
    );
    if (!response.ok) {
      throw await this.responseError(response, 'Could not delete this chat.');
    }
  }

  private async responseError(
    response: Response,
    fallback: string,
  ): Promise<Error> {
    const body: unknown = await response.json().catch(() => null);
    const detail =
      typeof body === 'object' &&
      body !== null &&
      'detail' in body &&
      typeof body.detail === 'string'
        ? body.detail
        : fallback;
    return new Error(detail);
  }

  async *streamReply(
    messages: ChatMessage[],
    conversationId: string | null = null,
  ): AsyncGenerator<string> {
    this.lastConversationId = conversationId;
    const response = await this.fetcher(this.apiUrl, {
      method: 'POST',
      credentials: 'include',
      headers: {
        Accept: 'text/event-stream',
        'Content-Type': 'application/json',
        'X-Session-ID': this.sessionId,
      },
      body: JSON.stringify({ messages, conversation_id: conversationId }),
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
          this.lastConversationId =
            typeof event.conversation_id === 'string'
              ? event.conversation_id
              : this.lastConversationId;
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
