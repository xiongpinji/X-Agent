import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'X-Agent',
  description: 'Enterprise Autonomous Agent Framework Documentation',
  lang: 'en-US',
  
  // Deployment settings
  head: [
    ['meta', { name: 'viewport', content: 'width=device-width, initial-scale=1' }],
    ['meta', { name: 'description', content: 'X-Agent: Enterprise-grade autonomous agent framework for AI product builders and enterprises' }],
    ['meta', { name: 'og:title', content: 'X-Agent Documentation' }],
    ['meta', { name: 'og:description', content: 'Build intelligent autonomous agents at enterprise scale' }],
    ['meta', { name: 'og:type', content: 'website' }],
  ],

  themeConfig: {
    // Site-wide navigation
    nav: [
      { text: 'Guide', link: '/guide/' },
      { text: 'API', link: '/api/' },
      { text: 'SDK', link: '/sdk/' },
      { text: 'Deploy', link: '/deploy/' },
      {
        text: 'More',
        items: [
          { text: 'Plugins', link: '/plugins/' },
          { text: 'FAQ', link: '/faq/' },
          { text: 'Contributing', link: '/contributing/' },
        ]
      }
    ],

    // Documentation sidebar navigation by section
    sidebar: {
      '/guide/': [
        {
          text: 'Getting Started',
          items: [
            { text: 'Introduction', link: '/guide/' },
            { text: 'Quick Start', link: '/guide/quickstart' },
            { text: 'Installation', link: '/guide/installation' },
            { text: 'Your First Agent', link: '/guide/first-agent' },
          ]
        },
        {
          text: 'Core Concepts',
          items: [
            { text: 'Architecture', link: '/guide/architecture' },
            { text: 'Agents', link: '/guide/agents' },
            { text: 'Tools', link: '/guide/tools' },
            { text: 'Memory Systems', link: '/guide/memory' },
            { text: 'Workflows', link: '/guide/workflows' },
          ]
        },
        {
          text: 'Advanced Topics',
          items: [
            { text: 'Multi-Agent Collaboration', link: '/guide/multi-agent' },
            { text: 'Custom Tool Development', link: '/guide/custom-tools' },
            { text: 'Hooks & Lifecycle', link: '/guide/hooks' },
            { text: 'Performance Optimization', link: '/guide/performance' },
            { text: 'Security Best Practices', link: '/guide/security' },
          ]
        },
        {
          text: 'Configuration',
          items: [
            { text: 'Configuration Overview', link: '/guide/configuration' },
            { text: 'Environment Variables', link: '/guide/env-config' },
            { text: 'LLM Providers', link: '/guide/llm-providers' },
            { text: 'Database Setup', link: '/guide/database' },
            { text: 'Observability', link: '/guide/observability' },
          ]
        }
      ],

      '/api/': [
        {
          text: 'API Overview',
          items: [
            { text: 'Introduction', link: '/api/' },
            { text: 'Authentication', link: '/api/authentication' },
            { text: 'Rate Limiting', link: '/api/rate-limiting' },
            { text: 'Error Handling', link: '/api/errors' },
            { text: 'Versioning', link: '/api/versioning' },
          ]
        },
        {
          text: 'Core Resources',
          items: [
            { text: 'Agents', link: '/api/agents' },
            { text: 'Runs', link: '/api/runs' },
            { text: 'Workflows', link: '/api/workflows' },
            { text: 'Tools', link: '/api/tools' },
            { text: 'Skills', link: '/api/skills' },
          ]
        },
        {
          text: 'Advanced APIs',
          items: [
            { text: 'Memory APIs', link: '/api/memory' },
            { text: 'Observability', link: '/api/observability' },
            { text: 'Webhooks', link: '/api/webhooks' },
            { text: 'Streaming', link: '/api/streaming' },
            { text: 'Batch Operations', link: '/api/batch' },
          ]
        },
        {
          text: 'Examples',
          items: [
            { text: 'Code Examples', link: '/api/examples' },
            { text: 'Integration Guides', link: '/api/integrations' },
            { text: 'CLI Usage', link: '/api/cli' },
          ]
        }
      ],

      '/sdk/': [
        {
          text: 'SDK Overview',
          items: [
            { text: 'Introduction', link: '/sdk/' },
            { text: 'Installation', link: '/sdk/installation' },
            { text: 'Python SDK', link: '/sdk/python' },
            { text: 'TypeScript SDK', link: '/sdk/typescript' },
            { text: 'REST Client', link: '/sdk/rest' },
          ]
        },
        {
          text: 'Python SDK',
          items: [
            { text: 'Getting Started', link: '/sdk/python/quickstart' },
            { text: 'Client Configuration', link: '/sdk/python/client' },
            { text: 'Agent Operations', link: '/sdk/python/agents' },
            { text: 'Error Handling', link: '/sdk/python/errors' },
            { text: 'Advanced Usage', link: '/sdk/python/advanced' },
          ]
        },
        {
          text: 'TypeScript SDK',
          items: [
            { text: 'Getting Started', link: '/sdk/typescript/quickstart' },
            { text: 'Client Configuration', link: '/sdk/typescript/client' },
            { text: 'Agent Operations', link: '/sdk/typescript/agents' },
            { text: 'Error Handling', link: '/sdk/typescript/errors' },
            { text: 'Advanced Usage', link: '/sdk/typescript/advanced' },
          ]
        }
      ],

      '/deploy/': [
        {
          text: 'Deployment Guide',
          items: [
            { text: 'Overview', link: '/deploy/' },
            { text: 'Docker Setup', link: '/deploy/docker' },
            { text: 'Docker Compose', link: '/deploy/docker-compose' },
            { text: 'Kubernetes', link: '/deploy/kubernetes' },
          ]
        },
        {
          text: 'Production Deployments',
          items: [
            { text: 'AWS ECS', link: '/deploy/aws-ecs' },
            { text: 'AWS EKS', link: '/deploy/aws-eks' },
            { text: 'Google Cloud', link: '/deploy/google-cloud' },
            { text: 'Azure', link: '/deploy/azure' },
            { text: 'Self-Hosted', link: '/deploy/self-hosted' },
          ]
        },
        {
          text: 'Operations',
          items: [
            { text: 'Monitoring', link: '/deploy/monitoring' },
            { text: 'Logging', link: '/deploy/logging' },
            { text: 'Database Management', link: '/deploy/database' },
            { text: 'Backup & Recovery', link: '/deploy/backup' },
            { text: 'Scaling', link: '/deploy/scaling' },
          ]
        },
        {
          text: 'Security',
          items: [
            { text: 'Network Security', link: '/deploy/network-security' },
            { text: 'Authentication', link: '/deploy/authentication' },
            { text: 'Secrets Management', link: '/deploy/secrets' },
            { text: 'SSL/TLS', link: '/deploy/tls' },
          ]
        }
      ]
    },

    // Social links in footer
    socialLinks: [
      { icon: 'github', link: 'https://github.com/xiongpinji/X-Agent' },
      { icon: 'x', link: 'https://x.com/xagentdev' },
      { icon: 'discord', link: 'https://discord.gg/xagent' },
    ],

    // Footer
    footer: {
      message: 'Released under the Apache License 2.0',
      copyright: 'Copyright © 2024-2026 X-Agent Contributors'
    },

    // Customize sidebar label
    sidebarMenuLabel: 'Menu',
    returnToTopLabel: 'Return to top',
    langMenuLabel: 'Change language',
    darkModeSwitchLabel: 'Appearance',

    // Search
    search: {
      provider: 'local',
      options: {
        detailedView: true,
      }
    }
  },

  // Markdown configuration
  markdown: {
    theme: {
      light: 'github-light',
      dark: 'github-dark'
    }
  }
})
