import asyncio
from dataclasses import dataclass

from autogen_core import (
    DefaultTopicId,
    MessageContext,
    RoutedAgent,
    SingleThreadedAgentRuntime,
    default_subscription,
    message_handler,
)
from autogen_ext.runtimes.grpc import GrpcWorkerAgentRuntime


@dataclass
class MyMessage:
    content: str


@default_subscription
class MyAgent(RoutedAgent):
    def __init__(self, name: str) -> None:
        super().__init__("My agent")
        self._name = name
        self._counter = 0

    @message_handler
    async def my_message_handler(self, message: MyMessage, ctx: MessageContext) -> None:
        self._counter += 1
        if self._counter > 5:
            return
        content = f"{self._name}: Hello x {self._counter}"
        print(content)
        await self.publish_message(MyMessage(content=content), DefaultTopicId())


async def main():
    # 模拟本地运行时
    worker0 = SingleThreadedAgentRuntime()
    await MyAgent.register(worker0, "worker0", lambda: MyAgent("worker0"))

    # 模拟主机1
    worker1 = GrpcWorkerAgentRuntime(host_address="localhost:50051")
    await worker1.start()
    await MyAgent.register(worker1, "worker1", lambda: MyAgent("worker1"))

    # 模拟主机2
    worker2 = GrpcWorkerAgentRuntime(host_address="localhost:50051")
    await worker2.start()
    await MyAgent.register(worker2, "worker2", lambda: MyAgent("worker2"))

    await worker2.publish_message(MyMessage(content="Hello!"), DefaultTopicId())

    # Let the agents run for a while.
    await asyncio.sleep(5)


asyncio.run(main())
