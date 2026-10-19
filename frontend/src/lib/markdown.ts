import MarkdownIt from 'markdown-it'

// Raw HTML is disabled, so model text is escaped and never becomes executable markup.
const md = new MarkdownIt({ html: false, linkify: true, breaks: true })
md.disable(['image'])

const defaultLink = md.renderer.rules.link_open ?? ((tokens, idx, options, _env, self) => self.renderToken(tokens, idx, options))
md.renderer.rules.link_open = (tokens, idx, options, env, self) => {
  tokens[idx].attrSet('target', '_blank')
  tokens[idx].attrSet('rel', 'noopener noreferrer nofollow')
  return defaultLink(tokens, idx, options, env, self)
}

export function renderMarkdown(text: string): string {
  return md.render(text)
}
