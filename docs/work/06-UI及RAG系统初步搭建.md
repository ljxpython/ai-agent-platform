

## UI框架改动



```
请仔细熟悉我的智能体发开框架及步骤,代码及说明在backend/ai_core中,应用范例:接口层:backend/api/v1/testcase.py,服务层:backend/services/testcase
现在我想在对外接口不变化的前提下将UI智能体系统的代码按照该框架实现,UI的接口代码:backend/api/v1/midscene.py,服务层代码:backend/services/ui_testing
```





1. **模块化设计**：`backend/ai_core/` 提供统一的LLM客户端、智能体工厂、内存管理、运行时管理、消息队列
2. ujn业务解耦**：通用组件与业务逻辑分离，提高复用性
3. **健壮性优先**：完整的错误处理和容错机制
4. **工程化友好**：简化业务代码开发，提高开发效率



- **接口层**：`backend/api/v1/testcase.py` - 使用SSE流式输出
- **服务层**：`backend/services/testcase/` - 基于AI核心框架的业务封装
- **智能体实现**：使用`create_assistant_agent`、消息队列、内存管理
- **运行时管理**：专用运行时`TestCaseRuntime`继承`BaseRuntime`



## RAG服务搭建



```
我想搭建一个RAG服务:
技术: LlamaIndex Ollama Milvus

```



现在deepseek上寻求帮助

```
我想llama_index 怎么和ollama及Milvus结合在一起,请做一个demo,框架化一点,我已经远程部署好ollama及Milvus了,我想做一个RAG系统
```

![image-20250624235702179](./assets/image-20250624235702179.png)



deepseek帮我生成了相应的代码,从这份代码学习,将该代码跑通,之后融合到我现在的服务框架中

后续我发现demo还不算太难,但是在这个过程中遇到了很多的报错,需要自己从deepseek的文档中学习查找





```
帮我完成一个RAG系统demo的开发,代码放在
examples/llama_rag_system_demo中
使用Milvus向量数据库,Ollama大模型服务,llama_index
框架如下:
RAG System
├── 数据加载模块 (Data Loader)
├── 嵌入生成模块 (Embedding Generator)
├── Milvus向量数据库 (Vector DB)
├── Ollama大模型服务 (LLM Service)
└── 查询引擎 (Query Engine)

环境的配置在examples/conf/constants.py的settings,具体值在examples/conf/settings.yaml中
嵌入模型: "nomic-embed-text"
大语言模deepseek
大语言开发框架: llama_index
llama_index的文档:https://docs.llamaindex.ai/en/stable/api_reference/
最后给出一个小的案例来进行展示

```



```
1. 关于你刚才遇到的llm导入问题:
可以从这个页面得到答案:https://docs.llamaindex.ai/en/stable/examples/llm/deepseek/
from llama_index.llms.deepseek import DeepSeek
# you can also set DEEPSEEK_API_KEY in your environment variables
llm = DeepSeek(model="deepseek-reasoner", api_key="you_api_key")
2. examples/llama_rag_system_demo/config.py中配置可以放到examples/conf创建一个名为rag_config的目录
2. examples/llama_rag_system_demo目录下,文件太多,删除掉多余的文件,测试文件放在test目录下,让我可以更快的上手这个服务,框架更加清晰明了


```



```
examples/llama_rag_system_demo 这个目录下非服务核心部分的代码全部放到tests目录下
```





**核心服务文件（保留在主目录）**：

- `__init__.py` - 包初始化
- `utils.py` - 工具模块
- `rag.py` - 主入口文件
- `data_loader.py` - 数据加载模块
- `embedding_generator.py` - 嵌入生成模块
- `vector_store.py` - 向量数据库模块
- `llm_service.py` - LLM服务模块
- `query_engine.py` - 查询引擎模块

**非核心文件（移动到tests目录）**：

- `demo.py` - 演示案例
- `quick_start.py` - 快速开始示例
- `simple_example.py` - 简单示例
- `rag_system.py` - 完整版RAG系统（可选保留或移动）
- `README.md` - 文档





