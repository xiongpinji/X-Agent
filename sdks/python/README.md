# xagent-partner (Python SDK)

X-Agent Partner API 的官方 Python SDK。

> **分发方式说明**: 本 SDK 当前以**源码形式分发**, **未发布到 PyPI**。
> `pip install xagent-partner` 目前不可用, 请使用下方的本地安装方式。

## 本地安装

从仓库根目录:

```bash
pip install ./sdks/python
```

或在本目录内:

```bash
pip install .
```

## 本地构建 wheel / sdist

```bash
# 方式一: pip (无需额外工具)
python -m pip wheel . --no-deps -w dist

# 方式二: build (需先 pip install build)
python -m build
```

构建产物为 `dist/xagent_partner-<version>-py3-none-any.whl` 与 sdist tarball。
版本号由 `xagent_partner.py` 中的 `__version__` 单一事实源动态读取。

## 使用

```python
from xagent_partner import PartnerClient

client = PartnerClient(
    api_key="xag_partner_xxx",
    base_url="https://your-x-agent-instance.example.com",  # 指向实际部署的后端
)
partner = client.register_partner(
    company_name="Acme Corp",
    contact_email="contact@acme.com",
    contact_name="John Doe",
)
print(partner)
```

## 依赖

- Python >= 3.9
- `httpx >= 0.24`(唯一运行时依赖)

## License

MIT
