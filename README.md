# Model Batch Test Platform

一个基于 Flask 的本地/内网模型批量测试平台基础框架，支持：

- 可视化页面单次调用模型 API
- 上传 CSV / JSON / JSONL / XLSX 测试集，XLS 可作为可选格式支持
- 批量执行测试集并查看输出
- 批量测试结果导出为 Excel `.xlsx`
- 并发压测并统计耗时、成功率、吞吐
- 模型 API 暂时使用配置中的写死地址，也可在页面临时覆盖

## 快速开始

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

打开浏览器访问：

```text
http://127.0.0.1:5001
```

功能页面：

- 概览：`/`
- 单次测试：`/single`
- 批量测试：`/batch`
- 压测：`/pressure`

## 配置模型 API

默认配置在 `config.py`：

```python
DEFAULT_MODEL_API_URL = "http://127.0.0.1:8000/v1/chat/completions"
DEFAULT_MODEL_NAME = "local-model"
```

页面中的“预设模型”也在 `config.py` 的 `MODEL_PRESETS` 中维护。选择预设后会自动填充 API 地址和模型名称，你仍然可以继续手动修改输入框。

如果本地模型 API 兼容 OpenAI Chat Completions，请保持默认 payload 格式即可。也可以通过环境变量覆盖：

```bash
MODEL_API_URL=http://10.0.0.10:8000/v1/chat/completions MODEL_NAME=qwen-local python run.py
```

如需指定 Web 服务端口：

```bash
PORT=8001 python run.py
```

## 测试集格式

CSV、XLSX 至少包含 `prompt` 列，第一行作为表头：

```csv
id,prompt,expected
1,介绍一下 Flask,
2,写一个 Python 排序函数,
```

JSON / JSONL 每条记录支持：

```json
{"id": "case-1", "prompt": "介绍一下 Flask", "expected": ""}
```

老式 `.xls` 文件需要额外安装 `xlrd` 才能解析。如果服务器无法安装 `xlrd`，建议先把 `.xls` 转成 `.xlsx` 后上传。

上传后的文件会保存到 `uploads/` 目录。