```
基于Milvus向量数据库,Ollama大模型服务,llama_index,deepseek开发一个RAG知识库系统,我已经完成了基础的框架,代码在examples/llama_rag_system_demo中
现在我想将其融合到我的后端代码中,后端代码在backend,可以在backend下建立一个rag_core的文件夹,将基础框架的代码放入其中
优化:rag未来支持多个collection可以为后端已有的服务或者不同的业务提供专业的知识库
```



```
向量数据的部分存在问题,嵌入数据库写到了本地backend/services/rag/milvus_llamaindex.db,而非远端的数据库中
```





```
优化AI对话模块backend/services/ai_chat/autogen_service.py,加入RAG知识库,支持选择不同的collection进行知识问答,支持前端上传文件到指定的collection中,回答能实时反馈RAG及智能体每个步骤返回的内容
前后端使用sse流式输出,可以参考backend/ai_core/message_queue.py和backend/services/testcase/agents.py及backend/api/v1/testcase.py中的消息队列流式输出的使用,代码能复用尽量复用
AI对话的API层backend/api/v1/chat.py
前端: frontend/src/pages/ChatPage.tsx做对应的修改和适配


```

前端

![image-20250625130859707](./assets/image-20250625130859707.png)



![image-20250625130916655](./assets/image-20250625130916655.png)





```
1.前段设计一个RAG管理界面放在AI模块下,可以对各个collection进行管理,可以对collection进行增删改查,可以collection中内容进行管理,后端进行相应的功能开发
2. AI对话模块右上角的选择collection及是否启用知识库的图标有些不美观
3. 前端的对话,RAG知识库的部分非流式输出,检查后端代码是否有问题
```



```
当前对话还是会被强制回到流式输出的位置,请继续修复这个问题
```







```
AI对话模块,当前滑动页面,会强制回到流式输出的位置,预期生成流式日志时,我应该还可以自由浏览相关内容
在前端页面刚打开时,会一直加载collecting,应该把collection写入到数据库中,直接调用数据库查询有哪些collecting,之后在前端展示
```







```
请你和我一起探索,作为一款RAG知识库系统,目前还欠缺那些功能,我们一起在已有服务的基础上,继续增强优化
我想在前端单独出一个RAG知识库管理的一级目录,其下面存放对RAG相关功能的管理
比如说单独的文件上传,解析,存储向量数据库等等这些
嵌入模型的管理等等这些
```



```
在backend/controllers目录下,是用来API和数据库交互的,backend/controllers/rag_controller.py不应该在该目录下,后端的目录backend下,backend/api存放接口,backend/controllers接口和数据库交互使用,backend/models数据库建模,backend/schemas接口及响应参数校验
请仔细阅读后端的代码,RAG相关的代码要符合该后端开发框架的规范
```



```
RAG知识库的代码backend/rag_core,请在其目录下创建一个docs,该目录下完成RAG开发规范及使用说明,范例,AI编程助手根据文档就可以知道如何进行相应的开发工作
```





```
统一请求结果和异常处理还需要再封装,抽象出一个可以复用的功能
参考: examples/backend_examples/app/schemas/base.py
和examples/backend_examples/app/core/exceptions.py中的后端框架做进一步优化,封装出通用的响应接口
受到影响的前端进行适配
```





```
请仔细阅读backend目录,在backend/docs目录下完成开发规范及使用说明
给出每一个模块的详细使用方式
sse的相关输出按照协议的规范来就可以了
API层,每个接口如何参数校验,如何统一返回参数,如何和数据库交互增删改查
backend/core/response.py的使用
backend/controllers中,如何复用已有的代码,简化增删改查操作,给出范例
backend/models,如何做模型定义,复用已有代码
backend/schemas 如何校验参数
backend/ai_core层,backend/rag_core层在其目录下已经有详细介绍了
```





```
对docs目录内的内容重新做整理,要分门别类清晰的放到对应的文件内,然后留下README.md
```









## 问题

```
问题一:
目前RAG里面其实就包含了和llm对话返回内容的部分,但是chat的服务还会调用Autogen的对话,再次问一遍,这个功能以后优化

目前RAG知识库不是流式输出,且内容输出不是使用的消息队列的方式,这个都放到面在优化

问题二
文本上传未来使用mino当前上传到本地,解析后,放入数据库中保存

流式输出的地方优化
```





