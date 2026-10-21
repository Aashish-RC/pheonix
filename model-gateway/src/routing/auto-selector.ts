/**
 * Pheonix Custom Auto Router with One-Line Reason
 * Dynamically analyzes prompt traits, tool usage, and modality to route to the optimal model.
 */

import { ChatCompletionRequest } from '../types/chat.js';
import { CapabilityMatrix } from './capability-matrix.js';

export interface AutoRouteDecision {
  model: string;
  targetAlias: string;
  oneLineReason: string;
  isOverride: boolean;
}

export class AutoRouter {
  private static instance: AutoRouter;
  private matrix: CapabilityMatrix;

  private constructor() {
    this.matrix = CapabilityMatrix.getInstance();
  }

  public static getInstance(): AutoRouter {
    if (!AutoRouter.instance) {
      AutoRouter.instance = new AutoRouter();
    }
    return AutoRouter.instance;
  }

  public route(
    req: ChatCompletionRequest,
    manualOverride?: string
  ): AutoRouteDecision {
    // 1. Manual Override check
    if (manualOverride && manualOverride.trim() !== '') {
      const cleanOverride = manualOverride.trim().toLowerCase();
      return {
        model: cleanOverride,
        targetAlias: cleanOverride,
        oneLineReason: `Manual override applied: User explicitly selected '${cleanOverride}' via X-Pheonix-Model-Override.`,
        isOverride: true
      };
    }

    // 2. Modality Analysis: Detect Vision / Multi-modal payloads
    const hasVision = this.detectVisionInput(req);
    if (hasVision) {
      const best = this.matrix.findBestMatch({ requiresVision: true });
      return {
        model: best.model,
        targetAlias: 'vision-tier',
        oneLineReason: 'Selected vision-tier: Multimodal image or document visual payload detected in prompt.',
        isOverride: false
      };
    }

    // 3. Tool Calling / Function calling
    const hasTools = Array.isArray(req.tools) && req.tools.length > 0;
    if (hasTools) {
      const best = this.matrix.findBestMatch({ requiresToolCall: true, requiresReasoning: true });
      return {
        model: best.model,
        targetAlias: 'smart-tier',
        oneLineReason: `Selected smart-tier: High-precision tool execution required for ${req.tools?.length} registered functions.`,
        isOverride: false
      };
    }

    // 4. Prompt Complexity Analysis (Code, Math, Long context)
    const totalChars = req.messages.reduce((acc, m) => acc + (typeof m.content === 'string' ? m.content.length : 100), 0);
    const combinedContent = req.messages.map((m) => (typeof m.content === 'string' ? m.content : '')).join(' ');

    const hasCodeIndicators = /```|function |class |def |SELECT |import |const |let /i.test(combinedContent);
    const hasReasoningIndicators = /explain step by step|prove that|derive|analyze the trade-offs|architecture design/i.test(combinedContent);

    if (totalChars > 12000 || hasCodeIndicators || hasReasoningIndicators) {
      const trait = hasCodeIndicators ? 'software development' : hasReasoningIndicators ? 'deep step-by-step reasoning' : 'large context processing';
      const best = this.matrix.findBestMatch({ requiresCode: hasCodeIndicators, requiresReasoning: hasReasoningIndicators });
      return {
        model: best.model,
        targetAlias: 'smart-tier',
        oneLineReason: `Selected smart-tier: High-complexity prompt detected requiring ${trait}.`,
        isOverride: false
      };
    }

    // 5. Default Fast Tier for standard conversational interaction
    const best = this.matrix.findBestMatch({ preferUltraFast: true, preferLowCost: true });
    return {
      model: best.model,
      targetAlias: 'fast-tier',
      oneLineReason: 'Selected fast-tier: Standard conversational query matched for ultra-fast, cost-effective inference.',
      isOverride: false
    };
  }

  private detectVisionInput(req: ChatCompletionRequest): boolean {
    for (const msg of req.messages) {
      if (Array.isArray(msg.content)) {
        for (const part of msg.content) {
          if (part && typeof part === 'object' && (part.type === 'image_url' || 'image_url' in part)) {
            return true;
          }
        }
      }
    }
    return false;
  }
}
