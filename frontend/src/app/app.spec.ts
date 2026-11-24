import { TestBed } from '@angular/core/testing';
import { ChatMessage } from './chat-api.service';
import { ChatApiService } from './chat-api.service';
import { App } from './app';

type StreamStep = string | Error | ((signal?: AbortSignal) => Promise<void>);

describe('App', () => {
  let streamedRequests: ChatMessage[][];
  let streamedSignals: (AbortSignal | undefined)[];
  let streamOutcomes: StreamStep[][];
  let taskExtractionInputs: string[];
  let taskExtractionSignals: (AbortSignal | undefined)[];
  let taskExtractionHandler: (
    text: string,
    signal?: AbortSignal,
  ) => Promise<{
    tasks: {
      title: string;
      priority: 'low' | 'medium' | 'high';
      due_date: string | null;
    }[];
  }>;
  let historyLoader: () => Promise<
    { id: string; title: string; updated_at: string }[]
  >;
  let userLoader: () => Promise<{ id: string; email: string } | null>;
  let taskExtractionResult: {
    tasks: {
      title: string;
      priority: 'low' | 'medium' | 'high';
      due_date: string | null;
    }[];
  };

  beforeEach(async () => {
    streamedRequests = [];
    streamedSignals = [];
    taskExtractionInputs = [];
    taskExtractionSignals = [];
    taskExtractionHandler = async () => taskExtractionResult;
    historyLoader = async () => [];
    userLoader = async () => null;
    taskExtractionResult = {
      tasks: [
        {
          title: 'Send the project brief',
          priority: 'high',
          due_date: '2026-12-01',
        },
      ],
    };
    streamOutcomes = [['Your', ' name is Alex.']];
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [
        {
          provide: ChatApiService,
          useValue: {
            lastConversationId: null,
            me: () => userLoader(),
            login: async () => ({ id: 'test-user', email: 'test@example.com' }),
            register: async () => ({ id: 'test-user', email: 'test@example.com' }),
            logout: async () => {},
            listConversations: () => historyLoader(),
            getConversation: async () => ({
              id: 'test-conversation',
              title: 'Test',
              updated_at: '',
              messages: [],
            }),
            deleteConversation: async () => {},
            extractTasks: (
              text: string,
              signal?: AbortSignal,
            ) => {
              taskExtractionInputs.push(text);
              taskExtractionSignals.push(signal);
              return taskExtractionHandler(text, signal);
            },
            streamReply: async function* (
              messages: ChatMessage[],
              _conversationId?: string | null,
              signal?: AbortSignal,
            ) {
              streamedRequests.push(messages);
              streamedSignals.push(signal);
              const outcome = streamOutcomes.shift() ?? [];
              for (const step of outcome) {
                if (typeof step === 'function') {
                  await step(signal);
                  continue;
                }
                if (step instanceof Error) {
                  throw step;
                }
                yield step;
              }
            },
          },
        },
      ],
    })
      .compileComponents();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    expect(app).toBeTruthy();
  });

  it('should render the chat welcome screen', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('h1')?.textContent).toContain('How can I help?');
  });

  it('should render assistant replies as Markdown', () => {
    const fixture = TestBed.createComponent(App);
    fixture.componentInstance['messages'].set([
      { role: 'assistant', content: '**Formatted**\n\n```python\nprint(1)\n```' },
    ]);
    fixture.detectChanges();

    expect(
      fixture.nativeElement.querySelector('.markdown-content strong')?.textContent,
    ).toBe('Formatted');
    expect(
      fixture.nativeElement.querySelector('.markdown-content pre code')
        ?.classList.contains('language-python'),
    ).toBe(true);
  });

  it('should extract tasks from the draft and display structured results', async () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    app['draft'].set('Send the project brief by December 1.');
    fixture.detectChanges();

    await app['extractTasksFromDraft']();
    fixture.detectChanges();

    expect(taskExtractionInputs).toEqual([
      'Send the project brief by December 1.',
    ]);
    expect(
      fixture.nativeElement.querySelector('.task-extraction-result')
        ?.textContent,
    ).toContain('Send the project brief');
    expect(
      fixture.nativeElement.querySelector('.task-priority')?.textContent,
    ).toContain('high');
    expect(fixture.nativeElement.textContent).toContain('2026-12-01');
  });

  it('should discard task results after the draft changes and abort the request', async () => {
    let resolveExtraction: (value: typeof taskExtractionResult) => void = () => {};
    taskExtractionHandler = () =>
      new Promise((resolve) => {
        resolveExtraction = resolve;
      });

    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    app['updateDraft']('Original text');
    const extraction = app['extractTasksFromDraft']();
    app['updateDraft']('Edited text');

    expect(taskExtractionSignals[0]?.aborted).toBe(true);
    expect(app['isExtractingTasks']()).toBe(false);
    resolveExtraction(taskExtractionResult);
    await extraction;
    fixture.detectChanges();

    expect(app['extractedTasks']()).toBeNull();
    expect(app['taskExtractionError']()).toBe('');
  });

  it('should show history loading errors and retry without clearing saved chats', async () => {
    historyLoader = async () => [
      { id: 'chat-1', title: 'Saved chat', updated_at: '' },
    ];
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    await fixture.whenStable();

    historyLoader = async () => {
      throw new Error('Network unavailable');
    };
    await app['retryLoadConversations']();
    fixture.detectChanges();

    expect(app['historyLoadError']()).toBe('Network unavailable');
    expect(app['conversations']()).toHaveLength(1);
    expect(fixture.nativeElement.textContent).toContain('Network unavailable');
    expect(fixture.nativeElement.textContent).toContain('Saved chat');

    historyLoader = async () => [];
    await app['retryLoadConversations']();
    fixture.detectChanges();
    expect(app['historyLoadError']()).toBe('');
  });

  it('should show account load errors instead of treating them as signed out', async () => {
    userLoader = async () => {
      throw new Error('Account service unavailable');
    };
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    await fixture.whenStable();
    fixture.detectChanges();

    expect(app['userLoadError']()).toBe('Account service unavailable');
    expect(fixture.nativeElement.textContent).toContain('Retry account');
    expect(fixture.nativeElement.textContent).not.toContain('Sign in');

    userLoader = async () => ({ id: 'user-1', email: 'person@example.com' });
    await app['retryLoadUser']();
    fixture.detectChanges();

    expect(app['userLoadError']()).toBe('');
    expect(fixture.nativeElement.textContent).toContain('person@example.com');
  });

  it('should send a message and display the assistant reply', async () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();

    const history: ChatMessage[] = [
      { role: 'user', content: 'My name is Alex.' },
      { role: 'assistant', content: 'Nice to meet you, Alex.' },
    ];
    fixture.componentInstance['messages'].set(history);
    const sending = fixture.componentInstance['sendMessage']('What is my name?');

    await sending;
    fixture.detectChanges();
    expect(streamedRequests).toEqual([
      [
        ...history,
        { role: 'user', content: 'What is my name?' },
      ],
    ]);
    expect(fixture.nativeElement.textContent).toContain('Your name is Alex.');
  });

  it('should retry a failed request without duplicating the user message', async () => {
    streamOutcomes = [[new Error('Connection lost')], ['Recovered response']];
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();

    await fixture.componentInstance['sendMessage']('Try this');
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Connection lost');
    expect(fixture.nativeElement.textContent).toContain('Try again');
    expect(fixture.componentInstance['messages']()).toEqual([
      { role: 'user', content: 'Try this' },
    ]);

    await fixture.componentInstance['retryLastMessage']();
    fixture.detectChanges();

    expect(streamedRequests).toEqual([
      [{ role: 'user', content: 'Try this' }],
      [{ role: 'user', content: 'Try this' }],
    ]);
    expect(fixture.componentInstance['messages']()).toEqual([
      { role: 'user', content: 'Try this' },
      { role: 'assistant', content: 'Recovered response' },
    ]);
    expect(fixture.nativeElement.textContent).not.toContain('Connection lost');
  });

  it('should clear the conversation and draft when starting a new chat', async () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const app = fixture.componentInstance;
    app['messages'].set([
      { role: 'user', content: 'Previous question' },
      { role: 'assistant', content: 'Previous answer' },
    ]);
    app['draft'].set('Unsent draft');
    app['error'].set('Previous error');
    app['canRetry'].set(true);

    app['startNewChat']();
    fixture.detectChanges();

    expect(app['messages']()).toEqual([]);
    expect(app['draft']()).toBe('');
    expect(app['error']()).toBe('');
    expect(app['canRetry']()).toBe(false);
    expect(fixture.nativeElement.querySelector('h1')?.textContent).toContain(
      'How can I help?',
    );
  });

  it('should show a waiting state while the streamed response is pending', async () => {
    let releaseStream = () => {};
    let signalStreamStarted = () => {};
    const streamStarted = new Promise<void>((resolve) => {
      signalStreamStarted = resolve;
    });
    streamOutcomes = [[
      () =>
        new Promise<void>((resolve) => {
          releaseStream = resolve;
          signalStreamStarted();
        }),
    ]];
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();

    const sending = fixture.componentInstance['sendMessage']('Wait');
    await streamStarted;
    fixture.detectChanges();

    expect(fixture.componentInstance['isSending']()).toBe(true);
    expect(
      fixture.nativeElement.querySelector('[role="status"]')?.getAttribute('aria-label'),
    ).toBe('Waiting for Gemini');
    expect(
      (Array.from(
        fixture.nativeElement.querySelectorAll('.new-chat-button') as NodeListOf<HTMLButtonElement>,
      ).find((button) => button.textContent?.includes('New chat')) as HTMLButtonElement)
        .disabled,
    ).toBe(true);

    releaseStream();
    await sending;
    fixture.detectChanges();
  });

  it('should stop generation and keep any partial response without showing an error', async () => {
    let responseStarted = () => {};
    const started = new Promise<void>((resolve) => {
      responseStarted = resolve;
    });
    streamOutcomes = [[
      'Partial answer',
      (signal?: AbortSignal) =>
        new Promise<void>((_resolve, reject) => {
          if (!signal) {
            reject(new Error('Expected request abort signal.'));
            return;
          }
          signal.addEventListener(
            'abort',
            () => reject(new DOMException('Aborted', 'AbortError')),
            { once: true },
          );
          responseStarted();
        }),
    ]];

    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    fixture.detectChanges();

    const sending = app['sendMessage']('Explain this');
    await started;
    fixture.detectChanges();

    const stopButton = fixture.nativeElement.querySelector(
      '.stop-button',
    ) as HTMLButtonElement;
    expect(stopButton).toBeTruthy();

    stopButton.click();
    await sending;
    fixture.detectChanges();

    expect(app['isSending']()).toBe(false);
    expect(app['error']()).toBe('');
    expect(streamedSignals[0]?.aborted).toBe(true);
    expect(app['messages']()).toEqual([
      { role: 'user', content: 'Explain this' },
      { role: 'assistant', content: 'Partial answer' },
    ]);
  });

  it('should scroll the message viewport to the latest response', async () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const viewport = fixture.nativeElement.querySelector(
      '.messages',
    ) as HTMLDivElement;
    Object.defineProperty(viewport, 'scrollHeight', {
      configurable: true,
      value: 500,
    });

    await fixture.componentInstance['sendMessage']('Scroll test');
    fixture.detectChanges();
    await fixture.whenStable();

    expect(viewport.scrollTop).toBe(500);
  });

  it('should show account loading and then the sign-in state', async () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(
      fixture.nativeElement.textContent,
    ).not.toContain('Loading...');
    expect(
      fixture.nativeElement.textContent,
    ).toContain('Sign in');
  });

  it('should open auth and switch to registration', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();

    fixture.componentInstance['openAuth']('login');
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.auth-dialog h2')?.textContent)
      .toContain('Sign in');

    fixture.componentInstance['openAuth']('register');
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.auth-dialog h2')?.textContent)
      .toContain('Create account');
  });

  it('should request deletion and allow cancellation', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();

    fixture.componentInstance['requestDeleteConversation']('chat-1');
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role="alertdialog"]'))
      .toBeTruthy();

    fixture.componentInstance['cancelDeleteConversation']();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role="alertdialog"]'))
      .toBeFalsy();
  });
});
