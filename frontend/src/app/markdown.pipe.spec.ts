import { MarkdownPipe } from './markdown.pipe';

describe('MarkdownPipe', () => {
  const pipe = new MarkdownPipe();

  it('should render common Markdown formatting', () => {
    const result = pipe.transform(
      '# Title\n\n- first\n- **second**\n\nUse `inline code`.',
    );

    expect(result).toContain('<h1>Title</h1>');
    expect(result).toContain('<ul>');
    expect(result).toContain('<strong>second</strong>');
    expect(result).toContain('<code>inline code</code>');
  });

  it('should highlight fenced code blocks with a recognized language', () => {
    const result = pipe.transform('```python\nprint("hello")\n```');

    expect(result).toContain('<pre><code class="hljs language-python">');
    expect(result).toContain('hljs-built_in');
    expect(result).toContain('print');
  });

  it('should safely render unclosed code fences during streaming', () => {
    const result = pipe.transform('```typescript\nconst answer = 42;');

    expect(result).toContain('<pre><code class="hljs language-typescript">');
    expect(result).toContain('answer');
  });

  it('should defer syntax highlighting while a response is streaming', () => {
    const result = pipe.transform('```typescript\nconst answer = 42;', false);

    expect(result).toContain('<pre><code>const answer = 42;</code></pre>');
    expect(result).not.toContain('hljs-keyword');
    expect(result).not.toContain('language-typescript');
  });

  it('should escape code blocks with unsupported language labels', () => {
    const result = pipe.transform('```unknown\n<script>alert(1)</script>\n```');

    expect(result).toContain('&lt;script&gt;');
    expect(result).not.toContain('<script>');
  });

  it('should sanitize unsafe HTML and javascript links', () => {
    const result = pipe.transform(
      '<img src=x onerror=alert(1)>\n\n<a href="javascript:alert(1)">bad</a>',
    );

    expect(result).not.toContain('onerror');
    expect(result).not.toContain('javascript:');
    expect(result).not.toContain('<img');
    expect(result).toContain('bad</a>');
  });
});
