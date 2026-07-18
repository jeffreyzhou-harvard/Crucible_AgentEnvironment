"""The agent loop — Claude driving a bash tool inside the sandbox container.

A manual tool-use loop (not the SDK tool runner) so that every step — assistant
text, each bash command, each command's output — is emitted as a `TraceEvent` and
streamed live to the frontend. Claude calls the Anthropic-defined `bash` tool; we
execute the command inside the container via the RuntimeBackend and feed the
result back until Claude ends its turn or we hit the iteration cap.

Auth: constructs a zero-arg `AsyncAnthropic`, which resolves credentials from
ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, or an `ant auth login` profile.
"""

from __future__ import annotations

from ..config import Settings
from ..models import ExecutionResult, WorkspaceRequest
from ..trace.tracer import Tracer
from .runtime import RuntimeBackend

# The bash tool is Anthropic-defined and schema-less — declare it by type+name only.
# Claude emits {"command": "..."} or {"restart": true}; we run the command in the box.
_BASH_TOOL = {"type": "bash_20250124", "name": "bash"}

_SYSTEM_PROMPT = """\
You are an autonomous software engineering agent working inside an isolated sandbox \
container. You have a `bash` tool that runs commands in the sandbox (working directory \
{workdir}). Any cloned repositories are already checked out there.

Work autonomously to complete the task:
- Explore with bash (ls, cat, grep) before making changes.
- Make changes by writing files with bash (e.g. python, tee, sed).
- Verify your work by running the project's tests or the program itself.
- When the task is complete, stop and give a one-paragraph summary of what you did \
and how you verified it.

You are running unattended — the user cannot answer questions mid-task. For minor \
decisions, pick a reasonable option and proceed rather than asking. Do not narrate \
routine actions; act, then report the outcome.
"""

# Cap how much command output we feed back to the model (and store in the trace).
_MAX_OUTPUT_CHARS = 8000


class ClaudeAgent:
    def __init__(self, settings: Settings, backend: RuntimeBackend) -> None:
        self.settings = settings
        self.backend = backend
        from anthropic import AsyncAnthropic  # lazy: only when the docker runtime is used

        self.client = AsyncAnthropic()

    async def run(
        self, runtime_ref: str, request: WorkspaceRequest, tracer: Tracer
    ) -> ExecutionResult:
        await tracer.emit("agent.start", model=self.settings.anthropic_model)

        system = _SYSTEM_PROMPT.format(workdir=self.settings.sandbox_workdir)
        messages: list[dict] = [{"role": "user", "content": request.task_prompt}]

        for _ in range(self.settings.agent_max_iterations):
            response = await self.client.messages.create(
                model=self.settings.anthropic_model,
                max_tokens=self.settings.agent_max_output_tokens,
                system=system,
                tools=[_BASH_TOOL],
                output_config={"effort": self.settings.agent_effort},
                messages=messages,
            )

            for block in response.content:
                if block.type == "text" and block.text.strip():
                    await tracer.emit("agent.message", text=block.text)

            if response.stop_reason != "tool_use":
                summary = " ".join(b.text for b in response.content if b.type == "text")
                await tracer.emit(
                    "agent.done", succeeded=True, stop_reason=response.stop_reason
                )
                return ExecutionResult(
                    workspace_id="",  # filled in by the orchestrator
                    trace_id=tracer.trace_id,
                    exit_code=0,
                    succeeded=True,
                    summary=summary[:1000],
                )

            # Preserve the assistant turn (incl. tool_use blocks) before answering it.
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type != "tool_use" or block.name != "bash":
                    continue
                if block.input.get("restart"):
                    await tracer.emit("tool_call", command="<restart shell>")
                    tool_results.append(
                        {"type": "tool_result", "tool_use_id": block.id, "content": "restarted"}
                    )
                    continue

                command = str(block.input.get("command", ""))
                await tracer.emit("tool_call", command=command)
                exit_code, out, err = await self.backend.exec(
                    runtime_ref, ["bash", "-lc", command]
                )
                combined = (out.decode("utf-8", "replace") + err.decode("utf-8", "replace"))[
                    :_MAX_OUTPUT_CHARS
                ]
                await tracer.emit("command_output", exit_code=exit_code, output=combined)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": combined or "(no output)",
                        "is_error": exit_code != 0,
                    }
                )

            messages.append({"role": "user", "content": tool_results})

        await tracer.emit("agent.done", succeeded=False, stop_reason="max_iterations")
        return ExecutionResult(
            workspace_id="",
            trace_id=tracer.trace_id,
            exit_code=1,
            succeeded=False,
            summary=f"Reached the {self.settings.agent_max_iterations}-iteration cap.",
        )
