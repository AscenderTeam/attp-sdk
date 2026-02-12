<div align="center">

  <!-- Logo Placeholder -->
  <img src="assets/logo.png" alt="attp-sdk" width="200" height="auto" />
  <h1>attp-sdk</h1>

  <!-- Typing SVG -->
  <a href="https://git.io/typing-svg">
    <img src="https://readme-typing-svg.herokuapp.com?font=Fira+Code&pause=1000&color=2496ED&center=true&vCenter=true&width=435&lines=Build+ATTP+Services;High+Performance+RPC;Reactive+Gateway" alt="Typing SVG" />
  </a>

  <p>
    <b>The robust Python SDK for building distributed services with the ATTP protocol.</b>
  </p>

  <!-- Badges -->
  <p>
    <a href="https://github.com/AscenderTeam/attp-sdk/stargazers">
      <img src="https://img.shields.io/github/stars/AscenderTeam/attp-sdk?style=for-the-badge&logo=github&color=yellow" alt="Stars"/>
    </a>
    <img src="https://img.shields.io/badge/python-3.11%2B-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.11+"/>
    <img src="https://img.shields.io/badge/ascender-2.0.4-orange?style=for-the-badge&logo=fire&logoColor=white" alt="Ascender Framework"/>
    <img src="https://img.shields.io/badge/pypi-v0.1.0-blueviolet?style=for-the-badge&logo=pypi&logoColor=white" alt="PyPI"/>
    <img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="License"/>
  </p>
</div>

---

## 📖 Introduction

**attp-sdk** is the official Python library for integrating with the **Ascender** ecosystem using the **ATTP** (Ascender Tool Transmission Protocol). It provides a powerful set of tools to build high-performance, scalable, and reactive microservices.

With `attp-sdk`, you can effortlessly create controllers, handle RPC calls, manage events, and orchestrate service lifecycles, all while leveraging the robustness of the Ascender Framework.

## ⚡ Features

-   **RPC Decoration**: Simple `@AttpCall` decorators to expose methods as RPC endpoints.
-   **Event Driven**: Reactive `@AttpEvent` handlers for asynchronous communication.
-   **Lifecycle Management**: Hooks for `@AttpLifecycle` events like `connect` and `disconnect`.
-   **Error Handling**: Centralized `@AttpErrorHandler` for graceful failure management.
-   **Dependency Injection**: Seamless integration with Ascender's DI system.
-   **Transmitter**: Fluent API for sending requests and notifications.

## 📦 Installation

Install via Poetry:

```bash
poetry add attp-sdk
```

Or using Pip:

```bash
pip install attp-sdk
```

Or using UV:

```bash
uv add attp-sdk
```

## ⚙️ Configuration

`attp-sdk` uses a configuration file (usually `attp.jsonc` or `attp.json`) to define node identity, authentication, and peer services.

### Example `attp.jsonc`

```jsonc
{
  "node": {
    "name": "my-service",
    "bind": "0.0.0.0:6563"
  },
  "caps": ["schema/msgpack", "streaming"],
  "client": {
    "auth": {
      "mode": "hmac",
      "secret": { "env": "ATTP_SHARED_SECRET" },
      "node_id": "my-service",
      "ttl_seconds": 30
    }
  },
  "services": {
    "peers": [
      { "namespace": "core-service", "uri": "attp://core-api:6563" }
    ]
  }
}
```

## 🚀 Usage

### Creating a Controller

Define your service logic using a class-based controller.

```python
from ascender.core import Controller
from attp.decorators import AttpCall, AttpEvent, AttpLifecycle
from attp.types.frame import AttpFrameDTO

class EchoRequest(AttpFrameDTO):
    message: str

class EchoResponse(AttpFrameDTO):
    message: str

@Controller(
    standalone=True,
    providers=[],
)
class MyController:
    
    @AttpCall("echo", namespace="core-service")
    async def echo(self, payload: EchoRequest) -> EchoResponse:
        print(f"Received: {payload.message}")
        return EchoResponse(message=payload.message)

    @AttpEvent("user.created")
    async def on_user_created(self, payload: dict):
        print(f"New user: {payload.get('id')}")

    @AttpLifecycle("connect")
    async def on_connect(self, meta: dict):
        print("Connected to ATTP network")
```

### Sending Messages

Use the `AttpTransmitter` to send requests or emit events.

```python
from attp.shared.transmitter import AttpTransmitter

# In your controller or service
async def trigger_action(self):
    response = await self.transmitter.send(
        "remote_procedure",
        MyPayload(data="foo"),
        namespace="target-service",
        expected_response=MyResponse
    )
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

<div align="center">
  <sub>Built with ❤️ by the Ascender Team</sub>
</div>