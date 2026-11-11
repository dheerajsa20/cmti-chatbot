# Mitra as an intelligent agent

## PEAS description
| | |
|---|---|
| **Performance measure** | Accurate answers grounded in the knowledge base; correct refusals for out-of-scope requests; "I don't know" instead of invented facts; replies under 5 seconds; low token cost; positive user feedback (thumbs up) |
| **Environment** | Website visitors (students, graduates, companies, colleges) asking questions in a chat window; CMTI's knowledge file; the language model (Gemini, called through the OpenAI SDK); the SQLite log |
| **Actuators** | Text replies in the chat window; polite refusals; referral to CMTI's phone and email; log entries |
| **Sensors** | The user's typed message; the stored conversation history of the session; the knowledge file |

## Task environment properties
| Property | Classification | Reason |
|---|---|---|
| Observable | Partially observable | The agent sees only typed text, not the user's intent, identity or context |
| Agents | Single agent | One assistant serves each user; users are not competing agents |
| Deterministic | Stochastic | The language model's output varies, and user input is unpredictable |
| Episodic | Sequential | Earlier turns change the meaning of later ones ("How long is it?") |
| Static | Static | The knowledge and environment don't change while the agent is thinking |
| Discrete | Discrete | Turns are discrete messages |
| Known | Known (rules) / unknown (users) | The rules and knowledge are defined, but user behaviour is not |

## Agent structure
A **model-based reflex agent with goals**:
- **State (model of the world):** the conversation history from SQLite, which acts as memory.
- **Goal:** satisfy the user's information need within CMTI's scope.
- **Condition-action rules:** the four layers of the system prompt (persona, knowledge, scope, safety).
- **Action selection:** the language model maps (rules + knowledge + history + new message) to a reply.

Problem-solving view (CO2): each query is a goal. The agent's actions are: answer from knowledge, ask a clarifying
question, admit it doesn't know and refer to the office, or refuse with a redirect.

## Ethical, legal and societal issues (CO3) and safeguards
| Issue | Safeguard in this bot |
|---|---|
| Privacy | No personal data asked for; notice that messages go to the AI provider (Google Gemini); emails, phones and USNs masked in logs; no names stored |
| Invented answers (hallucination) | Answers only from the knowledge file; explicit "I don't have that information" rule; fees and dates omitted on purpose |
| False promises | Never promises jobs, placements or salaries |
| Misuse | Out-of-scope refusal (e.g. "write my assignment"); prompt-injection resistance rule |
| Bias and accessibility | Neutral, polite tone; keyboard-accessible widget; mobile-friendly |
| Cost and availability | Low-cost model; token usage logged; clear messages for outages and rate limits |
