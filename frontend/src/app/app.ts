import {
  afterRenderEffect,
  Component,
  ElementRef,
  signal,
  viewChild,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ChatApiService, ChatMessage } from './chat-api.service';

@Component({
  imports: [FormsModule],
  selector: 'app-root',
  styleUrl: './app.css',
  templateUrl: './app.html',
})
export class App {
  private readonly messageViewport =
    viewChild<ElementRef<HTMLDivElement>>('messageViewport');

  protected readonly messages = signal<ChatMessage[]>([]);
  protected readonly draft = signal('');
  protected readonly isSending = signal(false);
  protected readonly hasReceivedToken = signal(false);
  protected readonly error = signal('');
  protected readonly canRetry = signal(false);
  protected readonly suggestions = [
    'Explain how LangChain works',
    'Help me plan my day',
    'Explain a complex topic in simple terms',
  ];

  constructor(private readonly chatApi: ChatApiService) {
    afterRenderEffect(() => {
      this.messages();
      this.isSending();
      const viewport = this.messageViewport()?.nativeElement;
      if (viewport) {
        viewport.scrollTop = viewport.scrollHeight;
      }
    });
  }

  protected startNewChat(): void {
    if (this.isSending()) {
      return;
    }

    this.messages.set([]);
    this.draft.set('');
    this.error.set('');
    this.canRetry.set(false);
  }

  protected async sendMessage(message = this.draft()): Promise<void> {
    const content = message.trim();
    if (!content || this.isSending()) {
      return;
    }

    this.messages.update((messages) => [...messages, { role: 'user', content }]);
    this.draft.set('');
    this.error.set('');
    this.canRetry.set(false);
    await this.requestReply();
  }

  protected async retryLastMessage(): Promise<void> {
    if (!this.canRetry() || this.isSending()) {
      return;
    }

    this.error.set('');
    this.canRetry.set(false);
    await this.requestReply();
  }

  private async requestReply(): Promise<void> {
    this.isSending.set(true);
    this.hasReceivedToken.set(false);

    try {
      const conversation = this.messages().slice(-20);
      this.messages.update((messages) => [
        ...messages,
        { role: 'assistant', content: '' },
      ]);
      for await (const token of this.chatApi.streamReply(conversation)) {
        this.hasReceivedToken.set(true);
        this.messages.update((messages) =>
          messages.map((item, index) =>
            index === messages.length - 1
              ? { ...item, content: item.content + token }
              : item,
          ),
        );
      }
    } catch (error: unknown) {
      this.messages.update((messages) => {
        const last = messages[messages.length - 1];
        return last?.role === 'assistant'
          ? messages.slice(0, -1)
          : messages;
      });
      this.error.set(
        error instanceof Error
          ? error.message
          : 'Could not get a response. Check that the backend is running.',
      );
      this.canRetry.set(true);
    } finally {
      this.isSending.set(false);
      this.hasReceivedToken.set(false);
    }
  }
}