## 问题解决

想了想,还是把基建搭好吧,防止以后推到重来

### 问题1

先说上面第一个问题,AI生成的代码我看了,那其实AI在输出结果是又调用了一次大模型,让大模型加工

代码如下:![image-20250625234750764](./assets/image-20250625234750764.png)



这部分让Autogen实现的assitant来完成即可,是一样的

其次,RAG的流程

入库:  文件清晰 -> 文件解析 ->   文件分块 ->  向量化 ->  存储到向量数据库中

出库:  用户的需求 -> 向量化  -> 语义检索,全文检索,混合检索 -> 召回 -> 一起给到大模型 -> 大模型加工出结果

大概就是如上的过程

那么我希望出库的时候把召回的内容是什么也打印出来到前端

和AI进行对话

```
1.  sse流式输出的使用消息队列的方式实现,消息队列复用backend/ai_core/message_queue.py中的代码
服务层的代码可以查看backend/services/testcase/agents.py中的队列消息使用
尽可能的复用backend/ai_core/message_queue.py代码中已有的功能
 sse流式输出的使用消息队列的方式实现,消息队列复用 backend/ai_core/message_queue.py中的代码

2.  backend/services/ai_chat/autogen_service.py代码中,下面这段内容
 # 构建增强的提示
                    if rag_context:
                        enhanced_message = f"""基于以下知识库信息回答用户问题：

知识库信息：
{rag_context}

用户问题：{message}

请结合知识库信息和你的知识来回答用户问题。如果知识库信息不足以回答问题，请说明并提供你的最佳建议。"""

                        # 流式发送RAG回答内容
                        rag_answer_start = {
                            "type": "rag_answer_start",
                            "source": "RAG知识库",
                            "content": "💡 知识库回答：",
                            "collection_name": collection_name,
                            "timestamp": datetime.now().isoformat(),
                        }
                        yield f"data: {json.dumps(rag_answer_start, ensure_ascii=False)}\n\n"

                        # 将RAG回答分块流式输出
                        chunk_size = 50  # 每块字符数
                        for i in range(0, len(rag_context), chunk_size):
                            chunk = rag_context[i : i + chunk_size]
                            rag_chunk_message = {
                                "type": "rag_answer_chunk",
                                "source": "RAG知识库",
                                "content": chunk,
                                "collection_name": collection_name,
                                "timestamp": datetime.now().isoformat(),
                            }
                            yield f"data: {json.dumps(rag_chunk_message, ensure_ascii=False)}\n\n"
                            # 添加小延迟模拟流式效果
                            await asyncio.sleep(0.05)

                        # RAG回答结束
                        rag_answer_end = {
                            "type": "rag_answer_end",
                            "source": "RAG知识库",
                            "content": "\n\n---\n",
                            "collection_name": collection_name,
                            "timestamp": datetime.now().isoformat(),
                        }
                        yield f"data: {json.dumps(rag_answer_end, ensure_ascii=False)}\n\n"

                else:
                    logger.info("❌ RAG查询无结果，使用原始消息")
                    # 发送RAG查询无结果的信息
                    no_rag_message = {
                        "type": "rag_no_result",
                        "source": "RAG知识库",
                        "content": f"📚 在 {collection_name} 知识库中未找到相关信息，将基于通用知识回答",
                        "collection_name": collection_name,
                        "timestamp": datetime.now().isoformat(),
                    }
                    yield f"data: {json.dumps(no_rag_message, ensure_ascii=False)}\n\n"
                    放到由Autogen创建的智能体中实现:  # 创建Agent
            agent = self.create_agent(conversation_id, system_message)
```



```
1. chat_stream_with_rag 函数中的逻辑不正确,用户的需求 -> 向量化  -> 语义检索,全文检索,混合检索 -> 召回 -> 一起给到大模型 -> 大模型加工出结果
也就是说,大模型这里给的不是llama_index中模型,而是Autogen中的assistant
2. 召回的内容也全部流式输出,让前端展示
3. API层/stream/rag接口未使用消息队列的方式处理sse消息,参照backend/api/v1/testcase.py中/generate/streaming的逻辑实现
4. 前端进行适配
```



