"""Human-in-the-Loop Pattern -- Agent with human approval checkpoints.

This pattern runs a primary agent that executes a task, then pauses at
a review checkpoint for human approval.  The human can approve, reject,
or redirect the task with feedback.

Typical use cases:
  - Mission-critical content generation requiring human oversight
  - Financial or legal document preparation
  - Any high-stakes output where human judgment is required
"""

from patterns.human_in_the_loop.pattern import HumanInTheLoopPattern, HumanInTheLoopState

__all__ = ["HumanInTheLoopPattern", "HumanInTheLoopState"]
