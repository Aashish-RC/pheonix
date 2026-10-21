/**
 * Pheonix Model Capability Matrix
 * Indexes model traits, modalities, context limits, and cost tiers.
 */

export interface ModelCapability {
  model: string;
  provider: string;
  contextWindow: number;
  hasVision: boolean;
  hasCode: boolean;
  hasReasoning: boolean;
  hasToolCall: boolean;
  costTier: 'free' | 'low' | 'medium' | 'high';
  latencyTier: 'ultra-fast' | 'fast' | 'standard';
}

export class CapabilityMatrix {
  private static instance: CapabilityMatrix;
  private capabilities: Map<string, ModelCapability> = new Map();

  private constructor() {
    this.registerDefaults();
  }

  public static getInstance(): CapabilityMatrix {
    if (!CapabilityMatrix.instance) {
      CapabilityMatrix.instance = new CapabilityMatrix();
    }
    return CapabilityMatrix.instance;
  }

  private registerDefaults(): void {
    const defaults: ModelCapability[] = [
      {
        model: 'gpt-4o',
        provider: 'openai',
        contextWindow: 128000,
        hasVision: true,
        hasCode: true,
        hasReasoning: true,
        hasToolCall: true,
        costTier: 'medium',
        latencyTier: 'fast'
      },
      {
        model: 'gpt-4o-mini',
        provider: 'openai',
        contextWindow: 128000,
        hasVision: true,
        hasCode: true,
        hasReasoning: false,
        hasToolCall: true,
        costTier: 'low',
        latencyTier: 'ultra-fast'
      },
      {
        model: 'claude-3-7-sonnet-20250219',
        provider: 'anthropic',
        contextWindow: 200000,
        hasVision: true,
        hasCode: true,
        hasReasoning: true,
        hasToolCall: true,
        costTier: 'high',
        latencyTier: 'standard'
      },
      {
        model: 'claude-3-5-haiku-20241022',
        provider: 'anthropic',
        contextWindow: 200000,
        hasVision: false,
        hasCode: true,
        hasReasoning: false,
        hasToolCall: true,
        costTier: 'low',
        latencyTier: 'ultra-fast'
      },
      {
        model: 'gemini-1.5-pro',
        provider: 'gemini',
        contextWindow: 1000000,
        hasVision: true,
        hasCode: true,
        hasReasoning: true,
        hasToolCall: true,
        costTier: 'medium',
        latencyTier: 'fast'
      },
      {
        model: 'gemini-2.0-flash',
        provider: 'gemini',
        contextWindow: 1000000,
        hasVision: true,
        hasCode: true,
        hasReasoning: false,
        hasToolCall: true,
        costTier: 'low',
        latencyTier: 'ultra-fast'
      },
      {
        model: 'llama3.2',
        provider: 'ollama',
        contextWindow: 8192,
        hasVision: false,
        hasCode: false,
        hasReasoning: false,
        hasToolCall: false,
        costTier: 'free',
        latencyTier: 'fast'
      }
    ];

    for (const cap of defaults) {
      this.capabilities.set(cap.model.toLowerCase(), cap);
    }
  }

  private activeProviders: Set<string> = new Set();

  public get(model: string): ModelCapability | undefined {
    return this.capabilities.get(model.toLowerCase());
  }

  public getModel(model: string): ModelCapability | undefined {
    return this.get(model);
  }

  public register(capability: ModelCapability): void {
    this.capabilities.set(capability.model.toLowerCase(), capability);
  }

  public setProviderActive(provider: string, active: boolean): void {
    const key = provider.toLowerCase();
    if (active) {
      this.activeProviders.add(key);
    } else {
      this.activeProviders.delete(key);
    }
  }

  public isProviderActive(provider: string): boolean {
    if (this.activeProviders.size === 0) return true;
    return this.activeProviders.has(provider.toLowerCase());
  }

  public resetActiveProviders(): void {
    this.activeProviders.clear();
  }

  public getActiveProviders(): string[] {
    return Array.from(this.activeProviders);
  }

  public syncProviders(
    updates: Array<{
      provider: string;
      active: boolean;
      latencyMs?: number | null;
      models?: string[];
    }>
  ): void {
    for (const update of updates) {
      this.setProviderActive(update.provider, update.active);
      if (update.models) {
        for (const m of update.models) {
          if (!this.capabilities.has(m.toLowerCase())) {
            this.register({
              model: m,
              provider: update.provider.toLowerCase(),
              contextWindow: 16384,
              hasVision: false,
              hasCode: true,
              hasReasoning: false,
              hasToolCall: true,
              costTier: 'medium',
              latencyTier: update.latencyMs && update.latencyMs < 500 ? 'ultra-fast' : 'fast'
            });
          }
        }
      }
    }
  }

  public findBestMatch(criteria: {
    requiresVision?: boolean;
    requiresCode?: boolean;
    requiresReasoning?: boolean;
    requiresToolCall?: boolean;
    preferLowCost?: boolean;
    preferUltraFast?: boolean;
  }): ModelCapability {
    let candidates = Array.from(this.capabilities.values());

    // If explicit active providers are tracked, filter by active providers
    if (this.activeProviders.size > 0) {
      const activeCandidates = candidates.filter((c) =>
        this.activeProviders.has(c.provider.toLowerCase())
      );
      if (activeCandidates.length > 0) {
        candidates = activeCandidates;
      }
    }

    if (criteria.requiresVision) {
      candidates = candidates.filter((c) => c.hasVision);
    }
    if (criteria.requiresCode) {
      candidates = candidates.filter((c) => c.hasCode);
    }
    if (criteria.requiresReasoning) {
      candidates = candidates.filter((c) => c.hasReasoning);
    }
    if (criteria.requiresToolCall) {
      candidates = candidates.filter((c) => c.hasToolCall);
    }

    if (candidates.length === 0) {
      // Fallback to default flagship model if criteria too restrictive
      return this.capabilities.get('gpt-4o')!;
    }

    if (criteria.preferUltraFast) {
      const ultra = candidates.find((c) => c.latencyTier === 'ultra-fast');
      if (ultra) return ultra;
    }

    if (criteria.preferLowCost) {
      const lowCost = candidates.find((c) => c.costTier === 'free' || c.costTier === 'low');
      if (lowCost) return lowCost;
    }

    // Default to first match
    return candidates[0];
  }
}

