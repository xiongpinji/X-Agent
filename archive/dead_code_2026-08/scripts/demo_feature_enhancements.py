"""
Demonstration scripts for X-Agent feature enhancements.

Shows practical usage of memory fusion, multi-agent collaboration,
browser automation, and repair loop features.
"""

import asyncio
from datetime import datetime, timedelta
from backend.app.core.memory_deduplication import (
    MemoryDeduplicator,
    Memory,
)
from backend.app.services.memory.hybrid_retriever import (
    HybridRetriever,
)
from backend.app.core.memory_graph_enhanced import (
    EnhancedMemoryGraph,
    MemoryNode,
    MemoryRelation,
)
from backend.app.core.memory_compression import (
    MemoryCompressor,
)
from backend.app.core.agent_communication import (
    AgentMessenger,
    MessageType,
    MessagePriority,
)
from backend.app.core.task_dispatcher import (
    TaskDispatcher,
    Task,
    TaskPriority,
)
from backend.app.services.browser.smart_locator import (
    SmartLocator,
    LocatorStrategy,
)
from backend.app.core.failure_detection import (
    FailureDetector,
    ExecutionContext,
)


def demo_memory_fusion():
    """Demonstrate memory fusion capabilities."""
    print("\n" + "="*60)
    print("DEMO: Advanced Memory Fusion")
    print("="*60)

    # 1. Memory Deduplication
    print("\n1. Memory Deduplication")
    print("-" * 40)

    deduplicator = MemoryDeduplicator(similarity_threshold=0.85)

    memories = [
        Memory(
            id="m1",
            content="Python is a high-level programming language",
            relevance_score=0.9,
        ),
        Memory(
            id="m2",
            content="Python is a programming language",
            relevance_score=0.8,
        ),
        Memory(
            id="m3",
            content="Java is an object-oriented programming language",
            relevance_score=0.7,
        ),
        Memory(
            id="m4",
            content="Python supports multiple programming paradigms",
            relevance_score=0.85,
        ),
    ]

    result = deduplicator.deduplicate(memories)
    stats = deduplicator.get_deduplication_stats(result)

    print(f"Original memories: {stats['original_count']}")
    print(f"After deduplication: {stats['deduplicated_count']}")
    print(f"Reduction rate: {stats['reduction_rate']:.1f}%")
    print(f"Merged groups: {len(result.merged_groups)}")

    # 2. Hybrid Retrieval
    print("\n2. Hybrid Memory Retrieval")
    print("-" * 40)

    retriever = HybridRetriever(vector_weight=0.6, keyword_weight=0.4)

    memory_data = [
        {"id": "m1", "content": "Python async programming with asyncio"},
        {"id": "m2", "content": "JavaScript async/await patterns"},
        {"id": "m3", "content": "Python concurrency and threading"},
        {"id": "m4", "content": "Rust async runtime implementation"},
    ]

    results = retriever.search(
        query="Python asynchronous programming",
        memories=memory_data,
        top_k=3,
        use_hybrid=True,
    )

    print(f"Query: 'Python asynchronous programming'")
    print(f"Results found: {len(results)}")
    for i, result in enumerate(results, 1):
        print(f"  {i}. {result.memory_id} (score: {result.combined_score:.3f})")

    # 3. Memory Graph
    print("\n3. Enhanced Memory Graph")
    print("-" * 40)

    graph = EnhancedMemoryGraph()

    # Add nodes
    nodes = [
        MemoryNode(id="n1", content="Python basics"),
        MemoryNode(id="n2", content="Python OOP"),
        MemoryNode(id="n3", content="Python async"),
        MemoryNode(id="n4", content="Python web frameworks"),
    ]

    for node in nodes:
        graph.add_node(node)

    # Add relations
    relations = [
        MemoryRelation("n1", "n2", "prerequisite", 0.9),
        MemoryRelation("n2", "n4", "related", 0.8),
        MemoryRelation("n1", "n3", "related", 0.7),
        MemoryRelation("n3", "n4", "related", 0.85),
    ]

    for relation in relations:
        graph.add_relation(relation)

    # Find related memories
    related = graph.find_related_memories("n1", depth=2, limit=5)
    print(f"Memories related to 'Python basics':")
    for memory_id, strength in related:
        print(f"  - {memory_id} (strength: {strength:.2f})")

    # Trace path
    path = graph.trace_memory_path("n1", "n4")
    if path:
        print(f"\nPath from 'Python basics' to 'Python web frameworks':")
        print(f"  Path: {' -> '.join(path.path_nodes)}")
        print(f"  Length: {path.path_length} steps")
        print(f"  Total strength: {path.total_strength:.2f}")

    # 4. Memory Compression
    print("\n4. Memory Compression")
    print("-" * 40)

    compressor = MemoryCompressor(
        retention_days=30,
        compression_threshold_days=7,
    )

    old_memories = [
        {
            "id": "m1",
            "content": "This is a detailed memory about Python programming. "
                      "It covers various aspects including syntax, data types, "
                      "control flow, functions, and object-oriented programming. "
                      "Python is widely used in web development, data science, "
                      "and artificial intelligence.",
            "created_at": (datetime.now() - timedelta(days=10)).isoformat(),
        },
        {
            "id": "m2",
            "content": "Another memory about web frameworks",
            "created_at": (datetime.now() - timedelta(days=5)).isoformat(),
        },
    ]

    compression_result = compressor.compress_old_memories(old_memories)
    compression_stats = compressor.get_compression_stats()

    print(f"Memories compressed: {compression_result.compressed_count}")
    print(f"Average compression ratio: {compression_stats['avg_compression_ratio']:.1%}")
    print(f"Total size before: {compression_result.total_size_before} bytes")
    print(f"Total size after: {compression_result.total_size_after} bytes")


