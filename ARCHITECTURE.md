# Architecture

## The problem

Companies are adopting AI tools faster than they are adopting any way to control them.
An employee with a confidential contract opens a chat tool, pastes it in, and gets a
useful summary back. The work gets done. Nobody is being careless on purpose.

But that document has now left the building. It went to a server the company does not
own, possibly in another jurisdiction. There is no record that it happened, no way to
answer a regulator asking where the data went, no idea what any of it cost, and no way
to tell whether anything hidden in that document manipulated the model into doing
something nobody asked for.

Multiply that by every employee and every tool, and the company has an AI problem it
cannot see.

## The core principle

**AI models must not decide what they are allowed to access or do.**

A language model is built to be helpful and to follow instructions in the text it is
given. That is what makes it useful, and it is also why it can be talked out of its own
rules by anyone whose text reaches it. You cannot fix this by instructing the model more
firmly — a model can always be argued with.

So the boundary is moved out of the model and into the infrastructure around it, where
it is enforced by code that has no opinion and cannot be persuaded.

The corollary: **detection is never the control.** The design assumes some attacks will
succeed, and limits what a successful attack can reach.

## The request path

Every request passes through one gateway before it reaches any model.

1. **Who is asking?** An API key or an SSO login identifies the user and their clearance.
   An unauthenticated request is refused here.
2. **How sensitive is this?** The request carries a classification label. The label is
   metadata attached by the source system or the user — it is never inferred by reading
   the text, because a guess can be wrong and can be manipulated.
3. **Where is this allowed to go?** A routing rule maps the classification to the set of
   models permitted to see it. A request that no permitted model can serve is refused,
   and the refusal is logged.
4. **Forward and receive.** The gateway calls the chosen provider and gets the answer.
5. **Record it.** User, timestamp, model, token counts, cost, classification, and whether
   the request was refused.
6. **Return the answer.** The caller sees an ordinary response and never learns which
   model served it.

Steps 1 to 3 happen before the model sees anything. They are ordinary code — comparisons
and lookups — so no text in the request can change what they do.

## Trust boundaries

Not all text in a request has the same origin, and the difference is the whole security
story.

**Trusted:** what the user typed. They are authenticated, and they are asking for their
own work to be done.

**Untrusted:** everything else that ends up in the prompt — a document the user asked to
be summarised, a page fetched from the web, a chunk retrieved from a knowledge base, an
email. Nobody wrote this with the company's interests in mind, and nobody reviewed it.

Untrusted text is where indirect prompt injection lives: an instruction hidden inside a
document, which the model reads as an order rather than as material.

Two things follow:

- Untrusted text is kept as a separate field all the way through the system, never glued
  into the user's message, so it can be treated differently.
- When it is finally assembled into a prompt, it is wrapped in explicit markers with a
  statement that the enclosed text is data and must never be obeyed.

That wrapping is a **mitigation, not a control**. A determined attacker can write the
closing marker into their own document, and a model may ignore the instruction anyway.
It raises the cost of the attack. It does not prevent it. The controls that actually hold
are the ones in the next section.

## Classification and routing

Four levels, mapped to the models permitted to serve them.

| Level | Example | Permitted destinations |
|---|---|---|
| PUBLIC | marketing copy, public documentation | any provider, including external APIs |
| INTERNAL | meeting notes, internal wiki pages | any approved provider |
| CONFIDENTIAL | contracts, personnel data, customer records | self-hosted models only |
| RESTRICTED | credentials, legal holds, regulated data | self-hosted only, or refused outright |

This is the strongest control in the system, and it is worth being precise about why.

It is not a filter that inspects text and makes a judgement. It is a lookup: this label
permits this set of destinations. If a confidential document is never sent to an external
provider, then no prompt injection, however clever, can cause that provider to leak it.
The data was not there.

The trade-off is accepted deliberately: self-hosted models are generally weaker than
frontier cloud models, so confidential work sometimes gets a less capable answer. That is
the price of the document not leaving the building, and it is a decision for the security
officer, not for the model.

## Components

