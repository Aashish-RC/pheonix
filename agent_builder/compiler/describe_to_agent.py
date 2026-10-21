"""Describe-to-Agent Compiler: Transforms natural language requests into complete AgentSpecifications."""

import time
from typing import List, Optional
from ..core.interfaces import (
    BaseDescribeToAgentCompiler,
    BaseRulesBinder,
    BaseToolMatcher,
)
from ..core.models import (
    AgentBuildResult,
    AgentModelBinding,
    AgentPersona,
    AgentSpecification,
    DescribeAgentRequest,
)
from .tool_matcher import ToolMatcher
from ..binding.rules_binder import RulesBinder


class DescribeToAgentCompiler(BaseDescribeToAgentCompiler):
    """Compiles natural language prompt descriptions into fully verified agent specifications."""

    def __init__(
        self,
        tool_matcher: Optional[BaseToolMatcher] = None,
        rules_binder: Optional[BaseRulesBinder] = None,
    ):
        self.tool_matcher = tool_matcher or ToolMatcher()
        self.rules_binder = rules_binder or RulesBinder()

    def _synthesize_name(self, prompt: str, domain: Optional[str]) -> str:
        prompt_lower = prompt.lower()
        if "security" in prompt_lower or "audit" in prompt_lower:
            return "Security Code Auditor"
        elif "research" in prompt_lower or "analyst" in prompt_lower:
            return "Web Research Analyst"
        elif "refactor" in prompt_lower or "python" in prompt_lower:
            return "Python Code Refactorer"
        elif domain:
            return f"{domain.capitalize()} Specialist Agent"
        return "Autonomous Task Assistant"

    def _synthesize_persona(self, prompt: str, domain: Optional[str]) -> AgentPersona:
        prompt_lower = prompt.lower()
        expertise = []
        if "python" in prompt_lower or "code" in prompt_lower:
            expertise.extend(["Python 3.14", "AST Analysis", "Clean Code Architecture"])
        if "security" in prompt_lower or "vulnerability" in prompt_lower:
            expertise.extend(["OWASP Top 10", "Secret Detection", "Static Code Analysis"])
        if "research" in prompt_lower or "web" in prompt_lower:
            expertise.extend(["Web Scraping", "Source Verification", "Synthesis"])

        if not expertise:
            expertise = ["General Task Execution", "Structured Problem Solving"]

        return AgentPersona(
            role=self._synthesize_name(prompt, domain),
            tone="precise, analytical, and structured",
            expertise_areas=expertise,
            operational_constraints=[
                "Always adhere to sandboxed execution boundaries",
                "Verify facts and source citations before final synthesis",
                "Never disclose internal tokens or sensitive secrets",
            ],
        )

    def _synthesize_system_prompt(self, prompt: str, persona: AgentPersona) -> str:
        constraints_str = "\n".join(f"- {c}" for c in persona.operational_constraints)
        expertise_str = ", ".join(persona.expertise_areas)
        return (
            f"You are {persona.role}, an autonomous intelligence agent.\n"
            f"Your expertise includes: {expertise_str}.\n\n"
            f"Core User Directive:\n\"{prompt}\"\n\n"
            f"Operating Guidelines:\n{constraints_str}\n\n"
            f"Execute all tasks with high rigor, leveraging provided tools accurately."
        )

    def compile_agent(self, request: DescribeAgentRequest) -> AgentBuildResult:
        start_time = time.perf_counter()
        notes: List[str] = []
        validation_errors: List[str] = []

        if not request.prompt or len(request.prompt.strip()) < 5:
            return AgentBuildResult(
                success=False,
                validation_errors=["Agent description prompt must be at least 5 characters long."],
            )

        # 1. Synthesize Persona & Name
        persona = self._synthesize_persona(request.prompt, request.target_domain)
        name = self._synthesize_name(request.prompt, request.target_domain)
        notes.append(f"Synthesized agent persona with {len(persona.expertise_areas)} expertise domains.")

        # 2. Synthesize System Prompt
        system_prompt = self._synthesize_system_prompt(request.prompt, persona)

        # 3. Match Tools
        tool_binding = self.tool_matcher.match_tools(request.prompt)
        notes.append(f"Bound {len(tool_binding.tool_ids)} tools ({', '.join(tool_binding.tool_ids)}).")

        # 4. Bind Rules & Permissions
        rules_binding = self.rules_binder.bind_rules(
            request.prompt, requested_mode=request.requested_permission_mode
        )
        notes.append(f"Applied permission mode '{rules_binding.permission_mode}'.")

        # 5. Model Selection
        model_binding = AgentModelBinding(
            primary_model="openai/gpt-4o" if "reasoning" in request.prompt.lower() else "anthropic/claude-3-5-sonnet",
            temperature=0.2,
            max_tokens=4096,
        )

        spec = AgentSpecification(
            name=name,
            description=request.prompt,
            persona=persona,
            system_prompt=system_prompt,
            model_binding=model_binding,
            tool_binding=tool_binding,
            rules_binding=rules_binding,
            memory_enabled=True,
        )

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        return AgentBuildResult(
            success=True,
            specification=spec,
            compile_duration_ms=round(duration_ms, 2),
            compiler_notes=notes,
            validation_errors=validation_errors,
        )