async def demo_multi_agent_collaboration():
    """Demonstrate multi-agent collaboration."""
    print("\n" + "="*60)
    print("DEMO: Multi-Agent Collaboration")
    print("="*60)

    # 1. Agent Communication
    print("\n1. Agent Communication Protocol")
    print("-" * 40)

    messenger = AgentMessenger()

    # Register agents
    agents = ["analyzer", "executor", "validator"]
    for agent in agents:
        messenger.register_agent(agent)

    print(f"Registered agents: {agents}")

    # Send messages
    print("\nSending messages:")

    msg_id1 = await messenger.send_message(
        from_agent_id="analyzer",
        to_agent_id="executor",
        message_type=MessageType.TASK_REQUEST,
        payload={"task": "analyze_data", "data": [1, 2, 3, 4, 5]},
        priority=MessagePriority.HIGH,
    )
    print(f"  analyzer -> executor: TASK_REQUEST (ID: {msg_id1[:8]}...)")

    msg_id2 = await messenger.send_message(
        from_agent_id="executor",
        to_agent_id="validator",
        message_type=MessageType.STATUS_UPDATE,
        payload={"status": "processing", "progress": 50},
    )
    print(f"  executor -> validator: STATUS_UPDATE (ID: {msg_id2[:8]}...)")

    # Check queue sizes
    print("\nMessage queue status:")
    for agent in agents:
        size = messenger.get_queue_size(agent)
        print(f"  {agent}: {size} messages")

    # Receive messages
    print("\nReceiving messages:")
    msg = await messenger.receive_message("executor")
    if msg:
        print(f"  executor received: {msg.message_type.value} from {msg.from_agent_id}")

    # 2. Task Dispatcher
    print("\n2. Task Dispatcher")
    print("-" * 40)

    dispatcher = TaskDispatcher()

    # Register agents with capabilities
    dispatcher.register_agent(
        "analyzer",
        max_concurrent_tasks=3,
        capabilities=["analysis", "data_processing"],
    )
    dispatcher.register_agent(
        "executor",
        max_concurrent_tasks=5,
        capabilities=["execution", "automation"],
    )
    dispatcher.register_agent(
        "validator",
        max_concurrent_tasks=2,
        capabilities=["validation", "testing"],
    )

    print("Registered agents with capabilities")

    # Create and decompose task
    main_task = Task(
        id="main_task",
        name="Data Processing Pipeline",
        description="Load data; Process data; Validate results; Generate report",
        priority=TaskPriority.HIGH,
    )

    subtasks = dispatcher.decompose_task(main_task, max_subtasks=4)
    print(f"\nDecomposed task into {len(subtasks)} subtasks:")
    for i, subtask in enumerate(subtasks, 1):
        print(f"  {i}. {subtask.name}")

    # Allocate tasks
    allocations = dispatcher.allocate_tasks(subtasks)
    print(f"\nTask allocations:")
    for allocation in allocations:
        if allocation.assigned_agent_id:
            print(f"  {allocation.task_id} -> {allocation.assigned_agent_id}")

    # Get stats
    stats = dispatcher.get_dispatcher_stats()
    print(f"\nDispatcher stats:")
    print(f"  Total tasks: {stats['total_tasks']}")
    print(f"  Utilization: {stats['utilization_rate']:.1f}%")


