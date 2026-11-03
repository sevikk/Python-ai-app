import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { ChatMessage } from './chat-api.service';
import { App } from './app';

describe('App', () => {
  let httpTestingController: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    })
      .compileComponents();
    httpTestingController = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpTestingController.verify());

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

    const request = httpTestingController.expectOne('http://localhost:8000/chat');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({
      messages: [
        ...history,
        { role: 'user', content: 'What is my name?' },
      ],
    });
    request.flush({ reply: 'Your name is Alex.' });

    await sending;
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Your name is Alex.');
  });
});
