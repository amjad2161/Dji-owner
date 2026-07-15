/**
 * SkyCore AI operator chat service.
 *
 * Calls the BACKEND proxy (POST /api/chat) so the OpenRouter API key stays
 * server-side (env OPENROUTER_API_KEY) instead of being shipped in the browser
 * bundle. The proxy is non-streaming, so the reply arrives as a single chunk;
 * it returns an honest "unavailable" reason when no key is configured.
 */

import { apiBase, authHeaders } from './auth';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
}

export class OpenRouterService {
  private static instance: OpenRouterService;
  private abortController: AbortController | null = null;

  private constructor() {}

  public static getInstance(): OpenRouterService {
    if (!OpenRouterService.instance) {
      OpenRouterService.instance = new OpenRouterService();
    }
    return OpenRouterService.instance;
  }

  public async streamCompletion(
    messages: ChatMessage[],
    onChunk: (text: string) => void,
    onComplete: () => void,
    onError: (error: Error) => void
  ): Promise<void> {
    // Stop any existing generation
    this.stopGeneration();

    this.abortController = new AbortController();

    try {
      // Proxy through the backend so the OpenRouter API key never reaches the browser.
      const res = await fetch(`${apiBase()}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({
          messages: messages.map(m => ({ role: m.role, content: m.content })),
        }),
        signal: this.abortController.signal,
      });

      if (!res.ok) {
        throw new Error(`chat proxy -> ${res.status}`);
      }

      const data = await res.json();
      if (data.ok && data.reply) {
        onChunk(data.reply as string);       // non-streaming: the full reply as one chunk
        onComplete();
      } else {
        onError(new Error(data.reason || 'AI chat is not configured on the server'));
      }
    } catch (error) {
      if ((error as Error).name === 'AbortError') {
        console.log('Generation stopped');
      } else {
        onError(error as Error);
      }
    }
  }

  public stopGeneration(): void {
    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }
  }

  // Pre-defined system prompts
  public getSystemPrompt(language: 'he' | 'en' | 'ar' = 'he'): string {
    const prompts = {
      he: `אתה מפעיל AI של מערכת SkyCore GCS לרחפנים. אתה עוזר למפעיל רחפן בטיחותי ומקצועי.
ע Ant תמיד הדגש בטיחות קודם.
• השתמש בשפה פשוטה וברורה.
• הסבר פקודות לפני ביצוע.
• הזהר ממזג אוויר ותנאים מסוכנים.
• עזור בתכנון משימות ופתרת בעיות.`,
      en: `You are an AI assistant for SkyCore GCS drone control system. You help drone operators safely and professionally.
• Always prioritize safety first.
• Use clear, simple language.
• Explain commands before execution.
• Warn about weather and dangerous conditions.
• Help with mission planning and problem solving.`,
      ar: `أنت مساعد ذكاء اصطناعي لنظام SkyCore GCS للتحكم بالطائرات بدون طيار.
• اعط الأولوية دائمًا للسلامة.
• استخدم لغة واضحة وبسيطة.
• اشرح الأوامر قبل التنفيذ.
• احذر من الطقس والظروف الخطرة.
• ساعد في تخطيط المهام وحل المشاكل.`
    };
    return prompts[language];
  }
}