import { describe, expect, it, beforeEach, afterEach } from 'vitest';
import { AutoRouter } from '../src/routing/auto-selector.js';
import { CapabilityMatrix } from '../src/routing/capability-matrix.js';
import { ModelRouter } from '../src/routing/router.js';
import { CooldownTracker } from '../src/resilience/cooldown.js';
import { getExtraRoutes } from '../src/routing/extra-routes.js';
import { createGatewayApp } from '../src/core/server.js';
import { SSRFGuard, createFakeDnsResolver } from '../src/security/ssrf.js';

describe('Auto Routing & Capability Matrix (Step 7)', () => {
  beforeEach(() => {
    SSRFGuard.setResolver(createFakeDnsResolver({
      'api.openai.com': ['93.184.216.34'],
      'api.anthropic.com': ['104.18.2.1'],
      'generativelanguage.googleapis.com': ['142.250.180.10'],
      'openrouter.ai': ['104.22.4.1'],
      'router.requesty.ai': ['104.22.5.1'],
      'api.edenai.run': ['104.22.6.1']
    }));
  });

  afterEach(() => {
    SSRFGuard.resetResolver();
  });

  it('CapabilityMatrix contains required flagship and open-weight models', () => {
    const matrix = CapabilityMatrix.getInstance();
    const gpt4o = matrix.getModel('gpt-4o');
    expect(gpt4o).toBeDefined();
    expect(gpt4o?.hasToolCall).toBe(true);
    expect(gpt4o?.hasVision).toBe(true);

    const claude = matrix.getModel('claude-3-7-sonnet-20250219');
    expect(claude).toBeDefined();
    expect(claude?.hasReasoning).toBe(true);

    const llama = matrix.getModel('llama3.2');
    expect(llama).toBeDefined();
    expect(llama?.provider).toBe('ollama');
  });

  it('AutoRouter routes vision prompts to vision-tier with one-line reason', () => {
    const autoRouter = AutoRouter.getInstance();
    const decision = autoRouter.route({
      model: 'auto',
      messages: [
        {
          role: 'user',
          content: [
            { type: 'text', text: 'What is inside this image?' },
            { type: 'image_url', image_url: { url: 'data:image/png;base64,iVBORw0KGgo...' } }
          ]
        }
      ]
    });

    expect(decision.targetAlias).toBe('vision-tier');
    expect(decision.oneLineReason).toContain('vision-tier');
    expect(decision.oneLineReason.length).toBeGreaterThan(10);
    expect(decision.isOverride).toBe(false);
  });

  it('AutoRouter routes tool calling prompts to smart-tier with one-line reason', () => {
    const autoRouter = AutoRouter.getInstance();
    const decision = autoRouter.route({
      model: 'auto',
      messages: [{ role: 'user', content: 'What is the stock price of AAPL?' }],
      tools: [
        {
          type: 'function',
          function: {
            name: 'get_stock_quote',
            parameters: { type: 'object', properties: { symbol: { type: 'string' } } }
          }
        }
      ]
    });

    expect(decision.targetAlias).toBe('smart-tier');
    expect(decision.oneLineReason).toContain('smart-tier');
    expect(decision.oneLineReason).toContain('tool execution');
  });

  it('AutoRouter routes complex coding queries to smart-tier', () => {
    const autoRouter = AutoRouter.getInstance();
    const decision = autoRouter.route({
      model: 'auto',
      messages: [
        {
          role: 'user',
          content: '```python\ndef fibonacci(n):\n    if n <= 1: return n\n    return fibonacci(n-1) + fibonacci(n-2)\n```\nOptimize this function using memoization and analyze trade-offs.'
        }
      ]
    });

    expect(decision.targetAlias).toBe('smart-tier');
    expect(decision.oneLineReason).toContain('software development');
  });

  it('AutoRouter routes general conversation to fast-tier for speed & efficiency', () => {
    const autoRouter = AutoRouter.getInstance();
    const decision = autoRouter.route({
      model: 'auto',
      messages: [{ role: 'user', content: 'Hello! How are you doing today?' }]
    });

    expect(decision.targetAlias).toBe('fast-tier');
    expect(decision.oneLineReason).toContain('fast-tier');
  });

  it('AutoRouter honors manual override with one-line justification', () => {
    const autoRouter = AutoRouter.getInstance();
    const decision = autoRouter.route(
      {
        model: 'auto',
        messages: [{ role: 'user', content: 'Simple query' }]
      },
      'smart-tier'
    );

    expect(decision.targetAlias).toBe('smart-tier');
    expect(decision.isOverride).toBe(true);
    expect(decision.oneLineReason).toContain("Manual override applied: User explicitly selected 'smart-tier'");
  });

  it('ModelRouter dynamically resolves "auto" alias to registered tier and records reason', () => {
    const tracker = new CooldownTracker();
    const router = new ModelRouter(tracker);

    // Register smart-tier and fast-tier
    router.registerRoute({
      alias: 'fast-tier',
      targets: [
        {
          id: 'mini-target',
          provider: 'openai',
          model: 'gpt-4o-mini',
          config: { id: 'cfg1', name: 'OpenAI Mini', baseUrl: 'https://api.openai.com' }
        }
      ]
    });

    const targets = router.resolveTargets('auto', undefined, {
      model: 'auto',
      messages: [{ role: 'user', content: 'Good morning!' }]
    });

    expect(targets.length).toBe(1);
    expect(targets[0].model).toBe('gpt-4o-mini');
    expect(router.lastResolvedReason).toContain('fast-tier');
  });

  it('Extra routes (OpenRouter, Requesty, Eden AI) are structured properly', () => {
    const extraRoutes = getExtraRoutes();
    expect(extraRoutes.length).toBe(3);

    const aliases = extraRoutes.map(r => r.alias);
    expect(aliases).toContain('openrouter');
    expect(aliases).toContain('requesty');
    expect(aliases).toContain('eden-ai');

    const openrouter = extraRoutes.find(r => r.alias === 'openrouter');
    expect(openrouter?.targets[0].provider).toBe('openai');
  });

  it('Server emits x-pheonix-auto-reason header on completions when auto routing is used', async () => {
    const { app, router } = createGatewayApp();

    router.registerRoute({
      alias: 'fast-tier',
      targets: [
        {
          id: 'mock-target',
          provider: 'openai',
          model: 'gpt-4o-mini',
          config: { id: 'cfg1', name: 'Mock Fast', baseUrl: 'https://api.openai.com', apiKey: 'fake-key' }
        }
      ]
    });

    // Mock global fetch for the upstream call
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async () => {
      return new Response(JSON.stringify({
        id: 'chatcmpl-mock-123',
        object: 'chat.completion',
        created: Math.floor(Date.now() / 1000),
        model: 'gpt-4o-mini',
        choices: [
          {
            index: 0,
            message: { role: 'assistant', content: 'Hello there!' },
            finish_reason: 'stop'
          }
        ],
        usage: { prompt_tokens: 10, completion_tokens: 5, total_tokens: 15 }
      }), {
        status: 200,
        headers: { 'content-type': 'application/json' }
      });
    };

    try {
      const res = await app.request('/v1/chat/completions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: 'auto',
          messages: [{ role: 'user', content: 'Hello!' }]
        })
      });

      expect(res.status).toBe(200);
      const autoReasonHeader = res.headers.get('x-pheonix-auto-reason');
      expect(autoReasonHeader).toBeDefined();
      expect(autoReasonHeader).toContain('fast-tier');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it('Server honors X-Pheonix-Model-Override header and reflects override reason', async () => {
    const { app, router } = createGatewayApp();

    router.registerRoute({
      alias: 'smart-tier',
      targets: [
        {
          id: 'mock-smart-target',
          provider: 'openai',
          model: 'gpt-4o',
          config: { id: 'cfg2', name: 'Mock Smart', baseUrl: 'https://api.openai.com', apiKey: 'fake-key' }
        }
      ]
    });

    const originalFetch = globalThis.fetch;
    globalThis.fetch = async () => {
      return new Response(JSON.stringify({
        id: 'chatcmpl-mock-override',
        object: 'chat.completion',
        created: Math.floor(Date.now() / 1000),
        model: 'gpt-4o',
        choices: [
          {
            index: 0,
            message: { role: 'assistant', content: 'Overridden smart response' },
            finish_reason: 'stop'
          }
        ],
        usage: { prompt_tokens: 8, completion_tokens: 6, total_tokens: 14 }
      }), {
        status: 200,
        headers: { 'content-type': 'application/json' }
      });
    };

    try {
      const res = await app.request('/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-pheonix-model-override': 'smart-tier'
        },
        body: JSON.stringify({
          model: 'fast-tier',
          messages: [{ role: 'user', content: 'Simple query' }]
        })
      });

      expect(res.status).toBe(200);
      const autoReasonHeader = res.headers.get('x-pheonix-auto-reason');
      expect(autoReasonHeader).toBeDefined();
      expect(autoReasonHeader).toContain("Manual override applied: User explicitly selected 'smart-tier'");
    } finally {
      globalThis.fetch = originalFetch;
    }
  });
});
