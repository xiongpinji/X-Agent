"""Tests for agent_v2 state management and execution coordination."""

import pytest
from datetime import datetime

from backend.app.core.agent_v2 import (
    AgentExecutor,
    AgentState,
    AgentStateManager,
    InvalidStateTransitionError,
)


class TestAgentState:
    """Test AgentState enum."""

    def test_all_states_defined(self):
        """Verify all required states are defined."""
        required_states = {
            "IDLE",
            "INITIALIZING",
            "PLANNING",
            "EXECUTING",
            "RECOVERING",
            "COMPLETING",
            "COMPLETED",
            "FAILED",
            "PAUSED",
        }
        actual_states = {state.name for state in AgentState}
        assert required_states == actual_states

    def test_state_values(self):
        """Verify state values are lowercase."""
        for state in AgentState:
            assert state.value == state.name.lower()


class TestAgentStateManager:
    """Test AgentStateManager state machine."""

    def test_initial_state(self):
        """Verify initial state is IDLE."""
        manager = AgentStateManager()
        assert manager.get_state() == AgentState.IDLE

    def test_valid_transition_idle_to_initializing(self):
        """Test valid transition from IDLE to INITIALIZING."""
        manager = AgentStateManager()
        manager.transition_to(AgentState.INITIALIZING)
        assert manager.get_state() == AgentState.INITIALIZING

    def test_valid_transition_sequence(self):
        """Test valid state transition sequence."""
        manager = AgentStateManager()
        sequence = [
            AgentState.INITIALIZING,
            AgentState.PLANNING,
            AgentState.EXECUTING,
            AgentState.COMPLETING,
            AgentState.COMPLETED,
        ]
        for state in sequence:
            manager.transition_to(state)
            assert manager.get_state() == state

    def test_invalid_transition_idle_to_executing(self):
        """Test invalid transition raises error."""
        manager = AgentStateManager()
        with pytest.raises(InvalidStateTransitionError) as exc_info:
            manager.transition_to(AgentState.EXECUTING)
        assert exc_info.value.from_state == AgentState.IDLE
        assert exc_info.value.to_state == AgentState.EXECUTING

    def test_executing_to_recovering_transition(self):
        """Test EXECUTING can transition to RECOVERING."""
        manager = AgentStateManager()
        manager.transition_to(AgentState.INITIALIZING)
        manager.transition_to(AgentState.PLANNING)
        manager.transition_to(AgentState.EXECUTING)
        manager.transition_to(AgentState.RECOVERING)
        assert manager.get_state() == AgentState.RECOVERING

    def test_recovering_to_executing_transition(self):
        """Test RECOVERING can transition back to EXECUTING."""
        manager = AgentStateManager()
        manager.transition_to(AgentState.INITIALIZING)
        manager.transition_to(AgentState.PLANNING)
        manager.transition_to(AgentState.EXECUTING)
        manager.transition_to(AgentState.RECOVERING)
        manager.transition_to(AgentState.EXECUTING)
        assert manager.get_state() == AgentState.EXECUTING

    def test_pause_from_any_state(self):
        """Test pause can be called from any non-terminal state."""
        states_to_test = [
            AgentState.IDLE,
            AgentState.INITIALIZING,
            AgentState.PLANNING,
            AgentState.EXECUTING,
        ]
        for state in states_to_test:
            manager = AgentStateManager()
            # Navigate to state
            if state != AgentState.IDLE:
                manager.transition_to(AgentState.INITIALIZING)
                if state != AgentState.INITIALIZING:
                    manager.transition_to(AgentState.PLANNING)
                    if state != AgentState.PLANNING:
                        manager.transition_to(AgentState.EXECUTING)
            # Pause
            manager.transition_to(AgentState.PAUSED)
            assert manager.get_state() == AgentState.PAUSED

    def test_resume_from_pause(self):
        """Test resume returns to previous state."""
        manager = AgentStateManager()
        manager.transition_to(AgentState.INITIALIZING)
        manager.transition_to(AgentState.PLANNING)
        manager.transition_to(AgentState.PAUSED)
        assert manager.is_paused()
        assert manager.get_paused_state() == AgentState.PLANNING
        manager.transition_to(AgentState.PLANNING)
        assert manager.get_state() == AgentState.PLANNING

    def test_state_history(self):
        """Test state history is recorded."""
        manager = AgentStateManager()
        manager.transition_to(AgentState.INITIALIZING)
        manager.transition_to(AgentState.PLANNING)
        manager.transition_to(AgentState.EXECUTING)

        history = manager.get_history()
        assert len(history) >= 3
        states = [state for state, _ in history]
        assert AgentState.IDLE in states
        assert AgentState.INITIALIZING in states
        assert AgentState.PLANNING in states

    def test_state_history_timestamps(self):
        """Test state history includes timestamps."""
        manager = AgentStateManager()
        manager.transition_to(AgentState.INITIALIZING)

        history = manager.get_history()
        for state, timestamp in history:
            assert isinstance(state, AgentState)
            assert isinstance(timestamp, datetime)

    def test_is_terminal_state_completed(self):
        """Test is_terminal_state returns True for COMPLETED."""
        manager = AgentStateManager()
        manager.transition_to(AgentState.INITIALIZING)
        manager.transition_to(AgentState.PLANNING)
        manager.transition_to(AgentState.EXECUTING)
        manager.transition_to(AgentState.COMPLETING)
        manager.transition_to(AgentState.COMPLETED)
        assert manager.is_terminal_state()

    def test_is_terminal_state_failed(self):
        """Test is_terminal_state returns True for FAILED."""
        manager = AgentStateManager()
        manager.transition_to(AgentState.INITIALIZING)
        manager.transition_to(AgentState.FAILED)
        assert manager.is_terminal_state()

    def test_is_terminal_state_non_terminal(self):
        """Test is_terminal_state returns False for non-terminal states."""
        manager = AgentStateManager()
        manager.transition_to(AgentState.INITIALIZING)
        assert not manager.is_terminal_state()

    def test_is_paused(self):
        """Test is_paused detection."""
        manager = AgentStateManager()
        assert not manager.is_paused()
        manager.transition_to(AgentState.INITIALIZING)
        manager.transition_to(AgentState.PAUSED)
        assert manager.is_paused()

    def test_reset(self):
        """Test reset returns to initial state."""
        manager = AgentStateManager()
        manager.transition_to(AgentState.INITIALIZING)
        manager.transition_to(AgentState.PLANNING)
        manager.transition_to(AgentState.EXECUTING)

        manager.reset()
        assert manager.get_state() == AgentState.IDLE
        history = manager.get_history()
        assert len(history) == 1
        assert history[0][0] == AgentState.IDLE


