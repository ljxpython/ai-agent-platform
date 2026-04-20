# Runtime Web

`apps/runtime-web` 是当前仓库里的 LangGraph 调试前端，用于直接连接 `runtime-service` 做本地交互验证。

## AI / 开发入口优先级

如果这是跨应用任务，或者你是先让 AI 判定该不该走 `runtime-web`，先读：

1. [Root AGENTS Routing Surface](../../AGENTS.md)
2. [AI 执行系统当前标准](../../docs/standards/01-ai-execution-system.md)
3. [AI 执行系统使用指南](../../docs/ai-execution-system-usage-guide.md)

然后再进入本 app 的当前 leaf standard：

- [Runtime Web 文档导航](./docs/README.md)
- [Runtime Web Debug Shell 标准](./docs/standards/runtime-web-debug-standard.md)

## 开发范式入口

跨应用统一开发方式先看根文档：

- [当前项目开发范式说明](../../docs/development-paradigm.md)

本应用的当前 leaf standard 再看：

- [Runtime Web Debug Shell 标准](./docs/standards/runtime-web-debug-standard.md)

对 `runtime-web` 来说，最重要的执行原则是：

1. 它是调试入口，不是正式平台管理入口
2. 智能体先在这里验证交互行为，再决定是否接当前正式平台链路
3. 如果服务层脚本还没跑通，就不要指望先靠这里把问题猜出来
4. 页面调试要聚焦 runtime 行为，不要把平台权限、结果域问题混进来

## Local Setup

在当前仓库中使用它时，不需要重新 `clone` 上游模板；直接在本目录安装依赖并启动即可。

Install dependencies:

```bash
pnpm install
```

Run the app:

```bash
PORT=3001 pnpm dev
```

The app will be available at `http://localhost:3001`.

## Usage

当前仓库推荐的本地链路是：

- `runtime-web -> runtime-service`
- `runtime-service`: `http://127.0.0.1:8123`
- `runtime-web`: `http://127.0.0.1:3001`

## Run Context 调试面板

`runtime-web` 现提供一个最小化的 **Run Context** 调试面板，用于把任意 JSON object 透传到 LangGraph run 的 `context` 字段。

这块的设计边界必须记死：

1. `runtime-web` 是通用调试壳，不按某个 graph 定制表单
2. 它只负责透传 `context`，不负责判断某个 graph 该传什么
3. 业务字段是否合法，由服务端自己报错
4. 页面只做最薄校验：`Run Context` 必须是合法 JSON，且根节点必须是 object

当前实现方式：

- 输入区工具栏提供 `Context` 按钮
- 点击后打开右侧 `Run Context` 面板
- 面板支持：
  - JSON 编辑
  - `Format`
  - `Save`
  - `Clear`
- 已保存的内容会按当前 `apiUrl + targetType + targetId` 维度存到 `localStorage`

提交时的上下文合并规则：

- `artifactContext`：来自 artifact 面板的附加上下文
- `manualRunContext`：用户在 `Run Context` 面板手工输入并保存的 JSON
- 最终提交时执行浅合并：

```ts
finalContext = {
  ...artifactContext,
  ...manualRunContext,
}
```

其中：

- 手工输入的 `manualRunContext` 覆盖同名 `artifactContext`
- 若合并后为空对象，则本轮 run 不传 `context`

推荐用途：

- 给 `runtime-service` 的 `RuntimeContext` 手工传参
- 快速验证 `project_id / model_id / system_prompt / enable_tools / tools`
- 不改平台层代码，直接调 runtime 运行时契约

不做的事情：

- 不按 graph 自动生成字段面板
- 不做 graph-specific 必填校验
- 不做 schema 驱动表单
- 不替服务端兜底契约错误

## 本应用的开发与验证要求

如果本轮需要验证 Agent 交互，但暂时不需要平台治理能力，优先用 `runtime-web`。

推荐用途：

- 验证 prompt / tools / skills / streaming
- 验证上传文件后的运行时行为
- 验证 graph 是否按预期工作

不推荐用它来代替：

- 正式平台管理面验证
- 平台权限与项目边界验证
- `interaction-data-service` 的结果域查询验证

关键约束：

- `runtime-web` 适合“把智能体调通”，不适合“替平台验收一切”
- 若问题可以在 `runtime-service` 脚本里复现，应优先在服务层排查