def demo_browser_automation():
    """Demonstrate browser automation enhancements."""
    print("\n" + "="*60)
    print("DEMO: Browser Automation Enhancements")
    print("="*60)

    # 1. Smart Element Locator
    print("\n1. Smart Element Locator")
    print("-" * 40)

    locator = SmartLocator(
        session_id="session_1",
        max_retries=3,
        enable_ai_fallback=True,
    )

    print("Locating elements with multiple strategies:")

    # Try different locators
    locators = [
        {
            "name": "CSS Selector",
            "css_selector": ".submit-button",
        },
        {
            "name": "XPath",
            "xpath": "//button[@type='submit']",
        },
        {
            "name": "Text Content",
            "text": "Submit",
        },
    ]

    for loc in locators:
        result = locator.find_element(**{k: v for k, v in loc.items() if k != "name"})
        status = "✓ Found" if result.found else "✗ Not found"
        print(f"  {loc['name']}: {status}")

    # Check cache
    cache_stats = locator.get_cache_stats()
    print(f"\nCache stats: {cache_stats['cache_size']} cached elements")


def demo_repair_loop():
    """Demonstrate repair loop functionality."""
    print("\n" + "="*60)
    print("DEMO: Repair Loop & Failure Detection")
    print("="*60)

    detector = FailureDetector()

    print("\n1. Failure Detection & Classification")
    print("-" * 40)

    # Simulate different failures
    failures = [
        {
            "name": "Network Error",
            "result": {
                "success": False,
                "error": "Connection refused to server",
                "error_code": "ECONNREFUSED",
            },
        },
        {
            "name": "Timeout",
            "result": {
                "success": False,
                "error": "Operation timeout after 30 seconds",
                "error_code": "ETIMEDOUT",
            },
        },
        {
            "name": "Element Not Found",
            "result": {
                "success": False,
                "error": "Element not found in DOM",
                "error_code": "ELEMENT_NOT_FOUND",
            },
        },
        {
            "name": "Permission Denied",
            "result": {
                "success": False,
                "error": "Permission denied for operation",
                "error_code": "EACCES",
            },
        },
    ]

    for failure_info in failures:
        context = ExecutionContext(
            task_id="task_1",
            agent_id="executor",
            step_index=1,
            action_type="click",
        )

        failure = detector.detect_failure(failure_info["result"], context)

        if failure:
            print(f"\n{failure_info['name']}:")
            print(f"  Category: {failure.category.value}")
            print(f"  Severity: {failure.severity.name}")
            print(f"  Root cause: {failure.root_cause}")
            print(f"  Suggestions:")
            for suggestion in failure.suggestions[:2]:
                print(f"    - {suggestion}")

    # Get statistics
    print("\n2. Failure Statistics")
    print("-" * 40)

    stats = detector.get_failure_stats()
    print(f"Total failures detected: {stats['total_failures']}")
    print(f"By category:")
    for category, count in stats["by_category"].items():
        print(f"  - {category}: {count}")


def main():
    """Run all demonstrations."""
    print("\n" + "="*60)
    print("X-AGENT FEATURE ENHANCEMENTS DEMONSTRATION")
    print("="*60)

    # Run synchronous demos
    demo_memory_fusion()
    demo_browser_automation()
    demo_repair_loop()

    # Run async demo
    print("\n" + "="*60)
    print("Running async demonstrations...")
    print("="*60)
    asyncio.run(demo_multi_agent_collaboration())

    print("\n" + "="*60)
    print("DEMONSTRATION COMPLETE")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