class TestAgentExecutor:
    """Test AgentExecutor coordination."""

    def test_executor_initialization(self):
        """Test executor initializes correctly."""
        executor = AgentExecutor(max_iterations=4)
        assert executor.max_iterations == 4
        assert executor.get_state() == AgentState.IDLE

    def test_executor_state_tracking(self):
        """Test executor tracks state correctly."""
        executor = AgentExecutor()
        assert executor.get_state() == AgentState.IDLE
        assert not executor.is_completed()

    def test_executor_pause_resume(self):
        """Test executor pause and resume."""
        executor = AgentExecutor()
        executor.state_manager.transition_to(AgentState.INITIALIZING)
        executor.pause()
        assert executor.get_state() == AgentState.PAUSED
        executor.resume()
        assert executor.get_state() == AgentState.INITIALIZING

    def test_executor_reset(self):
        """Test executor reset."""
        executor = AgentExecutor()
        executor.state_manager.transition_to(AgentState.INITIALIZING)
        executor.state_manager.transition_to(AgentState.PLANNING)
        executor.reset()
        assert executor.get_state() == AgentState.IDLE

    def test_executor_state_history(self):
        """Test executor state history."""
        executor = AgentExecutor()
        executor.state_manager.transition_to(AgentState.INITIALIZING)
        executor.state_manager.transition_to(AgentState.PLANNING)

        history = executor.get_state_history()
        assert len(history) >= 2
        states = [state for state, _ in history]
        assert "idle" in states
        assert "initializing" in states

    def test_executor_is_completed_false(self):
        """Test is_completed returns False for non-terminal states."""
        executor = AgentExecutor()
        # 状态机规则:IDLE 只能转 INITIALIZING/PAUSED,不能直达 EXECUTING。
        # 走合法路径 IDLE→INITIALIZING→PLANNING→EXECUTING 到达非终态,
        # 再断言 is_completed 为 False(与 test_executor_is_completed_true 一致)。
        executor.state_manager.transition_to(AgentState.INITIALIZING)
        executor.state_manager.transition_to(AgentState.PLANNING)
        executor.state_manager.transition_to(AgentState.EXECUTING)
        assert not executor.is_completed()

    def test_executor_is_completed_true(self):
        """Test is_completed returns True for terminal states."""
        executor = AgentExecutor()
        executor.state_manager.transition_to(AgentState.INITIALIZING)
        executor.state_manager.transition_to(AgentState.PLANNING)
        executor.state_manager.transition_to(AgentState.EXECUTING)
        executor.state_manager.transition_to(AgentState.COMPLETING)
        executor.state_manager.transition_to(AgentState.COMPLETED)
        assert executor.is_completed()


class TestStateTransitionRules:
    """Test comprehensive state transition rules."""

    def test_all_valid_transitions_from_idle(self):
        """Test all valid transitions from IDLE."""
        manager = AgentStateManager()
        valid_targets = {AgentState.INITIALIZING, AgentState.PAUSED}
        for target in valid_targets:
            manager = AgentStateManager()
            manager.transition_to(target)
            assert manager.get_state() == target

    def test_all_valid_transitions_from_executing(self):
        """Test all valid transitions from EXECUTING."""
        manager = AgentStateManager()
        manager.transition_to(AgentState.INITIALIZING)
        manager.transition_to(AgentState.PLANNING)
        manager.transition_to(AgentState.EXECUTING)

        valid_targets = {
            AgentState.RECOVERING,
            AgentState.COMPLETING,
            AgentState.FAILED,
            AgentState.PAUSED,
        }
        for target in valid_targets:
            manager = AgentStateManager()
            manager.transition_to(AgentState.INITIALIZING)
            manager.transition_to(AgentState.PLANNING)
            manager.transition_to(AgentState.EXECUTING)
            manager.transition_to(target)
            assert manager.get_state() == target

    def test_invalid_transitions_from_completed(self):
        """Test invalid transitions from COMPLETED."""
        manager = AgentStateManager()
        manager.transition_to(AgentState.INITIALIZING)
        manager.transition_to(AgentState.PLANNING)
        manager.transition_to(AgentState.EXECUTING)
        manager.transition_to(AgentState.COMPLETING)
        manager.transition_to(AgentState.COMPLETED)

        invalid_targets = {
            AgentState.INITIALIZING,
            AgentState.PLANNING,
            AgentState.EXECUTING,
            AgentState.COMPLETING,
        }
        for target in invalid_targets:
            with pytest.raises(InvalidStateTransitionError):
                manager.transition_to(target)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
