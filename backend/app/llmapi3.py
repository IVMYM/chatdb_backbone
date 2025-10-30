import asyncio
import os
import json
from dotenv import load_dotenv
import httpx
from fastmcp import Client
from fastmcp.client.transports import SSETransport
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

# ----------------------------------------------------
# 配置 (Configuration)
# ----------------------------------------------------
 
PROMPT = """你是一个专业的数据库查询助手，拥有调用 SQL 工具的能力。请根据用户的自然语言需求，分析并生成合适的 SQL 查询，然后调用对应的工具执行。
一、 你的能力
- 你可以调用以下工具：
  1. get_dbSchema_tables_list(): 获取数据库中所有带schema的表格列表
  2. get_table_definition(table_name: str,schema:Optional[str]=None): 获取指定表的结构定义（列名、数据类型等）
  3. get_table_data(querysql: str): 执行 SQL 查询并返回结果
二、 工作流程
1. 理解需求：仔细分析用户的问题，明确需要查询的数据内容和条件
2. 检查表结构（如果需要）：
   - 首先调用 `get_dbSchema_tables_list()` 获取所有表名
   - 然后调用 `get_table_definition()` 获取相关表的结构信息
3. 生成 SQL：根据表结构和用户需求，生成准确的 SQL 查询语句
4. 执行查询：调用 `get_table_data()` 执行 SQL 查询
5. 整理结果：将查询结果整理成自然语言回答用户
三、 思考过程
在回答用户之前，请先思考：
- 用户的问题需要哪些数据？
- 这些数据可能存储在哪些表中？
- 我是否知道这些表的结构？如果不知道，需要先调用工具获取
- SQL 查询需要哪些条件、聚合函数或连接操作？
- 如何确保 SQL 查询的安全性和效率？
四、 注意事项
- 必须使用工具：所有数据库操作必须通过调用提供的工具完成，不得直接回答假设性结果
- 表名和列名：严格使用从 `get_table_definition()` 获取的实际表名和列名
- SQL 语法：生成的 SQL 必须符合当前数据库类型语法规范
- 参数化查询：避免 SQL 注入风险，正确处理用户输入的参数
- 错误处理：如果工具调用失败或返回错误，请优雅地处理并向用户解释
- 结果格式：将查询结果以清晰易读的格式呈现给用户
 """
load_dotenv()
API_KEY = os.getenv('OAI_API_KEY')
SSE_URL = os.getenv('SSE_URL', 'http://localhost:19068/sse')
LLM_API = os.getenv('BASE_URL', "https://api.siliconflow.cn/v1/chat/completions")
# 显式设置第一次LLM调用的超时时间，默认为10秒
FIRST_PASS_TIMEOUT = float(os.getenv('FIRST_PASS_TIMEOUT', 10.0)) 
MODEL = os.getenv('MODEL', 'GPT-4o')
# Header Information
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# ----------------------------------------------------
# FastAPI Application Initialization
# ----------------------------------------------------
app = FastAPI(
    title="Streaming Database Inspector API (LLM/Tool Integration)",
    description="A FastAPI application demonstrating StreamingResponse (SSE) with LLM and fastmcp tool execution."
)

# ----------------------------------------------------
# Auxiliary Functions
# ----------------------------------------------------
def extract_tool_result(result):
    """Attempt to extract JSON content from fastmcp ClientCallResult"""
    try:
        if result.content:
            raw_text = result.content[0].text
            return json.loads(raw_text)
    except Exception as e:
        print("Failed to parse tool result:", e)
    return str(result)  # Fallback

async def function_calling_stream(messages, tools):
    """
    Asynchronously calls LLM for the second interaction and streams the final reply.
    """
    payload = {
        "model": MODEL,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "stream": True  # Key: Enable streaming response
    }

    # 使用全局客户端，它的默认超时为 60.0 秒，适合较长的流式响应
    async with httpx.AsyncClient(timeout=60.0) as http:
        async with http.stream("POST", LLM_API, headers=HEADERS, json=payload) as response:
            response.raise_for_status()
            async for chunk in response.aiter_text():
                if not chunk.strip():
                    continue
                # Parse SSE format chunk (OpenAI streaming response is JSON fragments)
                for line in chunk.splitlines():
                    line = line.strip()
                    if line.startswith("data: "):
                        data = line[6:]  # Remove "data: " prefix
                        if data == "[DONE]":
                            return
                        try:
                            json_data = json.loads(data)
                            # Extract content fragment (Markdown format)
                            content = json_data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if content:
                                yield content  # Stream out each fragment
                        except json.JSONDecodeError:
                            continue