如果没有预先配置环境变量，首次进入页面时仍可以手动填写：

- **Deployment URL**: 当前本地建议填写 `http://localhost:8123`
- **Assistant/Graph ID**: 当前仓库默认可先使用 `assistant`
- **LangSmith API Key**: 仅在连接需要额外鉴权的远端部署时才需要

After entering these values, click `Continue`. You'll then be redirected to a chat interface where you can start chatting with your LangGraph server.

## Environment Variables

You can bypass the initial setup form by setting the following environment variables:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8123
NEXT_PUBLIC_ASSISTANT_ID=assistant
```

> [!TIP]
> If you want to connect to a production LangGraph server, read the [Going to Production](#going-to-production) section.

To use these variables:

1. Copy the `.env.example` file to a new file named `.env`
2. Replace the template values with the current local values shown above, especially `NEXT_PUBLIC_API_URL=http://localhost:8123`
3. Restart the application

When these environment variables are set, the application will use them instead of showing the setup form.

For the current repository-wide local development conventions, see `docs/local-dev.md` and `docs/env-matrix.md`.

## Hiding Messages in the Chat

You can control the visibility of messages within the Agent Chat UI in two main ways:

**1. Prevent Live Streaming:**

To stop messages from being displayed _as they stream_ from an LLM call, add the `langsmith:nostream` tag to the chat model's configuration. The UI normally uses `on_chat_model_stream` events to render streaming messages; this tag prevents those events from being emitted for the tagged model.

_Python Example:_

```python
from langchain_anthropic import ChatAnthropic

# Add tags via the .with_config method
model = ChatAnthropic().with_config(
    config={"tags": ["langsmith:nostream"]}
)
```

_TypeScript Example:_

```typescript
import { ChatAnthropic } from "@langchain/anthropic";

const model = new ChatAnthropic()
  // Add tags via the .withConfig method
  .withConfig({ tags: ["langsmith:nostream"] });
```

**Note:** Even if streaming is hidden this way, the message will still appear after the LLM call completes if it's saved to the graph's state without further modification.

**2. Hide Messages Permanently:**

To ensure a message is _never_ displayed in the chat UI (neither during streaming nor after being saved to state), prefix its `id` field with `do-not-render-` _before_ adding it to the graph's state, along with adding the `langsmith:do-not-render` tag to the chat model's configuration. The UI explicitly filters out any message whose `id` starts with this prefix.

_Python Example:_

```python
result = model.invoke([messages])
# Prefix the ID before saving to state
result.id = f"do-not-render-{result.id}"
return {"messages": [result]}
```

_TypeScript Example:_

```typescript
const result = await model.invoke([messages]);
// Prefix the ID before saving to state
result.id = `do-not-render-${result.id}`;
return { messages: [result] };
```

This approach guarantees the message remains completely hidden from the user interface.

## Rendering Artifacts

The Agent Chat UI supports rendering artifacts in the chat. Artifacts are rendered in a side panel to the right of the chat. To render an artifact, you can obtain the artifact context from the `thread.meta.artifact` field. Here's a sample utility hook for obtaining the artifact context:

```tsx
export function useArtifact<TContext = Record<string, unknown>>() {
  type Component = (props: {
    children: React.ReactNode;
    title?: React.ReactNode;
  }) => React.ReactNode;

  type Context = TContext | undefined;

  type Bag = {
    open: boolean;
    setOpen: (value: boolean | ((prev: boolean) => boolean)) => void;

    context: Context;
    setContext: (value: Context | ((prev: Context) => Context)) => void;
  };

  const thread = useStreamContext<
    { messages: Message[]; ui: UIMessage[] },
    { MetaType: { artifact: [Component, Bag] } }
  >();

  return thread.meta?.artifact;
}
```

After which you can render additional content using the `Artifact` component from the `useArtifact` hook:

```tsx
import { useArtifact } from "../utils/use-artifact";
import { LoaderIcon } from "lucide-react";

export function Writer(props: {
  title?: string;
  content?: string;
  description?: string;
}) {
  const [Artifact, { open, setOpen }] = useArtifact();

  return (
    <>
      <div
        onClick={() => setOpen(!open)}
        className="cursor-pointer rounded-lg border p-4"
      >
        <p className="font-medium">{props.title}</p>
        <p className="text-sm text-gray-500">{props.description}</p>
      </div>

      <Artifact title={props.title}>
        <p className="p-4 whitespace-pre-wrap">{props.content}</p>
      </Artifact>
    </>
  );
}
```

