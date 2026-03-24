
部署名称：gpt-4o
模型名称 gpt-4o
模型版本
2024-11-20


https://wx-ai-coach-west-us.openai.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2025-01-01-preview

1b15cfa59fdc4ae4bb90f2bd886c5953


开始使用
下面是几个用例的示例代码片段。有关 OpenAI SDK 的其他信息，请参阅完整的 文档 和 示例 。

1. 使用 API 密钥进行身份验证
对于 OpenAI API 终结点，请部署模型以生成终结点 URL 和 API 密钥，从而针对服务进行身份验证。在此示例中，终结点和密钥是包含终结点 URL 和 API 密钥的字符串。

部署模型后，可以在“部署 + 终结点”页面查找 API 终结点 URL 和 API 密钥。

若要使用 API 密钥通过 OpenAI SDK 创建客户端，请将 API 密钥传递给 SDK 的配置以初始化客户端。这使你能够无缝地对 OpenAI 的服务进行身份验证和交互:

from openai import OpenAI

client = OpenAI(
    base_url=f"{endpoint}",
    api_key=api_key
)

2. 安装依赖项
使用 pip 安装 Open AI SDK (要求: Python >=3.8):

pip install openai

3. 运行基本代码示例
此示例演示了对聊天补全 API 的基本调用。调用是同步的。

from openai import OpenAI

endpoint = "https://wx-ai-coach-west-us.openai.azure.com/openai/v1/"
model_name = "gpt-4o"
deployment_name = "gpt-4o"

api_key = "<your-api-key>"

client = OpenAI(
    base_url=f"{endpoint}",
    api_key=api_key
)

completion = client.chat.completions.create(
    model=deployment_name,
    messages=[
        {
            "role": "user",
            "content": "What is the capital of France?",
        }
    ],
)

print(completion.choices[0].message)

