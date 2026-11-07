from framework.context import RunContext
from contracts.agent_result import AgentResult, AgentStatus, ConfidenceLevel
from framework.llm import bedrock

def context_agent(ctx: RunContext) -> AgentResult:
    """
    Example sequential handler.
    Always return the AgentResult contract.
    """
    
    # You can optionally load a SKILL.md for instructions, or define prompt in code.
    # instructions = ctx.load_skill("skills/context/SKILL.md")
    
    return AgentResult(
        agent="context-fetcher",
        task_id=ctx.task_id,
        status=AgentStatus.SUCCESS,
        confidence=ConfidenceLevel.HIGH,
        repos_inspected=ctx.repo_context,
        summary="Context successfully gathered.",
        blockers=[],
        suggestions=[],
        experience_candidates=[],
        citations=[],
        tokens_used=120,
        duration_seconds=0.5
    )

def log_agent(ctx: RunContext) -> AgentResult:
    """
    Example parallel handler.
    The framework tracks Langfuse spans automatically per handler.
    """
    # Logic to fetch logs via MCP or direct API
    return AgentResult(
        agent="log-analyzer",
        task_id=ctx.task_id,
        status=AgentStatus.SUCCESS,
        confidence=ConfidenceLevel.MEDIUM,
        repos_inspected=[],
        summary="Found 3 stack traces in logs.",
        blockers=[],
        suggestions=[],
        experience_candidates=[],
        citations=[],
        tokens_used=400,
        duration_seconds=2.1
    )

def validation_agent(ctx: RunContext) -> AgentResult:
    """
    Example validation handler that runs after a parallel merge.
    ctx.merged_inputs() contains the unified AgentResult from the previous step.
    """
    merged_data = ctx.merged_inputs()
    
    # Pass merged context to Claude for final reasoning
    prompt = f"Validate these findings: {merged_data.summary}"
    
    # bedrock.run handles the LLM call and returns a parsed AgentResult
    return bedrock.run(
        prompt=prompt, 
        context=ctx, 
        expected_schema=AgentResult
    )
