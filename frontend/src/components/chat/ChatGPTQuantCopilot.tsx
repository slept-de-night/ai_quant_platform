import React, { useState, useRef, useEffect } from 'react';
import { api } from '../../services/api';
import {
  MessageSquare,
  Send,
  Bot,
  User,
  X,
  Minimize2,
  Maximize2,
  Sparkles,
  RefreshCw,
  Zap,
  CheckCircle2,
  AlertCircle
} from 'lucide-react';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

interface ChatGPTQuantCopilotProps {
  selectedSymbol: string;
}

export const ChatGPTQuantCopilot: React.FC<ChatGPTQuantCopilotProps> = ({ selectedSymbol }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [modelBadge, setModelBadge] = useState<string>('ChatGPT Quant');
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      content: `👋 Hello! I am your **ChatGPT Quant Co-Pilot**.\n\nI have real-time institutional access to **${selectedSymbol}** balance sheets, 5-year financial statements, Altman Z-Score solvency models, and pre-trade portfolio VaR risk gates.\n\nHow can I assist your quantitative analysis today?`,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (isOpen) {
      scrollToBottom();
    }
  }, [messages, isOpen]);

  const handleSend = async (customPrompt?: string) => {
    const textToSend = customPrompt || input;
    if (!textToSend.trim() || isLoading) return;

    const userMsg: ChatMessage = {
      role: 'user',
      content: textToSend,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    if (!customPrompt) setInput('');
    setIsLoading(true);

    try {
      const history = messages
        .filter((m) => m.role === 'user' || m.role === 'assistant')
        .map((m) => ({ role: m.role, content: m.content }));
      history.push({ role: 'user', content: textToSend });

      const res = await api.chatWithCopilot(history, selectedSymbol);

      setModelBadge(res.model || 'gpt-4o');
      setIsConnected(Boolean(res.openai_connected));

      const assistantMsg: ChatMessage = {
        role: 'assistant',
        content: res.reply || 'No response received.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        role: 'assistant',
        content: `⚠️ Failed to connect to ChatGPT: ${err.message || 'Network error'}. Please check your server connection.`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const quickPrompts = [
    `Analyze ${selectedSymbol}'s Balance Sheet & Net Cash`,
    `Explain Altman Z-Score & Piotroski F for ${selectedSymbol}`,
    `Suggest an alpha factor strategy for ${selectedSymbol}`,
    `What are the 1-Day 95% VaR & Risk Limits?`,
  ];

  return (
    <div className="fixed bottom-5 right-5 z-50">
      {/* Floating Toggle Button (When Closed) */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="flex items-center gap-2 px-4 py-3 bg-gradient-to-r from-accent-cyan via-cyan-500 to-accent-blue text-slate-950 font-bold rounded-full shadow-2xl shadow-accent-cyan/30 hover:scale-105 transition cursor-pointer border border-cyan-300/40 group"
        >
          <Bot className="w-5 h-5 group-hover:rotate-12 transition-transform" />
          <span className="text-xs font-mono tracking-wide">ChatGPT Quant Co-Pilot</span>
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
        </button>
      )}

      {/* Interactive Chat Drawer Window (When Open) */}
      {isOpen && (
        <div
          className={`flex flex-col bg-card border border-card-border rounded-2xl shadow-2xl overflow-hidden transition-all duration-200 ${
            isExpanded
              ? 'w-[90vw] sm:w-[650px] h-[80vh]'
              : 'w-[90vw] sm:w-[420px] h-[540px]'
          }`}
        >
          {/* Header */}
          <div className="p-3.5 bg-background border-b border-card-border flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="p-1.5 rounded-lg bg-accent-cyan/10 border border-accent-cyan/30 text-accent-cyan">
                <Bot className="w-4 h-4" />
              </div>
              <div>
                <div className="flex items-center gap-1.5">
                  <h3 className="text-xs font-bold text-slate-100 font-mono">ChatGPT Quant Co-Pilot</h3>
                  <span
                    className={`px-1.5 py-0.2 text-[9px] font-mono font-bold rounded border ${
                      isConnected
                        ? 'bg-accent-emerald/20 text-accent-emerald border-accent-emerald/40'
                        : 'bg-accent-cyan/10 text-accent-cyan border-accent-cyan/30'
                    }`}
                  >
                    {modelBadge}
                  </span>
                </div>
                <div className="text-[10px] text-slate-400 font-mono">
                  Context: <strong className="text-accent-cyan">{selectedSymbol}</strong> • Quantitative Assistant
                </div>
              </div>
            </div>

            <div className="flex items-center gap-1 text-slate-400">
              <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="p-1 hover:text-slate-200 rounded hover:bg-card-border transition cursor-pointer"
                title={isExpanded ? 'Collapse' : 'Expand'}
              >
                {isExpanded ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
              </button>
              <button
                onClick={() => setIsOpen(false)}
                className="p-1 hover:text-slate-200 rounded hover:bg-card-border transition cursor-pointer"
                title="Close"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Messages Body */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3.5 text-xs font-sans">
            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex gap-2.5 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                {msg.role === 'assistant' && (
                  <div className="w-6 h-6 rounded-full bg-accent-cyan/10 border border-accent-cyan/30 flex items-center justify-center text-accent-cyan shrink-0 mt-0.5">
                    <Bot className="w-3.5 h-3.5" />
                  </div>
                )}

                <div
                  className={`p-3 rounded-xl max-w-[84%] leading-relaxed ${
                    msg.role === 'user'
                      ? 'bg-accent-cyan text-slate-950 font-semibold rounded-tr-none'
                      : 'bg-background border border-card-border text-slate-200 rounded-tl-none space-y-1.5 shadow-sm'
                  }`}
                >
                  <div className="whitespace-pre-wrap">{msg.content}</div>
                  <div
                    className={`text-[9px] font-mono text-right mt-1 ${
                      msg.role === 'user' ? 'text-slate-800' : 'text-slate-500'
                    }`}
                  >
                    {msg.timestamp}
                  </div>
                </div>

                {msg.role === 'user' && (
                  <div className="w-6 h-6 rounded-full bg-slate-800 border border-card-border flex items-center justify-center text-slate-300 shrink-0 mt-0.5">
                    <User className="w-3.5 h-3.5" />
                  </div>
                )}
              </div>
            ))}

            {isLoading && (
              <div className="flex gap-2.5 items-start">
                <div className="w-6 h-6 rounded-full bg-accent-cyan/10 border border-accent-cyan/30 flex items-center justify-center text-accent-cyan shrink-0 mt-0.5">
                  <Bot className="w-3.5 h-3.5 animate-spin" />
                </div>
                <div className="p-3 rounded-xl bg-background border border-card-border text-slate-400 font-mono text-[11px] flex items-center gap-2">
                  <Sparkles className="w-3.5 h-3.5 text-accent-cyan animate-pulse" />
                  <span>Synthesizing quantitative reasoning with ChatGPT...</span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Quick Action Suggestion Chips */}
          <div className="px-3 py-2 bg-background/50 border-t border-card-border overflow-x-auto flex gap-1.5 no-scrollbar">
            {quickPrompts.map((prompt, i) => (
              <button
                key={i}
                onClick={() => handleSend(prompt)}
                disabled={isLoading}
                className="px-2.5 py-1 text-[10px] font-mono rounded bg-card hover:bg-card-border border border-card-border text-slate-300 transition shrink-0 cursor-pointer disabled:opacity-50"
              >
                {prompt}
              </button>
            ))}
          </div>

          {/* Input Footer */}
          <div className="p-3 bg-background border-t border-card-border flex items-center gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isLoading}
              placeholder={`Ask ChatGPT about ${selectedSymbol} fundamentals, risk, or alphas...`}
              className="flex-1 bg-card border border-card-border rounded-lg px-3 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-accent-cyan font-mono"
            />
            <button
              onClick={() => handleSend()}
              disabled={!input.trim() || isLoading}
              className="p-2 rounded-lg bg-accent-cyan text-slate-950 hover:bg-cyan-400 transition cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed shrink-0"
              title="Send to ChatGPT"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
