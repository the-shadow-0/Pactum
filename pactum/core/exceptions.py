"""
Pactum exceptions — all error types raised by the runtime.
"""


class PactumError(Exception):
    """Base exception for all Pactum errors."""
    pass


class ContractViolationError(PactumError):
    """Raised when a contract is violated during execution."""

    def __init__(self, contract_name: str, message: str):
        self.contract_name = contract_name
        super().__init__(f"Contract '{contract_name}' violated: {message}")


class InputValidationError(ContractViolationError):
    """Raised when contract inputs fail validation."""

    def __init__(self, contract_name: str, field: str, expected: str, got: str):
        self.field = field
        self.expected = expected
        self.got = got
        super().__init__(contract_name, f"Input '{field}' expected {expected}, got {got}")


class OutputValidationError(ContractViolationError):
    """Raised when contract outputs fail validation."""

    def __init__(self, contract_name: str, field: str, expected: str, got: str):
        self.field = field
        self.expected = expected
        self.got = got
        super().__init__(contract_name, f"Output '{field}' expected {expected}, got {got}")


class ToolAccessDeniedError(ContractViolationError):
    """Raised when a contract tries to use a tool not in its allowed_tools."""

    def __init__(self, contract_name: str, tool_name: str, allowed: list[str]):
        self.tool_name = tool_name
        self.allowed = allowed
        super().__init__(
            contract_name,
            f"Tool '{tool_name}' not allowed. Allowed tools: {allowed}"
        )


class NonDetBudgetExceededError(ContractViolationError):
    """Raised when non-determinism budget (token count) is exceeded."""

    def __init__(self, contract_name: str, budget: int, used: int):
        self.budget = budget
        self.used = used
        super().__init__(
            contract_name,
            f"Non-determinism budget exceeded: {used} tokens used, budget is {budget}"
        )


class MemorySchemaError(ContractViolationError):
    """Raised when memory state doesn't conform to the declared schema."""

    def __init__(self, contract_name: str, key: str, message: str):
        self.key = key
        super().__init__(contract_name, f"Memory schema error on key '{key}': {message}")


class InvariantError(ContractViolationError):
    """Raised when a user-defined invariant/assertion fails."""

    def __init__(self, contract_name: str, invariant_name: str, message: str):
        self.invariant_name = invariant_name
        super().__init__(
            contract_name,
            f"Invariant '{invariant_name}' failed: {message}"
        )


class SnapshotNotFoundError(PactumError):
    """Raised when a snapshot ID is not found in the store."""

    def __init__(self, snapshot_id: str):
        self.snapshot_id = snapshot_id
        super().__init__(f"Snapshot not found: {snapshot_id}")


class ReplayError(PactumError):
    """Raised when replay fails due to mismatched state."""

    def __init__(self, snapshot_id: str, message: str):
        self.snapshot_id = snapshot_id
        super().__init__(f"Replay failed for snapshot {snapshot_id}: {message}")


class ConfigError(PactumError):
    """Raised when configuration is invalid or missing."""

    def __init__(self, message: str):
        super().__init__(f"Configuration error: {message}")
