import { HttpErrorResponse } from '@angular/common/http';
import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { ChatApiService, ChatMessage } from './chat-api.service';

@Component({
  imports: [FormsModule],
  selector: 'app-root',
  styleUrl: './app.css',
  templateUrl: './app.html',
})
export class App {
  protected readonly messages = signal<ChatMessage[]>([]);
  protected readonly draft = signal('');
  protected readonly isSending = signal(false);
  protected readonly error = signal('');
  protected readonly suggestions = [
    'Explain how LangChain works',
    'Help me plan my day',
    'Explain a complex topic in simple terms',
  ];

  constructor(private readonly chatApi: ChatApiService) {}

  protected async sendMessage(message = this.draft()): Promise<void> {
    const content = message.trim();
    if (!content || this.isSending()) {
      return;
    }

    this.messages.update((messages) => [...messages, { role: 'user', content }]);
    this.draft.set('');
    this.error.set('');
    this.isSending.set(true);

    try {
      const conversation = this.messages().slice(-20);
      const response = await firstValueFrom(
        this.chatApi.sendMessage(conversation),
      );
      this.messages.update((messages) => [
        ...messages,
        { role: 'assistant', content: response.reply },
      ]);
    } catch (error: unknown) {
      const detail =
        error instanceof HttpErrorResponse &&
        typeof error.error?.detail === 'string'
          ? error.error.detail
          : null;
      this.error.set(
        detail ?? 'Could not get a response. Check that the backend is running.',
      );
    } finally {
      this.isSending.set(false);
    }
  }
}