**Gateway** — the single entry point. Authentication, classification routing, provider
calls, logging, cost tracking. Built on LiteLLM.

**Model providers** — a local model served by Ollama, and one or more external APIs
(AWS Bedrock). The gateway presents one interface regardless of which is used, so a
provider can be swapped without changing any caller.

**Identity server** — Keycloak. Maps a user to their clearance, so authorisation is not a
list of API keys in a config file.

**Eval harness** — `eval/`. A command-line tool that runs a list of prompt-injection
attacks against a model and reports a score.

**The harness is not in the request path.** This is worth stating plainly, because it is
easy to assume otherwise. It does not inspect live traffic and it never blocks anything.
It is a drill, run on demand, against attacks written in advance, to measure whether the
defences moved after a change. The gateway protects; the harness measures.

## What is built and what is planned

**M0 — eval harness. Done.**

`eval/runner.py` loads attack cases from `eval/cases/attacks.yaml`, builds a prompt for
each, sends it to a model, checks the reply for canary strings, and prints a per-case
result and a score. There is no real model yet — a stub function returns canned replies,
deliberately failing one case so that the judge is proven able to detect a failure.

Four cases: direct injection, system-prompt extraction, indirect injection via a document,
and one benign request that must always pass. That last one exists to catch a judge that
fires on innocent replies; it has already caught a real bug.

Current score is 3/4, which measures the harness, not the defences. A real score arrives
at M1.

**M1 — gateway.** LiteLLM in front of Ollama and one external provider, API keys, token
and cost logging per request, everything started by one Docker Compose command. Then the
harness is pointed at the gateway instead of the stub, and the first meaningful score is
recorded.

**M2 — classification and identity.** The routing table above, enforced. Keycloak for SSO.

**M3 — AWS.** Bedrock as a provider, the gateway deployed, basic monitoring, billing
alerts configured before anything is created.

**M4 — Kubernetes.** Local cluster with kind.

Constraint held throughout: the local Docker Compose setup must always work with no cloud
account.

## Threat model

**What this defends against**

- Confidential data reaching an external provider — prevented by routing, before the model
  is involved.
- Unauthenticated or over-privileged access — prevented by identity and clearance checks.
- Invisible usage and runaway cost — prevented by per-request logging.
- Regressions in injection resistance after a model swap, a prompt change, or an upgrade —
  detected by the harness.

**What this does not defend against**

- **Prompt injection itself.** It is an unsolved problem, and this project does not solve
  it. A sufficiently clever instruction hidden in a document will sometimes be obeyed. The
  design accepts this and constrains the consequences.
- Attacks the harness has never been shown. The suite covers published techniques and
  grows as new ones are published; it will always be incomplete.
- A compromised self-hosted model or a malicious insider with legitimate clearance.

**The assumption the design rests on**

Assume the model gets fooled. Then ask what a fooled model can actually do. If it was
never given the confidential document, it cannot leak it. If it has no tool that reaches
the network, it cannot exfiltrate anything. If every request is logged, the damage can at
least be measured afterwards.

That is the difference between a system that hopes the model behaves and one that does
not need it to.

## Diagram

```
                  ┌──────────────────────────────────────────────┐
   user  ───────▶ │                  GATEWAY                     │
 (+ label,        │                                              │
  + untrusted     │  1. authenticate        who is asking?       │
    document)     │  2. read classification  how sensitive?      │
                  │  3. apply routing rule   where may it go?    │
                  │  4. build prompt         fence untrusted text│
                  │  5. log                  user/tokens/cost    │
                  └───────┬──────────────────────────┬───────────┘
                          │                          │
            CONFIDENTIAL  │                          │  PUBLIC / INTERNAL
            RESTRICTED    │                          │
                          ▼                          ▼
                 ┌─────────────────┐        ┌──────────────────┐
                 │  local model    │        │  external API    │
                 │    (Ollama)     │        │    (Bedrock)     │
                 └─────────────────┘        └──────────────────┘


   eval harness ──────▶ runs on demand, against either model,
   (not in the          with attacks written in advance.
    request path)       Reports a score. Blocks nothing.
```
