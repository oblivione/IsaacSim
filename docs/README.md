# LLM Assistant for Isaac Sim

A natural language interface extension for NVIDIA Isaac Sim that integrates Large Language Models (LLMs) to provide conversational control and assistance.

## Features

- 🤖 **Natural Language Interface**: Control Isaac Sim using plain English
- 🔗 **Multi-LLM Support**: Works with OpenAI, Anthropic, Ollama, and Azure OpenAI
- 🎯 **Context Awareness**: Understands current scene state and simulation status
- ⚡ **Quick Commands**: Pre-built buttons for common operations
- 🛡️ **Safe Execution**: Controlled code execution with error handling
- 📊 **Chat History**: Keep track of your conversations with the AI

## Installation

1. Place this extension in your Isaac Sim extensions directory
2. Enable the extension in Isaac Sim Extension Manager
3. Configure your LLM provider credentials
4. Start chatting with your AI assistant!

## Usage

### Basic Commands
- "Create a cube at position (1, 1, 1)"
- "What robots are in the scene?"
- "Start the physics simulation"
- "Load a Franka robot"

### Advanced Queries
- "Generate a Python script that moves the robot to pick up the cube"
- "Set up a camera sensor and show me the view"
- "Create a simple pick and place task"

## Configuration

Set up your LLM provider in the extension's configuration panel:

1. **Provider**: Choose your LLM service (OpenAI, Anthropic, etc.)
2. **API Key**: Enter your API credentials
3. **Model**: Specify the model name (gpt-4, claude-3-sonnet, etc.)
4. **Connect**: Initialize the connection

## Requirements

- Isaac Sim 5.0.0+
- Python 3.8+
- LLM API credentials (OpenAI, Anthropic, etc.)

## License

Apache-2.0 