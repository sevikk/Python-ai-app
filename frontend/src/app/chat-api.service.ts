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

export interface ExtractedTask {
  title: string;
  priority: 'low' | 'medium' | 'high';
  due_date: string | null;
}

export interface TaskExtractionResponse {
  tasks: ExtractedTask[];
}

export const FETCHER = new InjectionToken<typeof fetch>('FETCHER', {
  providedIn: 'root',
  factory: () => globalThis.fetch.bind(globalThis),
});

export const SESSION_STORAGE = new InjectionToken<
  Pick<Storage, 'getItem' | 'setItem'> | null
>('SESSION_STORAGE', {
  providedIn: 'root',
  factory: () => {
    try {
      return globalThis.localStorage;
    } catch {
      return null;
    }
  },
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
  private readonly sessionStorage = inject(SESSION_STORAGE);
  private readonly apiBaseUrl = environment.apiBaseUrl;
  private readonly sessionId = this.getSessionId(this.sessionStorage);
  lastConversationId: string | null = null;

  private endpoint(path: string): string {
    return new URL(path, this.apiBaseUrl).toString();
  }

  async register(email: string, password: string): Promise<AuthUser> {
    return this.authRequest('/auth/register', email, password);
  }

  async login(email: string, password: string): Promise<AuthUser> {
    return this.authRequest('/auth/login', email, password);
  }

  async me(): Promise<AuthUser | null> {
    const response = await this.fetcher(
      this.endpoint('auth/me'),
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
      this.endpoint('auth/logout'),
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
      this.endpoint(path.replace(/^\//, '')),
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

  private getSessionId(
    storage: Pick<Storage, 'getItem' | 'setItem'> | null,
  ): string {
    const storageKey = 'ai-chat-session-id';
    try {
      const existing = storage?.getItem(storageKey);
      if (existing) {
        return existing;
      }
    } catch {
      // Fall back to an in-memory session if browser storage is unavailable.
    }
    const generated =
      typeof crypto.randomUUID === 'function'
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    try {
      storage?.setItem(storageKey, generated);
    } catch {
      // The generated ID remains usable for this page session.
    }
    return generated;
  }

  private sessionHeaders(): HeadersInit {
    return { 'X-Session-ID': this.sessionId };
  }

  async listConversations(): Promise<ConversationSummary[]> {
    const response = await this.fetcher(this.endpoint('conversations'), {
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
      this.endpoint(`conversations/${encodeURIComponent(conversationId)}`),
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
      this.endpoint(`conversations/${encodeURIComponent(conversationId)}`),
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

  async extractTasks(
    text: string,
    signal?: AbortSignal,
  ): Promise<TaskExtractionResponse> {
    const response = await this.fetcher(
      this.endpoint('tasks/extract'),
      {
        method: 'POST',
        credentials: 'include',
        headers: {
          ...this.sessionHeaders(),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ text }),
        signal,
      },
    );
    if (!response.ok) {
      throw await this.responseError(response, 'Could not extract tasks.');
    }
    return (await response.json()) as TaskExtractionResponse;
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
    signal?: AbortSignal,
  ): AsyncGenerator<string> {
    this.lastConversationId = conversationId;
    const response = await this.fetcher(this.endpoint('chat/stream'), {
      method: 'POST',
      credentials: 'include',
      headers: {
        Accept: 'text/event-stream',
        'Content-Type': 'application/json',
        'X-Session-ID': this.sessionId,
      },
      body: JSON.stringify({ messages, conversation_id: conversationId }),
      signal,
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
    let receivedDoneEvent = false;

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
          receivedDoneEvent = true;
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
      if (!receivedDoneEvent) {
        throw new Error('The response stream ended before it was complete.');
      }
    } finally {
      await reader.cancel().catch(() => undefined);
      reader.releaseLock();
    }
  }
}
