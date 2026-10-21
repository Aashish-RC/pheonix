/**
 * Pheonix Gateway -> Memory Subsystem Writeback
 * Pushes conversation turns from model completions to the 3-tier memory engine.
 */

import { ChatCompletionRequest, ChatCompletionResponse } from '../types/chat.js';
import { RequestContext } from '../types/ra1.js';

export interface MemoryWritebackOptions {
  serviceUrl?: string;
  enabled?: boolean;
}

export class MemoryWritebackService {
  private static instance: MemoryWritebackService;
  private serviceUrl: string;
  private enabled: boolean;
  private dispatchedEvents: Array<{ userId: string; text: string; sessionId?: string }> = [];

  constructor(options?: MemoryWritebackOptions) {
    this.serviceUrl = (options?.serviceUrl || process.env.MEMORY_SERVICE_URL || 'http://localhost:8001').replace(/\/+$/, '');
    this.enabled = options?.enabled ?? true;
  }

  public static getInstance(options?: MemoryWritebackOptions): MemoryWritebackService {
    if (!MemoryWritebackService.instance) {
      MemoryWritebackService.instance = new MemoryWritebackService(options);
    }
    return MemoryWritebackService.instance;
  }

  public getDispatchedEvents() {
    return [...this.dispatchedEvents];
  }

  public clearDispatchedEvents() {
    this.dispatchedEvents = [];
  }

  public async recordChatTurn(
    req: ChatCompletionRequest,
    res: ChatCompletionResponse,
    ctx: RequestContext
  ): Promise<boolean> {
    if (!this.enabled) return false;

    const userMessage = [...req.messages].reverse().find((m) => m.role === 'user');
    const assistantContent = res.choices?.[0]?.message?.content || '';

    if (!userMessage || !assistantContent) return false;

    const userText = typeof userMessage.content === 'string'
      ? userMessage.content
      : JSON.stringify(userMessage.content);

    const exchangeText = `User: ${userText}\nAssistant: ${assistantContent}`;
    const userId = ctx.actor || (ctx.metadata?.userId as string) || 'default_user';
    const sessionId = (ctx.metadata?.sessionId as string) || ctx.requestId;

    this.dispatchedEvents.push({ userId, text: exchangeText, sessionId });

    try {
      const response = await fetch(`${this.serviceUrl}/api/v1/remember`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          session_id: sessionId,
          text: exchangeText,
          metadata: {
            model: res.model,
            tokens_total: res.usage?.total_tokens,
            gateway_request_id: ctx.requestId
          }
        })
      });
      return response.ok;
    } catch {
      // Non-blocking telemetry writeback: failure in memory storage does not crash gateway completion
      return false;
    }
  }
}