## Going to Production

Once you're ready to go to production, you'll need to update how you connect, and authenticate requests to your deployment. By default, the Agent Chat UI is setup for local development, and connects to your LangGraph server directly from the client. This is not possible if you want to go to production, because it requires every user to have their own LangSmith API key, and set the LangGraph configuration themselves.

### Production Setup

To productionize the Agent Chat UI, you'll need to pick one of two ways to authenticate requests to your LangGraph server. Below, I'll outline the two options:

### Quickstart - API Passthrough

The quickest way to productionize the Agent Chat UI is to use the [API Passthrough](https://github.com/bracesproul/langgraph-nextjs-api-passthrough) package ([NPM link here](https://www.npmjs.com/package/langgraph-nextjs-api-passthrough)). This package provides a simple way to proxy requests to your LangGraph server, and handle authentication for you.

This repository already contains all of the code you need to start using this method. The only configuration you need to do is set the proper environment variables.

```bash
NEXT_PUBLIC_ASSISTANT_ID="agent"
# This should be the deployment URL of your LangGraph server
LANGGRAPH_API_URL="https://my-agent.default.us.langgraph.app"
# This should be the URL of your website + "/api". This is how you connect to the API proxy
NEXT_PUBLIC_API_URL="https://my-website.com/api"
# Your LangSmith API key which is injected into requests inside the API proxy
LANGSMITH_API_KEY="lsv2_..."
```

Let's cover what each of these environment variables does:

- `NEXT_PUBLIC_ASSISTANT_ID`: The ID of the assistant you want to use when fetching, and submitting runs via the chat interface. This still needs the `NEXT_PUBLIC_` prefix, since it's not a secret, and we use it on the client when submitting requests.
- `LANGGRAPH_API_URL`: The URL of your LangGraph server. This should be the production deployment URL.
- `NEXT_PUBLIC_API_URL`: The URL of your website + `/api`. This is how you connect to the API proxy. For the [Agent Chat demo](https://agentchat.vercel.app), this would be set as `https://agentchat.vercel.app/api`. You should set this to whatever your production URL is.
- `LANGSMITH_API_KEY`: Your LangSmith API key to use when authenticating requests sent to LangGraph servers. Once again, do _not_ prefix this with `NEXT_PUBLIC_` since it's a secret, and is only used on the server when the API proxy injects it into the request to your deployed LangGraph server.

For in depth documentation, consult the [LangGraph Next.js API Passthrough](https://www.npmjs.com/package/langgraph-nextjs-api-passthrough) docs.

### Advanced Setup - Custom Authentication

Custom authentication in your LangGraph deployment is an advanced, and more robust way of authenticating requests to your LangGraph server. Using custom authentication, you can allow requests to be made from the client, without the need for a LangSmith API key. Additionally, you can specify custom access controls on requests.

To set this up in your LangGraph deployment, please read the LangGraph custom authentication docs for [Python](https://langchain-ai.github.io/langgraph/tutorials/auth/getting_started/), and [TypeScript here](https://langchain-ai.github.io/langgraphjs/how-tos/auth/custom_auth/).

Once you've set it up on your deployment, you should make the following changes to the Agent Chat UI:

1. Configure any additional API requests to fetch the authentication token from your LangGraph deployment which will be used to authenticate requests from the client.
2. Set the `NEXT_PUBLIC_API_URL` environment variable to your production LangGraph deployment URL.
3. Set the `NEXT_PUBLIC_ASSISTANT_ID` environment variable to the ID of the assistant you want to use when fetching, and submitting runs via the chat interface.
4. Modify the [`useTypedStream`](src/providers/Stream.tsx) (extension of `useStream`) hook to pass your authentication token through headers to the LangGraph server:

```tsx
const streamValue = useTypedStream({
  apiUrl: process.env.NEXT_PUBLIC_API_URL,
  assistantId: process.env.NEXT_PUBLIC_ASSISTANT_ID,
  // ... other fields
  defaultHeaders: {
    Authentication: `Bearer ${addYourTokenHere}`, // this is where you would pass your authentication token
  },
});
```
