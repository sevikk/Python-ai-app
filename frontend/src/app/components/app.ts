import {
  afterRenderEffect,
  Component,
  ElementRef,
  signal,
  viewChild,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HistoryPanelComponent } from './history-panel.component';
import { MarkdownPipe } from '../markdown.pipe';
import { TaskExtractionResultComponent } from './task-extraction-result.component';
import {
  ChatApiService,
  ChatMessage,
  AuthUser,
  ConversationSummary,
  TaskExtractionResponse,
} from '../chat-api.service';

@Component({
  imports: [
    FormsModule,
    HistoryPanelComponent,
    MarkdownPipe,
    TaskExtractionResultComponent,
  ],
  selector: 'app-root',
  styleUrl: './app.scss',
  templateUrl: './app.html',
})
export class App {
  private activeRequestController: AbortController | null = null;
  private taskExtractionController: AbortController | null = null;
  private readonly messageViewport =
    viewChild<ElementRef<HTMLDivElement>>('messageViewport');

  protected readonly messages = signal<ChatMessage[]>([]);
  protected readonly draft = signal('');
  protected readonly isSending = signal(false);
  protected readonly hasReceivedToken = signal(false);
  protected readonly error = signal('');
  protected readonly canRetry = signal(false);
  protected readonly conversations = signal<ConversationSummary[]>([]);
  protected readonly activeConversationId = signal<string | null>(null);
  protected readonly currentUser = signal<AuthUser | null>(null);
  protected readonly showAuth = signal(false);
  protected readonly authMode = signal<'login' | 'register'>('login');
  protected readonly authEmail = signal('');
  protected readonly authPassword = signal('');
  protected readonly authError = signal('');
  protected readonly isUserLoading = signal(true);
  protected readonly userLoadError = signal('');
  protected readonly isAuthBusy = signal(false);
  protected readonly isHistoryLoading = signal(true);
  protected readonly historyLoadError = signal('');
  protected readonly isAccountMenuOpen = signal(false);
  protected readonly isHistoryOpen = signal(false);
  protected readonly deleteTarget = signal<string | null>(null);
  protected readonly extractedTasks = signal<TaskExtractionResponse | null>(null);
  protected readonly isExtractingTasks = signal(false);
  protected readonly taskExtractionError = signal('');
  protected readonly suggestions = [
    'Explain how LangChain works',
    'Help me plan my day',
    'Explain a complex topic in simple terms',
  ];

  constructor(private readonly chatApi: ChatApiService) {
    void this.loadConversations();
    void this.loadUser();
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

    this.cancelTaskExtraction();
    this.messages.set([]);
    this.draft.set('');
    this.error.set('');
    this.canRetry.set(false);
    this.activeConversationId.set(null);
    this.isHistoryOpen.set(false);
    this.extractedTasks.set(null);
    this.taskExtractionError.set('');
  }

  protected async openConversation(conversationId: string): Promise<void> {
    if (this.isSending()) {
      return;
    }
    this.isHistoryOpen.set(false);

    try {
      const conversation =
        await this.chatApi.getConversation(conversationId);
      this.activeConversationId.set(conversationId);
      this.messages.set(conversation.messages);
      this.error.set('');
      this.canRetry.set(false);
    } catch (error: unknown) {
      this.error.set(
        error instanceof Error ? error.message : 'Could not load this chat.',
      );
    }
  }

  protected async deleteConversation(conversationId: string): Promise<void> {
    if (this.isSending()) {
      return;
    }

    try {
      await this.chatApi.deleteConversation(conversationId);
      this.conversations.update((items) =>
        items.filter((item) => item.id !== conversationId),
      );
      if (this.activeConversationId() === conversationId) {
        this.startNewChat();
      }
      this.deleteTarget.set(null);
    } catch (error: unknown) {
      this.error.set(
        error instanceof Error ? error.message : 'Could not delete this chat.',
      );
    }
  }

  protected requestDeleteConversation(conversationId: string): void {
    this.deleteTarget.set(conversationId);
  }

  protected cancelDeleteConversation(): void {
    this.deleteTarget.set(null);
  }

  protected toggleAccountMenu(): void {
    this.isAccountMenuOpen.update((open) => !open);
  }

  protected toggleHistory(): void {
    this.isHistoryOpen.update((open) => !open);
  }

  private async loadConversations(): Promise<void> {
    this.isHistoryLoading.set(true);
    this.historyLoadError.set('');
    try {
      this.conversations.set(await this.chatApi.listConversations());
    } catch (error: unknown) {
      this.historyLoadError.set(
        error instanceof Error ? error.message : 'Could not load chat history.',
      );
    } finally {
      this.isHistoryLoading.set(false);
    }
  }

  private async loadUser(): Promise<void> {
    this.isUserLoading.set(true);
    this.userLoadError.set('');
    try {
      this.currentUser.set(await this.chatApi.me());
    } catch (error: unknown) {
      this.userLoadError.set(
        error instanceof Error ? error.message : 'Could not load account.',
      );
    } finally {
      this.isUserLoading.set(false);
    }
  }

  protected retryLoadUser(): Promise<void> {
    return this.loadUser();
  }

  protected retryLoadConversations(): Promise<void> {
    return this.loadConversations();
  }

