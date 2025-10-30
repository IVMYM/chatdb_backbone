import asyncio
import os
import json
from typing import Optional, Dict, List, Any,AsyncGenerator  
from dotenv import load_dotenv
import httpx
from fastmcp import Client
from fastmcp.client.transports import SSETransport
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from datetime import datetime
from base64 import b64encode
import hmac
import hashlib
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

# 加载环境变量
load_dotenv()
API_KEY = os.getenv('OAI_API_KEY')
SSE_URL = os.getenv('SSE_URL', 'http://localhost:19068/sse')
LLM_API = os.getenv('BASE_URL', "https://api.siliconflow.cn/v1/chat/completions")
FIRST_PASS_TIMEOUT = float(os.getenv('FIRST_PASS_TIMEOUT', 10.0)) 
MODEL = os.getenv('MODEL', 'GPT-4o')
# AI接口配置（与前端一致）
APP_ID = os.getenv("APP_ID", "0FCBBC4DB13541E8AE20")
APP_SECRET = os.getenv("APP_SECRET", "F8C1FFF55A1B450999E23DC474D24226")
WS_BASE_URL = os.getenv("WS_BASE_URL", "http://10.196.91.30:30000")
ASSISTANT_CODE = os.getenv("ASSISTANT_CODE", "scene@1971108944157155328")
CHAT_ENDPOINT = os.getenv("CHAT_ENDPOINT", "/openapi/flames/api/v1/chat")
# 请求头信息
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# ----------------------------------------------------
# FastAPI 应用初始化
# ----------------------------------------------------
app = FastAPI(
    title="Streaming Database Inspector API (LLM/Tool Integration)",
    description="A FastAPI application demonstrating StreamingResponse (SSE) with LLM and fastmcp tool execution."
)

# ----------------------------------------------------
# 辅助函数
# ----------------------------------------------------
def extract_tool_result(result: Any) -> Dict[str, Any]:
    """从工具调用结果中提取JSON内容"""
    try:
        if result.content:
            raw_text = result.content[0].text
            return json.loads(raw_text)
    except Exception as e:
        print(f"解析工具结果失败: {str(e)}")
    return {"error": "解析工具结果失败", "raw_result": str(result)}

async def get_llm_first_response(http_client: httpx.AsyncClient, messages: List[Dict], tools: List[Dict]) -> Dict:
    """获取LLM的第一次响应（决策阶段）"""
    payload = {
        "model": MODEL,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "stream": False
    }
    
    try:
        response = await http_client.post(
            LLM_API,
            headers=HEADERS,
            json=payload,
            timeout=FIRST_PASS_TIMEOUT
        )
        response.raise_for_status()
        return json.loads(response.text)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail=f"LLM API 超时，超过 {FIRST_PASS_TIMEOUT} 秒")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail=f"LLM API 请求失败: {str(e)}")
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"解析LLM响应失败: {str(e)}")

async def stream_llm_response(http_client: httpx.AsyncClient, messages: List[Dict], tools: List[Dict]):
    """流式获取LLM的最终响应"""
    payload = {
        "model": MODEL,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "stream": True
    }

    try:
        async with http_client.stream(
            "POST", 
            LLM_API, 
            headers=HEADERS, 
            json=payload
        ) as response:
            response.raise_for_status()
            async for chunk in response.aiter_text():
                if not chunk.strip():
                    continue
                for line in chunk.splitlines():
                    line = line.strip()
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            return
                        try:
                            json_data = json.loads(data)
                            content = json_data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue
    except httpx.HTTPError as e:
        yield f"❌ LLM 流式响应失败: {str(e)}"

