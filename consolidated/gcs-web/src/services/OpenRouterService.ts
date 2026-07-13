/**
 * SkyCore OpenRouter AI Service
 * Streaming chat with AI operator assistant
 */

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
      // In production, use actual OpenRouter API
      const response = await fetch('https://openrouter.ai/api/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${import.meta.env.VITE_OPENROUTER_API_KEY || ''}`,
          'HTTP-Referer': 'https://skycore.local',
          'X-Title': 'SkyCore GCS'
        },
        body: JSON.stringify({
          model: 'anthropic/claude-3-haiku',
          messages: messages.map(m => ({
            role: m.role,
            content: m.content
          })),
          stream: true
        }),
        signal: this.abortController.signal
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      // Handle streaming response
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('No response body');
      }

      let fullText = '';

      while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') {
              onComplete();
              return;
            }

            try {
              const parsed = JSON.parse(data);
              const content = parsed.choices?.[0]?.delta?.content;
              if (content) {
                fullText += content;
                onChunk(content);
              }
            } catch (e) {
              // Skip invalid JSON
            }
          }
        }
      }

      onComplete();
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