# X-Agent Documentation Site

This directory contains the VitePress documentation site for X-Agent.

## Development

### Prerequisites

- Node.js 18+
- npm, yarn, or pnpm

### Installation

```bash
cd docs/site
npm install
```

### Running Locally

```bash
# Development server with hot reload
npm run dev

# Access at http://localhost:5173
```

### Building

```bash
# Build for production
npm run build

# Preview production build
npm run preview
```

The production build output is in `dist/`.

## File Structure

```
docs/site/
├── .vitepress/
│   └── config.ts              # VitePress configuration
├── index.md                   # Home/landing page
├── guide/
│   └── index.md              # Guide introduction
├── api/
│   └── index.md              # API reference
├── sdk/
│   └── index.md              # SDK documentation
├── deploy/
│   └── index.md              # Deployment guide
├── package.json
└── README.md                 # This file
```

## Adding Pages

1. Create a markdown file in the appropriate section (e.g., `guide/quickstart.md`)
2. Add the link to `.vitepress/config.ts` in the `sidebar` configuration
3. The page will be automatically included in navigation

Example:
```markdown
# Quick Start

Your content here...
```

Then add to config:
```typescript
{
  text: 'Quick Start',
  link: '/guide/quickstart'
}
```

## Markdown Features

VitePress supports standard markdown plus:

### Code Blocks with Syntax Highlighting

````markdown
```python
def hello():
    print("Hello, X-Agent!")
```
````

### Callout Boxes

```markdown
::: info
This is an info box
:::

::: warning
This is a warning
:::

::: danger
This is a danger box
:::
```

### Tabs

```markdown
::: tabs
== Python
```python
code here
```

== TypeScript
```typescript
code here
```
:::
```

### Links

- Internal: `[text](/path/to/page)`
- External: `[text](https://example.com)`

## Customization

### Site Configuration

Edit `.vitepress/config.ts` to customize:
- Title and description
- Navigation menu
- Sidebar structure
- Theme colors
- Social links
- Search settings

### Theme

VitePress uses a default dark/light theme. Customize colors in `.vitepress/theme/index.ts` (if created).

## Deployment

### Vercel

1. Connect the X-Agent GitHub repository to Vercel
2. Set build command: `npm run build`
3. Set output directory: `dist`

### Netlify

1. Connect the X-Agent GitHub repository
2. Set build command: `npm run build`
3. Set publish directory: `docs/site/dist`

### GitHub Pages

Add to `.github/workflows/docs.yml`:

```yaml
name: Deploy Documentation

on:
  push:
    branches: [main]
    paths: ['docs/site/**']

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - run: cd docs/site && npm install && npm run build
      - uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./docs/site/dist
```

### Custom Hosting

```bash
# Build
npm run build

# Copy dist/ to your web server
scp -r dist/* user@server:/var/www/xagent-docs/
```

## Editing Guide

### Writing Docs

1. Use clear, concise language
2. Include code examples where applicable
3. Add links to related pages
4. Use proper headings hierarchy (# for h1, ## for h2, etc.)
5. Keep lines under 100 characters for readability

### Structure

- **Guide**: Concepts and tutorials (what/why/how)
- **API**: Reference documentation (detailed specifications)
- **SDK**: Language-specific client libraries
- **Deploy**: Infrastructure and operations

## Troubleshooting

### Build Fails

```bash
# Clear dependencies and rebuild
rm -rf node_modules package-lock.json
npm install
npm run build
```

### Hot Reload Not Working

Restart the dev server:
```bash
npm run dev
```

### Markdown Not Rendering

- Check file has `.md` extension
- Verify frontmatter syntax (YAML between `---`)
- Check sidebar config includes the page

## Contributing

To contribute documentation:

1. Fork the repository
2. Create a branch: `git checkout -b docs/my-improvement`
3. Make changes and test locally: `npm run dev`
4. Commit: `git commit -m "docs: add new page"`
5. Push and create a Pull Request

## Resources

- [VitePress Documentation](https://vitepress.dev/)
- [Markdown Guide](https://www.markdownguide.org/)
- [X-Agent GitHub](https://github.com/xiongpinji/X-Agent)

## Support

- Report issues: [GitHub Issues](https://github.com/xiongpinji/X-Agent/issues)
- Discuss: [GitHub Discussions](https://github.com/xiongpinji/X-Agent/discussions)
- Chat: [Discord](https://discord.gg/xagent)
