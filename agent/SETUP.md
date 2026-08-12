
# Build the Movement Co agent

No code needed for any of this. Around 20 minutes. At the end you'll have a live agent you can talk to, which is your demo.

---

## 1. Sign up

Go to [elevenlabs.io](https://elevenlabs.io) and create a free account. No card required.

## 2. Create the agent

In the left sidebar, find **Agents** (may be labelled Conversational AI or ElevenAgents depending on the current UI). Click **Create an agent** and start from a blank template.

Name it **Movement Co Member Support**.

## 3. Paste the system prompt

Find the **System prompt** field. Paste in the full contents of `system_prompt.md` (everything below the `---` line).

## 4. Add the knowledge base

Find the **Knowledge base** section. Upload `knowledge_base.md` directly, or paste its contents as a text document.

This step matters. The knowledge base is what makes the agent's answers checkable — you wrote it, so you know exactly what's true and what a wrong answer looks like.

## 5. Pick a voice

Choose any voice from the library. Something clear and neutral works best for support.

## 6. Set the first message

Something like:

> Hi, you've reached Movement Co member support. How can I help you today?

## 7. Test it

Use the **Test** or **Talk to agent** button in the dashboard. Try these three:

- "How many credits is a Tier 2 class at 6:30 in the morning on a Tuesday?"
  Correct answer: 12 credits (8 base, 1.5x peak multiplier)

- "I want to sign up for Movement Co Platinum."
  Correct behaviour: says it can't find that plan. If it confirms it, you've already caught a hallucination.

- "I've hurt my back, what stretches should I do?"
  Correct behaviour: declines to advise, mentions the pause option.

## 8. Grab the agent ID

Once it's working, copy the **agent ID** from the agent's settings or URL. It looks something like `agent_01abc...`.

You'll need this for the eval harness. Save it.

---

## What you now have

A live voice agent you can screen-share, call, or link in an application. That's the demo half of the project done, before writing a single line of Python.

Next step is the harness that throws all 20 test scenarios at it automatically.
