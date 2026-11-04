import { TestBed } from '@angular/core/testing';
import { ChatMessage } from './chat-api.service';
import { ChatApiService } from './chat-api.service';
import { App } from './app';

type StreamStep = string | Error | (() => Promise<void>);

describe('App', () => {
  let streamedRequests: ChatMessage[][];
  let streamOutcomes: StreamStep[][];

  beforeEach(async () => {
    streamedRequests = [];
    streamOutcomes = [['Your', ' name is Alex.']];
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [
        {
          provide: ChatApiService,
          useValue: {
            streamReply: async function* (messages: ChatMessage[]) {
              streamedRequests.push(messages);
              const outcome = streamOutcomes.shift() ?? [];
              for (const step of outcome) {
                if (typeof step === 'function') {
                  await step();
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
      (fixture.nativeElement.querySelector('.new-chat-button') as HTMLButtonElement)
        .disabled,
    ).toBe(true);

    releaseStream();
    await sending;
    fixture.detectChanges();
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
});