```
1. 后端报错2025-06-26 01:10:47 | ERROR    | backend.services.ai_chat.autogen_service:get_rag_collections:125 | 获取RAG集合失败: 'RAGService' object has no attribute 'get_collections'
2.前端警告: chunk-BOEZ7BP5.js?v=e99c2e18:1190 Warning: [antd: Select] `bordered` is deprecated. Please use `variant` instead.
3. /stream/rag  接口的流式输出没有输出
请修复上述问题
```



查询不存在的

![image-20250626114645268](./assets/image-20250626114645268.png)

查询存在的:

![image-20250626114846916](./assets/image-20250626114846916.png)



需要优化的点是,召回的内容应该放到一个文本框里面



### 问题2

```
上传文件的逻辑需要优化
首先,上传的文件,先解析记录md5,之后解析后将内容存储到MySQL或者数据库中
后面再次有文件传入,先查询一次数据库,如果值存在,则使用已有的值,可以服用document中的逻辑

1.每个召回的内容都放到一个文本框中
2. 用数据库记录 上传的文件的相关信息:必要的有用户,md5,文件类型,解析内容,上传到那个collection等等信息
3. backend/api/v1/chat.py接口增加功能: 可以参照backend/services/document/document_service.py中代码实现,判断上传文件为之前上传过的,那么不需要处理,告诉前端,该内容已经存入RAG如需上传

```





```
1.前端每个召回的内容都放到一个文本框中
2. 用数据库记录 上传的文件的相关信息:必要的有用户,md5,文件类型,解析内容,上传到那个collection等等信息
3. backend/api/v1/chat.py接口增加功能: 可以参照backend/services/document/document_service.py中代码实现,判断上传文件为之前上传过的,那么不需要处理,告诉前端,该内容已经存入RAG如需上传
```





```
步骤一:将当前的代码还原到上一个版本重新设计
步骤二:数据库设计思路如下:
维护一个RAG上传文件的记录的表: 最关键的字段:记录文件的MD5,及上传到那个collection
步骤三: 使用:当用户上传文件时,如果该文件(MD5判断)已经上传到对应的collection,就不需要再次重复上传了
步骤四: 修改对应的上传文件接口
```



```
1. 前端优化:上传文件到知识库模块,应该添加一个确认的按钮,当点击确认后才执行,且支持多个文件同时上传
2. 前端每个召回的内容都放到一个文本框中
```





```
召回的相关文档 放置的位置不对,应该放置在用户需求和AI智能体回答之间的位置
```





```
1. RAG知识库,文档管理的前端和后端没有打通,实现文档管理的部分的后端
2. RAG知识库,下面几个模块还未开发完成:向量管理,系统监控,配置管理,当用户打开后,最好有一个暖心的提醒,告诉用户,该模块当前正处于开发过程,暂不对外使用

```





```
问题1:前端文档管理为空 /api/v1/rag/documents接口返回结果为空:{
    "code": 200,
    "msg": "获取文档列表成功",
    "data": {
        "documents": []
    },
    "total": 0,
    "page": 1,
    "page_size": 20
}
问题2: 打开添加文本:目标collection显示的为0123,而非对应的文本
问题3: 打开添加文本,添加文本后,/api/v1/rag/documents/add-text报错
{
    "code": 422,
    "msg": "请求参数验证失败",
    "data": {
        "errors": [
            {
                "type": "missing",
                "loc": [
                    "body",
                    "title"
                ],
                "msg": "Field required",
                "input": null
            },
            {
                "type": "missing",
                "loc": [
                    "body",
                    "content"
                ],
                "msg": "Field required",
                "input": null
            }
        ]
    }
}
对应后端报错2025-06-26 22:59:09 | ERROR    | backend.api_core.exceptions:request_validation_handler:101 | 请求参数验证异常: [{'type': 'missing', 'loc': ('body', 'title'), 'msg': 'Field required', 'input': None}, {'type': 'missing', 'loc':  'content'), 'msg': 'Field required', 'input': None}]
2025-06-26 22:59:09 - INFO - 127.0.0.1:56930 - "POST /api/v1/rag/documents/add-text HTTP/1.1" 422 Unprocessable Entity
问题4: 上传文件功能,点击后应该添加一个确认的按钮,当点击确认后才执行,且支持多个文件同时上传
```