# ----------------------------------------------------
# 核心逻辑
# ----------------------------------------------------                                          
async def mcp_main(question: str) -> AsyncGenerator[str, Any]:
    """处理用户查询的异步生成器"""
    if not API_KEY:
        yield "data: {\"error\": \"OAI_API_KEY 环境变量未设置\"}\n\n"
        return

    # 初始化客户端
    transport = SSETransport(SSE_URL)

    try:
        async with Client(transport) as mcp_client, httpx.AsyncClient(timeout=60.0) as http_client:
            # 1. 工具发现
            await mcp_client.ping()
            tool_defs = await mcp_client.list_tools()
            
            # 转换工具定义为LLM可识别的格式
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
            
            # 2. 第一次LLM调用：决策阶段
            messages = [
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": question}
            ]
            
            try:
                llm_response = await get_llm_first_response(http_client, messages, tools)
            except HTTPException as e:
                yield f"data: ❌ {e.detail}\n\n"
                return

            # 解析LLM响应
            try:
                choice = llm_response["choices"][0]
                assistant_message = choice["message"]
                tool_calls = assistant_message.get("tool_calls", [])
            except (IndexError, KeyError) as e:
                error_msg = f"❌ 解析LLM响应结构失败: {str(e)}\n响应内容: {json.dumps(llm_response, ensure_ascii=False)}"
                yield f"data: {error_msg}\n\n"
                return

            # 3. 如果LLM直接回复（无需工具调用）
            if not tool_calls:
                direct_response = assistant_message.get("content", "未能获取LLM回复")
                for line in direct_response.split('\n'):
                    if line:
                        yield f"data: {line}\n\n"
                        await asyncio.sleep(0.1)
                return

            # 4. 执行工具调用
            messages.append(assistant_message)  # 将工具调用请求添加到消息历史
            
            for call in tool_calls:
                tool_name = call["function"]["name"]
                try:
                    arguments = json.loads(call["function"]["arguments"])
                except json.JSONDecodeError:
                    error_msg = f"❌ 工具调用参数解析错误: {call['function']['arguments']}"
                    yield f"data: {error_msg}\n\n"
                    continue

                # 调用MCP工具
                try:
                    result = await mcp_client.call_tool(tool_name, arguments)
                    tool_result = extract_tool_result(result)
                    # 将工具结果添加到消息历史
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": json.dumps(tool_result, ensure_ascii=False)
                    })
                except Exception as e:
                    error_msg = f"❌ 调用工具 {tool_name} 失败: {str(e)}"
                    yield f"data: {error_msg}\n\n"
                    continue

            # 5. 流式返回最终结果
            async for chunk in stream_llm_response(http_client, messages, tools):
                yield f"data: {chunk}\n\n"
                await asyncio.sleep(0.02)

    except Exception as e:
        error_msg = f"❌ 处理查询时发生意外错误: {str(e)}"
        yield f"data: {error_msg}\n\n"
 # 生成AI接口的WebSocket签名 
async def create_ai_ws_url():
    now = datetime.utcnow()
    date = now.strftime("%a, %d %b %Y %H:%M:%S GMT")  # 符合HTTP标准的UTC时间
    host = WS_BASE_URL.split("//")[-1].split(":")[0]  # 提取主机名
    
    # 构建签名原始字符串
    signature_origin = f"host: {host}\ndate: {date}\nGET {CHAT_ENDPOINT} HTTP/1.1"
    # HMAC-SHA256签名
    hmac_obj = hmac.new(APP_SECRET.encode(), signature_origin.encode(), hashlib.sha256)
    signature_base64 = b64encode(hmac_obj.digest()).decode()
    
    # 构建Authorization
    auth_origin = f'hmac api_key="{APP_ID}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature_base64}"'
    authorization = b64encode(auth_origin.encode()).decode()
    # 拼接WebSocket URL
    params = {
        "authorization": authorization,
        "date": date,
        "host": host,
        "assistantCode": ASSISTANT_CODE
    }
    params_str = "&".join([f"{k}={v}" for k, v in params.items()])
    ws_base = WS_BASE_URL.replace("http", "ws")
    return f"{ws_base}{CHAT_ENDPOINT}?{params_str}"
