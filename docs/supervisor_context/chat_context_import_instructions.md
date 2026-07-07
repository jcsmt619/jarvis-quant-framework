# Chat Context Import Instructions

The OpenAI API supervisor cannot automatically read private ChatGPT conversations.

To give it prior chat knowledge, convert important chats into local repo files.

Recommended folder:

docs/supervisor_context/imported_chats/

Recommended files:
- moonshot_jarvis_strategy_chat.md
- ai_for_quant_trading_chat.md
- jarvis_master_roadmap_chat.md

Rules:
- Remove API keys, tokens, passwords, broker credentials, personal credentials, and private secrets.
- Summarize long chats into decisions, requirements, and constraints.
- Prefer source-of-truth summaries over huge raw transcripts.
- Keep live trading disabled unless explicitly approved later.