# ----------------------------------------------------
# Core Logic Function (Asynchronous Generator)
# ----------------------------------------------------
async def mcp_main(question: str = ''):
    """
    Processes user query, returns content in Markdown format as a stream.
    Returns: Asynchronous generator, outputs Markdown string chunk by chunk.
    """
    if not API_KEY:
        yield "{\"error\": \"OAI_API_KEY not set in environment.\"}"
        return

    transport = SSETransport(SSE_URL)
    print(f"Using SSE Transport URL: {SSE_URL}")

    # 客户端超时设置为 60.0 秒，但第一次 POST 请求会使用更短的 FIRST_PASS_TIMEOUT
    async with Client(transport) as client, httpx.AsyncClient(timeout=60.0) as http:
        try:
            # 1. Tool discovery
            # yield "data: ### 🚀 初始化工具环境...\n\n\n" # Yield header in SSE format
            await client.ping()
            tool_defs = await client.list_tools()

            # Convert tool definition to LLM recognizable format
            tools = []
            for tool in tool_defs:
                tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema
                    }
                })
            
            # Yield discovery message in SSE format
            # yield f"data: ✅ 发现 {len(tools)} 个可用工具。开始 LLM 决策 ({FIRST_PASS_TIMEOUT}s 超时)....\n\n\n"
            await asyncio.sleep(0.5)

            # 2. First LLM call: Decision making (non-streaming)
            messages = [{"role":"system","content": PROMPT},{"role": "user", "content": question}]
            payload = {
                "model": MODEL,
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto",
                "stream": False  # First call is non-streaming for quick decision
            }

            # 明确设置超时，以保证快速决策
            response = await http.post(
                LLM_API, 
                headers=HEADERS, 
                json=payload,
                timeout=FIRST_PASS_TIMEOUT 
            )
            print(f"LLM 第一次请求状态码 : {response.status_code}")
            if response.status_code >= 400:
                print(f"LLM 第一次请求错误响应 (First LLM request error response): {response.text}")
            
            response.raise_for_status()
            
            response_text = response.text # Keep response_text for parsing

            try:
                # 尝试 JSON 解码
                data = json.loads(response_text)
            except json.JSONDecodeError as e:
                # 捕获 JSON 解码错误，并打印原始响应文本
                print("!!! JSON DECODE ERROR (Status 200) !!!")
                print(f"错误类型: {type(e).__name__}, 消息: {str(e)}")
                print("原始响应文本:")
                raw_text = response_text
                print(raw_text[:500] + "..." if len(raw_text) > 500 else raw_text)
                # 重新抛出异常，由外部 handler 处理
                raise e 

            try:
                choice = data["choices"][0]
                assistant_message = choice["message"]
                print(f"LLM 回复内容: {assistant_message}")
                tool_calls = assistant_message.get("tool_calls")
            except (IndexError, KeyError) as e:
                # 捕获结构访问错误，并打印接收到的 JSON 数据
                print("==============================================")
                print("!!! UNEXPECTED JSON STRUCTURE (Status 200) !!!")
                print(f"错误类型: {type(e).__name__}, 消息: {str(e)}")
                print("JSON DATA (请检查 'choices' 或 'message' 键/索引):")
                print(json.dumps(data, indent=2, ensure_ascii=False))
                print("==============================================")
                # 重新抛出异常
                raise e

            # 3. If LLM replies directly (no tool call)
            if not tool_calls:
                direct_response = assistant_message.get("content", "未能获取 LLM 回复")
                await asyncio.sleep(0.05) # Yield header first
                # Stream the direct response line by line, enforced SSE format
                for line in direct_response.split('\n'):
                    if line:
                        yield f"data: {line}\n\n"
                        await asyncio.sleep(0.1) # Simulate noticeable flow
                return 
            await asyncio.sleep(0.5)

            # Add tool call request to message history
            messages.append(assistant_message)
            # Execute tool calls and output intermediate results
            tool_result_content = ""
            for call in tool_calls:
                tool_name = call["function"]["name"]
                try:
                    arguments = json.loads(call["function"]["arguments"])
                except json.JSONDecodeError:
                    error_msg = f"❌ 工具调用参数解析错误：{call['function']['arguments']}\n\n"
                    print(error_msg)
                    yield f"data: {error_msg}\n\n" # Yield error in SSE format
                    continue
                await asyncio.sleep(0.3)
                # Call MCP tool
                result = await client.call_tool(tool_name, arguments)
                tool_result_content = extract_tool_result(result)
                await asyncio.sleep(0.5)
                # Add tool result to message history
                messages.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": json.dumps(tool_result_content, ensure_ascii=False)
                })

            async for chunk in function_calling_stream(messages, tools):
                yield f"data: {chunk}\n\n"
                # await asyncio.sleep(0.02)  # Control streaming speed

        except httpx.TimeoutException:
            # 专门捕获超时错误
            error_msg = f" ❌ 处理失败 - 超时连接 LLM API ({LLM_API}) 超时，已超过 {FIRST_PASS_TIMEOUT} 秒。\n"
            print(error_msg)
            error_msg += "请检查网络连接、API 密钥额度或尝试增加 `FIRST_PASS_TIMEOUT`。\n"
            yield f"data: {error_msg}\n\n"
        except Exception as e:
            # 捕获其他所有异常
            error_msg = f" ❌ 处理失败 - 发生意外错误：`{type(e).__name__}: {str(e)}`\n"
            print(error_msg)
            yield f"data: {error_msg}\n\n"
            