```
1. 上传文本和添加文本中目标Collection下拉的选项不是真正的collection,真正已经存在的Collection,请调用接口从数据库中查找,后端报错2025-06-26 23:29:18 | INFO     | backend.services.ai_chat.autogen_service:add_content_to_rag:491 | 添加内容到RAG | 文件: 协程使用.md | 集合: 1 | 内容长度: 4437
2025-06-26 23:29:18 | ERROR    | backend.services.rag.rag_service:add_text:176 | ❌ 文本添加失败 - Collection: 1: Collection不存在: 1
2. http://localhost:8000/api/v1/rag/documents/?page=1&page_size=20 是可以查到值的,但是调用http://localhost:3000/api/v1/rag/documents,前端却没有值
修复上述两个问题
```





```
1. 前端调取/api/v1/rag/documents接口为空问题:
2025-06-27 00:54:06 - INFO - 127.0.0.1:59807 - "GET /api/v1/rag/documents/ HTTP/1.1" 200 OK 可以获取到结果
2025-06-27 00:54:15 - INFO - 127.0.0.1:59851 - "GET /api/v1/rag/documents HTTP/1.1" 200 OK  结果为空
2. 文档管理:处理消息队列一栏 文件名和Collection列没有正确的展示
3. RAG知识库系统没有一个对Collection进行管理的界面,实现前后端,界面放在管理中心下方,支持对Collection的增删改查
4. 管理中心中文档总数没有正确的显示,快速操作中,上传文档和创建Collection的功能都为实现
5. 参考后端其他服务的代码,为RAG系统增加完善的日志,这样有利于排查问题,前段也同样增加详细的日志
```





```
调用后端报错,创建Collection报错,再次调用报错test已存在,不过向量数据库里查询却没有
2025-06-27 01:24:19 | ERROR    | backend.api.v1.rag_collections:create_collection:134 | ❌ 创建Collection失败: 'RAGCollection' object has no attribute 'embedding_model'
2025-06-27 01:24:19 | ERROR    | backend.api_core.exceptions:http_exception_handler:92 | HTTP异常: 500 - 创建Collection失败: 'RAGCollection' object has no attribute 'embedding_model'
2025-06-27 01:24:19 - INFO - 127.0.0.1:53225 - "POST /api/v1/rag/collections-manage/ HTTP/1.1" 500 Internal Server Error
2025-06-27 01:24:26 | INFO     | backend.api.v1.rag_collections:create_collection:91 | 📝 创建Collection: test
2025-06-27 01:24:26 | WARNING  | backend.api.v1.rag_collections:create_collection:96 | ⚠️ Collection名称已存在: test
2025-06-27 01:24:26 | ERROR    | backend.api_core.exceptions:http_exception_handler:92 | HTTP异常: 400 - Collection名称 'test' 已存在
2025-06-27 01:24:26 - INFO - 127.0.0.1:53260 - "POST /api/v1/rag/collections-manage/ HTTP/1.1" 400 Bad Request
目前RAG相关配置在backend/conf/settings.yaml中backend/conf/rag_config.py封装

```



## RAG相关功能的完善

```
RAG知识库的中每个Collection实例化一个是否有必要
使用filter来过滤元数据是否有必要

前端:文档框架不符合要求,回调了两份内容

RAG知识库创建Collection的的代码

后端服务的API router注册都放在init中来管理

```





```
1. 前端调用接口:/api/v1/rag/collections/9 405 Method Not Allowed  为什么是9 Request Method DELETE 方法不对,检查更新的方法是不是也报这个错误
2. /api/v1/rag/collections/3/stats  查看统计的接口也报错
Request Method
GET
Status Code
404 Not Found
3. 想拖动左侧的导航栏发现,右侧的页面在滑动
```
