import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
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

    const sending = fixture.componentInstance['sendMessage']('Hello');

    const request = httpTestingController.expectOne('http://localhost:8000/chat');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ message: 'Hello' });
    request.flush({ reply: 'Hello there!' });

    await sending;
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Hello there!');
  });
});
