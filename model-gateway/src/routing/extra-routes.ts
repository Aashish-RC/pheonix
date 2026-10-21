/**
 * Extra Routes & Provider Connectors
 * OpenRouter, Requesty, and Eden AI provider endpoints and routing registrations.
 */

import { ModelRouteConfig } from './router.js';

export function getExtraRoutes(): ModelRouteConfig[] {
  return [
    {
      alias: 'openrouter',
      strategy: 'least-busy',
      targets: [
        {
          id: 'openrouter-primary',
          provider: 'openai', // OpenRouter exposes OpenAI-compatible /chat/completions
          model: 'auto',
          config: {
            id: 'openrouter-config',
            name: 'OpenRouter Aggregator',
            baseUrl: process.env.OPENROUTER_BASE_URL || 'https://openrouter.ai/api/v1',
            apiKey: process.env.OPENROUTER_API_KEY || ''
          }
        }
      ]
    },
    {
      alias: 'requesty',
      strategy: 'weighted',
      targets: [
        {
          id: 'requesty-primary',
          provider: 'openai', // Requesty unified API
          model: 'default',
          config: {
            id: 'requesty-config',
            name: 'Requesty Gateway Connector',
            baseUrl: process.env.REQUESTY_BASE_URL || 'https://router.requesty.ai/v1',
            apiKey: process.env.REQUESTY_API_KEY || ''
          }
        }
      ]
    },
    {
      alias: 'eden-ai',
      strategy: 'weighted',
      targets: [
        {
          id: 'eden-ai-primary',
          provider: 'openai', // Eden AI multi-provider connector
          model: 'eden-ai-default',
          config: {
            id: 'eden-ai-config',
            name: 'Eden AI Connector',
            baseUrl: process.env.EDEN_AI_BASE_URL || 'https://api.edenai.run/v2/workflow',
            apiKey: process.env.EDEN_AI_API_KEY || ''
          }
        }
      ]
    }
  ];
}