  protected openAuth(mode: 'login' | 'register'): void {
    this.authMode.set(mode);
    this.authEmail.set('');
    this.authPassword.set('');
    this.authError.set('');
    this.showAuth.set(true);
  }

  protected closeAuth(): void {
    this.showAuth.set(false);
  }

  protected async submitAuth(): Promise<void> {
    if (this.isAuthBusy()) {
      return;
    }
    this.authError.set('');
    this.isAuthBusy.set(true);
    try {
      const user =
        this.authMode() === 'register'
          ? await this.chatApi.register(
              this.authEmail(),
              this.authPassword(),
            )
          : await this.chatApi.login(
              this.authEmail(),
              this.authPassword(),
            );
      this.currentUser.set(user);
      this.showAuth.set(false);
      await this.loadConversations();
    } catch (error: unknown) {
      this.authError.set(
        error instanceof Error ? error.message : 'Authentication failed.',
      );
    } finally {
      this.isAuthBusy.set(false);
    }
  }

  protected async logout(): Promise<void> {
    this.isAccountMenuOpen.set(false);
    try {
      await this.chatApi.logout();
      this.currentUser.set(null);
      await this.loadConversations();
    } catch (error: unknown) {
      this.authError.set(
        error instanceof Error ? error.message : 'Could not log out.',
      );
    }
  }

  protected async sendMessage(message = this.draft()): Promise<void> {
    const content = message.trim();
    if (!content || this.isSending()) {
      return;
    }

    this.cancelTaskExtraction();
    this.messages.update((messages) => [...messages, { role: 'user', content }]);
    this.draft.set('');
    this.error.set('');
    this.canRetry.set(false);
    this.extractedTasks.set(null);
    this.taskExtractionError.set('');
    await this.requestReply();
  }

  protected async extractTasksFromDraft(): Promise<void> {
    const text = this.draft().trim();
    if (!text || this.isSending() || this.isExtractingTasks()) {
      return;
    }

    const controller = new AbortController();
    this.taskExtractionController = controller;
    this.isExtractingTasks.set(true);
    this.extractedTasks.set(null);
    this.taskExtractionError.set('');
    try {
      const result = await this.chatApi.extractTasks(text, controller.signal);
      if (!controller.signal.aborted && this.draft().trim() === text) {
        this.extractedTasks.set(result);
      }
    } catch (error: unknown) {
      if (!controller.signal.aborted) {
        this.taskExtractionError.set(
          error instanceof Error ? error.message : 'Could not extract tasks.',
        );
      }
    } finally {
      if (this.taskExtractionController === controller) {
        this.taskExtractionController = null;
        this.isExtractingTasks.set(false);
      }
    }
  }

  protected updateDraft(value: string): void {
    if (value !== this.draft()) {
      this.cancelTaskExtraction();
    }
    this.draft.set(value);
    this.extractedTasks.set(null);
    this.taskExtractionError.set('');
  }

  private cancelTaskExtraction(): void {
    this.taskExtractionController?.abort();
    this.taskExtractionController = null;
    this.isExtractingTasks.set(false);
  }

  protected async retryLastMessage(): Promise<void> {
    if (!this.canRetry() || this.isSending()) {
      return;
    }

    this.error.set('');
    this.canRetry.set(false);
    await this.requestReply();
  }

  protected stopGeneration(): void {
    this.activeRequestController?.abort();
  }

  private async requestReply(): Promise<void> {
    const controller = new AbortController();
    this.activeRequestController = controller;
    this.isSending.set(true);
    this.hasReceivedToken.set(false);
    let pendingTokens = '';
    let updateTimer: ReturnType<typeof setTimeout> | null = null;

    const flushPendingTokens = (): void => {
      if (updateTimer !== null) {
        clearTimeout(updateTimer);
        updateTimer = null;
      }
      if (!pendingTokens) {
        return;
      }

      const tokens = pendingTokens;
      pendingTokens = '';
      this.hasReceivedToken.set(true);
      this.messages.update((messages) =>
        messages.map((item, index) =>
          index === messages.length - 1
            ? { ...item, content: item.content + tokens }
            : item,
        ),
      );
    };

    try {
      const conversation = this.messages().slice(-20);
      this.messages.update((messages) => [
        ...messages,
        { role: 'assistant', content: '' },
      ]);
      for await (const token of this.chatApi.streamReply(
        conversation,
        this.activeConversationId(),
        controller.signal,
      )) {
        pendingTokens += token;
        if (updateTimer === null) {
          updateTimer = setTimeout(flushPendingTokens, 50);
        }
      }
      flushPendingTokens();
      if (controller.signal.aborted) {
        return;
      }
      this.activeConversationId.set(
        this.chatApi.lastConversationId,
      );
      await this.loadConversations();
    } catch (error: unknown) {
      if (controller.signal.aborted) {
        flushPendingTokens();
        this.messages.update((messages) => {
          const last = messages[messages.length - 1];
          return last?.role === 'assistant' && !last.content
            ? messages.slice(0, -1)
            : messages;
        });
      } else {
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
      }
    } finally {
      if (updateTimer !== null) {
        clearTimeout(updateTimer);
      }
      if (this.activeRequestController === controller) {
        this.activeRequestController = null;
      }
      this.isSending.set(false);
      this.hasReceivedToken.set(false);
    }
  }
}
