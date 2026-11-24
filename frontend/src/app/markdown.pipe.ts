import { Pipe, PipeTransform } from '@angular/core';
import DOMPurify from 'dompurify';
import hljs from 'highlight.js/lib/core';
import bash from 'highlight.js/lib/languages/bash';
import css from 'highlight.js/lib/languages/css';
import java from 'highlight.js/lib/languages/java';
import javascript from 'highlight.js/lib/languages/javascript';
import json from 'highlight.js/lib/languages/json';
import python from 'highlight.js/lib/languages/python';
import sql from 'highlight.js/lib/languages/sql';
import typescript from 'highlight.js/lib/languages/typescript';
import xml from 'highlight.js/lib/languages/xml';
import yaml from 'highlight.js/lib/languages/yaml';
import { Marked } from 'marked';

hljs.registerLanguage('bash', bash);
hljs.registerLanguage('css', css);
hljs.registerLanguage('java', java);
hljs.registerLanguage('javascript', javascript);
hljs.registerLanguage('json', json);
hljs.registerLanguage('python', python);
hljs.registerLanguage('sql', sql);
hljs.registerLanguage('typescript', typescript);
hljs.registerLanguage('xml', xml);
hljs.registerLanguage('yaml', yaml);

const languageAliases: Record<string, string> = {
  bash: 'bash',
  css: 'css',
  html: 'xml',
  java: 'java',
  javascript: 'javascript',
  js: 'javascript',
  json: 'json',
  py: 'python',
  python: 'python',
  sh: 'bash',
  shell: 'bash',
  sql: 'sql',
  ts: 'typescript',
  typescript: 'typescript',
  xml: 'xml',
  yml: 'yaml',
  yaml: 'yaml',
};

const markdown = new Marked({
  gfm: true,
  breaks: false,
  renderer: {
    code({ text, lang }) {
      const language = lang?.trim().toLowerCase().split(/\s+/, 1)[0] ?? '';
      const registeredLanguage = languageAliases[language];
      if (!registeredLanguage) {
        return `<pre><code>${escapeHtml(text)}</code></pre>\n`;
      }

      const highlighted = hljs.highlight(text, {
        language: registeredLanguage,
      }).value;
      return `<pre><code class="hljs language-${registeredLanguage}">${highlighted}</code></pre>\n`;
    },
  },
});

@Pipe({
  name: 'markdown',
  standalone: true,
})
export class MarkdownPipe implements PipeTransform {
  transform(value: string, highlightCode = true): string {
    let rendered: string;
    if (highlightCode) {
      rendered = markdown.parse(value, { async: false });
    } else {
      const renderer = new markdown.Renderer();
      renderer.code = ({ text }) =>
        `<pre><code>${escapeHtml(text)}</code></pre>\n`;
      rendered = markdown.parse(value, { async: false, renderer });
    }
    return DOMPurify.sanitize(rendered, {
      FORBID_TAGS: ['img'],
    });
  }
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => {
    switch (character) {
      case '&':
        return '&amp;';
      case '<':
        return '&lt;';
      case '>':
        return '&gt;';
      case '"':
        return '&quot;';
      default:
        return '&#39;';
    }
  });
}
